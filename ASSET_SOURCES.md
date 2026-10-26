# 素材、字体与参考来源

核对日期：2026-10-26（Asia/Shanghai）。**四张角色图的公开再分发许可尚未核验。用户已知悉该状态并明确要求使用现有图片发布；这项操作授权不代表权利方许可。人物素材不属于本项目原创，项目源码许可证不授予这些图片的使用权。**

最初四个素材包文件与用户直接附加的四张图逐一 SHA-256 相同；此前按用户要求，将 Footer 改用新提供的透明背景娜可露露立绘。原件在本地 `assets/source/` 保留，公开仓库使用其处理图及合成 PNG/SVG。原件没有修改，也未使用 AI 重绘。

| 角色 | 原文件与尺寸 | SHA-256 | 处理与署名 |
|---|---|---|---|
| 戴拿 | `戴拿立绘.png`，393×937 RGBA | `4ef48cea7b961a8f8ef68e35a37eae3a383e81e04bb5ae8d1e8c39a3d20a0b72` | 保留原始 alpha，按透明边界裁切，等比缩放；保留头部、计时器、动作与全身 |
| 死侍 | `515b63ef22a00c15eae21c26571b5lc5.jpg`，1280×720 RGB | `1b343a28d0c6238d54ee8dc5dfc375fbfcd88591c319d0b55b3bfcd27b9c8f8e` | 仅移除与画布边界连通的近白背景，保留被主体包围的白色眼睛；保留比心姿势 |
| 蜘蛛侠 | `f5b29402f2d6e5e5 (1).webp`，800×608 RGB | `60c692887e4c93055b75a2e63aa310497af4d8f4a4adaa58fb3a5d6d017420eb` | 原棋盘格为像素；边界连通中性色键遮罩去除，闭合眼睛不被误删，保留蹲姿 |
| 娜可露露（当前 Footer） | `e927eadd35d3aabe9d8557363e436d52f035747e2b317-XnGlS7_fw658.webp`，658×494 RGBA | `15751e756538c3b281c5007d8b980966ff7ad5884cfd47c7845892f01529a5ff` | 使用用户指定的新图；仅去除左侧 205px 透明留白，得到 453×494；可见图像与原 alpha 逐像素保留，无重绘 |

处理参数、裁切边界、源文件哈希、输出尺寸见 `assets/processed/manifest.json`；两张抠图的全尺寸遮罩单独保留。Spider 最低中性亮度 182、通道差≤40；Deadpool 最低亮度 220、通道差≤28；边缘向内约 1px，羽化 sigma 0.35px，导出时 Lanczos 缩放。无需网络模型或 AI 重绘。

第二轮曾选择戴拿放大 20%；最终精修在此基础上缩小 6%，桌面/手机版设计画布高度为 239.136/137.616px，向左下微调。蜘蛛侠为 90/74px，向左和下方略靠近 Works 标题。死侍在上一版基础上缩小 5% 至 117.8/79.8px，仍位于 Community 右侧；饱和度 0.78，纸色融合 4%，最底部 24% 渐隐，比心动作清晰。人物均在画布内，不遮挡文案或数字。

娜可露露保持靠右的透明立绘，左侧版权与维护文字共用原页面左边距。最终精修较替换素材时缩小 10%，人物桌面/手机版设计画布高度为 158.4/113.4px，向左 8/6px、向上 4px；Footer 画布仍为 224/174px（840/420px 设计宽度），增加人物右侧和底部留白。合成饱和度 0.72，浅色/深色纸底融合 6%/10%，最底部 8% 轻微渐隐；这些展示处理不修改原件或 processed 像素。新图本身已有的边界保持原样，没有补画手臂、头发或身体。所有最终合成参数与边界见 `previews/layout-audit.json`，当前完整明暗预览见 `previews/final-preview.html`；更早的素材替换对比保留在 `previews/footer-comparison.html`。

旧全幅图 `chao-liu-n-snk.jpg`（SHA-256：`37de2362dfa24a7e5ed16aa47efe5fb2ae9ae27df8d148999ac01210c936ac2e`）仅作为本地历史原件保留，已退出当前配置与 Footer。替换前截图保存在 `previews/footer-before/`。

本地前后对照见 `previews/asset-comparison.png`，深色底边缘检查见 `previews/spiderman-dark-check.png` 与 `previews/deadpool-dark-check.png`。

## 权利状态

戴拿、死侍、蜘蛛侠的精确来源网址与再分发许可文件未交接。规格提及 pngsucai、萌娘百科、Bahamut GNN，但未给出可逐图绑定的完整链接；本报告不猜测具体 URL，也不将网站提供下载等同于权利授权。

旧娜可露露全幅图的来源线索是 [Cosmo Liu ArtStation 作品页](https://cosmoliu.artstation.com/projects/o2EeRO)，与此次透明立绘不同。新图由用户直接提供，未提供可绑定的作者或许可网址，不沿用旧图的作者归属。两份原件均原样保留于本地。

没有将个人非商业用途、保留署名或用户提供图片描述为已取得权利方许可。源码的 MIT 许可不覆盖角色图、处理图及包含角色的 PNG/SVG；相关权利仍归原权利人。本次没有替换、删除或重新生成任何角色。

此前的许可核查报告与原件只保存在本地交付目录，不随公开仓库分发。不对当前四图虚构来源作者或许可证。

## 开源字体

使用独立选择的 Libre Baskerville（主标题、英文正文和数据）、Noto Serif SC（中文），以及 B 方案新增的 Caveat Medium 500（宣言与五个英文模块标题）。字体文件原样来自 [Google Fonts 官方仓库](https://github.com/google/fonts)，采用 **SIL Open Font License 1.1**。许可位于 `assets/fonts/LibreBaskerville-OFL.txt`、`NotoSerifSC-OFL.txt` 和 `Caveat-OFL.txt`；逐文件来源与 SHA-256 见 `assets/fonts/manifest.json`。原 Libre Baskerville 斜体文件保留，便于历史版本复现。

静态模块的字体在本地光栅化到 2x PNG；统计 SVG 使用这些字体的真实字形轮廓，GitHub 展示不依赖系统字体、远程字体或 SVG 内嵌字体。Caveat 保留官方原始可变 TTF，PNG 与 SVG 在构建时均固定为 500 字重，SVG 写入静态字形路径；不向浏览器发送可变字体。正文、数字、项目、Footer 和中文标题继续使用原有易读字体。没有复制参考仓库内的 STIX 字体文件。

手写风的字体对比、离线构建验证与具体使用范围见 `reports/HANDWRITING_B.md` 和 `previews/handwriting-comparison.html`。

## 参考实现

已读取 [DRAG0NM/DRAG0NM](https://github.com/DRAG0NM/DRAG0NM) 当前的 README、SETUP、完整生成脚本、montage_path 头部和更新工作流。

| 文件 | 审计时 blob SHA |
|---|---|
| README.md | `387f8d1c82742f3ff91461f5c044f090c45ea51a` |
| SETUP.md | `4bf292dbffd4892d214e614d823e95360221dbf3` |
| scripts/generate.py | `2c722b9e1831c78411ebabfa7cdac06b1d5169fb` |
| scripts/montage_path.py | `838f09008457b878d59b81f0ccdd081942de1dc1` |
| .github/workflows/profile.yml | `66fa42917fb48771b047ae7fd59d2b61e4fb1b8e` |

借鉴了纸面排版、picture 明暗切换、独立作品链接、连续统计、数据缓存与有变化才提交。实现、排版与遮罩重新编写，没有复制原作者姓名、签名、作品、统计值或装饰文字路径。参考实现混用了年度贡献与全部历史社区指标，本项目逐项标注范围；也没有复制其高权限 classic PAT 建议。
