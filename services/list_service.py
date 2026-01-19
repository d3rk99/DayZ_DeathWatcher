import os
import subprocess
import sys
from pathlib import Path
from typing import List

from services.file_utils import atomic_write_text


def load_list(path: str) -> List[str]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    return [line.strip() for line in file_path.read_text().splitlines() if line.strip()]


def open_in_system_editor(path: str) -> None:
    file_path = Path(path)
    if os.name == "nt":
        os.startfile(file_path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(file_path)])
    else:
        subprocess.Popen(["xdg-open", str(file_path)])


def force_sync(path: str) -> None:
    file_path = Path(path)
    if not file_path.exists():
        atomic_write_text(file_path, "")
    else:
        atomic_write_text(file_path, "\n".join(load_list(path)))
