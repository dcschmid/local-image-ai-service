#!/usr/bin/env python3
"""Real CPU evaluation with transparent detection limits, without GPU generation."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anatomy import AnatomyChecker
from anatomy_fixtures import fixtures


def main():
    cache = Path.home() / ".cache/local-image-ai-service"
    report = {"date": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cases": {}}
    with tempfile.TemporaryDirectory(prefix="anatomy-integration-", dir=cache) as work:
        checker = AnatomyChecker({}, Path(work))
        for name, raw in fixtures():
            result = checker.check(raw)
            report["cases"][name] = result
            if not result["checked"] or result["backend"] != "local_cpu":
                raise AssertionError("Real CPU review did not run")
            if name in ("normal", "three_legs", "occluded_body") and result["status"] != "REVIEW_REQUIRED":
                raise AssertionError(f"{name} was incorrectly auto-approved or conclusively rejected")
            if name == "three_arms" and result["status"] != "ISSUE_DETECTED":
                raise AssertionError("Known third arm was not detected with the selected profile")
            if name == "no_people" and result["status"] != "NOT_APPLICABLE":
                raise AssertionError("Blank image was not recognized as having no people")
            print(f"{name}: {result['status']} ({result['seconds']} seconds)", flush=True)
    legs = report["cases"]["three_legs"]["people"]
    report["extra_leg_count_detected"] = any(p["visible_legs"] > 2 for p in legs)
    report["calibration"] = "LIMITATIONS_FOUND: extra legs can be missed; people always require human review"
    report["conservative_policy_checks"] = "passed"
    report["temporary_images"] = "removed; diagrams were generated in memory and used only under the service cache"
    (cache / "anatomy-integration-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
