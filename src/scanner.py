"""
Python wrapper around the compiled C++ scanner shared library (scanner.so).
Falls back to a pure-Python os.walk implementation when the library is absent
(e.g. before `make build` has been run).
"""
import ctypes
import os
from pathlib import Path
from typing import Optional

_lib = None
_LIB_PATH = Path(__file__).parent / "libscanner.so"
_BUF_SIZE = 8 * 1024 * 1024  # 8 MB ought to cover 100+ file repos comfortably


def _load() -> Optional[ctypes.CDLL]:
    global _lib
    if _lib is not None:
        return _lib
    if not _LIB_PATH.exists():
        return None
    try:
        lib = ctypes.CDLL(str(_LIB_PATH))
        lib.scan_directory.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        lib.scan_directory.restype = ctypes.c_int
        lib.count_files.argtypes = [ctypes.c_char_p]
        lib.count_files.restype = ctypes.c_int
        _lib = lib
        return _lib
    except OSError:
        return None


def scan_directory(path: str, buf_size: int = _BUF_SIZE) -> tuple[list[str], int]:
    """Return (all_paths, file_count) for every non-hidden entry under *path*.

    Uses the compiled C++ scanner when available; falls back to Python otherwise.
    """
    lib = _load()
    if lib is not None:
        buf = ctypes.create_string_buffer(buf_size)
        file_count = lib.scan_directory(path.encode(), buf, buf_size)
        paths = [p for p in buf.value.decode(errors="replace").splitlines() if p]
        return paths, file_count

    return _python_scan(path)


def count_files(path: str) -> int:
    """Return the number of regular non-hidden files under *path*."""
    lib = _load()
    if lib is not None:
        return lib.count_files(path.encode())
    _, n = _python_scan(path)
    return n


def _python_scan(path: str) -> tuple[list[str], int]:
    """Pure-Python fallback using os.walk."""
    all_paths: list[str] = []
    file_count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.startswith("."):
                continue
            full = os.path.join(root, name)
            all_paths.append(full)
            file_count += 1
        for name in dirs:
            all_paths.append(os.path.join(root, name))
    return all_paths, file_count
