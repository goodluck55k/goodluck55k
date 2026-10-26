"""One-time download of OFL fonts from Google Fonts. No image uploads."""
import urllib.request
from urllib.parse import quote
from common import ROOT, write_bytes, write_json, sha256

FILES = {
    "NotoSerifSC.ttf": "notoserifsc/NotoSerifSC[wght].ttf",
    "NotoSerifSC-OFL.txt": "notoserifsc/OFL.txt",
    "LibreBaskerville.ttf": "librebaskerville/LibreBaskerville[wght].ttf",
    "LibreBaskerville-Italic.ttf": "librebaskerville/LibreBaskerville-Italic[wght].ttf",
    "LibreBaskerville-OFL.txt": "librebaskerville/OFL.txt",
    "Caveat.ttf": "caveat/Caveat[wght].ttf",
    "Caveat-OFL.txt": "caveat/OFL.txt",
}


def main():
    manifest = []
    for name, source in FILES.items():
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/" + quote(source, safe="/")
        path = ROOT / "assets/fonts" / name
        if not path.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                write_bytes(path, response.read())
        manifest.append({"file": name, "source": url, "sha256": sha256(path), "license": "SIL OFL 1.1"})
        print("Font ready:", name)
    write_json(ROOT / "assets/fonts/manifest.json", manifest)


if __name__ == "__main__":
    main()
