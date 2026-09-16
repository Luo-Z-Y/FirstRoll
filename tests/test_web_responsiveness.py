"""Run the dependency-free JavaScript race regressions in the existing CI test gate."""

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_request_responsiveness() -> None:
    environment = os.environ.copy()
    # The CI contract exercises tracked source, never an old local build.
    environment.pop("FIRSTROLL_TEST_APP", None)
    result = subprocess.run(
        ["node", "--test", "tests/web/responsiveness.test.cjs"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
