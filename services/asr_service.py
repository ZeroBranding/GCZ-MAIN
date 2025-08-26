import asyncio
import logging
import os
from typing import Any, Dict, List

import numpy as np
import onnxruntime
import torch
import torchaudio
from faster_whisper import WhisperModel

from core.config import load_config

logger = logging.getLogger(__name__)

class SileroVAD:
    def __init__(self, model_path: str = "models/silero_vad.onnx"):
        self.model_path = model_path
        self._create_model()
        self.sampling_rate = 16000

    def _create_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Silero VAD model not found at {self.model_path}")
        opts = onnxruntime.SessionOptions()
        opts.log_severity_level = 4
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self.session = onnxruntime.InferenceSession(self.model_path, providers=['CPUExecutionProvider'], sess_options=opts)

    def __call__(self, x: torch.Tensor, sr: int) -> torch.Tensor:
        if len(x.shape) == 1:
            x = x.unsqueeze(0)
        if sr != self.sampling_rate:
            transform = torchaudio.transforms.Resample(orig_freq=sr, new_freq=self.sampling_rate)
            x = transform(x)

        ort_inputs = {'input': x.numpy(), 'sr': np.array(self.sampling_rate, dtype=np.int64)}
        ort_outs = self.session.run(None, ort_inputs)
        return torch.from_numpy(ort_outs[0])


class ASRService:
    def __init__(self):
        asr_config = load_config("asr")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        model_size = asr_config.get("whisper_model", "large-v3")
        compute_type = "float16" if self.device == "cuda" else "int8"

        logger.info(f"Loading Whisper model '{model_size}' on device '{self.device}' with compute type '{compute_type}'")
        self.model = WhisperModel(model_size, device=self.device, compute_type=compute_type)

        vad_model_path = asr_config.get("vad_model_path", "models/silero_vad.onnx")
        self.vad = SileroVAD(vad_model_path)
        logger.info(f"VAD model loaded from {vad_model_path}")

    async def transcribe_stream(self, audio_path: str, lang: str = 'de') -> List[Dict[str, Any]]:
        """
        Transcribes an audio file in streaming mode with VAD.
        Returns a list of segments with text and timestamps.
        """
        try:
            waveform, sample_rate = torchaudio.load(audio_path)
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            speech_timestamps = self._get_speech_timestamps(waveform, sample_rate)

            if not speech_timestamps:
                logger.warning("No speech detected in the audio file.")
                return []

            segments_with_text = []

            for ts in speech_timestamps:
                start_sample = int(ts['start'] * sample_rate / self.vad.sampling_rate)
                end_sample = int(ts['end'] * sample_rate / self.vad.sampling_rate)

                audio_segment = waveform[:, start_sample:end_sample].squeeze().numpy().astype(np.float32)

                segments, _ = self.model.transcribe(
                    audio_segment,
                    language=lang,
                    beam_size=5,
                    word_timestamps=True
                )

                for segment in segments:
                    segment_dict = {
                        "start": segment.start + (start_sample / sample_rate),
                        "end": segment.end + (start_sample / sample_rate),
                        "text": segment.text.strip(),
                        "words": [
                            {"word": w.word, "start": w.start + (start_sample / sample_rate), "end": w.end + (start_sample / sample_rate)}
                            for w in segment.words
                        ]
                    }
                    segments_with_text.append(segment_dict)
                    logger.debug(f"Segment: {segment_dict['start']:.2f}s -> {segment_dict['end']:.2f}s - {segment_dict['text']}")

            return segments_with_text

        except Exception as e:
            logger.error(f"Error during transcription: {e}", exc_info=True)
            return []

    def _get_speech_timestamps(self,
                              audio: torch.Tensor,
                              threshold: float = 0.5,
                              min_speech_duration_ms: int = 250,
                              min_silence_duration_ms: int = 100,
                              window_size_samples: int = 512,
                              speech_pad_ms: int = 30) -> List[dict]:

        if not torch.is_tensor(audio):
            raise TypeError("Audio is not a torch tensor!")

        min_speech_samples = self.vad.sampling_rate * min_speech_duration_ms / 1000
        min_silence_samples = self.vad.sampling_rate * min_silence_duration_ms / 1000
        speech_pad_samples = self.vad.sampling_rate * speech_pad_ms / 1000

        audio_length_samples = audio.shape[1]
        speech_probs = []
        for current_pos in range(0, audio_length_samples, window_size_samples):
            end_pos = current_pos + window_size_samples
            if end_pos > audio_length_samples:
                end_pos = audio_length_samples
            chunk = audio[:, current_pos:end_pos]
            speech_prob = self.vad(chunk, self.vad.sampling_rate).item()
            speech_probs.append(speech_prob)

        triggered = False
        speeches = []
        current_speech = {}
        neg_threshold = threshold - 0.15
        temp_end = 0

        for i, speech_prob in enumerate(speech_probs):
            if (speech_prob >= threshold) and temp_end:
                temp_end = 0

            if (speech_prob >= threshold) and not triggered:
                triggered = True
                current_speech['start'] = i * window_size_samples
                continue

            if (speech_prob < neg_threshold) and triggered:
                if not temp_end:
                    temp_end = (i - 1) * window_size_samples
                if ((i * window_size_samples) - temp_end) >= min_silence_samples:
                    current_speech['end'] = temp_end
                    speeches.append(current_speech)
                    current_speech = {}
                    triggered = False
                    temp_end = 0

        if current_speech and 'start' in current_speech and 'end' not in current_speech:
             current_speech['end'] = audio_length_samples - 1
             speeches.append(current_speech)

        for i, speech in enumerate(speeches):
            if i == 0:
                speech['start'] = int(max(0, speech['start'] - speech_pad_samples))
            if i != len(speeches) - 1:
                silence_duration = speeches[i+1]['start'] - speech['end']
                if silence_duration < 2 * speech_pad_samples:
                    speech['end'] = int(speech['end'] + silence_duration // 2)
                    speeches[i+1]['start'] = int(speeches[i+1]['start'] - silence_duration // 2)
                else:
                    speech['end'] = int(min(audio_length_samples, speech['end'] + speech_pad_samples))
            else:
                speech['end'] = int(min(audio_length_samples, speech['end'] + speech_pad_samples))

        final_speeches = []
        for speech in speeches:
            if (speech['end'] - speech['start']) > min_speech_samples:
                final_speeches.append(speech)

        return final_speeches


async def main():
    # This is for testing purposes
    logging.basicConfig(level=logging.DEBUG)
    asr_service = ASRService()
    # Create a dummy audio file for testing
    if not os.path.exists("test.wav"):
        logging.info("Creating dummy audio file test.wav")
        sample_rate = 16000
        duration = 5  # seconds
        frequency = 440  # Hz
        t = torch.linspace(0., duration, int(sample_rate * duration), dtype=torch.float32)
        waveform = torch.sin(2 * torch.pi * frequency * t)
        silence = torch.zeros(int(sample_rate * 1))
        waveform = torch.cat([silence, waveform, silence], 0).unsqueeze(0)
        torchaudio.save("test.wav", waveform, sample_rate)

    result = await asr_service.transcribe_stream("test.wav")
    print(result)
    os.remove("test.wav")


if __name__ == "__main__":
    asyncio.run(main())
