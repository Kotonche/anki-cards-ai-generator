import os
import platform
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_processing_directory() -> str:
    return str(project_root() / "processing")


def default_anki_media_directory() -> str:
    home = Path.home()
    system = platform.system()

    if system == "Windows":
        profile = Path(os.environ.get("USERPROFILE", home))
        return str(profile / "AppData" / "Roaming" / "Anki2" / "User 1" / "collection.media")
    if system == "Darwin":
        return str(home / "Library" / "Application Support" / "Anki2" / "User 1" / "collection.media")
    return str(home / ".local" / "share" / "Anki2" / "User 1" / "collection.media")
