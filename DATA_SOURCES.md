# 数据来源与查询验证（第二轮）

只读采集 GitHub 公开数据；凭据由本机 GitHub CLI 保管，没有提取、打印或提交 Token。所有数量来自 API 缓存；测试样本未写入主页数据。

## Works

状态：`ok`；有效数据时间：`2026-11-10T10:45:11+00:00`。

作品区不再维护固定名单。`collect.py` 从 REST `/users/goodluck55k/repos?type=owner` 自动发现公开自有仓库，规则为：排除 Profile README 仓库（仓库名等于用户名）、Fork、已归档、空仓库（`size` 为 0）、纯资源仓库（`/repos/{owner}/{repo}/languages` 返回空映射，即无检测到的代码语言），以及携带通用 Topic `profile-hide` 的仓库。其余仓库按 `pushed_at` 降序取前 5 个。名称使用真实仓库名；简介优先使用 GitHub Repository Description，缺失时以仓库名本身作中性展示，不编造文案；链接使用仓库 `html_url`。过长简介在渲染时单行截断并加省略号，README 的 alt 文本保留完整官方简介。

当前自动发现结果（按 `pushed_at` 降序）：ShiXu、NailongQuanxue、human-talk-checker、human-rate-web（无简介，中性展示）。新建符合条件的公开仓库会在下一次成功采集与构建后自动进入展示；采集失败时保留 `assets/data/works.json` 的上次成功缓存，不清空作品区。

## Languages

状态：`ok`；有效数据时间：`2026-11-10T10:45:11+00:00`。

REST `/users/goodluck55k/repos?type=owner` 分页列出公开自有仓库；逐仓库 `/repos/{owner}/{repo}/languages` 取得真实字节。排除 Fork、主页仓库 goodluck55k、空资源仓库 goodluck。

| 语言 | bytes | 占比 |
|---|---:|---:|
| Python | 378488 | 63.3% |
| TypeScript | 120400 | 20.1% |
| JavaScript | 58208 | 9.7% |
| CSS | 16543 | 2.8% |
| PowerShell | 10124 | 1.7% |
| Other | 14069 | 2.4% |

总字节：597832。最多六行；超过六种时为前五种+Other；所有字节为分母，最大余数法保留一位小数。任何仓库请求失败时不发布不完整比例，保留整份有效缓存。

## Activity

状态：`ok`；有效数据时间：`2026-11-10T11:00:38+00:00`（Actions 内 GITHUB_TOKEN 采集）。

GraphQL `User.contributionsCollection(from:...,to:...).contributionCalendar`。指标为 contributions，不是纯 Git commits。

窗口 `2025-11-11 / 2026-11-10`（UTC），365 天、53 周、总贡献 248、周峰值 141。保留首尾不完整周。逐日与逐周合计均校验 API 总数。

该账号存在私有仓库活动，`restrictedContributionsCount` 为 167。日历与 GitHub 公开个人主页向匿名访客展示的日历完全一致（同日窗口下同为 248）：只含逐日计数，不含私有仓库名、提交或任何私有细节；其中包含用户通过 “Private contributions” 设置主动公开的匿名私有贡献计数。缓存以 `includes_anonymized_private` 标记该口径，图内注释为“每周贡献总量 · 含用户公开的匿名私有计数”，不与纯公开 Commits 口径混称。若某日窗口内 `restrictedContributionsCount` 为 0，则日历总数必须等于公开贡献分解之和，否则拒绝生成。

| 非零贡献日 | contributions |
|---|---:|
| 2025-11-24 | 2 |
| 2026-04-22 | 2 |
| 2026-05-09 | 4 |
| 2026-05-10 | 3 |
| 2026-10-26 | 3 |
| 2026-10-27 | 2 |
| 2026-10-29 | 1 |
| 2026-10-30 | 15 |
| 2026-10-31 | 29 |
| 2026-11-01 | 6 |
| 2026-11-02 | 21 |
| 2026-11-03 | 2 |
| 2026-11-04 | 20 |
| 2026-11-05 | 7 |
| 2026-11-06 | 45 |
| 2026-11-07 | 40 |
| 2026-11-08 | 22 |
| 2026-11-09 | 14 |
| 2026-11-10 | 10 |

曲线使用真实每周计数和日期坐标。单调三次插值经过原始点，不制造新峰值；坐标、峰值、总数均取自缓存。缺日、重复日、负值或合计不一致时拒绝生成新数据。

## Community

| 指标 | 实际值 | 状态 | 时间窗口 | GitHub 字段 |
|---|---:|---|---|---|
| Commits | 58 | ok | 2025-11-11 / 2026-11-10 | `ContributionsCollection.totalCommitContributions` |
| PRs | 16 | ok | 2025-11-11 / 2026-11-10 | `ContributionsCollection.totalPullRequestContributions` |
| Issues | 0 | ok | 2025-11-11 / 2026-11-10 | `ContributionsCollection.totalIssueContributions` |
| Reviews | 0 | ok | 2025-11-11 / 2026-11-10 | `ContributionsCollection.totalPullRequestReviewContributions` |
| Discussions | 0 | ok | all history · 公开可见 | `User.repositoryDiscussions` |
| Answers | 0 | ok | all history · 公开可见 | `User.repositoryDiscussionComments(onlyAnswers:true)` |

前四项使用相同 365 日窗口，且只统计公开仓库贡献：每个 `total*` 字段必须与对应 `*ContributionsByRepository` 分解中公开仓库（`isPrivate:false`）的 `contributions.totalCount` 之和一致，否则拒绝发布（`CONTRIBUTION_TOTAL_MISMATCH`）。该口径不含私有贡献，与 Activity 日历的匿名私有计数口径明确区分。Discussions / Answers 为全部历史，逐项注明，不混称年度总数。Answers 是被标记为答案的讨论回复，使用 `onlyAnswers:true`。讨论连接按 cursor 分页，只保留公开节点的数量，不缓存正文、用户列表或私有仓库名。

## Stars

状态：`ok`；有效数据时间：`2026-11-10T11:00:38+00:00`。

当前数量来自公开自有非 Fork 仓库 `stargazers_count`，Top 6 用于历史系列。非零历史使用 REST `Accept: application/vnd.github.star+json`，失败后尝试 GraphQL `repository.stargazers.edges.starredAt`。两者均分页，数量须与仓库快照一致。

| 仓库 | 当前 Stars | 历史状态 | 来源 |
|---|---:|---|---|
| goodluck55k/NailongQuanxue | 1 | ok | `/repos/goodluck55k/NailongQuanxue/stargazers (star+json)` |
| goodluck55k/ShiXu | 0 | ok | `/repos/goodluck55k/ShiXu · stargazers_count (zero snapshot)` |
| goodluck55k/goodluck | 0 | ok | `/repos/goodluck55k/goodluck · stargazers_count (zero snapshot)` |
| goodluck55k/goodluck55k | 0 | ok | `/repos/goodluck55k/goodluck55k · stargazers_count (zero snapshot)` |
| goodluck55k/human-rate-web | 0 | ok | `/repos/goodluck55k/human-rate-web · stargazers_count (zero snapshot)` |
| goodluck55k/human-talk-checker | 0 | ok | `/repos/goodluck55k/human-talk-checker · stargazers_count (zero snapshot)` |

当前总 Stars=1。真实 0 不等于历史获取失败；为零时不伪造历史曲线。时间戳只代表目前仍存在的 Stars，不代表已取消 Star 的全部历史。

## 失败与缓存

`ok` 为成功数据；`stale` 为失败后保留的有效旧 payload，并显示缓存日期；`unavailable` 为未取得数据；`failed` 为请求错误且没有有效缓存。只有接口成功返回零时显示 0。文件通过临时文件替换写入；相同 payload 保留原 fetched_at，避免无意义提交。每个 Community 指标独立缓存。`collect.py` 结束时逐项打印 `Metric status summary`，列出每个缓存的 ok / stale / failed / unavailable 状态、最后有效时间与失败原因，供 Actions 日志核对。

REST Star 历史或 GraphQL 返回不完整时，优先真实旧历史，随后退化为当前快照并标注历史不可用。参考仓库本轮实际出现 metadata=1，但 REST 历史404、GraphQL connection返回0条的情况，程序正确拒绝该历史，未写入本账户缓存。HTTP本身不足以断定是权限策略还是上游数据可见性问题。

本地优先通过 gh credential store 认证；Actions 使用自动提供的 GITHUB_TOKEN。GraphQL query 不请求私有仓库名称/正文。`restrictedContributionsCount` 大于 0 不再使整份贡献集合失效：该计数只要账号存在私有活动就长期非零（本账号自 2026-10-30 起为 167），旧保护逻辑因此把 Activity、Commits、Reviews 永久冻结在旧缓存。现在公开四项总数逐项与按仓库分解的公开部分校验一致后才发布；分解中出现私有项（`PRIVATE_CONTRIBUTIONS_EXCLUDED`）或分组达到 100 上限（`PUBLIC_CONTRIBUTION_SCOPE_LIMIT`）仍整体拒绝。日历只取逐日计数，与公开主页匿名视图一致，并在含匿名私有计数时明确标注口径；日历总数小于公开贡献之和、或无受限计数时与公开之和不一致，均拒绝（`CALENDAR_PUBLIC_TOTAL_MISMATCH`）。

## 可复核证据与官方资料

本次匿名 403/配额信息：`reports/round2-api-probes.json`。认证请求 HTTP/限流头：`reports/round2-authenticated-api.json`。真实联调、Star 差异与 GitHub GFM 渲染：`reports/round2-real-validation.json`。原始公共缓存在 `assets/data/`。报告文件默认不公开。

- [GitHub Contribution Calendar / Collection 与 User 字段](https://docs.github.com/en/graphql/reference/users)
- [GitHub GraphQL 认证与 query 规则](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql)
- [GitHub Stargazers API](https://docs.github.com/en/rest/activity/starring#list-stargazers)
- [GitHub Markdown 无状态渲染 API](https://docs.github.com/en/rest/markdown/markdown)
- [GitHub CLI 浏览器登录](https://cli.github.com/manual/gh_auth_login)
