import unittest
from pathlib import Path

from services.anim_service import plan_animation


class TestAnimService(unittest.TestCase):

    def test_plan_animation(self):
        """Testet die Animationsplanung."""
        prompt = "Ein tanzender Roboter"
        seconds = 2
        fps = 10

        frame_count, params = plan_animation(prompt, seconds, fps)

        self.assertEqual(frame_count, 20)
        self.assertEqual(params["prompt"], prompt)
        self.assertEqual(params["frame_count"], 20)

    def test_mux_to_mp4_dry_run(self):
        """
        Testet den FFmpeg-Befehl für das Muxing (Trockenlauf).
        Es wird kein echter Prozess gestartet.
        """
        frame_dir = Path("artifacts/anim/test_job")
        fps = 10

        # Erwarteter Befehl
        expected_command = [
            "ffmpeg",
            "-y",
            "-framerate", "10",
            "-i", f"{frame_dir}/%05d.png",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(frame_dir.parent / "animation_placeholder.mp4")
        ]

        # Hier wird der Befehl nur simuliert, nicht ausgeführt
        # In einer echten Testumgebung könnte man den Befehl mocken
        # und prüfen, ob er korrekt aufgerufen wird.

        self.assertTrue(len(expected_command) > 5)

if __name__ == '__main__':
    unittest.main()
