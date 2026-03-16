from pathlib import Path
from bs4 import BeautifulSoup, Tag

CLOSE_CIRCLE_OUTLINE_PATH: Path = Path("docs/assets") / "icons" / "close-circle-outline.svg"
CLOSE_CIRCLE_OUTLINE_TAG: Tag = BeautifulSoup(CLOSE_CIRCLE_OUTLINE_PATH.read_text(encoding="utf-8"), features="html.parser")

CLOSE_OCTAGON_OUTLINE_PATH: Path = Path("docs/assets") / "icons" / "close-octagon-outline.svg"
CLOSE_OCTAGON_OUTLINE_TAG: Tag = BeautifulSoup(CLOSE_OCTAGON_OUTLINE_PATH.read_text(encoding="utf-8"), features="html.parser")

MUSIC_BOX_PATH: Path = Path("docs/assets") / "icons" / "music-box.svg"
MUSIC_BOX_TAG: Tag = BeautifulSoup(MUSIC_BOX_PATH.read_text(encoding="utf-8"), features="html.parser")

MUSIC_BOX_OUTLINE_PATH: Path = Path("docs/assets") / "icons" / "music-box-outline.svg"
MUSIC_BOX_OUTLINE_TAG: Tag = BeautifulSoup(MUSIC_BOX_OUTLINE_PATH.read_text(encoding="utf-8"), features="html.parser")

PLAY_CIRCLE_OUTLINE_PATH: Path = Path("docs/assets") / "icons" / "play-circle-outline.svg"
PLAY_CIRCLE_OUTLINE_TAG: Tag = BeautifulSoup(PLAY_CIRCLE_OUTLINE_PATH.read_text(encoding="utf-8"), features="html.parser")
