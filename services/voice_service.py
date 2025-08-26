import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

import numpy as np
import soundfile as sf
import torch
from openvoice import se_extractor
from openvoice.api import ToneColorConverter
from piper.voice import PiperVoice
from TTS.api import TTS

from core.config import load_config

logger = logging.getLogger(__name__)

class VoiceProfile:
    def __init__(self, name: str, profile_dir: str):
        self.name = name
        self.profile_dir = os.path.join(profile_dir, name)
        os.makedirs(self.profile_dir, exist_ok=True)
        self.metadata_file = os.path.join(self.profile_dir, "metadata.json")
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}

    def save_metadata(self):
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def set(self, key: str, value: Any):
        self.metadata[key] = value
        self.save_metadata()


class VoiceService:
    def __init__(self):
        self.config = load_config("voice")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.profile_base_dir = self.config.get("profile_dir", "models/voice")
        self.output_dir = self.config.get("output_dir", "artifacts/tts")
        os.makedirs(self.output_dir, exist_ok=True)

        # Cache for loaded models
        self._xtts_model = None
        self._piper_voices: Dict[str, PiperVoice] = {}
        self._openvoice_converter = None

        logger.info(f"VoiceService initialized. Device: {self.device}, Profile Dir: {self.profile_base_dir}")

    def _get_xtts_model(self):
        if self._xtts_model is None:
            model_name = self.config.get("xtts_model", "tts_models/de/thorsten/vits")
            logger.info(f"Loading XTTS model: {model_name}")
            try:
                self._xtts_model = TTS(model_name).to(self.device)
            except Exception as e:
                logger.error(f"Failed to load XTTS model: {e}", exc_info=True)
                raise
        return self._xtts_model

    def _get_piper_voice(self, model_name: str):
        if model_name not in self._piper_voices:
            model_path = os.path.join(self.config.get("piper_model_dir", "models/piper"), f"{model_name}.onnx")
            if not os.path.exists(model_path):
                logger.error(f"Piper model not found at {model_path}")
                return None
            logger.info(f"Loading Piper voice: {model_name}")
            self._piper_voices[model_name] = PiperVoice.load(model_path)
        return self._piper_voices[model_name]

    def _get_openvoice_converter(self):
        if self._openvoice_converter is None:
            logger.info("Loading OpenVoice Tone Color Converter.")
            # Paths should be configurable
            ckpt_converter = self.config.get("openvoice_converter_ckpt", "models/openvoice/converter")
            device = self.device
            self._openvoice_converter = ToneColorConverter(f'{ckpt_converter}/config.json', device=device)
            self._openvoice_converter.load_ckpt(f'{ckpt_converter}/checkpoint.pth')
        return self._openvoice_converter

    def _get_voice_profile(self, name: str) -> VoiceProfile:
        return VoiceProfile(name, self.profile_base_dir)

    def _generate_output_path(self, text: str, voice_name: str, backend: str) -> str:
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        filename = f"{voice_name}_{backend}_{text_hash}.wav"
        return os.path.join(self.output_dir, filename)

    def synthesize(self, text: str, voice_profile_name: str, backend: str = 'openvoice',
                   lang: str = 'de', rate: Optional[float] = None, pitch: Optional[float] = None) -> Optional[str]:

        output_path = self._generate_output_path(text, voice_profile_name, backend)
        if os.path.exists(output_path):
            logger.info(f"Found cached audio at {output_path}")
            return output_path

        profile = self._get_voice_profile(voice_profile_name)

        try:
            if backend == 'openvoice':
                wav_path = self._synthesize_openvoice(text, profile, lang)
            elif backend == 'xtts':
                wav_path = self._synthesize_xtts(text, profile, lang)
            elif backend == 'piper':
                wav_path = self._synthesize_piper(text, profile)
            else:
                logger.error(f"Unsupported TTS backend: {backend}")
                return None

            if wav_path:
                os.rename(wav_path, output_path)
                return output_path
            return None

        except Exception as e:
            logger.error(f"Error synthesizing speech with {backend}: {e}", exc_info=True)
            return None

    def _synthesize_openvoice(self, text: str, profile: VoiceProfile, lang: str) -> Optional[str]:
        converter = self._get_openvoice_converter()
        openvoice_config = self.config.get('openvoice', {})

        # Determine source speaker based on language
        source_se_path = os.path.join(
            openvoice_config.get("base_speaker_dir", "models/openvoice/base_speakers"),
            f"{lang}.json" # Expects something like 'de.json'
        )
        if not os.path.exists(source_se_path):
            logger.error(f"OpenVoice base speaker for language '{lang}' not found at {source_se_path}")
            return None

        # Get target speaker embedding from profile
        target_se_path = profile.get("openvoice_embedding")
        if not target_se_path or not os.path.exists(target_se_path):
            # As a fallback, try to find a reference wav and compute it
            reference_wav = profile.get("reference_wav")
            if reference_wav and os.path.exists(reference_wav):
                logger.info(f"Generating OpenVoice embedding for {profile.name} from {reference_wav}")
                target_se_path = os.path.join(profile.profile_dir, "openvoice_embedding.pth")
                se_extractor.get_se(reference_wav, target_se_path, self._get_openvoice_converter())
                profile.set("openvoice_embedding", target_se_path)
            else:
                logger.error(f"No OpenVoice embedding or reference wav found for profile {profile.name}")
                return None

        source_se = torch.load(source_se_path, map_location=self.device)
        target_se = torch.load(target_se_path, map_location=self.device)

        # Synthesize with base speaker (can't directly synthesize with cloned voice)
        # This part needs a base TTS, e.g. XTTS or Piper to generate the source audio first
        # Let's use Piper for this as it's fast
        base_wav_path = self._synthesize_piper(text, self._get_voice_profile("default_de")) # Assumes a default piper profile
        if not base_wav_path:
            logger.error("Could not generate base audio for OpenVoice conversion.")
            return None

        save_path = f"{base_wav_path}.converted.wav"

        # Convert tone color
        converter.convert(
            audio_src_path=base_wav_path,
            src_se=source_se,
            tgt_se=target_se,
            output_path=save_path,
            message=text # Optional for some models
        )

        os.remove(base_wav_path)
        return save_path

    def _synthesize_xtts(self, text: str, profile: VoiceProfile, lang: str) -> Optional[str]:
        model = self._get_xtts_model()
        speaker_wav = profile.get("reference_wav")
        if not speaker_wav or not os.path.exists(speaker_wav):
            logger.error(f"Reference wav for XTTS not found for profile {profile.name}")
            return None

        temp_path = os.path.join(self.output_dir, "temp_xtts.wav")
        model.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=lang,
            file_path=temp_path
        )
        return temp_path

    def _synthesize_piper(self, text: str, profile: VoiceProfile) -> Optional[str]:
        model_name = profile.get("piper_model")
        if not model_name:
            logger.error(f"No piper model specified for profile {profile.name}")
            return None

        voice = self._get_piper_voice(model_name)
        if not voice:
            return None

        temp_path = os.path.join(self.output_dir, "temp_piper.wav")
        with open(temp_path, "wb") as wav_file:
            voice.synthesize(text, wav_file)
        return temp_path


async def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting VoiceService test.")

    # Setup dummy profiles and models for testing
    os.makedirs("models/voice/test_piper/files", exist_ok=True)
    os.makedirs("models/voice/test_xtts/files", exist_ok=True)
    os.makedirs("models/voice/test_openvoice/files", exist_ok=True)
    os.makedirs("artifacts/tts", exist_ok=True)
    os.makedirs("models/piper", exist_ok=True)

    # You would need to download actual models for this to work.
    # For now, this will fail but it demonstrates the structure.

    # Create a dummy reference audio
    samplerate = 22050
    data = np.random.uniform(-1, 1, samplerate * 3)
    sf.write("models/voice/test_xtts/reference.wav", data, samplerate)
    sf.write("models/voice/test_openvoice/reference.wav", data, samplerate)

    # Create dummy profiles
    piper_profile = VoiceProfile("test_piper", "models/voice")
    piper_profile.set("piper_model", "de_DE-thorsten-medium") # Assumes this model exists

    xtts_profile = VoiceProfile("test_xtts", "models/voice")
    xtts_profile.set("reference_wav", "models/voice/test_xtts/reference.wav")

    ov_profile = VoiceProfile("test_openvoice", "models/voice")
    ov_profile.set("reference_wav", "models/voice/test_openvoice/reference.wav")

    service = VoiceService()
    text = "Hallo Welt, dies ist ein Test der Sprachsynthese."

    # Test Piper (will fail if model not present)
    try:
        piper_path = service.synthesize(text, "test_piper", backend='piper')
        if piper_path:
            logger.info(f"Piper audio saved to: {piper_path}")
    except Exception as e:
        logger.error(f"Piper test failed: {e}")

    # Test XTTS (will fail if model not present)
    try:
        xtts_path = service.synthesize(text, "test_xtts", backend='xtts', lang='de')
        if xtts_path:
            logger.info(f"XTTS audio saved to: {xtts_path}")
    except Exception as e:
        logger.error(f"XTTS test failed: {e}")

    # Test OpenVoice (will fail if models not present)
    try:
        ov_path = service.synthesize(text, "test_openvoice", backend='openvoice', lang='de')
        if ov_path:
            logger.info(f"OpenVoice audio saved to: {ov_path}")
    except Exception as e:
        logger.error(f"OpenVoice test failed: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
