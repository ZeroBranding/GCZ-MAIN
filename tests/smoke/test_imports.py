import pytest
import importlib
from pathlib import Path
import os
import sys

# Add project root to the path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# --- Test Configuration ---
SOURCE_DIRECTORIES = ["core", "services", "agent", "agents"]
# List of modules that are known to fail import and should be fixed later.
KNOWN_FAILURES = [
    "services.instagram_service", # Missing instagrapi dependency due to pydantic conflict
    "services.voice_service",     # Missing system-level FFmpeg libs for 'av' dependency
]

def find_modules_to_test():
    """
    Finds all Python modules in the specified source directories.
    """
    project_root = Path(__file__).resolve().parents[2]
    modules = []
    for directory in SOURCE_DIRECTORIES:
        source_path = project_root / directory
        if not source_path.is_dir():
            continue
        for py_file in source_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            relative_path = py_file.relative_to(project_root)
            module_name = str(relative_path.with_suffix("")).replace(os.path.sep, ".")

            if module_name in KNOWN_FAILURES:
                # Mark known failures to be xfailed by pytest
                modules.append(pytest.param(module_name, marks=pytest.mark.xfail(reason="Known import issue")))
            else:
                modules.append(module_name)
    return modules

@pytest.mark.parametrize("module_to_test", find_modules_to_test())
def test_dynamic_module_import(module_to_test):
    """
    A dynamically generated test that attempts to import a specific module.
    """
    try:
        importlib.import_module(module_to_test)
    except ImportError as e:
        pytest.fail(f"Failed to import module {module_to_test}: {e}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred while importing {module_to_test}: {e}")
