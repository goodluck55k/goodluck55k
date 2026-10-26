# 数据来源与查询验证（第二轮）

只读采集 GitHub 公开数据；凭据由本机 GitHub CLI 保管，没有提取、打印或提交 Token。所有数量来自 API 缓存；测试样本未写入主页数据。

## Languages

状态：`ok`；有效数据时间：`2026-10-26T01:28:50+00:00`。

REST `/users/goodluck55k/repos?type=owner` 分页列出公开自有仓库；逐仓库 `/repos/{owner}/{repo}/languages` 取得真实字节。排除 Fork、主页仓库 goodluck55k、空资源仓库 goodluck。human-rate-web 虽未列为 Works，仍计入代码语言。

| 语言 | bytes | 占比 |
|---|---:|---:|
| JavaScript | 57827 | 68.8% |
| CSS | 16543 | 19.7% |
| HTML | 9626 | 11.5% |

总字节：83996。最多六行；超过六种时为前五种+Other；所有字节为分母，最大余数法保留一位小数。任何仓库请求失败时不发布不完整比例，保留整份有效缓存。

## Activity

状态：`ok`；有效数据时间：`2026-10-26T01:28:50+00:00`。

GraphQL `User.contributionsCollection(from:...,to:...).contributionCalendar`。指标为 contributions，不是纯 Git commits。

窗口 `2025-10-27 / 2026-10-26`（UTC），365 天、53 周、总贡献 11、周峰值 4。保留首尾不完整周。逐日与逐周合计均校验 API 总数。

| 非零贡献日 | contributions |
|---|---:|
| 2025-11-24 | 2 |
| 2026-04-22 | 2 |
| 2026-05-09 | 4 |
| 2026-05-10 | 3 |

曲线使用真实每周计数和日期坐标。单调三次插值经过原始点，不制造新峰值；坐标、峰值、总数均取自缓存。缺日、重复日、负值或合计不一致时拒绝生成新数据。

## Community

| 指标 | 实际值 | 状态 | 时间窗口 | GitHub 字段 |
|---|---:|---|---|---|
| Commits | 7 | ok | 2025-10-27 / 2026-10-26 | `ContributionsCollection.totalCommitContributions` |
| PRs | 0 | ok | 2025-10-27 / 2026-10-26 | `ContributionsCollection.totalPullRequestContributions` |
| Issues | 0 | ok | 2025-10-27 / 2026-10-26 | `ContributionsCollection.totalIssueContributions` |
| Reviews | 0 | ok | 2025-10-27 / 2026-10-26 | `ContributionsCollection.totalPullRequestReviewContributions` |
| Discussions | 0 | ok | all history · 公开可见 | `User.repositoryDiscussions` |
| Answers | 0 | ok | all history · 公开可见 | `User.repositoryDiscussionComments(onlyAnswers:true)` |

前四项使用相同 365 日窗口；Discussions / Answers 为全部历史，逐项注明，不混称年度总数。Answers 是被标记为答案的讨论回复，使用 `onlyAnswers:true`。讨论连接按 cursor 分页，只保留公开节点的数量，不缓存正文、用户列表或私有仓库名。

## Stars

状态：`ok`；有效数据时间：`2026-10-26T01:45:04+00:00`。

当前数量来自公开自有非 Fork 仓库 `stargazers_count`，Top 6 用于历史系列。非零历史使用 REST `Accept: application/vnd.github.star+json`，失败后尝试 GraphQL `repository.stargazers.edges.starredAt`。两者均分页，数量须与仓库快照一致。

| 仓库 | 当前 Stars | 历史状态 | 来源 |
|---|---:|---|---|
| goodluck55k/goodluck | 0 | ok | `/repos/goodluck55k/goodluck · stargazers_count (zero snapshot)` |
| goodluck55k/human-rate-web | 0 | ok | `/repos/goodluck55k/human-rate-web · stargazers_count (zero snapshot)` |
| goodluck55k/human-talk-checker | 0 | ok | `/repos/goodluck55k/human-talk-checker · stargazers_count (zero snapshot)` |

当前总 Stars=0。真实 0 不等于历史获取失败；为零时不伪造历史曲线。时间戳只代表目前仍存在的 Stars，不代表已取消 Star 的全部历史。

## 失败与缓存

`ok` 为成功数据；`stale` 为失败后保留的有效旧 payload，并显示缓存日期；`unavailable` 为未取得数据；`failed` 为请求错误且没有有效缓存。只有接口成功返回零时显示 0。文件通过临时文件替换写入；相同 payload 保留原 fetched_at，避免无意义提交。每个 Community 指标独立缓存。

REST Star 历史或 GraphQL 返回不完整时，优先真实旧历史，随后退化为当前快照并标注历史不可用。参考仓库本轮实际出现 metadata=1，但 REST 历史404、GraphQL connection返回0条的情况，程序正确拒绝该历史，未写入本账户缓存。HTTP本身不足以断定是权限策略还是上游数据可见性问题。

本地优先通过 gh credential store 认证；Actions 使用自动提供的 GITHUB_TOKEN。GraphQL query 不请求私有仓库名称/正文；若贡献按仓库分组出现私有项或受限贡献，则不把这些数据混入公开日历。分组超过可审计范围同样拒绝。

## 可复核证据与官方资料

本次匿名 403/配额信息：`reports/round2-api-probes.json`。认证请求 HTTP/限流头：`reports/round2-authenticated-api.json`。真实联调、Star 差异与 GitHub GFM 渲染：`reports/round2-real-validation.json`。原始公共缓存在 `assets/data/`。报告文件默认不公开。

- [GitHub Contribution Calendar / Collection 与 User 字段](https://docs.github.com/en/graphql/reference/users)
- [GitHub GraphQL 认证与 query 规则](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql)
- [GitHub Stargazers API](https://docs.github.com/en/rest/activity/starring#list-stargazers)
- [GitHub Markdown 无状态渲染 API](https://docs.github.com/en/rest/markdown/markdown)
- [GitHub CLI 浏览器登录](https://cli.github.com/manual/gh_auth_login)
