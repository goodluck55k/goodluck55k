"""Shared deterministic file helpers. No secrets are ever serialized."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def config():
    c = json.loads((ROOT / "config/profile.json").read_text(encoding="utf-8"))
    if not 1 <= len(c["works"]) <= 5:
        raise ValueError("Works must contain 1–5 entries")
    for work in c["works"]:
        if not work["url"].startswith("https://github.com/"):
            raise ValueError("Works must link to a public GitHub repository")
    return c


def write_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content:
        return False
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(content)
    temp.replace(path)
    return True


def write_text(path, content):
    return write_bytes(path, content.encode("utf-8"))


def write_json(path, data):
    return write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
