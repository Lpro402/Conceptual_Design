"""Guard: this repository holds software and code only.

No course instructions, course-booklet pages, lecture slides, vendor datasheets
or office documents may be committed. Images are allowed only where the team's
own software renders them (docs/assets).
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".zip", ".f3d", ".f3z"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".wdp", ".emf"}
IMAGE_DIRS = ("docs/assets/",)
FORBIDDEN_PHRASES = ("חוברת הקורס", "הוראות הקורס", "דוגמת הקורס", "הנחיות הקורס")


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [line for line in out.splitlines() if line]


def test_no_office_or_pdf_documents() -> None:
    offenders = [f for f in tracked_files() if Path(f).suffix.lower() in FORBIDDEN_SUFFIXES]
    assert not offenders, offenders


def test_images_only_in_software_asset_folders() -> None:
    offenders = [f for f in tracked_files()
                 if Path(f).suffix.lower() in IMAGE_SUFFIXES and not f.startswith(IMAGE_DIRS)]
    assert not offenders, offenders


def test_no_course_instruction_text() -> None:
    offenders = []
    for f in tracked_files():
        path = ROOT / f
        if path.suffix.lower() in {".py", ".js", ".html", ".md", ".json", ".css", ".txt", ".drawio", ".toml", ".yml"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            offenders += [f"{f}: {p}" for p in FORBIDDEN_PHRASES if p in text and path.name != Path(__file__).name]
    assert not offenders, offenders
