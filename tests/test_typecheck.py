import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TYPECHECKING_DIR = Path(__file__).parent / "typechecking"


def test_pyright_project():
    """Type-check src/, tests/, and examples/ using the project pyright config."""
    result = subprocess.run(
        ["pyright", "-p", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_pyright_typechecking():
    """Targeted type-safety checks (invariance, contract signatures, etc.)."""
    result = subprocess.run(
        ["pyright", "-p", str(TYPECHECKING_DIR)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
