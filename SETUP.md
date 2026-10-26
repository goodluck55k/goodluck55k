# 本地构建与后续维护

本项目是 `goodluck55k/goodluck55k` 的 GitHub Profile README，使用 Python 3.11、Pillow、numpy 与 fontTools。四统计输出原生 SVG，文字转换为开源字体轮廓；同时保留 2x PNG 回退。Header、Works、Footer 使用 2x PNG。`previews/index.html` 仅用于本地检查。用户已明确要求使用当前图片发布；图片许可仍未核验，不将用户的发布指令描述为权利方授权。

当前字体采用 B 方案：宣言与 Works / Languages / Activity / Community / Stars 使用 Caveat Medium 500，其余内容保留 Libre Baskerville / Noto Serif SC。字体原文件与 OFL 许可已随项目保存，正常离线构建不访问字体网络服务。PNG 与 SVG 均固定使用同一 500 字重，SVG 输出字形路径。

## Windows 首次运行

在本项目目录打开 PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/build.py
.\.venv\Scripts\python.exe scripts/preview.py
Start-Process .\previews\index.html
```

源码、处理后的图片、字体及许可、公共缓存均随公开仓库提供，原始素材只在作者本地保留。正常离线重建校验处理图缓存，不必下载字体或联网。`scripts/bootstrap_fonts.py` 只在字体丢失时从 Google Fonts 官方仓库恢复开源字体，校验记录在 `assets/fonts/manifest.json`。重新处理人物时需要对应原件，不能以处理图覆盖原件。

可使用已有 Python：`py -3.11 scripts/build.py`。Linux 对应命令为 `python3.11 -m pip install -r requirements.txt` 与 `python3.11 scripts/build.py`。

## 修改内容

唯一文案入口为 `config/profile.json`：用户名、身份标签、指定宣言、Works、主题、断点和原图映射均从这里读取。保留冻结规格指定的身份与宣言。Works 支持 1–5 条，每条为 `name`、`description`、`url`。新增作品前核实仓库实际存在与描述，简介过长导致单行放不下时，构建会明确报错。

```powershell
py -3.11 scripts/build.py
py -3.11 scripts/preview.py
py -3.11 -m unittest discover -s tests -v
```

删除作品后，多余的 `assets/static/work-N-*.png` 会在受控生成目录内清理，README 链接自动同步。四项统计输出在连续纸面 `assets/stats/stats-{light,dark}[-mobile].svg`，并有同名 PNG 回退。SVG 文字与图表是矢量路径；角色由原图像素编码，无外部字体、图片、CSS、脚本或 data URI 依赖。Header、Works、Footer 与数据分离。原图处理有 SHA-256 和算法版本缓存，每日统计更新不会重复抠图。

## 刷新公开统计

```powershell
py -3.11 scripts/collect.py
py -3.11 scripts/build.py
```

第二轮已由用户本人完成 GitHub CLI 浏览器登录，并通过真实 GraphQL/REST 请求验证。`collect.py` 默认 `--auth auto`：本地优先使用已登录的 `gh`，Actions 继续使用 GitHub 自动提供的 Token。整个过程不执行 `gh auth token`，不提取、打印或复制 Token。使用匿名 REST 时仍可能限流；认证失败或无数据时显示明确状态。

当前工作区安装了官方校验过的 gh 便携版 `.tools/gh/bin/gh.exe`。换电脑后可从 [GitHub CLI 官方发布页](https://github.com/cli/cli/releases) 安装。登录必须由本人在浏览器完成：

```powershell
& .\.tools\gh\bin\gh.exe auth login --hostname github.com --git-protocol https --web
py -3.11 scripts/collect.py --auth gh
py -3.11 scripts/build.py
```

若 GitHub CLI 已安装到 PATH，可直接使用 `gh auth login --web`。不需要额外创建 PAT/Secret。只读传输层仅支持 GET、GraphQL query 与无状态的 Markdown 渲染，不能发起仓库写操作。CLI 凭据由其本机凭据管理器保管，不包含在项目交付或公开候选清单中。

Activity、Commits、Reviews、Discussions、Answers 当前已取得真实 GraphQL 数据。后续没有认证或请求失败时仍保留模块并显示“暂不可用”或旧缓存。公开 PRs 与 Issues 可由 REST 搜索回退。Stars 优先取得 REST 时间戳；必要时尝试 GraphQL；若时间戳总数与仓库快照不一致则拒绝假历史，保留真实旧缓存或数量快照。详情及逐项口径见 [DATA_SOURCES.md](DATA_SOURCES.md)。

有效缓存文件 `assets/data/*.json` 内含来源、范围、最后有效数据时间、状态与公开 payload。失败不会把旧数字覆盖成 0；缓存状态会标为 `stale` 并显示缓存日期。没有有效缓存时区分 `failed` 与 `unavailable`。不得手工填入推测的数字。

同一输入在同一构建环境中会输出相同文件哈希；JSON 成功采集但内容未变化时保留原时间戳。数据窗口推进、真实数据变化、从失败恢复或状态变更可能合理产生变化。跨操作系统字节一致性尚未验证。

## 本地截图

交付包含 `previews/light-840.png`、`dark-840.png`、`light-375.png`、`dark-375.png`，以及 `github-` 前缀的四张 GitHub 官方渲染 HTML 本地重放截图。当前中等手写风的明暗与前后对比入口为 `previews/handwriting-comparison.html`，说明见 `reports/HANDWRITING_B.md`。角色精修、透明 Footer 替换、第一/二轮的历史对比仍分别保留在 `previews/final-preview.html`、`previews/footer-comparison.html`、`previews/comparison.html`。使用本机 Chrome，手机截图实际视口为 375 CSS px，截图页面禁止远程网络请求。

若要重新生成截图，安装可选开发工具（不属于远程构建依赖）：

```powershell
npm install --prefix .tools --no-audit --no-fund playwright
py -3.11 scripts/preview.py
node scripts/screenshots.cjs
```

截图脚本当前配置了 Windows 的 Chrome 默认路径，其他系统请修改 `scripts/screenshots.cjs` 中的 `executablePath`。浏览器检查记录在 `previews/browser-audit.json`。它验证实际资源选择、SVG 解码、作品图片链接与无横向溢出。GitHub `/markdown` 的真实 GFM 渲染已经验证，但还未发布到实际个人主页，不能宣称已验证真实发布页面或 Actions。

完整只读联调与报告命令：

```powershell
py -3.11 scripts/validate_remote.py
py -3.11 scripts/verify.py
node scripts/screenshots.cjs
py -3.11 scripts/compare_visuals.py
py -3.11 scripts/report.py
```

`validate_remote.py` 通过 gh 读取 API 并调用无状态 Markdown 渲染，不会创建、提交或推送仓库。该脚本只在本地验收时使用，不在每日更新中重复进行参考仓库诊断。

## GitHub Actions 预备配置

工作流位于 `.github/workflows/profile.yml`，实际执行状态请查看目标仓库的 Actions 页面，不以本地测试代替远程运行结果。

- 每天 `03:17 UTC`，即中国标准时间 `11:17`；也支持 Actions 页的 **Run workflow** 手动触发。
- 脚本、配置、测试、处理图、字体或工作流变化触发更新；生成的图片、数据与 README 不作为 push 触发路径，避免递归。
- 顶层 `contents: read`，仅更新 job 使用 `contents: write`，用于提交当前主页仓库内产生的变化。只使用 GitHub 自动提供的 `github.token`，不创建 Secrets。
- 先离线构建并执行测试，再采集公开数据，随后重建。只暂存 README、静态成品、统计成品与公共缓存；`git diff --cached --quiet` 无差异时不提交。
- 若公开包不包含原图，两个原件追溯检查会明确跳过；处理图完整性与其他逻辑测试仍执行。本地交付保留原图，已完成这两个检查。
- 调度并不保证准点。公开仓库连续 60 天没有活动可能停用 schedule；获得发布批准后，可到 Actions 对应工作流选择 Enable workflow，再手动 Run workflow。参考 [GitHub schedule 官方说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。
- 分支保护或账号政策可能阻止机器人 push；必须在真实授权发布后验证，不能将本地检查视为远程成功。

## 发布前的单独关卡

用户已知悉四张角色图尚无可核验公开再分发许可，并明确授权将当前最终版本发布到公开仓库 `goodluck55k/goodluck55k`。本次不更换角色、不重新生成图像、不修改其他仓库，也不虚构授权或原创归属。人物素材的权利状态与源码许可证范围见 [ASSET_SOURCES.md](ASSET_SOURCES.md) 和 [LICENSE](LICENSE)。

发布候选的逐文件清单与哈希见 `reports/publish-manifest.json`，可读清单见 `reports/PUBLISH_FILES.md`。原始规格副本 `SPEC.md` 包含本地路径，原图 `assets/source/` 权利未核实，预览、测试日志、本地依赖与报告默认不放入公开包。处理图与最终成品仍包含角色版权，排除原图并不能消除权利问题。

首次使用 OAuth 凭据上传 `.github/workflows/profile.yml` 需要 `workflow` scope。如 GitHub 提示缺少权限，由本人执行 `gh auth refresh --hostname github.com --scopes workflow` 并在浏览器授权，不绕过平台限制。发布采用明确文件清单，排除 Token、CLI 凭据、`.env`、本地工具与缓存；本地报告和原始素材不随公开包分发。
