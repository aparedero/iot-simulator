"""Guard the product Python matrix (3.14 and 3.15)."""
import sys
from importlib.metadata import version


def test_python_version_is_at_least_3_14():
    assert sys.version_info >= (3, 14), (
        f"Unsupported Python {sys.version_info.major}.{sys.version_info.minor}; "
        "this project requires 3.14 or newer"
    )


def test_critical_native_wheels_import():
    import pydantic_core
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    assert pydantic_core.__version__
    assert AESGCM is not None
    assert version("pydantic").startswith("2.")
    assert version("fastapi")
