"""Read-only public endpoint diagnostics. Never reads browser/connector credentials."""
import datetime as dt
import hashlib
import json
import urllib.error
import urllib.request
from urllib.parse import urlencode
from common import ROOT, config, write_bytes, write_json


def main():
    c = config()
    user = c["user"]
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    end = now.date()
    start = end - dt.timedelta(days=364)
    calendar_url = f"https://github.com/users/{user}/contributions?" + urlencode({"from": start.isoformat(), "to": end.isoformat()})
    urls = [
        ("rate_limit", "https://api.github.com/rate_limit", None),
        ("repositories", f"https://api.github.com/users/{user}/repos?type=owner&sort=full_name&per_page=100&page=1", None),
        ("languages-talk", f"https://api.github.com/repos/{user}/human-talk-checker/languages", None),
        ("languages-rate", f"https://api.github.com/repos/{user}/human-rate-web/languages", None),
        ("graphql-public", "https://api.github.com/graphql", {"query": "query($login:String!){user(login:$login){login contributionsCollection{contributionCalendar{totalContributions}}}}", "variables": {"login": user}}),
        ("public-calendar", calendar_url, None),
    ]
    results = []
    directory = ROOT / ".build/remote-evidence"
    directory.mkdir(parents=True, exist_ok=True)
    for key, url, body in urls:
        headers = {"User-Agent": "goodluck55k-profile-verification", "Accept": "text/html" if key == "public-calendar" else "application/vnd.github+json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=headers)
        record = {"key": key, "url": url, "method": request.get_method(), "authentication": "anonymous", "checked_at": now.isoformat()}
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
                record["status"] = response.status
                record["headers"] = {k: response.headers.get(k) for k in ("Content-Type", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-RateLimit-Resource")}
            record["sha256"] = hashlib.sha256(content).hexdigest()
            suffix = ".html" if key == "public-calendar" else ".json"
            write_bytes(directory / (key + suffix), content)
            record["evidence_file"] = ".build/remote-evidence/" + key + suffix
            if suffix == ".json":
                value = json.loads(content)
                record["summary"] = value if key.startswith("languages") or key == "rate_limit" else [{"name": r["name"], "stars": r["stargazers_count"]} for r in value] if isinstance(value, list) else value
            else:
                record["bytes"] = len(content)
        except urllib.error.HTTPError as error:
            record["status"] = error.code
            record["headers"] = {k: error.headers.get(k) for k in ("X-RateLimit-Remaining", "X-RateLimit-Reset", "X-RateLimit-Resource", "Retry-After")}
            try:
                message = json.loads(error.read()).get("message", "")
            except (ValueError, OSError):
                message = "Non-JSON error response"
            record["error"] = message[:240]
        except (OSError, ValueError) as error:
            record["status"] = "NETWORK_ERROR"
            record["error"] = type(error).__name__
        results.append(record)
        print(key, record["status"], json.dumps(record.get("summary", record.get("error", "HTML saved")), ensure_ascii=False))
    write_json(ROOT / "reports/round2-api-probes.json", results)


if __name__ == "__main__":
    main()
