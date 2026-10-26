"""Meaningful boundary/failure tests. All test fixtures are synthetic and local.

Fixtures NEVER enter assets/data or the final profile. Real API integration,
remote GitHub rendering and remote Actions are reported separately.
"""
from contextlib import redirect_stdout
import datetime as dt
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect import (Cache, Client, DataError, contribution_data, discussion_count,
                     language_data, percentages, public_repos, star_data, weekly_calendar)
from common import ROOT, config, read_json, sha256
from render import Paper, build, draw_activity, draw_community, draw_stars, readme, state_label
from process_assets import process


def response(value):
    return BytesIO(json.dumps(value).encode())


def repo(name="example", stars=0, fork=False):
    return {"name": name, "full_name": "tester/" + name, "fork": fork, "size": 1,
            "created_at": "2025-01-01T00:00:00Z", "stars": stars}


class DataTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".build").mkdir(exist_ok=True)

    def test_pagination_keeps_second_page(self):
        c = Client(opener=Mock(side_effect=[response([{"i": i} for i in range(100)]), response([{"i": 100}])]))
        self.assertEqual(len(c.pages("/repos/tester/example/stargazers")), 101)
        self.assertIn("page=2", c.opener.call_args[0][0].full_url)

    def test_auth_errors_do_not_retry_or_print_credentials(self):
        for status in (401, 403, 404, 429):
            with self.subTest(status=status):
                op = Mock(side_effect=urllib.error.HTTPError("https://api.github.com/", status, "secret-body", {}, BytesIO(b"token-secret")))
                c = Client("token-secret", opener=op)
                with self.assertRaises(DataError) as result:
                    c.request("/repos/tester/example")
                self.assertNotIn("secret", str(result.exception))
                self.assertEqual(op.call_count, 1)

    def test_network_timeout_retries_then_fails(self):
        op = Mock(side_effect=TimeoutError("do not expose request details"))
        c = Client(opener=op, sleeper=Mock())
        with self.assertRaisesRegex(DataError, "NETWORK_OR_INVALID_RESPONSE"):
            c.request("/repos/tester/example")
        self.assertEqual(op.call_count, 3)

    def test_read_only_query_and_fixed_host(self):
        c = Client(opener=Mock())
        for path in ("https://elsewhere.example", "//elsewhere.example"):
            with self.assertRaises(DataError):
                c.request(path)
        with self.assertRaises(DataError):
            c.request("/graphql", query="mutation { deleteRepository }")
        c.opener.assert_not_called()

    def test_public_owned_only(self):
        rows = [{"name": name, "full_name": f"{owner}/{name}", "owner": {"login": owner},
                 "private": private, "created_at": "2025-01-01T00:00:00Z", "fork": False,
                 "size": 1, "stargazers_count": 0}
                for name, owner, private in (("yes", "tester", False), ("private", "tester", True), ("other", "someone", False))]
        c = Mock()
        c.pages.return_value = rows
        self.assertEqual([r["name"] for r in public_repos(c, "tester")], ["yes"])

    def test_language_empty_maps_forks_and_exclusions(self):
        c = Mock()
        c.request.side_effect = [{"Python": 300}, {}, {"Python": 100, "HTML": 100}]
        data = language_data(c, [repo("one"), repo("empty"), repo("two"), repo("profile"), repo("fork", fork=True)], ["profile"])
        self.assertEqual(data["languages"], {"Python": 400, "HTML": 100})
        self.assertEqual(data["total_bytes"], 500)
        self.assertEqual(len(data["repos"]), 3)

    def test_zero_languages_does_not_draw_fake_bars(self):
        self.assertEqual(percentages({}), [])
        self.assertEqual(percentages({"Python": 0}), [])

    def test_rounding_all_bytes_and_max_six_rows(self):
        rows = percentages({str(i): i + 1 for i in range(8)})
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(round(r["percent"] * 10) for r in rows), 1000)
        self.assertEqual(sum(r["bytes"] for r in rows), 36)
        self.assertEqual(rows[-1]["name"], "Other")

    def test_calendar_keeps_partial_weeks_and_year_boundary(self):
        calendar = {"totalContributions": 10, "weeks": [
            {"contributionDays": [{"date": "2025-12-31", "contributionCount": 2}]},
            {"contributionDays": [{"date": f"2026-01-0{i}", "contributionCount": count} for i, count in ((1, 0), (2, 3), (3, 5))]},
        ]}
        data = weekly_calendar(calendar, "2025-12-31", "2026-01-03")
        self.assertEqual([w["count"] for w in data["weeks"]], [2, 8])
        self.assertEqual(data["total"], 10)
        self.assertEqual(data["peak"], 8)

    def test_incomplete_or_mismatched_calendar_rejected(self):
        calendar = {"totalContributions": 2, "weeks": [{"contributionDays": [{"date": "2026-01-01", "contributionCount": 2}]}]}
        with self.assertRaisesRegex(DataError, "INCOMPLETE"):
            weekly_calendar(calendar, "2026-01-01", "2026-01-02")
        calendar["totalContributions"] = 3
        with self.assertRaisesRegex(DataError, "MISMATCH"):
            weekly_calendar(calendar, "2026-01-01", "2026-01-01")

    def test_private_contribution_guard(self):
        c = Mock(token="fixture")
        c.request.return_value = {"data": {"user": {"contributionsCollection": {"restrictedContributionsCount": 1}}}}
        with self.assertRaisesRegex(DataError, "RESTRICTED"):
            contribution_data(c, "tester", "2025-01-01", "2025-12-31")

    def test_no_graphql_credential_means_unknown_not_zero(self):
        with self.assertRaisesRegex(DataError, "NO_GRAPHQL_TOKEN"):
            contribution_data(Client(), "tester", "2025-01-01", "2025-12-31")

    def test_discussion_pagination_public_only(self):
        c = Mock(token="fixture")
        c.request.side_effect = [{"data": {"user": {"repositoryDiscussions": {
            "nodes": [{"repository": {"isPrivate": False}}, {"repository": {"isPrivate": True}}],
            "pageInfo": {"hasNextPage": True, "endCursor": "next"}}}}},
            {"data": {"user": {"repositoryDiscussions": {"nodes": [{"repository": {"isPrivate": False}}],
            "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}]
        self.assertEqual(discussion_count(c, "tester")["value"], 2)
        self.assertEqual(c.request.call_args.kwargs["variables"]["after"], "next")

    def test_answers_use_comment_discussion_repository_path(self):
        c = Mock(token="fixture")
        c.request.return_value = {"data": {"user": {"repositoryDiscussionComments": {
            "nodes": [{"discussion": {"repository": {"isPrivate": False}}}, {"discussion": None}],
            "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}
        self.assertEqual(discussion_count(c, "tester", True)["value"], 1)
        self.assertIn("nodes { discussion { repository", c.request.call_args.kwargs["query"])

    def test_stars_uses_real_timestamp_pages(self):
        c = Mock()
        c.pages.return_value = [{"starred_at": "2025-02-02T10:00:00Z"}, {"starred_at": "2025-01-02T10:00:00Z"}]
        data = star_data(c, [repo(stars=2)])
        self.assertEqual(data["series"][0]["starred_at"][0], "2025-01-02T10:00:00Z")
        self.assertEqual(data["total_current"], 2)
        self.assertEqual(c.pages.call_args.kwargs["accept"], "application/vnd.github.star+json")

    def test_star_history_failure_keeps_real_snapshot(self):
        c = Mock()
        c.pages.side_effect = DataError("RATE_LIMIT")
        data = star_data(c, [repo(stars=7)])
        self.assertEqual(data["total_current"], 7)
        self.assertEqual(data["series"][0]["history_state"], "unavailable")
        self.assertEqual(data["series"][0]["starred_at"], [])
        self.assertNotIn("zero snapshot",data["series"][0]["source"])

    def test_star_history_failure_prefers_real_cache(self):
        c = Mock()
        c.pages.side_effect = DataError("RATE_LIMIT")
        old = {"series": [{"name": "example", "history_state": "ok", "starred_at": ["2025-02-02T10:00:00Z"]}]}
        data = star_data(c, [repo(stars=2)], old, "2025-04-01T00:00:00Z")
        self.assertEqual(data["series"][0]["history_state"], "stale")
        self.assertEqual(len(data["series"][0]["starred_at"]), 1)
        self.assertEqual(data["series"][0]["current"], 2)

    def test_zero_stars_needs_no_history_request(self):
        c = Mock()
        self.assertEqual(star_data(c, [repo()])["total_current"], 0)
        c.pages.assert_not_called()

    def test_last_good_cache_survives_failure_and_recovers(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".build") as directory, redirect_stdout(StringIO()):
            cache = Cache(Path(directory), "2026-01-01T00:00:00Z")
            cache.success("sample", {"number": 12}, "public-api")
            failed = cache.failure("sample", "RATE_LIMIT", "public-api")
            self.assertEqual(failed["state"], "stale")
            self.assertEqual(failed["payload"]["number"], 12)
            good = cache.success("sample", {"number": 12}, "public-api")
            self.assertEqual(good["state"], "ok")

    def test_same_data_does_not_change_timestamp_or_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".build") as directory:
            path = Path(directory)
            Cache(path, "2026-01-01").success("sample", {"n": 0}, "public-api")
            before = (path / "sample.json").read_bytes()
            Cache(path, "2026-01-02").success("sample", {"n": 0}, "public-api")
            self.assertEqual(before, (path / "sample.json").read_bytes())

    def test_failure_without_cache_is_not_zero(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".build") as directory, redirect_stdout(StringIO()):
            data = Cache(Path(directory), "2026-01-01").failure("sample", "HTTP_403", "public-api")
            self.assertEqual(data["state"], "failed")
            self.assertIsNone(data["payload"])


class ArtifactTests(unittest.TestCase):
    def test_original_hashes_match_handoff(self):
        if not (ROOT / "assets/source/戴拿立绘.png").exists():
            self.skipTest("Originals retained locally; not included in the public candidate")
        expected = {"戴拿立绘.png": "4ef48cea7b961a8f8ef68e35a37eae3a383e81e04bb5ae8d1e8c39a3d20a0b72",
                    "515b63ef22a00c15eae21c26571b5lc5.jpg": "1b343a28d0c6238d54ee8dc5dfc375fbfcd88591c319d0b55b3bfcd27b9c8f8e",
                    "f5b29402f2d6e5e5 (1).webp": "60c692887e4c93055b75a2e63aa310497af4d8f4a4adaa58fb3a5d6d017420eb",
                    "e927eadd35d3aabe9d8557363e436d52f035747e2b317-XnGlS7_fw658.webp": "15751e756538c3b281c5007d8b980966ff7ad5884cfd47c7845892f01529a5ff"}
        for name, digest in expected.items():
            self.assertEqual(sha256(ROOT / "assets/source" / name), digest)

    def test_nakoruru_visible_pixels_and_original_alpha_are_preserved(self):
        source = ROOT / "assets/source" / config()["assets"]["nakoruru"]
        if not source.exists():
            self.skipTest("Original artwork is required for the local pixel comparison")
        original = Image.open(source).convert("RGBA")
        self.assertEqual(original.getchannel("A").getextrema(), (0, 255))
        src = original.crop(original.getchannel("A").getbbox())
        out = Image.open(ROOT / "assets/processed/nakoruru.png")
        self.assertEqual(src.size, out.size)
        self.assertEqual(src.tobytes(), out.tobytes())

    def test_checkerboard_removed_and_eyes_retained(self):
        mask = Image.open(ROOT / "assets/processed/spiderman-mask.png")
        for x, y in ((10, 10), (750, 50), (700, 500), (50, 400)):
            self.assertEqual(mask.getpixel((x, y)), 0)
        # These white eye pixels are enclosed foreground, unlike boundary checkerboard.
        for x, y in ((360, 87), (407, 89)):
            self.assertGreater(mask.getpixel((x, y)), 240)

    def test_audited_derivatives_build_without_publishing_originals(self):
        (ROOT / ".build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".build") as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "assets/processed", root / "assets/processed")
            with patch("process_assets.ROOT", root):
                self.assertTrue(process()["output_sha256"])
                (root / "assets/processed/dyna.png").write_bytes(b"invalid")
                with self.assertRaises(FileNotFoundError):
                    process()

    def test_works_one_to_five_independent_links(self):
        import copy
        c = copy.deepcopy(config())
        original = c["works"][0]
        for count in range(1, 6):
            c["works"] = [{**original, "url": f"https://github.com/fixture/project-{i}"} for i in range(count)]
            result = readme(c)
            self.assertEqual(result.count('<a href='), count)
            for i in range(count):
                self.assertIn(f'https://github.com/fixture/project-{i}', result)
                self.assertIn(f'assets/static/work-{i + 1}-light.png', result)

    def test_readme_paths_and_precise_identity(self):
        c = config()
        html = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Developer · Explorer · Creator", html)
        self.assertIn("“Johnny, come out and play.”", html)
        paths = re.findall(r'(?:src|srcset)="([^"]+)"', html)
        self.assertTrue(paths)
        for path in paths:
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertEqual(html.count('<a href='), len(c["works"]))

    def test_stats_four_sections_and_mobile_sizes(self):
        audit = read_json(ROOT / "previews/layout-audit.json")
        for record in audit:
            if '/stats/' in record['file']:
                text = [row["text"] for row in record["text"]]
                self.assertLess(text.index("Languages"), text.index("Activity"))
                self.assertLess(text.index("Activity"), text.index("Community"))
                self.assertLess(text.index("Community"), text.index("Stars"))
                for name in ("Commits", "PRs", "Issues", "Reviews", "Discussions", "Answers"):
                    self.assertIn(name, text)

    def test_unavailable_labels_are_distinct(self):
        self.assertNotEqual(state_label({"state": "failed"}), state_label({"state": "unavailable"}))
        self.assertIn("缓存", state_label({"state": "stale", "fetched_at": "2026-01-01"}))

    def test_activity_chart_nonzero_and_zero_paths(self):
        for width in (420, 840):
            for total in (0, 10):
                p = Paper(width, 310, config()["themes"]["light"], "test activity")
                entry = {"state": "ok", "payload": {"start": "2025-12-31", "end": "2026-01-03", "total": total,
                         "weeks": [{"count": 0}, {"count": total}]}}
                draw_activity(p, 0, entry, 310)
                self.assertTrue(p.bounds)

    def test_star_chart_real_steps_and_snapshot_paths(self):
        for width in (420, 840):
            for state in ("ok", "stale", "unavailable"):
                p = Paper(width, 500, config()["themes"]["light"], "test stars")
                entry = {"state": "ok", "fetched_at": "2026-01-01T00:00:00Z", "payload": {"total_current": 2,
                         "series": [{"name": "example", "current": 2, "created_at": "2025-01-01T00:00:00Z",
                                     "history_state": state, "starred_at": [] if state == "unavailable" else ["2025-04-01T00:00:00Z", "2025-08-01T00:00:00Z"]}]}}
                draw_stars(p, 0, entry, 500)
                self.assertTrue(p.bounds)

    def test_offline_build_is_byte_reproducible(self):
        files = [ROOT / "README.md", *(ROOT / "assets/static").glob("*.png"), *(ROOT / "assets/stats").glob("*.png"), *(ROOT / "assets/stats").glob("*.svg")]
        before = {str(p): sha256(p) for p in files}
        with redirect_stdout(StringIO()):
            build()
        self.assertEqual(before, {str(p): sha256(p) for p in files})

    def test_text_and_theme_contrast(self):
        def luminance(hex_value):
            channels = [int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
            return sum(v * weight for v, weight in zip(channels, (.2126, .7152, .0722)))
        for theme in config()["themes"].values():
            for key in ("ink", "muted", "accent"):
                low, high = sorted((luminance(theme["bg"]), luminance(theme[key])))
                self.assertGreaterEqual((high + .05) / (low + .05), 4.5)

    def test_workflow_permissions_and_no_recursive_outputs(self):
        workflow = (ROOT / ".github/workflows/profile.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("17 3 * * *", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("git diff --cached --quiet", workflow)
        paths = workflow.split("paths:", 1)[1].split("permissions:", 1)[0]
        for output in ("assets/data", "assets/static", "assets/stats", "README.md"):
            self.assertNotIn(output, paths)
        self.assertNotIn("PROFILE_TOKEN", workflow)


if __name__ == "__main__":
    unittest.main()
