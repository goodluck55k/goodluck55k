"""Run offline tests and record actual evidence; never claim remote validation."""
import io
from pathlib import Path
import sys
import unittest
from common import ROOT, sha256, write_json, write_text


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    buffer = io.StringIO()
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(suite)
    write_text(ROOT / "reports/test-output.txt", buffer.getvalue())
    files = [ROOT / "README.md", *(ROOT / "assets/static").glob("*.png"), *(ROOT / "assets/stats").glob("*.png"), *(ROOT / "assets/stats").glob("*.svg")]
    evidence = {"tests_run": result.testsRun, "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
                "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                "command": "python scripts/verify.py", "exit_code": 0 if result.wasSuccessful() else 1,
                "remote_github_rendering": "NOT TESTED", "remote_actions": "NOT TESTED",
                "output_hashes": {str(p.relative_to(ROOT)).replace('\\', '/'): sha256(p) for p in sorted(files)}}
    write_json(ROOT / "reports/verification.json", evidence)
    print(f"{result.testsRun} tests: {evidence['passed']} passed; {evidence['failures']} failures; {evidence['errors']} errors.")
    if not result.wasSuccessful():
        print(buffer.getvalue())
    return evidence["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
