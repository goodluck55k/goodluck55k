"""Read-only public GitHub statistics, pagination, independent last-good caches.

No PAT is required. A repository-scoped Actions GITHUB_TOKEN enables GraphQL.
Failures remain distinct from zero. Never store request headers or user objects.
"""
import argparse
from collections import defaultdict
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from common import ROOT, config, read_json, write_json

UTC = dt.timezone.utc
API = "https://api.github.com"


class DataError(Exception):
    """Safe, fixed-category errors: contains no response body or credentials."""


class Client:
    def __init__(self, token=None, opener=None, sleeper=time.sleep):
        self.token = token
        self.opener = opener or urllib.request.urlopen
        self.sleeper = sleeper

    def request(self, path, query=None, variables=None, accept="application/vnd.github+json"):
        if not path.startswith("/") or path.startswith("//"):
            raise DataError("UNTRUSTED_ENDPOINT")
        headers = {"Accept": accept, "User-Agent": "goodluck55k-profile-local-builder",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        body = None
        if query is not None:
            if not query.lstrip().startswith("query"):
                raise DataError("READ_ONLY_QUERY_REQUIRED")
            headers["Content-Type"] = "application/json"
            body = json.dumps({"query": query, "variables": variables or {}}).encode()
        request = urllib.request.Request(API + path, data=body, headers=headers)
        for attempt in range(3):
            try:
                with self.opener(request, timeout=25) as response:
                    result = json.load(response)
                if isinstance(result, dict) and result.get("errors"):
                    raise DataError("GRAPHQL_ERRORS")
                return result
            except urllib.error.HTTPError as error:
                reason = "RATE_LIMIT" if error.code == 429 or (error.code == 403 and error.headers and error.headers.get("X-RateLimit-Remaining") == "0") else "HTTP_" + str(error.code)
                if error.code < 500 or attempt == 2:
                    raise DataError(reason) from None
            except (OSError, ValueError, TimeoutError):
                if attempt == 2:
                    raise DataError("NETWORK_OR_INVALID_RESPONSE") from None
            self.sleeper(0.5 * (attempt + 1))
        raise DataError("NETWORK_FAILURE")

    def pages(self, path, accept="application/vnd.github+json"):
        result, page = [], 1
        while True:
            separator = "&" if "?" in path else "?"
            rows = self.request(path + separator + urlencode({"per_page": 100, "page": page}), accept=accept)
            if not isinstance(rows, list):
                raise DataError("INVALID_PAGINATION")
            result.extend(rows)
            if len(rows) < 100:
                return result
            page += 1
            if page > 1000:
                raise DataError("PAGINATION_LIMIT")


def public_repos(client, user):
    rows = client.pages(f"/users/{user}/repos?type=owner&sort=full_name")
    return [{"name": r["name"], "full_name": r["full_name"], "created_at": r["created_at"],
             "stars": r["stargazers_count"], "fork": r["fork"], "size": r["size"]}
            for r in rows if not r.get("private", True) and r["owner"]["login"].lower() == user.lower()]


def language_data(client, repos, excluded):
    totals = defaultdict(int)
    evidence = []
    for repo in repos:
        if repo["fork"] or repo["name"] in excluded:
            continue
        values = client.request(f"/repos/{repo['full_name']}/languages")
        if not isinstance(values, dict) or any(not isinstance(n, int) or n < 0 for n in values.values()):
            raise DataError("INVALID_LANGUAGE_BYTES")
        for language, size in values.items():
            totals[language] += size
        evidence.append({"repo": repo["full_name"], "bytes": values})
    return {"languages": dict(sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))),
            "total_bytes": sum(totals.values()), "repos": evidence, "excluded": excluded,
            "policy": "Public owned non-fork repositories, excluding configured profile/resource repositories; empty language maps contribute zero bytes."}


def percentages(languages, limit=6):
    """Top six divided by ALL bytes; a real Others row closes rounding to 100%."""
    rows = [(k, v) for k, v in sorted(languages.items(), key=lambda kv: (-kv[1], kv[0])) if v > 0]
    total = sum(v for _, v in rows)
    if total == 0:
        return []
    take = limit - 1 if len(rows) > limit else limit
    picked = rows[:take]
    other = sum(v for _, v in rows[take:])
    if other:
        picked.append(("Other", other))
    units = [v * 1000 // total for _, v in picked]
    remainder = 1000 - sum(units)
    order = sorted(range(len(picked)), key=lambda i: (-(picked[i][1] * 1000 % total), i))
    for i in order[:remainder]:
        units[i] += 1
    return [{"name": name, "bytes": count, "percent": units[i] / 10} for i, (name, count) in enumerate(picked)]


def weekly_calendar(calendar, start, end):
    days, seen, weeks = [], set(), []
    for week in calendar["weeks"]:
        selected = []
        for day in week["contributionDays"]:
            date = day["date"]
            if start <= date <= end:
                if date in seen or day["contributionCount"] < 0:
                    raise DataError("INVALID_CALENDAR_DAY")
                seen.add(date)
                selected.append({"date": date, "count": day["contributionCount"]})
        if selected:
            selected.sort(key=lambda d: d["date"])
            days.extend(selected)
            weeks.append({"start": selected[0]["date"], "end": selected[-1]["date"],
                          "count": sum(d["count"] for d in selected), "days": len(selected)})
    expected = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1
    if len(days) != expected:
        raise DataError("INCOMPLETE_CALENDAR")
    weeks.sort(key=lambda w: w["start"])
    total = sum(d["count"] for d in days)
    if total != calendar["totalContributions"]:
        raise DataError("CALENDAR_TOTAL_MISMATCH")
    return {"start": start, "end": end, "days": sorted(days, key=lambda d: d["date"]),
            "weeks": weeks, "total": total, "peak": max((w["count"] for w in weeks), default=0)}


CALENDAR_QUERY = """query($login:String!, $from:DateTime!, $to:DateTime!) {
 user(login:$login) { contributionsCollection(from:$from,to:$to) {
  restrictedContributionsCount
  totalCommitContributions totalPullRequestContributions totalIssueContributions totalPullRequestReviewContributions
  commitContributionsByRepository(maxRepositories:100) { repository { isPrivate } }
  issueContributionsByRepository(maxRepositories:100) { repository { isPrivate } }
  pullRequestContributionsByRepository(maxRepositories:100) { repository { isPrivate } }
  pullRequestReviewContributionsByRepository(maxRepositories:100) { repository { isPrivate } }
  contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
 } }
}"""


def contribution_data(client, user, start, end):
    if not client.token:
        raise DataError("NO_GRAPHQL_TOKEN")
    result = client.request("/graphql", query=CALENDAR_QUERY,
                            variables={"login": user, "from": start + "T00:00:00Z", "to": end + "T23:59:59Z"})
    collection = result["data"]["user"]["contributionsCollection"]
    # A broad credential must never silently add private activity to this public profile.
    if collection["restrictedContributionsCount"]:
        raise DataError("RESTRICTED_CONTRIBUTIONS_EXCLUDED")
    for field in ("commitContributionsByRepository", "issueContributionsByRepository", "pullRequestContributionsByRepository", "pullRequestReviewContributionsByRepository"):
        if len(collection[field]) >= 100:
            raise DataError("PUBLIC_CONTRIBUTION_SCOPE_LIMIT")
        if any(row["repository"]["isPrivate"] for row in collection[field]):
            raise DataError("PRIVATE_CONTRIBUTIONS_EXCLUDED")
    activity = weekly_calendar(collection["contributionCalendar"], start, end)
    fields = {"Commits": "totalCommitContributions", "PRs": "totalPullRequestContributions",
              "Issues": "totalIssueContributions", "Reviews": "totalPullRequestReviewContributions"}
    community = {name: {"value": collection[field], "state": "ok", "window": f"{start} / {end}",
                        "field": "ContributionsCollection." + field} for name, field in fields.items()}
    return activity, community


def discussion_count(client, user, answers=False):
    """Paginate public visible discussions/accepted replies, all history.

    Only public counts are retained; node identifiers/bodies/names are not stored.
    With the default repository-scoped Actions token, other private repositories
    are not visible. A defensive isPrivate filter excludes any broader visibility.
    """
    if not client.token:
        raise DataError("NO_GRAPHQL_TOKEN")
    connection = "repositoryDiscussionComments" if answers else "repositoryDiscussions"
    argument = ",onlyAnswers:true" if answers else ""
    selection = "discussion { repository { isPrivate } }" if answers else "repository { isPrivate }"
    query = ("query($login:String!,$after:String) { user(login:$login) { " + connection +
             "(first:100,after:$after" + argument + ") { pageInfo { hasNextPage endCursor } "
             "nodes { " + selection + " } } } }")
    count, after, seen = 0, None, set()
    while True:
        response = client.request("/graphql", query=query, variables={"login": user, "after": after})
        values = response["data"]["user"][connection]
        for node in values["nodes"]:
            target = (node.get("discussion") if node and answers else node)
            if target and not target["repository"]["isPrivate"]:
                count += 1
        info = values["pageInfo"]
        if not info["hasNextPage"]:
            return {"value": count, "state": "ok", "window": "all history · 公开可见", "field": "User." + connection + ("(onlyAnswers:true)" if answers else "")}
        after = info["endCursor"]
        if not after or after in seen:
            raise DataError("INVALID_GRAPHQL_CURSOR")
        seen.add(after)


def search_count(client, user, kind, start, end):
    query = f"author:{user} is:public is:{kind} created:{start}..{end}"
    result = client.request("/search/issues?" + urlencode({"q": query, "per_page": 1}))
    if result.get("incomplete_results", True):
        raise DataError("INCOMPLETE_SEARCH")
    return {"value": result["total_count"], "state": "ok", "window": f"{start} / {end}",
            "field": "REST search/issues · " + query}


def star_times_graphql(client, full_name):
    owner,name=full_name.split("/",1)
    query="""query($owner:String!,$name:String!,$after:String){repository(owner:$owner,name:$name){isPrivate stargazers(first:100,after:$after,orderBy:{field:STARRED_AT,direction:ASC}){pageInfo{hasNextPage endCursor}edges{starredAt}}}}"""
    times,after,seen=[],None,set()
    while True:
        result=client.request("/graphql",query=query,variables={"owner":owner,"name":name,"after":after})
        repository=result["data"]["repository"]
        if repository is None:
            raise DataError("STAR_REPOSITORY_UNAVAILABLE")
        if repository["isPrivate"]:
            raise DataError("PRIVATE_STAR_REPOSITORY_EXCLUDED")
        connection=repository["stargazers"]
        times.extend(row["starredAt"] for row in connection["edges"])
        info=connection["pageInfo"]
        if not info["hasNextPage"]:
            return times
        after=info["endCursor"]
        if not after or after in seen or len(seen)>=1000:
            raise DataError("INVALID_STAR_GRAPHQL_CURSOR")
        seen.add(after)


def star_data(client, repos, previous=None, previous_date=None):
    series = []
    eligible = sorted((r for r in repos if not r["fork"]), key=lambda r: (-r["stars"], r["name"]))
    for repo in eligible[:6]:
        row = {"name": repo["name"], "full_name": repo["full_name"], "current": repo["stars"],
               "created_at": repo["created_at"], "history_state": "ok", "starred_at": [],
               "source": f"/repos/{repo['full_name']} · stargazers_count ("+("zero snapshot" if repo["stars"]==0 else "current snapshot; history unavailable")+")"}
        if repo["stars"]:
            try:
                attempts=[]
                try:
                    events = client.pages(f"/repos/{repo['full_name']}/stargazers", accept="application/vnd.github.star+json")
                    times = [e["starred_at"] for e in events]
                    row["source"]=f"/repos/{repo['full_name']}/stargazers (star+json)"
                except (DataError,KeyError,TypeError) as rest_error:
                    attempts.append({"source":"REST star+json","reason":str(rest_error) if isinstance(rest_error,DataError) else "MISSING_STAR_TIMESTAMPS"})
                    if not isinstance(getattr(client,"token",None),str) or not client.token:
                        raise DataError(attempts[-1]["reason"])
                    times=star_times_graphql(client,repo["full_name"])
                    row["source"]="GraphQL repository.stargazers.edges.starredAt"
                    row["fallback_attempts"]=attempts
                if len(times) != repo["stars"] or any(not isinstance(t, str) for t in times):
                    raise DataError("STAR_SNAPSHOT_CHANGED_OR_INCOMPLETE")
                for timestamp in times:
                    dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                row["starred_at"] = sorted(times)
            except (DataError, KeyError, ValueError,TypeError) as error:
                row["history_state"] = "unavailable"
                row["reason"] = str(error) if isinstance(error, DataError) else "INVALID_STAR_TIMESTAMPS"
                cached = next((r for r in (previous or {}).get("series", []) if r["name"] == row["name"]), None)
                if cached and cached.get("history_state") in ("ok", "stale") and cached.get("starred_at"):
                    row["history_state"] = "stale"
                    row["starred_at"] = cached["starred_at"]
                    row["history_fetched_at"] = cached.get("history_fetched_at") or previous_date
        series.append(row)
    return {"total_current": sum(r["stars"] for r in eligible), "series": series,
            "policy": "Top 6 public owned non-fork repositories. Dates describe surviving stars, not cancelled historical stars."}


class Cache:
    def __init__(self, directory, now):
        self.directory = directory
        self.now = now

    def success(self, name, payload, source):
        path = self.directory / (name + ".json")
        previous = read_json(path, {})
        fetched_at = previous.get("fetched_at") if previous.get("payload") == payload else None
        result = {"schema": 1, "state": "ok", "payload": payload, "source": source,
                  "fetched_at": fetched_at or self.now, "reason": None}
        write_json(path, result)
        return result

    def failure(self, name, reason, source, context=None):
        path = self.directory / (name + ".json")
        previous = read_json(path, {})
        payload = previous.get("payload")
        result = {"schema": 1, "state": "stale" if payload is not None else "unavailable" if reason == "NO_GRAPHQL_TOKEN" else "failed",
                  "payload": payload, "source": source, "fetched_at": previous.get("fetched_at"), "reason": reason}
        if context:
            result["requested_scope"] = {key: context[key] for key in ("window", "field") if key in context}
        write_json(path, result)
        print(f"WARNING: {name}: {reason}; " + ("last good data retained" if payload is not None else "no data available"))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="UTC end date (YYYY-MM-DD); default today")
    parser.add_argument("--auth", choices=("auto", "gh", "anonymous"), default="auto", help="Use gh credential store locally; workflow token remains supported")
    args = parser.parse_args()
    c = config()
    user = c["user"]
    if not re.fullmatch(r"[A-Za-z0-9-]+", user):
        raise SystemExit("Invalid GitHub login")
    now = dt.datetime.now(UTC).replace(microsecond=0)
    end = dt.date.fromisoformat(args.as_of) if args.as_of else now.date()
    start = end - dt.timedelta(days=364)
    start, end = start.isoformat(), end.isoformat()
    # Use the default workflow token in Actions, or gh's credential store below.
    # Never extract or copy a locally stored personal credential.
    workflow_token = os.environ.get("GITHUB_TOKEN") if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REPOSITORY") == f"{user}/{user}" else None
    client = Client(workflow_token)
    graph_client = Client(workflow_token)
    transport = None
    if not workflow_token and args.auth != "anonymous":
        from github_cli import GhTransport, login_status
        status = login_status()
        if status.get("logged_in"):
            transport = GhTransport()
            client = Client("gh-managed")
            client.request = transport.call
            graph_client = client
            print("Authenticated read-only API transport: GitHub CLI")
        elif args.auth == "gh":
            raise SystemExit("GitHub CLI is not logged in. Complete gh auth login --web locally; do not send credentials to chat.")
    cache = Cache(ROOT / "assets/data", now.isoformat())
    repo_source = f"{API}/users/{user}/repos?type=owner · paginated"
    repos = None
    try:
        repos = public_repos(client, user)
        cache.success("repositories", repos, repo_source)
    except (DataError, KeyError, TypeError) as error:
        cache.failure("repositories", str(error) if isinstance(error, DataError) else "INVALID_REPOSITORIES_RESPONSE", repo_source)
    for name, source, fn in [
        ("languages", f"{API}/repos/{{owner}}/{{repo}}/languages", lambda: language_data(client, repos, c["exclude_language_repos"])),
        ("stars", f"{API}/repos/{{owner}}/{{repo}}/stargazers", lambda: star_data(client, repos,
            read_json(ROOT / "assets/data/stars.json", {}).get("payload"),
            read_json(ROOT / "assets/data/stars.json", {}).get("fetched_at"))),
    ]:
        try:
            if repos is None:
                raise DataError("REPOSITORIES_REQUEST_FAILED")
            cache.success(name, fn(), source)
        except (DataError, KeyError, TypeError) as error:
            cache.failure(name, str(error) if isinstance(error, DataError) else "INVALID_RESPONSE", source)
    community = {}
    try:
        activity, community = contribution_data(graph_client, user, start, end)
        cache.success("activity", activity, API + "/graphql · contributionCalendar")
    except (DataError, KeyError, TypeError) as error:
        reason = str(error) if isinstance(error, DataError) else "INVALID_RESPONSE"
        cache.failure("activity", reason, API + "/graphql · contributionCalendar")
        for name in ("Commits", "Reviews"):
            community[name] = {"value": None, "state": "unavailable", "reason": reason,
                               "window": f"{start} / {end}", "field": "ContributionsCollection"}
        for name, kind in (("PRs", "pr"), ("Issues", "issue")):
            try:
                community[name] = search_count(client, user, kind, start, end)
            except DataError as error:
                community[name] = {"value": None, "state": "failed", "reason": str(error),
                                   "window": f"{start} / {end}", "field": "REST search/issues"}
    for name, answers in (("Discussions", False), ("Answers", True)):
        try:
            community[name] = discussion_count(graph_client, user, answers)
        except (DataError, KeyError, TypeError) as error:
            community[name] = {"value": None, "state": "unavailable", "reason": str(error) if isinstance(error, DataError) else "INVALID_RESPONSE",
                               "window": "all history · 公开可见", "field": "User.repositoryDiscussionComments(onlyAnswers:true)" if answers else "User.repositoryDiscussions"}
    # Keep successful metric caches independently; failures cannot replace a number with zero.
    merged = {}
    for name, metric in community.items():
        key = "community-" + name.lower()
        if metric["state"] == "ok":
            entry = cache.success(key, metric, API + ("/search/issues" if metric["field"].startswith("REST") else "/graphql"))
        else:
            entry = cache.failure(key, metric["reason"], API + ("/search/issues" if metric["field"].startswith("REST") else "/graphql"), metric)
        merged[name] = entry
    write_json(ROOT / "assets/data/community.json", {"schema": 1, "metrics": merged})
    if transport:
        write_json(ROOT / "reports/round2-authenticated-api.json", {"checked_at": now.isoformat(), "window": [start, end],
            "authentication": "gh credential store; token never extracted", "requests": transport.observations})
    print("Public data refresh complete. No remote writes performed.")


if __name__ == "__main__":
    main()
