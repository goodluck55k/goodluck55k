"""Deterministic 2x PNG composition: no SVG font/image runtime dependency.

Desktop 840px and mobile 420px have independent typography and layout.
The four data panels share one continuous paper canvas in each variant.
"""
from functools import lru_cache
from io import BytesIO
import random
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from collect import percentages
from common import ROOT, config, read_json, write_bytes, write_json
from process_assets import png_bytes, process
from vector import SvgDocument, monotone_curve

DRAW_RECORDS = []


@lru_cache(maxsize=96)
def font(size, kind="regular", scale=2):
    name = {"regular": "LibreBaskerville.ttf", "italic": "LibreBaskerville-Italic.ttf",
            "chinese": "NotoSerifSC.ttf", "handwritten": "Caveat.ttf"}[kind]
    # Use the same unshaped glyphs as the SVG outline renderer, on every host.
    face = ImageFont.truetype(str(ROOT / "assets/fonts" / name), round(size * scale),
                              layout_engine=ImageFont.Layout.BASIC if kind == "handwritten" else None)
    if kind == "handwritten":
        face.set_variation_by_axes([500])
    return face


def kind_for(text, italic=False):
    if any(ord(c) > 0x2fff for c in text):
        return "chinese"
    return "italic" if italic else "regular"


class Paper:
    def __init__(self, width, height, theme, label, scale=2, vector=False):
        self.w, self.h, self.t, self.label, self.s = width, height, theme, label, scale
        self.im = Image.new("RGB", (width * scale, height * scale), theme["bg"])
        self.draw = ImageDraw.Draw(self.im)
        self.mobile = width < 600
        self.margin = 22 if self.mobile else 44
        self.bounds = []
        self.vector = SvgDocument(width, height, theme, label) if vector else None
        self.images = []
        rng = random.Random(550)
        bg = tuple(int(theme["bg"][i:i + 2], 16) for i in (1, 3, 5))
        fibre = tuple(v + (-4 if sum(bg) > 400 else 5) for v in bg)
        for _ in range(width * height // 150):
            x, y = rng.randrange(width * scale), rng.randrange(height * scale)
            self.draw.line((x, y, x + rng.randrange(1, 5), y + 1), fill=fibre, width=1)

    def text(self, x, y, text, size=18, color="ink", italic=False, align="left", kind=None):
        kind = kind or kind_for(text, italic)
        f = font(size, kind, self.s)
        width = self.draw.textlength(text, font=f) / self.s
        if align == "right":
            x -= width
        elif align == "center":
            x -= width / 2
        bbox = self.draw.textbbox((round(x * self.s), round(y * self.s)), text, font=f, anchor="lt")
        if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > self.w * self.s or bbox[3] > self.h * self.s:
            raise ValueError(f"Text outside {self.label}: {text!r} at {bbox}")
        self.draw.text((round(x * self.s), round(y * self.s)), text, font=f, fill=self.t.get(color, color), anchor="lt")
        if self.vector:
            self.vector.text(x, y, text, size, self.t.get(color, color), kind, f, self.s)
        self.bounds.append({"text": text, "box": [round(v / self.s, 2) for v in bbox], "size": size})
        return width

    def line(self, x1, y1, x2, y2, color="line", width=1):
        self.draw.line(tuple(round(v * self.s) for v in (x1, y1, x2, y2)), fill=self.t.get(color, color), width=max(1, round(width * self.s)))
        if self.vector:
            self.vector.line(x1, y1, x2, y2, self.t.get(color, color), width)

    def curve(self, points, color="accent", width=1.6):
        path, samples = monotone_curve(points)
        if len(samples) > 1:
            self.draw.line([(round(x*self.s), round(y*self.s)) for x, y in samples], fill=self.t.get(color,color), width=max(1,round(width*self.s)))
            if self.vector:
                self.vector.path(path, self.t.get(color,color), width)
        return samples

    def polyline(self, points, color="accent", width=1.4):
        self.draw.line([(round(x*self.s), round(y*self.s)) for x, y in points], fill=self.t.get(color,color), width=max(1,round(width*self.s)))
        if self.vector:
            path = "M" + "L".join(f"{x:.3f} {y:.3f}" for x,y in points)
            self.vector.path(path,self.t.get(color,color),width)

    def circle(self,x,y,radius,color="accent"):
        self.draw.ellipse(((x-radius)*self.s,(y-radius)*self.s,(x+radius)*self.s,(y+radius)*self.s),fill=self.t.get(color,color))
        if self.vector:
            self.vector.circle(x,y,radius,self.t.get(color,color))

    def title(self, y, english, chinese, number):
        x = self.margin
        size = 30 if self.mobile else 35
        length = self.text(x, y, english, size=size, kind="handwritten")
        self.text(x + length + 12, y + 4, "· " + chinese, size=15 if self.mobile else 18, color="muted")
        self.text(self.w - x, y + 7, number, size=12, color="muted", align="right")

    def image(self, role, x, y, height=None, width=None, saturation=1, paper_blend=0, bottom_fade=0):
        image = Image.open(ROOT / "assets/processed" / (role + ".png")).convert("RGBA")
        if width is None:
            width = image.width * height / image.height
        else:
            height = image.height * width / image.width
        if x < 0 or y < 0 or x + width > self.w + .01 or y + height > self.h + .01:
            raise ValueError(f"Image outside canvas: {role}")
        image = image.resize((round(width * self.s), round(height * self.s)), Image.Resampling.LANCZOS)
        if saturation != 1 or paper_blend:
            alpha = image.getchannel("A")
            image = ImageEnhance.Color(image).enhance(saturation)
            if paper_blend:
                image = Image.blend(image,Image.new("RGBA",image.size,self.t["bg"]),paper_blend)
            image.putalpha(alpha)
        if bottom_fade:
            import numpy as np
            alpha=np.asarray(image.getchannel("A"),dtype=float)
            start=round(image.height*(1-bottom_fade))
            alpha[start:]*=np.linspace(1,0,image.height-start)[:,None]
            image.putalpha(Image.fromarray(alpha.astype("uint8")))
        self.im.paste(image, (round(x * self.s), round(y * self.s)), image)
        self.images.append({"role":role,"box":[x,y,x+width,y+height],"saturation":saturation,"paper_blend":paper_blend,"bottom_fade":bottom_fade})
        if self.vector:
            self.vector.bitmap(image,x,y,width,height,role+" · original artwork pixels")
        return width, height

    def save(self, path):
        write_bytes(path, png_bytes(self.im))
        if self.vector:
            from common import write_text
            write_text(path.with_suffix(".svg"),self.vector.xml())
        DRAW_RECORDS.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"), "label": self.label,
                             "width": self.w, "height": self.h, "text": self.bounds, "images":self.images})


def state_label(entry):
    state = entry.get("state", "unavailable")
    if state == "stale":
        return "缓存 · " + (entry.get("fetched_at") or "未知时间")[:10]
    if state == "failed":
        return "请求失败 · 暂不可用"
    if state == "unavailable":
        return "暂不可用"
    return ""


def header(c, theme, width):
    mobile = width < 600
    scale=c.get("visual",{}).get("dyna_scale",1.128)
    figure_height=(122 if mobile else 212)*scale
    # Keep the established canvas and typography while insetting the artwork.
    p = Paper(width, 204 if mobile else 279, theme, "Header")
    x = p.margin
    p.text(x, 34 if mobile else 49, c["user"], size=35 if mobile else 58)
    p.text(x, 90 if mobile else 128, c["identity"], size=13 if mobile else 18, color="muted")
    p.line(x, 125 if mobile else 166, x + 44, 125 if mobile else 166, "accent", 1.2)
    p.text(x, 147 if mobile else 189, c["quote"], size=24 if mobile else 32, kind="handwritten")
    p.image("dyna", width - (96 if mobile else 179), 18 if mobile else 20, height=figure_height)
    return p


def works_heading(theme, width):
    mobile = width < 600
    p = Paper(width, 88 if mobile else 100, theme, "Works heading")
    p.title(24, "Works", "近作", "")
    p.image("spiderman", width - (112 if mobile else 173), 10 if mobile else 8, height=74 if mobile else 90)
    return p


def work_row(work, index, theme, width):
    mobile = width < 600
    p = Paper(width, 58 if mobile else 64, theme, work["name"])
    x, y = p.margin, 9
    name_size, description_size = (15, 13) if mobile else (24, 21)
    # Keep the name and description on one line; shorten configuration, never clip.
    nw = p.draw.textlength(work["name"], font=font(name_size, "chinese")) / 2
    text_width = p.draw.textlength(work["description"], font=font(description_size, "chinese")) / 2
    while nw + text_width + 28 > width - x * 2 and description_size > (10 if mobile else 15):
        description_size -= 1
        text_width = p.draw.textlength(work["description"], font=font(description_size, "chinese")) / 2
    if nw + text_width + 28 > width - x * 2:
        raise ValueError("Works description is too long for one line; shorten config/profile.json")
    p.text(x, y, work["name"], size=name_size)
    p.text(x + nw + 9, y + (2 if mobile else 3), "—", size=description_size, color="muted")
    p.text(x + nw + 28, y + (2 if mobile else 3), work["description"], size=description_size, color="muted")
    p.line(x, p.h - 8, x + 44, p.h - 8, "line")
    return p


def language_height(entry, mobile):
    data = entry.get("payload") or {}
    count = len(percentages(data.get("languages", {})))
    return 108 + max(1, count) * (35 if mobile else 39)


def draw_languages(p, top, entry):
    p.title(top + 28, "Languages", "语言", "01")
    m = p.margin
    data = entry.get("payload")
    if data is None:
        p.text(m, top + 83, state_label(entry), size=18, color="muted")
        return
    rows = percentages(data.get("languages", {}))
    if not rows:
        p.text(m, top + 83, "暂无语言数据 · 0 bytes", size=18, color="muted")
        return
    step = 35 if p.mobile else 39
    for i, row in enumerate(rows):
        y = top + 83 + i * step
        p.text(m, y, row["name"], size=16 if p.mobile else 20)
        left = 133 if p.mobile else 225
        right = p.w - m - (61 if p.mobile else 87)
        p.line(left, y + 11, right, y + 11, "line", 2)
        if row["percent"]:
            p.line(left, y + 11, left + (right - left) * row["percent"] / 100, y + 11, "accent" if i == 0 else "muted", 3.5)
        p.text(p.w - m, y + 1, f"{row['percent']:.1f}%", size=14 if p.mobile else 18, color="muted", align="right")
    note = state_label(entry) or "公开自有代码库 · 按字节计"
    p.text(m, top + 83 + len(rows) * step + 2, note, size=12 if p.mobile else 15, color="muted")


def draw_activity(p, top, entry, height):
    p.title(top + 28, "Activity", "贡献轨迹", "02")
    m, data = p.margin, entry.get("payload")
    if data is None:
        p.text(m, top + 91, state_label(entry), size=22 if p.mobile else 27)
        message = "贡献日历需要 GitHub API 认证" if entry.get("reason") == "NO_GRAPHQL_TOKEN" else "尚未获取可展示的公开贡献日历"
        p.text(m, top + 135, message, size=14 if p.mobile else 19, color="muted")
        p.text(m, top + 169, "未获取数据，不以提交次数替代。", size=13 if p.mobile else 17, color="muted")
        return
    weeks = data["weeks"]
    p.text(m, top + 77, f"{data['total']:,}", size=30 if p.mobile else 40)
    p.text(m + (86 if p.mobile else 126), top + 94, "contributions", size=13 if p.mobile else 17, color="muted")
    left, right, high, base = m, p.w - m, top + 155, top + height - 70
    peak = max((w["count"] for w in weeks), default=0)
    points = []
    for i, week in enumerate(weeks):
        if "start" in week and "end" in week:
            import datetime as dt
            day=dt.date.fromisoformat(week["start"]).toordinal()
            last=dt.date.fromisoformat(data["end"]).toordinal()
            first=dt.date.fromisoformat(data["start"]).toordinal()
            x=left+(right-left)*(day-first)/max(1,last-first)
        else:
            x = left + (right - left) * i / max(1, len(weeks) - 1)
        y = base - (base - high) * week["count"] / max(1, peak)
        points.append((x, y))
    p.line(left, base, right, base, "line")
    if len(points) > 1:
        samples=p.curve(points,"accent",1.7)
        # Short diagonal ink marks sit under real samples; counts and peaks are unchanged.
        for i,(x,y) in enumerate(samples):
            if i%3==0 and base-y>5:
                p.line(x,min(base,y+8),min(right,x+3),min(base,y+11),"line",.65)
    if points:
        peak_i = next((i for i, w in enumerate(weeks) if w["count"] == peak), 0)
        x, y = points[peak_i]
        p.circle(x,y,3)
        p.text(right, top + 126, f"peak · {peak}", size=13, color="accent", align="right")
    p.text(left, base + 12, data["start"], size=12 if p.mobile else 15, color="muted")
    p.text(right, base + 12, data["end"], size=12 if p.mobile else 15, color="muted", align="right")
    p.text(m, top + height - 28, state_label(entry) or "每周贡献总量 · 含首尾不完整周", size=12 if p.mobile else 15, color="muted")


def draw_community(p, top, entries, height):
    p.title(top + 28, "Community", "社区参与", "03")
    m = p.margin
    names = ("Commits", "PRs", "Issues", "Reviews", "Discussions", "Answers")
    visual=config().get("visual",{})
    column = (p.w - m * 2) / 3 if p.mobile else (p.w - m * 2 - 164) / 3
    for i, name in enumerate(names):
        x = m + (i % 3) * column
        y = top + 87 + (i // 3) * (95 if p.mobile else 98)
        entry = entries.get(name, {})
        payload = entry.get("payload") or {}
        value = payload.get("value")
        p.text(x, y, "—" if value is None else f"{value:,}", size=28 if p.mobile else 34)
        p.text(x, y + 39, name, size=13 if p.mobile else 17, color="muted")
        if entry.get("state") == "stale":
            note = "缓存"
        elif value is None:
            note = "请求失败" if entry.get("state") == "failed" else "暂不可用"
        else:
            note = "近365日" if i < 4 else "全部历史"
        p.text(x, y + 61, note, size=11 if p.mobile else 13, color="muted")
    if p.mobile:
        p.image("deadpool", p.w - 129, top + 289, height=84*visual.get("deadpool_scale",.95),saturation=visual.get("deadpool_saturation",.78),paper_blend=visual.get("deadpool_paper_blend",.04),bottom_fade=visual.get("deadpool_bottom_fade",.24))
        p.text(m, top + 298, "公开活动", size=13, color="muted")
        p.text(m, top + 326, "— 表示尚未取得数据", size=12, color="muted")
    else:
        p.image("deadpool", p.w - 195, top + 145, height=124*visual.get("deadpool_scale",.95),saturation=visual.get("deadpool_saturation",.78),paper_blend=visual.get("deadpool_paper_blend",.04),bottom_fade=visual.get("deadpool_bottom_fade",.24))
    windows=[(entries.get(name,{}).get("payload") or entries.get(name,{}).get("requested_scope",{})).get("window") for name in names[:4]]
    actual=next((w for w in windows if w and "/" in w),None)
    caption="近365日 · "+actual if actual else "Commits / PRs / Issues / Reviews：近365日"
    p.text(m, top + height - 36, caption, size=11 if p.mobile else 14, color="muted")
    p.text(m, top + height - 16, "Discussions / Answers：全部历史 · 仅公开", size=11 if p.mobile else 14, color="muted")


def draw_stars(p, top, entry, height):
    p.title(top + 28, "Stars", "星迹", "04")
    m, data = p.margin, entry.get("payload")
    if data is None:
        p.text(m, top + 91, state_label(entry), size=20, color="muted")
        return
    total = data["total_current"]
    p.text(m, top + 83, str(total), size=36 if p.mobile else 44)
    p.text(m + (63 if p.mobile else 86), top + 105, "current stars", size=14 if p.mobile else 18, color="muted")
    if total == 0:
        p.text(m, top + 151, "暂无星迹 · 公开仓库当前为 0", size=14 if p.mobile else 19, color="muted")
    else:
        valid = [r for r in data["series"] if r["current"] > 0 and r["history_state"] in ("ok", "stale")]
        unavailable = [r for r in data["series"] if r["current"] > 0 and r["history_state"] == "unavailable"]
        if not valid:
            p.text(m, top + 154, "当前数量快照 · 历史暂不可用", size=14 if p.mobile else 18, color="muted")
        else:
            import datetime as dt
            parse = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
            start = min(parse(r["created_at"]) for r in valid)
            end = parse(entry["fetched_at"])
            peak = max(len(r["starred_at"]) for r in valid)
            left, right, base, high = m, p.w - m, top + 250, top + 165
            p.line(left, base, right, base, "line")
            for i, row in enumerate(valid):
                points = [(left, base)]
                count = 0
                for stamp in row["starred_at"]:
                    x = left + (right - left) * (parse(stamp) - start) / max(1, end - start)
                    points.extend([(x, base - (base - high) * count / peak), (x, base - (base - high) * (count + 1) / peak)])
                    count += 1
                points.append((right, base - (base - high) * count / peak))
                p.polyline(points,"accent" if i==0 else "muted",1.5)
            p.text(left, base + 12, dt.datetime.fromtimestamp(start, dt.timezone.utc).date().isoformat(), size=11 if p.mobile else 14, color="muted")
            p.text(right, base + 12, entry["fetched_at"][:10], size=11 if p.mobile else 14, color="muted", align="right")
        y = top + (294 if valid else 198)
        for row in data["series"]:
            label = f"{row['name']} · {row['current']}"
            if row in unavailable:
                label += " · 历史暂不可用"
            elif row.get("history_state") == "stale":
                label += f" · 历史缓存 {len(row['starred_at'])}"
            p.text(m, y, label, size=12 if p.mobile else 16, color="muted")
            y += 27
    p.text(m, top + height - 31, state_label(entry) or "仅公开自有非 Fork 仓库", size=12 if p.mobile else 15, color="muted")


def stats(theme, width):
    entries = {name: read_json(ROOT / "assets/data" / (name + ".json"), {}) for name in ("languages", "activity", "community", "stars")}
    mobile = width < 600
    lang_h = language_height(entries["languages"], mobile)
    activity_h = 310 if entries["activity"].get("payload") else 236
    community_h = 427 if mobile else 329
    star_payload = entries["stars"].get("payload") or {}
    star_h = 226 if not star_payload.get("total_current") else 328 + 27 * len(star_payload.get("series", []))
    heights = [lang_h, activity_h, community_h, star_h]
    p = Paper(width, sum(heights) + 20, theme, "Languages / Activity / Community / Stars",vector=True)
    top = 0
    draw_languages(p, top, entries["languages"])
    top += lang_h
    p.line(p.margin, top + 5, p.margin + 48, top + 5)
    draw_activity(p, top, entries["activity"], activity_h)
    top += activity_h
    p.line(p.margin, top + 5, p.margin + 48, top + 5)
    draw_community(p, top, entries["community"].get("metrics", {}), community_h)
    top += community_h
    p.line(p.margin, top + 5, p.margin + 48, top + 5)
    draw_stars(p, top, entries["stars"], star_h)
    return p


def footer(c, theme, width):
    mobile = width < 600
    margin = 22 if mobile else 44
    visual = c.get("visual", {})
    base_height = 126 if mobile else 176
    image_height = base_height * visual.get("footer_scale", .9)
    with Image.open(ROOT / "assets/processed/nakoruru.png") as art:
        original_width = base_height * art.width / art.height
    p = Paper(width, base_height + 48, theme, "Nakoruru transparent art footer")
    p.line(margin, 6, width - margin, 6)
    dark = theme["bg"] == c["themes"]["dark"]["bg"]
    # Right-aligned original alpha silhouette balances the quieter text at left.
    p.image("nakoruru", width - margin - original_width - (6 if mobile else 8), 20, height=image_height,
            saturation=visual.get("footer_saturation", .72),
            paper_blend=visual.get("footer_paper_blend_dark" if dark else "footer_paper_blend_light", .06),
            bottom_fade=visual.get("footer_bottom_fade", .08))
    p.text(margin, 75 if mobile else 98, "© " + c["user"], size=13 if mobile else 17, color="muted")
    p.text(margin, 103 if mobile else 132, "Maintained with GitHub Actions", size=9 if mobile else 13, color="muted")
    return p


def picture(base, alt, width, breakpoint, prefer_svg=False):
    import html
    if prefer_svg:
        sources=[]
        for extension in ("svg","png"):
            mime="image/svg+xml" if extension=="svg" else "image/png"
            for media,suffix in ((f"(prefers-color-scheme: dark) and (max-width: {breakpoint}px)","dark-mobile"),(f"(max-width: {breakpoint}px)","light-mobile"),("(prefers-color-scheme: dark)","dark")):
                sources.append(f'  <source type="{mime}" media="{media}" srcset="{base}-{suffix}.{extension}">')
            if extension=="svg":
                sources.append(f'  <source type="{mime}" srcset="{base}-light.svg">')
        return '<picture>\n'+'\n'.join(sources)+f'\n  <img src="{base}-light.png" width="{width}" alt="{html.escape(alt,quote=True)}">\n</picture>'
    return (f'<picture>\n'
            f'  <source media="(prefers-color-scheme: dark) and (max-width: {breakpoint}px)" srcset="{base}-dark-mobile.png">\n'
            f'  <source media="(max-width: {breakpoint}px)" srcset="{base}-light-mobile.png">\n'
            f'  <source media="(prefers-color-scheme: dark)" srcset="{base}-dark.png">\n'
            f'  <img src="{base}-light.png" width="{width}" alt="{html.escape(alt, quote=True)}">\n'
            f'</picture>')


def readme(c):
    from html import escape
    w, breakpoint = c["layout"]["desktop_width"], c["layout"]["mobile_breakpoint"]
    pic = lambda base, alt: picture(base, alt, w, breakpoint)
    parts = ['<!-- Generated by scripts/build.py from config/profile.json; edit the configuration. -->',
             pic("assets/static/header", f"{c['user']} · {c['identity']} · {c['quote']}"),
             pic("assets/static/works-heading", "Works · 近作；蜘蛛侠蹲姿点缀")]
    works=[]
    for i, work in enumerate(c["works"], 1):
        works.append(f'<a href="{escape(work["url"], quote=True)}">' + pic(f"assets/static/work-{i}", work["name"] + " — " + work["description"]) + '</a><br>')
    parts.append('<p>\n'+'\n'.join(works)+'\n</p>')
    parts.append(picture("assets/stats/stats", "Languages / Activity（贡献日历，非纯 Commits）/ Community / Stars；仅公开数据；— 表示暂不可用；各指标时间范围见图及 DATA_SOURCES.md",w,breakpoint,prefer_svg=True))
    parts.append(pic("assets/static/footer", "娜可露露：用户提供的透明背景立绘，置于页脚右侧。版权归原权利人。"))
    return "\n\n".join(parts) + "\n"


def build():
    c = config()
    process()
    DRAW_RECORDS.clear()
    expected = set()
    for mode, theme in c["themes"].items():
        for width, suffix in ((c["layout"]["desktop_width"], ""), (c["layout"]["mobile_width"], "-mobile")):
            outputs = {"assets/static/header": header(c, theme, width),
                       "assets/static/works-heading": works_heading(theme, width),
                       "assets/static/footer": footer(c, theme, width),
                       "assets/stats/stats": stats(theme, width)}
            for i, work in enumerate(c["works"], 1):
                outputs[f"assets/static/work-{i}"] = work_row(work, i, theme, width)
            for name, paper in outputs.items():
                path = ROOT / (name + "-" + mode + suffix + ".png")
                paper.save(path)
                expected.add(path)
    # Only clean stale generated Works rows in the known output directory.
    for old in (ROOT / "assets/static").glob("work-[1-5]-*.png"):
        if old not in expected:
            old.unlink()
    from common import write_text
    write_text(ROOT / "README.md", readme(c))
    write_json(ROOT / "previews/layout-audit.json", DRAW_RECORDS)
    print(f"Built {len(expected)} local PNGs and README; no network access in build.")
    return c
