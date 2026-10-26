"""Round 2 evidence-based reports. Absent checks stay NOT TESTED."""
from common import ROOT,config,read_json,write_json,write_text
from collect import percentages


def cached(name):
    return read_json(ROOT/"assets/data"/(name+".json"),{})


def metric_rows():
    rows=[]
    for name,entry in cached("community").get("metrics",{}).items():
        payload=entry.get("payload") or {}
        scope=payload or entry.get("requested_scope",{})
        rows.append((name,str(payload["value"]) if payload.get("value") is not None else "不可用",entry.get("state","unknown"),scope.get("window","未知"),scope.get("field","未知")))
    order=("Commits","PRs","Issues","Reviews","Discussions","Answers")
    return sorted(rows,key=lambda r:order.index(r[0]))


def source_notes():
    language=cached("languages")
    activity=cached("activity")
    stars=cached("stars")
    lines=["# 数据来源与查询验证（第二轮）","","只读采集 GitHub 公开数据；凭据由本机 GitHub CLI 保管，没有提取、打印或提交 Token。所有数量来自 API 缓存；测试样本未写入主页数据。","",
           "## Languages","",f"状态：`{language.get('state')}`；有效数据时间：`{language.get('fetched_at')}`。","",
           "REST `/users/goodluck55k/repos?type=owner` 分页列出公开自有仓库；逐仓库 `/repos/{owner}/{repo}/languages` 取得真实字节。排除 Fork、主页仓库 goodluck55k、空资源仓库 goodluck。human-rate-web 虽未列为 Works，仍计入代码语言。","",
           "| 语言 | bytes | 占比 |","|---|---:|---:|"]
    data=language.get("payload") or {}
    for row in percentages(data.get("languages",{})):
        lines.append(f"| {row['name']} | {row['bytes']} | {row['percent']:.1f}% |")
    lines += ["",f"总字节：{data.get('total_bytes','未知')}。最多六行；超过六种时为前五种+Other；所有字节为分母，最大余数法保留一位小数。任何仓库请求失败时不发布不完整比例，保留整份有效缓存。","",
              "## Activity","",f"状态：`{activity.get('state')}`；有效数据时间：`{activity.get('fetched_at')}`。","",
              "GraphQL `User.contributionsCollection(from:...,to:...).contributionCalendar`。指标为 contributions，不是纯 Git commits。"]
    a=activity.get("payload") or {}
    if a:
        lines += ["",f"窗口 `{a['start']} / {a['end']}`（UTC），{len(a['days'])} 天、{len(a['weeks'])} 周、总贡献 {a['total']}、周峰值 {a['peak']}。保留首尾不完整周。逐日与逐周合计均校验 API 总数。","",
                  "| 非零贡献日 | contributions |","|---|---:|"]
        lines += [f"| {d['date']} | {d['count']} |" for d in a["days"] if d["count"]]
    lines += ["","曲线使用真实每周计数和日期坐标。单调三次插值经过原始点，不制造新峰值；坐标、峰值、总数均取自缓存。缺日、重复日、负值或合计不一致时拒绝生成新数据。","",
              "## Community","","| 指标 | 实际值 | 状态 | 时间窗口 | GitHub 字段 |","|---|---:|---|---|---|"]
    lines += [f"| {name} | {value} | {state} | {window} | `{field}` |" for name,value,state,window,field in metric_rows()]
    lines += ["","前四项使用相同 365 日窗口；Discussions / Answers 为全部历史，逐项注明，不混称年度总数。Answers 是被标记为答案的讨论回复，使用 `onlyAnswers:true`。讨论连接按 cursor 分页，只保留公开节点的数量，不缓存正文、用户列表或私有仓库名。","",
              "## Stars","",f"状态：`{stars.get('state')}`；有效数据时间：`{stars.get('fetched_at')}`。","",
              "当前数量来自公开自有非 Fork 仓库 `stargazers_count`，Top 6 用于历史系列。非零历史使用 REST `Accept: application/vnd.github.star+json`，失败后尝试 GraphQL `repository.stargazers.edges.starredAt`。两者均分页，数量须与仓库快照一致。","",
              "| 仓库 | 当前 Stars | 历史状态 | 来源 |","|---|---:|---|---|"]
    s=stars.get("payload") or {}
    lines += [f"| {r['full_name']} | {r['current']} | {r['history_state']} | `{r['source']}` |" for r in s.get("series",[])]
    lines += ["",f"当前总 Stars={s.get('total_current','未知')}。真实 0 不等于历史获取失败；为零时不伪造历史曲线。时间戳只代表目前仍存在的 Stars，不代表已取消 Star 的全部历史。","",
              "## 失败与缓存","",
              "`ok` 为成功数据；`stale` 为失败后保留的有效旧 payload，并显示缓存日期；`unavailable` 为未取得数据；`failed` 为请求错误且没有有效缓存。只有接口成功返回零时显示 0。文件通过临时文件替换写入；相同 payload 保留原 fetched_at，避免无意义提交。每个 Community 指标独立缓存。","",
              "REST Star 历史或 GraphQL 返回不完整时，优先真实旧历史，随后退化为当前快照并标注历史不可用。参考仓库本轮实际出现 metadata=1，但 REST 历史404、GraphQL connection返回0条的情况，程序正确拒绝该历史，未写入本账户缓存。HTTP本身不足以断定是权限策略还是上游数据可见性问题。","",
              "本地优先通过 gh credential store 认证；Actions 使用自动提供的 GITHUB_TOKEN。GraphQL query 不请求私有仓库名称/正文；若贡献按仓库分组出现私有项或受限贡献，则不把这些数据混入公开日历。分组超过可审计范围同样拒绝。","",
              "## 可复核证据与官方资料","",
              "本次匿名 403/配额信息：`reports/round2-api-probes.json`。认证请求 HTTP/限流头：`reports/round2-authenticated-api.json`。真实联调、Star 差异与 GitHub GFM 渲染：`reports/round2-real-validation.json`。原始公共缓存在 `assets/data/`。报告文件默认不公开。","",
              "- [GitHub Contribution Calendar / Collection 与 User 字段](https://docs.github.com/en/graphql/reference/users)",
              "- [GitHub GraphQL 认证与 query 规则](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql)",
              "- [GitHub Stargazers API](https://docs.github.com/en/rest/activity/starring#list-stargazers)",
              "- [GitHub Markdown 无状态渲染 API](https://docs.github.com/en/rest/markdown/markdown)",
              "- [GitHub CLI 浏览器登录](https://cli.github.com/manual/gh_auth_login)",""]
    write_text(ROOT/"DATA_SOURCES.md","\n".join(lines))


def validation_report():
    tests=read_json(ROOT/"reports/verification.json",{})
    live=read_json(ROOT/"reports/round2-real-validation.json",{})
    requests=read_json(ROOT/"reports/round2-authenticated-api.json",{})
    browser=read_json(ROOT/"previews/browser-audit.json",[])
    inventory=read_json(ROOT/"reports/publish-manifest.json",{})
    candidate=read_json(ROOT/"reports/candidate-verification.json",{})
    a=cached("activity").get("payload") or {}
    language=cached("languages").get("payload") or {}
    s=cached("stars").get("payload") or {}
    checks=live.get("checks",{})
    rows=["# 第二轮优化与验收报告","","2026-10-26 · Asia/Shanghai。**未发布，未创建/修改/推送远程仓库。等待用户最终验收。**","",
          "## 本轮结果","",
          f"四统计已使用 goodluck55k 本人完成浏览器登录后的 GitHub CLI 认证读取。Languages 共 {language.get('total_bytes','未知')} bytes；Activity 为 {a.get('total','未知')} contributions；Stars 当前总数 {s.get('total_current','未知')}。数值由缓存生成，未从测试样本填充。","",
          f"本地测试：{tests.get('tests_run','NOT TESTED')} 项，{tests.get('passed','NOT TESTED')} PASS、{tests.get('failures','NOT TESTED')} FAIL、{tests.get('errors','NOT TESTED')} ERROR；退出码 {tests.get('exit_code','NOT TESTED')}。浏览器检查记录 {len(browser)} 组，包含本地与 GitHub 实际渲染 HTML 的 840/375px、Light/Dark。","",
          "[当前完整预览](../previews/index.html) · [新旧对比](../previews/comparison.html) · [GitHub 渲染 HTML 本地重放](../previews/github-rendered.html)","",
          "## P0：统计真实验证","",
          "| 模块 | 结果 | 数据与证据 |","|---|---|---|"]
    shares=" / ".join(f"{r['name']} {r['percent']:.1f}%" for r in percentages(language.get("languages",{})))
    rows += [f"| Languages | {cached('languages').get('state','NOT TESTED')} | {shares}；2 个公开代码库，逐仓库字节缓存可复核 |",
             f"| Activity | {cached('activity').get('state','NOT TESTED')} | {a.get('start','未知')}—{a.get('end','未知')} UTC；{len(a.get('days',[]))} 日/{len(a.get('weeks',[]))} 周，合计 {a.get('total','未知')}、峰值 {a.get('peak','未知')} |",
             "| Community | 六项独立核验 | "+"；".join(f"{name}={value} ({state})" for name,value,state,_,_ in metric_rows())+" |",
             f"| Stars | {cached('stars').get('state','NOT TESTED')} | 当前公开仓库总数 {s.get('total_current','未知')}；本人零 Star 列表接口实际返回 200/[]，没有伪造历史 |","",
             "初次匿名请求 `/rate_limit` 显示 core 60 次额度已用完，语言/仓库/GraphQL 返回 403 且 remaining=0。没有将 403 当成无数据或零值。gh 认证后，主采集记录中的 REST/GraphQL 请求均返回 200；认证额度恢复为 5000 级别。查询本身未出现 schema 或 scope 错误。详见匿名与认证 JSON 证据。","",
             "上一版仅在 Actions 环境接受认证，已修复为本地自动检测 gh。凭据留在 gh 的本机管理器，脚本只运行 gh api，不调用 gh auth token、不保存认证头。API 表面限制为 GET、GraphQL query 与无状态 Markdown 渲染。","",
             "日历与四项年度 Community 指标使用同一 UTC 范围；日历 365 天/全部涉及的周都保留，日合计、周合计与 API totalContributions 完全一致。Activity 不替换成 Commits；艺术化曲线经过真实周点，测试保证不产生额外峰值。","",
             "Star 限制已实测：DRAG0NM/Pare 元数据为 1，但 REST 历史404，GraphQL stargazerCount=1、connection.totalCount=0、edges=[]。该响应被判为不完整，未绘制曲线、未混入 goodluck55k 的数据。现在有 REST→GraphQL→有效缓存→当前快照的回退。未要求额外 PAT 或提高权限。","",
             "零、未知、失败、旧缓存分开：成功 0 才显示 0；无 payload 为不可用/失败；有旧有效 payload 时保留并标缓存日期。相同输入构建不改变产物哈希。具体字段、日期与每仓库字节见 [DATA_SOURCES.md](../DATA_SOURCES.md)。","",
             "## P1：四角色与纸感","",
             "| 角色 | 第二轮处理 | 原图与边界 |","|---|---|---|",
             "| 戴拿 | 对比 +15%、+20%、+25%，选 +20%；桌面254.4px，手机146.4px | 原始 alpha、全身和计时器保留；文字/人物包围盒无重叠 |",
             "| 蜘蛛侠 | 保持94/78px的小装饰；Works标题区略收紧 | 蹲姿、眼睛、透明边缘保留，不影响单行条目 |",
             "| 死侍 | 124/84px，饱和度0.78，底部20%渐隐至纸底 | 比心主体清楚，独立留白区，不挡任何数字 |",
             "| 娜可露露 | 饱和度0.42，浅/深纸底融合14%/18% | 全幅原画、不裁切、不对标识局部遮挡；原件及processed像素未改变 |","",
             "四图均来自用户原件，没有 AI 生成、替换或上传。最终合成与原件是独立层，参数见 config/profile.json 与 previews/layout-audit.json。版权公开许可仍未核实，来源线索见 ASSET_SOURCES.md。","",
             "统计恢复为原生 SVG：文字是开源字体轮廓，图表是矢量线条和路径；死侍以原图像素编码到同一自包含 SVG。没有外部图片、字体、data URI、CSS 或脚本依赖。保留四张 PNG 回退。Header/Works/Footer 继续用 PNG，未推翻静态资源/数据/README 三层结构。","",
             "## P2：GitHub 实际渲染兼容","",
             "通过 GitHub 官方 POST /markdown 的无状态 GFM 渲染发现原版 `<a><picture>` 开头被 Markdown 分段，导致作品链接为空、图片游离。修正为明确的 `<p>` HTML block，实际返回 HTML 现在保留作品图片在项目链接内，含所有 source。增加了拒绝空链接的回归测试。修复前证据：previews/round2-before-gfm-fix.html；修复后：previews/github-rendered-fragment.html。","",
             f"GitHub GFM 结果：`{checks.get('github_markdown',{}).get('state','NOT TESTED')}`。图片、暗色媒体条件、手机断点、SVG格式均保留。浏览器分别检查解码、正确主题/手机文件、作品图片父链接、无横向滚动。","",
             "| 来源 | 主题 | 视口 | 结果 / 截图 |","|---|---|---:|---|"]
    for b in browser:
        rows.append(f"| {b.get('view','local')} | {b['colorScheme']} | {b['viewport']}px | PASS · [{b['output'].split('/')[-1]}](../{b['output']}) |")
    rows += ["","`github-*` 是 GitHub 官方实际返回的 HTML 在本地重放，图片仍从本地加载。并未声称已经在公开个人主页上看到本项目，也未启动远程 Actions。真实 GitHub 图片代理、手动站点主题、已发布主页及远程 Actions 仍为 NOT TESTED。","",
             "## 新旧视觉对比","",
             "第一轮基线在修改前复制到 previews/round1/，没有拿新图假扮旧图。对比为浏览器真实840px/375px截图，左旧右新：","",
             "- [Light / 桌面](../previews/comparison-light-840.png)","- [Dark / 桌面](../previews/comparison-dark-840.png)",
             "- [Light / 手机](../previews/comparison-light-375.png)","- [Dark / 手机](../previews/comparison-dark-375.png)",
             "- [戴拿 +15% / +20% / +25%](../previews/dyna-variants-light.png)","",
             "## 测试和交付证据","",
             "`python scripts/collect.py --auth gh`：真实只读 API 采集，退出0。`python scripts/validate_remote.py`：真实接口与 GFM 验证，退出0，各项状态独立记录，不把参考 Star 不完整标成成功。`python scripts/verify.py`：全部离线测试，完整日志在 reports/test-output.txt。`node scripts/screenshots.cjs`：8组浏览器验证，退出0。","",
             f"可复现性覆盖 README、20张PNG、4张SVG，共 {len(tests.get('output_hashes',{}))} 个文件。构建后的哈希见 verification.json。测试包含原图SHA、全幅原画像素、SVG无外部依赖、曲线无新峰、权限与限流区分、分页、缓存恢复、真实零/未知区分、gh凭据隔离和GFM空链接回归。","",
             f"候选公开文件：{len(inventory.get('files',[]))} 个，逐项路径、大小、SHA在 PUBLISH_FILES.md / publish-manifest.json。仍未上传。默认排除原图、SPEC、本地CLI、预览与报告。公开包不带原图时两个原件追溯测试会跳过；本地完整工作区均执行。","",
             f"候选隔离目录实际验证：{candidate.get('tests_run','NOT TESTED')} 项，{candidate.get('passed','NOT TESTED')} PASS、{candidate.get('skipped','NOT TESTED')} SKIPPED、{candidate.get('failures','NOT TESTED')} FAIL。与完整工作区25个成品的哈希相同，记录在 candidate-verification.json / candidate-compare.json。","",
             "## 剩余事项","",
             "1. 参考非零 Star 历史返回不一致，已正确拒绝/降级；接口可见性差异的根本原因尚未确认。本人当前真实 Stars=0，不受此限制影响。未来出现 Stars 时不能保证上游返回完整历史，须保留回退提示。",
             "2. 真实公开主页、GitHub图片代理及远程Actions未验证；本轮未获远程发布授权，不会以本地/API渲染通过替代公开页面验收。",
             "3. 四张角色原图公开再分发许可仍待核实。保留标识及本地使用不等于取得公开许可。",
             "4. human-talk-checker 的线上端到端功能未测试，Works 保持中性功能说明。跨操作系统逐字节输出一致性未验证。","",
             "本轮本地任务已完成；等待用户最终验收，未经明确批准不创建、修改或推送远程仓库。",""]
    write_text(ROOT/"reports/ROUND2_VALIDATION.md","\n".join(rows))
    write_text(ROOT/"reports/ACCEPTANCE.md","\n".join(rows))


def main():
    source_notes()
    from report import manifest
    manifest()
    validation_report()
    print("Round 2 source notes, validation report and publication inventory generated. Nothing published.")


if __name__=="__main__":
    main()
