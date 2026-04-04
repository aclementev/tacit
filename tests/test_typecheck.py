import subprocess
from pathlib import Path

TYPECHECKING_DIR = Path(__file__).parent / "typechecking"


def test_pyright_typechecking():
    result = subprocess.run(
        ["pyright", "-p", str(TYPECHECKING_DIR)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
