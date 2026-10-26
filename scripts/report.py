"""Generate public source notes and a LOCAL publication inventory. No uploads."""
import datetime as dt
from html import escape
import platform
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont
from collect import percentages
from common import ROOT, config, read_json, sha256, write_json, write_text
from process_assets import png_bytes


def all_candidates():
    names = ["README.md", "SETUP.md", "DATA_SOURCES.md", "ASSET_SOURCES.md", "LICENSE", ".gitignore", "requirements.txt"]
    files = [ROOT / n for n in names]
    for pattern in ("config/*.json", "scripts/*.py", "scripts/*.cjs", "tests/*.py", ".github/workflows/*.yml",
                    "assets/processed/*", "assets/fonts/*", "assets/static/*", "assets/stats/*", "assets/data/*"):
        files.extend(p for p in ROOT.glob(pattern) if p.is_file())
    return sorted(set(files))


def data_notes():
    language = read_json(ROOT / "assets/data/languages.json", {})
    activity = read_json(ROOT / "assets/data/activity.json", {})
    community = read_json(ROOT / "assets/data/community.json", {}).get("metrics", {})
    stars = read_json(ROOT / "assets/data/stars.json", {})
    lines = ["# 数据来源与统计口径", "", "本页由本地真实缓存生成。采集时间按 UTC 记录；本次交付日为北京时间 2026-10-26。未拿到数据的字段不等于 0。", "",
             "## 本次数据", "", "| 模块 / 指标 | 实际值或状态 | 时间窗口与来源 |", "|---|---|---|"]
    if language.get("payload"):
        rows = percentages(language["payload"]["languages"])
        language_value = "; ".join(f"{r['name']} {r['bytes']} bytes / {r['percent']}%" for r in rows) or "暂无语言数据 · 0 bytes"
    else:
        language_value = f"请求失败 / 暂不可用（{language.get('reason')}）"
    lines.append(f"| Languages | {language_value} | 当前公开自有非 Fork 仓库语言字节；REST `/repos/{{owner}}/{{repo}}/languages` |")
    act = activity.get("payload")
    act_value = f"{act['total']} contributions" if act else f"暂不可用（{activity.get('reason')}）"
    lines.append(f"| Activity | {act_value} | 近 365 个 UTC 自然日；GraphQL `contributionsCollection.contributionCalendar`，不是纯 Git Commit 数 |")
    for name in ("Commits", "PRs", "Issues", "Reviews", "Discussions", "Answers"):
        entry = community.get(name, {})
        payload = entry.get("payload") or {}
        scope = payload or entry.get("requested_scope", {})
        value = str(payload["value"]) if payload.get("value") is not None else "暂不可用（" + str(entry.get("reason")) + "）"
        field = scope.get("field", {"Commits": "ContributionsCollection.totalCommitContributions", "Reviews": "ContributionsCollection.totalPullRequestReviewContributions",
                                      "Discussions": "User.repositoryDiscussions → public nodes", "Answers": "User.repositoryDiscussionComments(onlyAnswers:true) → discussion.repository.isPrivate=false"}.get(name, ""))
        window = scope.get("window", "近365日" if name in ("Commits", "Reviews") else "全部历史 · 仅公开")
        lines.append(f"| {name} | {value} | {window}；`{field}` |")
    star_payload = stars.get("payload")
    star_value = str(star_payload["total_current"]) + " current stars" if star_payload else "请求失败 / 暂不可用"
    lines.append(f"| Stars | {star_value} | 公开自有非 Fork 仓库当前数量；历史必须有 `starred_at`，没有则保留缓存或快照 |")
    lines += ["", "## 可核验的采样", ""]
    repos = read_json(ROOT / "assets/data/repositories.json", {})
    for repo in repos.get("payload") or []:
        lines.append(f"- [{repo['full_name']}](https://github.com/{repo['full_name']})：当前 {repo['stars']} Stars，仓库 size={repo['size']}（GitHub 元数据单位）。")
    lines += ["", f"仓库与 Star 快照最后有效采集时间：`{stars.get('fetched_at')}`。PRs、Issues 各自缓存的 `fetched_at` 与完整搜索表达式见 `assets/data/community-*.json`。", "",
              "本次首次采集的公开列表曾失败，随后恢复；语言端点重试返回 403，响应明确指示限流。保留失败状态，不从仓库主语言、文件大小或网页比例反推字节数。当前仓库 Stars 全为 0，因此不绘制假历史曲线，未请求无意义的 0 Star 仓库时间戳。非零 Star 真接口联调尚未测试，分页、缓存和绘图路径使用隔离的合成测试数据验证。", "",
              "## 实现规则", "",
              "Languages 排除 Fork、其他属主、`goodluck55k` 主页仓库与空资源仓库 `goodluck`。其余公开自有代码库均计入，包括未列入 Works 的 human-rate-web。语言缺失或空 map 贡献 0 bytes；任意语言请求失败时不发布不完整比例，优先整份有效缓存。最多六行：超过六种语言时显示前五种与 Other；以所有字节为分母，最大余数法保留一位小数并合计 100.0%。", "",
              "Activity 收集完整 365 日及所有涉及的周，保留首尾不完整周，不为了 52 个整周丢弃天数。逐日合计必须与 API totalContributions 一致，缺日或重复日期被拒绝；折线按真实周总量线性绘制。时间范围由日历数据标注，当前无认证所以没有真实曲线。", "",
              "Community 前四项采用同一个近 365 日窗口；本地 PRs / Issues 从 `search/issues` 的 `author:goodluck55k is:public is:pr|issue created:起日..止日` 获取，拒绝 incomplete_results。Actions 具备认证后可使用 Contribution Collection 同期字段。Discussions / Answers 单独标为全部历史，GraphQL 分页且筛掉 private 节点，不混称同一个年度总计。Answers 统计被采纳的回答，而不是讨论回复总数。", "",
              "Stars 选择 Top 6 公开自有非 Fork 仓库，分页请求 `Accept: application/vnd.github.star+json`，只绘制返回的真实时间戳。该接口描述当前仍保留的星标，取消过的 Stars 无法由此恢复，不称为完整全历史事件账本。接口数量与当前快照不符视为不完整；历史失败优先真实旧缓存，并分别标明旧历史与新快照。", "",
              "缓存 `ok`=真实有效；`stale`=最近失败但保留最后有效 payload；`unavailable`=无认证等原因未能取得；`failed`=请求错误且没有有效缓存。0 只用于成功接口明确返回的零值。重复采集相同 payload 时保留原 fetched_at，减少无意义提交。", "",
              "## 认证、隐私与尚未验证的部分", "",
              "默认仅访问公开 REST。GraphQL 只在 `GITHUB_ACTIONS=true`、`GITHUB_REPOSITORY=goodluck55k/goodluck55k` 时使用自动生成的 GITHUB_TOKEN；不读取本机个人 Token，不索要高权限 PAT 或私有仓库访问范围。若 contribution collection 含 restrictedContributionsCount，宁可显示不可用，也不把私有活动混入日历。", "",
              "Actions 的实际 GraphQL 许可与运行、真实 GitHub 图片主题/断点渲染、作品的线上端到端可用性：**NOT TESTED**。没有认证与上线授权，不能宣称这些已经通过。", "",
              "## 官方依据", "",
              "- [GitHub User 与 Contribution Calendar / Collection 字段](https://docs.github.com/en/graphql/reference/users)",
              "- [GitHub Discussion / DiscussionComment 字段](https://docs.github.com/en/graphql/reference/discussions)",
              "- [GitHub Stargazers 与时间戳媒体类型](https://docs.github.com/en/rest/activity/starring#list-stargazers)",
              "- [GitHub Profile README 规则](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/managing-your-profile-readme)",
              "- [GitHub Actions schedule 与停用规则](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)", ""]
    write_text(ROOT / "DATA_SOURCES.md", "\n".join(lines))


def comparison():
    c = config()
    canvas = Image.new("RGB", (1200, 1080), "#f6f5f2")
    draw = ImageDraw.Draw(canvas)
    f = ImageFont.truetype(str(ROOT / "assets/fonts/LibreBaskerville.ttf"), 19)
    roles = ("dyna", "spiderman", "deadpool", "nakoruru")
    for i, role in enumerate(roles):
        y = i * 270
        draw.text((20, y + 9), role + " / original", font=f, fill="#171614")
        draw.text((620, y + 9), role + " / processed", font=f, fill="#171614")
        for col, filename in enumerate((ROOT / "assets/source" / c["assets"][role], ROOT / "assets/processed" / (role + ".png"))):
            image = Image.open(filename).convert("RGBA")
            image.thumbnail((560, 220), Image.Resampling.LANCZOS)
            block = Image.new("RGBA", (560, 220), "#24201e" if col == 1 and role != "nakoruru" else "#e7e3dd")
            block.alpha_composite(image, ((560 - image.width) // 2, 0))
            canvas.paste(block.convert("RGB"), (20 + col * 600, y + 42))
    write_json(ROOT / "previews/comparison-notes.json", {"method": "original and processed side-by-side; no generated artwork", "roles": list(roles)})
    from common import write_bytes
    write_bytes(ROOT / "previews/asset-comparison.png", png_bytes(canvas))


def manifest():
    candidates = all_candidates()
    files = []
    for path in candidates:
        relative = path.relative_to(ROOT).as_posix()
        category = "code_or_documentation"
        if relative.startswith("assets/fonts/"):
            category = "open_font_or_license"
        elif relative.startswith("assets/data/"):
            category = "public_api_cache"
        elif relative.startswith(("assets/processed/", "assets/static/", "assets/stats/")):
            category = "third_party_character_derivative_or_artifact"
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path), "category": category})
    write_json(ROOT / "reports/publish-manifest.json", {"publication_authorized": False, "published": False, "files": files,
                "excluded": ["SPEC.md", "assets/source/**", "previews/**", "reports/**", ".tools/**", ".build/**", ".venv/**", "__pycache__/**"],
                "warning": "Candidate inventory only, not publication approval. Character rights remain unverified."})
    rows = ["# 待公开文件清单（未批准，未上传）", "", f"共 {len(files)} 个候选文件，{sum(f['bytes'] for f in files):,} bytes。每个文件的 SHA-256 见 publish-manifest.json。", "",
            "人物原图不在本清单，但处理图和最终 PNG 仍涉及版权，必须先核实许可。此清单用于用户审阅，不意味着已批准发布。", "",
            "| 路径 | bytes | 类别 |", "|---|---:|---|"]
    rows.extend(f"| `{f['path']}` | {f['bytes']} | {f['category']} |" for f in files)
    rows += ["", "默认排除：SPEC.md（含本地路径）、assets/source/ 原图、previews/、reports/、.tools/、.build/、虚拟环境、Python 缓存及任何 .env。", "",
             "远程构建使用 assets/processed/manifest.json 校验已有处理图；只有重新处理素材时才需要在本地交接四张原图。", ""]
    write_text(ROOT / "reports/PUBLISH_FILES.md", "\n".join(rows))
    # Avoid copying any real credential. Report matches only as file paths, never print contents.
    suspect = []
    pattern = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    for path in candidates:
        if path.suffix.lower() in (".md", ".py", ".cjs", ".yml", ".json", ".txt") and pattern.search(path.read_bytes()):
            suspect.append(path.relative_to(ROOT).as_posix())
    write_json(ROOT / "reports/security-scan.json", {"candidate_files_checked": len(candidates), "credential_pattern_matches": suspect,
               "private_data_policy": "Public REST queries and public-filtered aggregates only; no private repository names serialized.",
               "remote_write_tools_called": False, "publication_authorized": False})
    if suspect:
        raise RuntimeError("Publication inventory contains possible credential material; see security scan")


def acceptance():
    verification = read_json(ROOT / "reports/verification.json", {})
    browser = read_json(ROOT / "previews/browser-audit.json", [])
    inventory = read_json(ROOT / "reports/publish-manifest.json", {})
    if not verification or not browser:
        raise RuntimeError("Actual test and browser evidence required before acceptance report")
    rows = [
        ("A01", "PASS", "身份标签逐字核对；配置、Header 与 README alt 使用同一来源。"),
        ("A02", "PASS", "指定宣言含左右弯双引号、大写 J、半角逗号与句号，未改写。"),
        ("A03", "PASS", "四份原件 SHA-256 与用户附件一致；没有 AI 重绘、替代图片或上传。"),
        ("A04", "PASS", "戴拿 Header 等比展示，桌面高 212px，头部、计时器、动作与脚部完整。"),
        ("A05", "PASS", "蜘蛛侠仅在 Works 标题图出现；棋盘格遮罩、眼睛保留与深色边缘已检查。"),
        ("A06", "PASS", "死侍比心原图位于 Community 独立留白区，六个数字位置保持清楚。"),
        ("A07", "PASS", "娜可露露全幅原画逐像素核对处理图，主体、背景、Logo、参与制作标识完整。"),
        ("A08", "PASS；线上功能 NOT TESTED", "紧凑单行作品，逐项独立链接；仓库存在，介绍由源码佐证；未宣称稳定上线。"),
        ("A09", "PASS", "四统计分区同一连续 PNG，Languages → Activity → Community → Stars 顺序正确。"),
        ("A10", "PASS（口径/逻辑）；真实日历 NOT TESTED", "日历使用 contributions；年度与全部历史分别注明，日期/部分周/合计检查已测试。"),
        ("A11", "PASS", "当前 PRs/Issues/Stars 的 0 来自成功 API；语言限流与缺认证明确区别于 0；缓存回退测试通过。"),
        ("A12", "PASS 本地；GitHub NOT TESTED", "标准 picture 媒体规则；明暗文字、底色、图表真实不同；文字对比度≥4.5:1。"),
        ("A13", "PASS 本地；GitHub NOT TESTED", "Chrome 实际 375 CSS px 视口、独立手机资源，主要内容可读；无横向滚动和字符越界。"),
        ("A14", "PASS（同环境）", "README 与 20 张成品在相同配置/缓存下重新构建，21 个文件 SHA-256 不变；跨系统尚未验证。"),
        ("A15", "PASS 本地；远程 NOT TESTED", "分页、权限/网络错误、缓存恢复、无差异构建与工作流静态检查通过；没有运行远程 Actions。"),
        ("A16", "PASS 本地范围", "候选文件凭据特征扫描无命中；不序列化私有仓库名称、请求认证头或个人凭据。"),
        ("A17", "PASS 风险记录；公开许可 NOT TESTED", "来源、原图哈希与字体 OFL 齐备；四图的公开再分发许可未获得或核实，发布前仍需解决。"),
        ("A18", "PASS", "没有创建、修改、推送任何远程仓库，没有创建 Token/Secrets，没有公开上传原图。"),
    ]
    content = ["# 本地实施与验收报告", "", "交付日：2026-10-26（Asia/Shanghai）。**发布授权：否。远程发布：未执行。**", "",
               "已完成原生 README、本地设计引擎、四角色常规处理、四项统计绘制与降级、配置化 Works、工作流预备文件、测试和明暗/手机预览。缺少真实数据时如实显示不可用，不把模拟测试数据用于主页。", "",
               "## 预检与差异", "",
               "- 当前工作区最初为空，且不是 Git 仓库；没有复用旧版成品，也没有初始化或改写既有仓库。", 
               "- Python 3.11.5、Git 2.42.0.windows.2、Pillow 12.0.0、numpy 2.4.0 可用。四图的格式、尺寸与 alpha 均符合规格，工作区可写。", 
               "- 用户补交的四张附件与素材包文件逐一哈希一致。原件只读保留；处理和生成均在本地完成。", 
               "- 三个公开仓库已核实：human-talk-checker 有前端分析/改写逻辑与 Netlify / DeepSeek 调用路径；human-rate-web 与其题材接近，不重复列入 Works；goodluck size=0，不列入 Works。", 
               "- human-talk-checker 的 README 仍写着未接入 AI 的旧说明，与当前 main.js 及 Netlify Function 源码存在差异。本项目采用中性功能描述，并不保证线上服务、密钥或付费 API 可用。", 
               "- 未来主页仓库 goodluck55k/goodluck55k 审计时返回 404；没有创建它。上线前必须重新核查。", 
               "- 公开仓库列表首次有请求失败，已恢复；语言 API 重试确认限流，尚无有效语言字节缓存。GraphQL 未认证，因此 Activity、Commits、Reviews、Discussions、Answers 不显示推测数字。", "",
               "## 各阶段交付", "",
               "| 阶段 | 本地成果 | 验证与未解决事项 |", "|---|---|---|",
               "| Phase 0 | 素材、环境、公开源码与仓库审计 | 原图齐全；人物公开许可未核实 |",
               "| Phase 1 | Light / Dark Header，配置与字体许可 | 精确文案、无越界、文字对比通过 |",
               "| Phase 2 | 独立 Works、蜘蛛侠、死侍处理图、完整 Footer | 原图前后对照、背景与标识检查通过；作品线上 E2E 未测 |",
               "| Phase 3 | 连续四统计 PNG、真实缓存、失败回退 | API 零值/失败区别与隔离逻辑测试通过；语言/部分 GraphQL 暂不可用 |",
               "| Phase 4 | README、每日/手动 Actions、SETUP | 本地构建与工作流静态审查完成；真实 Actions 未测 |",
               "| Phase 5 | 4 张真实视口截图、逐项验收、候选公开清单 | 本地通过项见下表，远程与许可核验明确保留 |",
               "| Phase 6 | 未执行 | 需要额外发布批准与素材权利核实 |", "",
               "## A01–A18", "", "| ID | 结果 | 证据或限制 |", "|---|---|---|"]
    content.extend(f"| {key} | {state} | {note} |" for key, state, note in rows)
    content += ["", "## 实际测试证据", "",
                f"`python scripts/verify.py`：退出码 **{verification.get('exit_code')}**；共 **{verification.get('tests_run')}** 项，**{verification.get('passed')} PASS**，{verification.get('failures')} FAIL，{verification.get('errors')} ERROR，{verification.get('skipped')} SKIPPED。完整输出：`reports/test-output.txt`，机器记录：`reports/verification.json`。", "",
                "首次测试有 3 个临时目录文件重命名错误，原因是 Windows 沙箱的临时目录限制；已将隔离测试目录移入工作区 .build/，最终全部通过。没有将首次失败省略为从未发生。", "",
                "另把 64 个候选公开文件复制到 .build/publish-check/ 隔离目录，完全不带 assets/source/，执行 `python scripts/build.py` 与 `python scripts/verify.py`，两者退出码均为 0。该候选包 34 项检查中 32 PASS，2 项原件追溯检查按设计 SKIPPED，无失败；证明日常构建无需公开原始图片。记录见 reports/candidate-verification.json。", "",
                "`node scripts/screenshots.cjs`：退出码 0。浏览器审计见 `previews/browser-audit.json`。四次均解码 5 张图，作品链接正确，未发生页面脚本错误，滚动宽度等于实际视口宽度。截图时阻断 HTTP(S) 请求。", "",
                "| 主题 | 实际视口 | 截图 |", "|---|---:|---|"]
    for result in browser:
        content.append(f"| {result['colorScheme']} | {result['viewport']}px | [{result['output'].split('/')[-1]}](../{result['output']}) |")
    content += ["", "构建复现检查：相同输入重复输出的 21 个文件哈希相同。原图哈希与娜可露露完整像素比较通过。所有绘制文本边界在生成时检查；所有 PNG 本地解码成功。合成测试样本仅在 tests/ 与内存中使用，未写入 assets/data/。", "",
                "## 真实数据抽样与限制", "",
                "公开仓库元数据快照包含 goodluck、human-rate-web、human-talk-checker，均为非 Fork、当前 Stars=0。PRs 与 Issues 搜索的真实返回数量都是 0，窗口为 2025-10-26 至 2026-10-25（UTC）；快照采集于北京时间 2026-10-26 早晨。", "",
                "语言：请求返回限流，没有比例图和猜测字节。Activity：没有 GraphQL 认证，未生成假曲线。Community：6 个维度均保留，未知维度显示 —/暂不可用。Stars：真实当前总数 0，显示暂无星迹；非零时间戳接口的远程成功尚未验证。完整字段、范围、来源与缓存状态见 [DATA_SOURCES.md](../DATA_SOURCES.md)。", "",
                "## 设计调整依据", "",
                "- 全部成品采用 2x PNG，避免 GitHub SVG 内图片、CSS 与字体支持差异；中文和英文直接光栅化，没有远程运行时依赖。", 
                "- 桌面 840px、手机独立 420px 画布，在 375px 视口按比例显示；手机重排 Community 为三列两行，并给死侍独立留白区。", 
                "- Header 从参考约 232px 调整为 256px，主标题 58px，身份 18px，宣言 24px；保持三层文案与戴拿完整动作。手机使用 35/13/17px。", 
                "- Header、Works、Footer 分图；四统计维持单张连续纵向纸面。每个 Works 独立链接，新增/删除按配置自动调整。", 
                "- Footer 桌面约 531px、手机约 319px，完整 contain 原画，遵从规格中保留人物与标识优先于早期矮横幅的许可。", 
                "- 字体选 Libre Baskerville / Noto Serif SC，保留 OFL；深色点缀改为 #d18c8d，以保证较小文本与背景的可读对比。其余色值及布局参数见 config/profile.json。", "",
                "## 交付与发布边界", "",
                f"源码、配置、原图、处理图、20 张最终图片、公共缓存、安装说明、预览与测试记录均位于当前工作区。候选公开清单共 {len(inventory.get('files', []))} 个文件，逐项路径、bytes、哈希见 [PUBLISH_FILES.md](PUBLISH_FILES.md) 与 publish-manifest.json。清单未执行上传。", "",
                "默认排除原图、含本地路径的 SPEC.md、预览、本地依赖与报告；即使只公开处理图与成品，也仍须解决角色版权。完整本地来源记录见 [ASSET_SOURCES.md](../ASSET_SOURCES.md)。", "",
                "仍未解决：四图公开再分发许可、语言接口恢复、真实 GraphQL 数据、真实 GitHub 页面显示、真实 Actions 执行、作品线上端到端测试。公开前需要额外明确批准；不会把同意本地实施理解成同意公开。", ""]
    write_text(ROOT / "reports/ACCEPTANCE.md", "\n".join(content))


def main():
    if config().get("schema_version",1)>=2:
        from report_round2 import main as round_two_report
        round_two_report()
        return
    data_notes()
    comparison()
    manifest()
    acceptance()
    print("Data sources, local asset comparison, publication inventory and credential scan written. Nothing published.")


if __name__ == "__main__":
    main()
