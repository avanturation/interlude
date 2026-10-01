"""Hash editable font sources in a deterministic order."""
from pathlib import Path
import hashlib
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Interlude.glyphspackage'
def source_hash():
    digest = hashlib.sha256()
    for path in sorted(SOURCE.rglob('*')):
        if path.is_file() and path.suffix in {'.glyph', '.plist'} and path.name != 'UIState.plist':
            digest.update(path.relative_to(SOURCE).as_posix().encode() + b'\0')
            digest.update(path.read_bytes())
    return digest.hexdigest()
def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
