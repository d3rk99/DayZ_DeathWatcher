import os
import subprocess
import sys
from pathlib import Path
from typing import List


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
        file_path.touch()
    else:
        file_path.write_text("\n".join(load_list(path)))
