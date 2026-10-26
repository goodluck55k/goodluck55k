"""Use gh's credential store without extracting, printing or copying its token."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from common import ROOT


def find_gh():
    executable = shutil.which("gh")
    if executable:
        return executable
    portable = ROOT / ".tools/gh/bin/gh.exe"
    return str(portable) if portable.is_file() else None


def safe_environment():
    environment = dict(os.environ)
    environment.pop("GH_DEBUG", None)
    environment["GH_PROMPT_DISABLED"] = "1"
    environment["GH_PAGER"] = "cat"
    return environment


def run_gh(arguments, input_text=None, executable=None):
    return subprocess.run([executable or find_gh(), *arguments], input=input_text,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8", errors="replace", timeout=60,
                          env=safe_environment(), creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def login_status():
    gh = find_gh()
    if not gh:
        return {"installed": False, "logged_in": False}
    response = run_gh(["auth", "status", "--hostname", "github.com"], executable=gh)
    # Deliberately discard both captured status streams: either may contain credentials.
    result = {"installed": True, "logged_in": response.returncode == 0}
    if result["logged_in"]:
        account = run_gh(["api", "--hostname", "github.com", "--method", "GET", "user", "--jq", ".login"], executable=gh)
        name = account.stdout.strip()
        if account.returncode == 0 and re.fullmatch(r"[A-Za-z0-9-]+", name):
            result["login"] = name
    return result


class GhTransport:
    """The API surface is GET plus explicitly read-only GraphQL and Markdown render."""
    def __init__(self, executable=None, runner=run_gh):
        self.executable = executable or find_gh()
        self.runner = runner
        self.observations = []

    def call(self, path, query=None, variables=None, accept="application/vnd.github+json", markdown=None):
        from collect import DataError
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise DataError("UNTRUSTED_ENDPOINT")
        body = None
        method = "GET"
        if query is not None:
            if path != "/graphql" or not re.match(r"^\s*query\b", query):
                raise DataError("READ_ONLY_QUERY_REQUIRED")
            body = {"query": query, "variables": variables or {}}
            method = "POST"
        elif markdown is not None:
            if path != "/markdown":
                raise DataError("UNTRUSTED_ENDPOINT")
            body = {"text": markdown, "mode": "gfm"}
            method = "POST"
        args = ["api", "--hostname", "github.com", "--method", method, path.lstrip("/"), "--include",
                "--header", "Accept: " + accept, "--header", "X-GitHub-Api-Version: 2022-11-28"]
        if body is not None:
            args += ["--input", "-"]
        try:
            response = self.runner(args, json.dumps(body) if body is not None else None, self.executable)
        except (OSError, subprocess.TimeoutExpired):
            raise DataError("GH_NETWORK_OR_EXECUTION_FAILURE") from None
        output = response.stdout.replace("\r\n", "\n")
        head, _, content = output.partition("\n\n")
        match = re.search(r"^HTTP/\S+\s+(\d+)", head)
        status = int(match.group(1)) if match else None
        headers = {}
        for row in head.splitlines()[1:]:
            key, separator, value = row.partition(":")
            if separator:
                headers[key.lower()] = value.strip()
        record = {"endpoint": path, "method": method, "status": status,
                  "authentication": "gh credential store", "rate_remaining": headers.get("x-ratelimit-remaining"),
                  "rate_reset": headers.get("x-ratelimit-reset"), "rate_resource": headers.get("x-ratelimit-resource")}
        self.observations.append(record)
        if status is None:
            raise DataError("GH_AUTH_OR_RESPONSE_FAILURE")
        if status >= 400:
            reason = "RATE_LIMIT" if status == 429 or status == 403 and headers.get("x-ratelimit-remaining") == "0" else "HTTP_" + str(status)
            record["error"] = reason
            raise DataError(reason)
        if markdown is not None:
            return content
        try:
            result = json.loads(content)
        except ValueError:
            raise DataError("GH_INVALID_JSON") from None
        if isinstance(result, dict) and result.get("errors"):
            # Field paths and typed error categories diagnose queries without exposing bodies.
            record["graphql_errors"] = [{"type": e.get("type") or e.get("extensions", {}).get("code"),
                                         "path": e.get("path"), "message": e.get("message", "")[:180]}
                                        for e in result["errors"]]
            raise DataError("GRAPHQL_ERRORS")
        if response.returncode:
            raise DataError("GH_API_FAILURE")
        return result
