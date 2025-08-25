import asyncio
import logging
import subprocess
from typing import Optional

from core.config import get_config

logger = logging.getLogger(__name__)

class PhoneService:
    """
    Manages the phone service integration with baresip.
    """
    def __init__(self):
        self.config = get_config("phone.yml")
        self._process: Optional[subprocess.Popen] = None

    async def start(self):
        if not self.config.get("enabled"):
            logger.info("Phone service is disabled in the configuration.")
            return

        executable = self.config.get("baresip", {}).get("executable")
        if not executable:
            logger.error("Baresip executable not configured.")
            return

        cmd = [
            executable,
            "-f", self.config.get("baresip", {}).get("config_path", "configs/baresip"),
            "-e", "/log_level " + self.config.get("baresip", {}).get("log_level", "info"),
        ]

        try:
            logger.info(f"Starting baresip with command: {' '.join(cmd)}")
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            asyncio.create_task(self._log_output(self._process.stdout, logging.INFO))
            asyncio.create_task(self._log_output(self._process.stderr, logging.ERROR))
            logger.info(f"Baresip process started with PID: {self._process.pid}")

        except FileNotFoundError:
            logger.error(f"Baresip executable not found at: {executable}")
            self._process = None
        except Exception as e:
            logger.error(f"Failed to start baresip: {e}")
            self._process = None

    async def stop(self):
        if self._process:
            logger.info(f"Stopping baresip process (PID: {self._process.pid})...")
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10.0)
                logger.info("Baresip process stopped.")
            except asyncio.TimeoutError:
                logger.warning("Baresip process did not terminate gracefully, killing.")
                self._process.kill()
            self._process = None

    async def _log_output(self, pipe, level):
        if pipe is None:
            return
        # Use a blocking read in a thread to avoid blocking the asyncio event loop
        loop = asyncio.get_event_loop()
        for line in iter(pipe.readline, b''):
            decoded_line = line.decode().strip()
            await loop.run_in_executor(None, logger.log, level, f"baresip: {decoded_line}")
        pipe.close()

    async def on_incoming_call(self, call_info: dict):
        """
        Handles the half-duplex ASR -> LLM -> TTS loop for an incoming call.
        This is a placeholder for the actual implementation.
        """
        logger.info(f"Incoming call received: {call_info}")

        # This is where the half-duplex loop will be implemented.
        # 1. Answer the call
        # 2. Play a welcome message (TTS)
        # 3. Loop:
        #    a. Record a segment of audio
        #    b. Transcribe the audio (ASR)
        #    c. Get a response from the agent (LLM)
        #    d. Synthesize the response (TTS)
        #    e. Play the synthesized audio
        # 4. Hang up the call on silence or end command.

        await self._handle_call_flow()

    async def _handle_call_flow(self):
        """
        Placeholder for the detailed call handling logic.
        """
        try:
            # Simulate the call flow for now
            logger.info("Starting call handling flow...")
            await asyncio.sleep(self.config.get("call_handling", {}).get("record_segment_duration", 5))
            logger.info("...recording segment...")
            await asyncio.sleep(2)
            logger.info("...processing with ASR->LLM->TTS...")
            await asyncio.sleep(3)
            logger.info("...playing response...")
            logger.info("Call handling flow finished.")
        except Exception as e:
            logger.error(f"Error during call handling: {e}")

if __name__ == '__main__':
    # Example usage
    async def main():
        logging.basicConfig(level=logging.INFO)
        service = PhoneService()
        await service.start()
        try:
            # Simulate running for a while
            await asyncio.sleep(60)
        finally:
            await service.stop()

    asyncio.run(main())
