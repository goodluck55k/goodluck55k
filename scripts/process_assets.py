"""Local conventional masking; originals and all attribution remain intact."""
from collections import deque
from io import BytesIO
import numpy as np
from PIL import Image, ImageFilter
from common import ROOT, config, read_json, sha256, write_bytes, write_json

VERSION = 3


def connected_background(rgb, minimum, spread):
    """Flood only pale, neutral pixels connected to the image boundary.

    Closed white eyes remain foreground. The threshold also catches WebP
    checkerboard compression. Output is a mask, never a generated subject.
    """
    a = np.asarray(rgb, dtype=np.int16)
    candidate = (a.min(axis=2) >= minimum) & (np.ptp(a, axis=2) <= spread)
    h, w = candidate.shape
    seen = np.zeros((h, w), dtype=bool)
    pending = deque()
    for x in range(w):
        for y in (0, h - 1):
            if candidate[y, x] and not seen[y, x]:
                seen[y, x] = True
                pending.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if candidate[y, x] and not seen[y, x]:
                seen[y, x] = True
                pending.append((y, x))
    while pending:
        y, x = pending.popleft()
        for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= yy < h and 0 <= xx < w and candidate[yy, xx] and not seen[yy, xx]:
                seen[yy, xx] = True
                pending.append((yy, xx))
    return Image.fromarray(np.where(seen, 0, 255).astype(np.uint8))


def png_bytes(image):
    stream = BytesIO()
    image.save(stream, "PNG", optimize=True)
    return stream.getvalue()


def process(force=False):
    c = config()
    source = ROOT / "assets/source"
    out = ROOT / "assets/processed"
    old = read_json(out / "manifest.json", {})
    if not all((source / name).exists() for name in c["assets"].values()):
        # Daily public builds use audited derivatives; originals need not be published.
        hashes = old.get("output_sha256", {})
        if not force and old.get("signature", {}).get("version") == VERSION and hashes and all(
            (out / name).is_file() and sha256(out / name) == digest for name, digest in hashes.items()
        ) and all((out / (role + ".png")).exists() for role in c["assets"]):
            return old
        missing = [name for name in c["assets"].values() if not (source / name).exists()]
        raise FileNotFoundError("Missing originals and no valid processed cache: " + ", ".join(missing))
    signature = {"version": VERSION, "originals": {k: sha256(source / v) for k, v in c["assets"].items()}}
    if not force and old.get("signature") == signature and all((out / (k + ".png")).exists() for k in c["assets"]):
        return old
    records = []
    for role, filename in c["assets"].items():
        original = Image.open(source / filename)
        image = original.convert("RGBA")
        crop = (0, 0, image.width, image.height)
        if role in ("spiderman", "deadpool"):
            minimum, spread = (182, 40) if role == "spiderman" else (220, 28)
            mask = connected_background(image.convert("RGB"), minimum, spread)
            # One pixel inward feather removes pale compression fringes at 2x export.
            mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.35))
            image.putalpha(mask)
            crop = image.getbbox()
            write_bytes(out / (role + "-mask.png"), png_bytes(mask))
            image = image.crop(crop)
            operation = {"mask": "boundary-connected neutral-key", "minimum": minimum, "spread": spread,
                         "erosion_px": 1, "feather_sigma_px": 0.35}
        elif role == "dyna":
            crop = image.getbbox()
            image = image.crop(crop)
            operation = {"mask": "original alpha, unchanged"}
        else:
            # The replacement is already transparent: trim empty alpha margins only.
            crop = image.getchannel("A").getbbox()
            image = image.crop(crop)
            operation = {"mask": "original alpha, unchanged", "crop": "transparent margins only",
                         "artwork": "all visible source pixels retained; no generated pixels"}
        write_bytes(out / (role + ".png"), png_bytes(image))
        records.append({"role": role, "original": filename, "sha256": sha256(source / filename),
                        "original_size": list(original.size), "original_mode": original.mode,
                        "crop_box": list(crop), "output_size": list(image.size), "operation": operation})
    manifest = {"signature": signature, "assets": records,
                "output_sha256": {p.name: sha256(p) for p in sorted(out.glob("*.png"))},
                "rights": "Third-party character artwork; redistribution permissions unverified; not covered by the source-code license"}
    write_json(out / "manifest.json", manifest)
    print("Processed four original images locally; originals unchanged.")
    return manifest


if __name__ == "__main__":
    process()
