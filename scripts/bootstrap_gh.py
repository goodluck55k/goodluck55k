"""Install a checksum-verified official portable gh inside this workspace."""
import hashlib
from pathlib import Path
import urllib.request
import zipfile
from common import ROOT, write_bytes, write_json

VERSION = "2.103.2"


def main():
    name = f"gh_{VERSION}_windows_amd64.zip"
    base = f"https://github.com/cli/cli/releases/download/v{VERSION}/"
    directory = ROOT / ".tools/gh"
    directory.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(base + f"gh_{VERSION}_checksums.txt", timeout=60) as response:
        checksums = response.read().decode()
    expected = next(line.split()[0] for line in checksums.splitlines() if line.split()[-1] == name)
    archive = ROOT / ".tools" / name
    if not archive.exists():
        with urllib.request.urlopen(base + name, timeout=60) as response:
            write_bytes(archive, response.read())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError("Official GitHub CLI checksum mismatch")
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (directory / member.filename).resolve()
            if not target.is_relative_to(directory.resolve()):
                raise RuntimeError("Archive path escapes the local tool directory")
        bundle.extractall(directory)
    executables = list(directory.rglob("gh.exe"))
    if len(executables) != 1:
        raise RuntimeError("Expected one official GitHub CLI executable")
    write_json(ROOT / "reports/gh-install.json", {"version": VERSION, "source": base + name,
               "sha256": digest, "checksum_verified": True, "executable": executables[0].relative_to(ROOT).as_posix()})
    print("Official portable GitHub CLI installed locally; checksum verified.")
    print("Executable:", executables[0].relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
