import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

import pytest

# Under test
from ai.graph.run import start_graph


@pytest.fixture(scope="module")
def tmp_workspace(tmp_path_factory):
    """Provide isolated workspace directory via env override."""
    wp = tmp_path_factory.mktemp("workspace")
    os.environ["WORKSPACE_PATH"] = str(wp)
    # Ensure artifacts root exists
    (wp / "artifacts").mkdir(parents=True, exist_ok=True)
    return wp


@pytest.fixture(scope="module")
async def prompt_text():
    fixtures_dir = Path(__file__).parent / "fixtures"
    prompt_path = fixtures_dir / "prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("a cute test prompt")
    return prompt_path.read_text().strip()


@pytest.mark.asyncio
async def test_img_flow_idempotent(tmp_workspace, prompt_text):
    # Deterministic session id for reproducibility
    session_id = "test_session_123"
    goal = f"/img {prompt_text}"

    # First run
    first_result = await start_graph(session_id=session_id, goal=goal, user_context={})
    assert first_result["status"] in {"completed", "executing", "planning"}  # depending on mocks

    artifacts = first_result.get("artifacts", [])
    assert artifacts, "No artifacts produced"

    # Validate path pattern: /artifacts/YYYY-MM-DD/txt2img/...
    today = datetime.now().strftime("%Y-%m-%d")
    pattern = re.compile(rf".*/artifacts/{today}/txt2img/.*")
    assert any(pattern.match(p) for p in artifacts)

    # Capture initial artifact set on disk
    all_files_first = list(Path(os.environ["WORKSPACE_PATH"]).glob("artifacts/**/*"))

    # Second run with same session id (should resume, not duplicate)
    second_result = await start_graph(session_id=session_id, goal=goal, user_context={})
    assert second_result["status"] == first_result["status"]
    assert second_result.get("artifacts", []) == artifacts

    all_files_second = list(Path(os.environ["WORKSPACE_PATH"]).glob("artifacts/**/*"))
    assert len(all_files_second) == len(all_files_first), "Duplicate artifacts produced on resume"