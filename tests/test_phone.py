import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.phone_service import PhoneService


class TestPhoneService(unittest.TestCase):

    def setUp(self):
        # Mock the config loaded by the service
        self.mock_config = {
            "enabled": True,
            "baresip": {
                "executable": "path/to/baresip.exe",
                "config_path": "configs/baresip",
                "log_level": "debug"
            },
            "call_handling": {
                "record_segment_duration": 1
            }
        }
        self.patcher = patch('services.phone_service.get_config', return_value=self.mock_config)
        self.mock_get_config = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch('subprocess.Popen')
    def test_start_stop_baresip_process(self, mock_popen):
        """
        Tests the successful start and stop of the baresip subprocess.
        """
        # Arrange
        mock_process = MagicMock()
        mock_process.pid = 1234
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        mock_popen.return_value = mock_process

        service = PhoneService()

        # Act
        async def run_test():
            await service.start()

            # Assert Start
            expected_cmd = [
                "path/to/baresip.exe",
                "-f", "configs/baresip",
                "-e", "/log_level debug",
            ]
            mock_popen.assert_called_once()
            # Check the command list argument by argument
            called_args, _ = mock_popen.call_args
            self.assertEqual(called_args[0], expected_cmd)

            self.assertIsNotNone(service._process)
            self.assertEqual(service._process.pid, 1234)

            # Mock the async wait for the process to stop
            service._process.wait = AsyncMock()
            await service.stop()

            # Assert Stop
            service._process.terminate.assert_called_once()
            service._process.wait.assert_awaited_once()
            self.assertIsNone(service._process)

        asyncio.run(run_test())

    def test_service_disabled(self):
        """
        Tests that baresip is not started if the service is disabled in config.
        """
        # Arrange
        self.mock_config["enabled"] = False
        service = PhoneService()

        # Act & Assert
        with patch('subprocess.Popen') as mock_popen:
            asyncio.run(service.start())
            mock_popen.assert_not_called()

    @patch('subprocess.Popen')
    def test_start_file_not_found(self, mock_popen):
        """
        Tests error handling when the baresip executable is not found.
        """
        # Arrange
        mock_popen.side_effect = FileNotFoundError("Executable not found")
        service = PhoneService()

        # Act
        asyncio.run(service.start())

        # Assert
        self.assertIsNone(service._process)
        # We would also check for a log message here if logging was mocked

    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_call_handling_flow(self, mock_sleep):
        """
        Dry-run test for the placeholder call handling logic.
        """
        # Arrange
        service = PhoneService()
        service.config = self.mock_config # Ensure config is set for this async test

        # Act
        await service.on_incoming_call({"from": "test_caller"})

        # Assert
        # Check that the placeholder logic "waits" for the configured duration
        mock_sleep.assert_any_call(self.mock_config["call_handling"]["record_segment_duration"])
        self.assertGreaterEqual(mock_sleep.call_count, 1)


if __name__ == '__main__':
    unittest.main()
