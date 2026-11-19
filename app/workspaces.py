import re
import unicodedata
from pathlib import Path


def make_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    if not slug:
        raise ValueError("Project name must contain letters or numbers.")
    return slug[:64].strip("-")


def create_workspace(root: Path, slug: str) -> Path:
    root = root.expanduser().resolve()
    target = (root / slug).resolve()
    if target == root or root not in target.parents:
        raise ValueError("Workspace path escapes the configured root.")
    target.mkdir(parents=True, exist_ok=False)
    return target
