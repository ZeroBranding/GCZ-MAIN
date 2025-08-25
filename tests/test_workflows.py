import unittest
from pathlib import Path

from core.workflows.engine import WorkflowEngine


class TestWorkflowEngine(unittest.TestCase):

    def setUp(self):
        self.flows_dir = Path("flows")
        self.artifacts_dir = Path("artifacts")
        self.artifacts_dir.mkdir(exist_ok=True)

    def test_upload_all_plan(self):
        workflow_path = self.flows_dir / "upload_all.yml"
        engine = WorkflowEngine(workflow_path)
        plan = engine.plan()

        self.assertEqual(len(plan), 4)
        self.assertEqual(plan[0]['name'], 'sanitize_caption')

        step_names = [step['name'] for step in plan]
        self.assertIn('plan_tiktok', step_names)
        self.assertIn('plan_instagram', step_names)
        self.assertIn('plan_youtube', step_names)

        # Check path safety (simple version)
        for step in plan:
            for path in step['artifacts_in'] + step['artifacts_out']:
                self.assertTrue(Path(path).parts[0] == 'artifacts')

    def test_video_avatar_plan(self):
        workflow_path = self.flows_dir / "video_avatar.yml"
        engine = WorkflowEngine(workflow_path)
        plan = engine.plan()

        self.assertEqual(len(plan), 4)

        actual_order = [step['name'] for step in plan]

        # The exact order isn't guaranteed by the graph, only the dependencies.
        # Let's check dependencies instead
        self.assertLess(actual_order.index('avatar_plan'), actual_order.index('tts_plan'))
        self.assertLess(actual_order.index('upscale_plan'), actual_order.index('avatar_plan'))
        self.assertLess(actual_order.index('mux_plan'), actual_order.index('upscale_plan'))
        self.assertLess(actual_order.index('mux_plan'), actual_order.index('tts_plan'))


    def test_sd_generate_plan(self):
        workflow_path = self.flows_dir / "sd_generate.yml"
        engine = WorkflowEngine(workflow_path)
        plan = engine.plan()

        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0]['name'], 'txt2img_plan')
        self.assertEqual(plan[1]['name'], 'upscale_plan')

    def test_variable_resolution(self):
        workflow_path = self.flows_dir / "sd_generate.yml"
        engine = WorkflowEngine(workflow_path)
        plan = engine.plan()

        txt2img_step = plan[0]
        self.assertIn("a beautiful landscape", txt2img_step['command'])
        self.assertIn("artifacts/generated_image.png", txt2img_step['command'])

if __name__ == '__main__':
    unittest.main()
