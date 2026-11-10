"""Translate the release's SemVer into OpenType's three-digit minor version."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RELEASE=(ROOT/'version.txt').read_text().strip()
parts=[int(p) for p in RELEASE.split('.')]
MAJOR,MINOR,PATCH=(parts+[0,0])[:3]
FONT_MINOR=MINOR*100+PATCH
FONT_REVISION=MAJOR+FONT_MINOR/1000
FONT_VERSION=f'Version {MAJOR}.{FONT_MINOR:03d}'
