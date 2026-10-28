"""Policy and process tests for anatomy screening; no model or GPU is needed."""
from copy import deepcopy
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import anatomy
import service


def observation(arms=2, legs=2, cropped=False, issue=False):
    return {"people_present": "yes", "uncertain": False, "summary": "Visible human figure.", "people": [
        {"visible_arms": arms, "visible_legs": legs, "occluded_or_cropped": cropped,
         "anatomy_issue": issue, "details": "Visible limbs inspected."}]}


class AnatomyPolicyTests(unittest.TestCase):
    def test_extra_arms_and_legs_are_rejected(self):
        for arms, legs in ((3, 2), (2, 3), (4, 4)):
            with self.subTest(arms=arms, legs=legs):
                report = anatomy.interpret(observation(arms, legs))
                self.assertEqual(report["status"], "ISSUE_DETECTED")
                self.assertTrue(report["issues"])

    def test_normal_is_an_observation_not_a_correctness_guarantee(self):
        report = anatomy.interpret(observation())
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(report["human_review_required"])
        self.assertIn("not a correctness guarantee", report["limitation"])

    def test_occlusion_missing_visible_limbs_and_uncertainty_require_review(self):
        for value in (observation(cropped=True), observation(1, 2), observation(2, 0),
                      dict(observation(3, 2), uncertain=True),
                      dict(observation(), people_present="uncertain")):
            self.assertEqual(anatomy.interpret(value)["status"], "REVIEW_REQUIRED")

    def test_people_are_not_combined_into_one_four_arm_person(self):
        value = observation()
        value["people"].append(deepcopy(value["people"][0]))
        self.assertEqual(anatomy.interpret(value)["status"], "REVIEW_REQUIRED")

    def test_no_people_is_not_applicable(self):
        value = dict(observation(), people_present="no", people=[])
        self.assertEqual(anatomy.interpret(value)["status"], "NOT_APPLICABLE")

    def test_contradictory_or_empty_people_detection_is_never_approved(self):
        for value in (dict(observation(), people=[]), dict(observation(), people_present="no")):
            self.assertEqual(anatomy.interpret(value)["status"], "REVIEW_REQUIRED")

    def test_subjective_deformation_without_extra_limbs_requires_review(self):
        self.assertEqual(anatomy.interpret(observation(issue=True))["status"], "REVIEW_REQUIRED")

    def test_invalid_output_cannot_be_treated_as_a_valid_assessment(self):
        values = [None, [], {}, dict(observation(), people="not a list"), dict(observation(), uncertain=1),
                  dict(observation(), people=[{}]), dict(observation(), summary=42)]
        for key, value in (("visible_arms", True), ("visible_legs", -1), ("visible_arms", 9),
                           ("anatomy_issue", "false"), ("details", 12)):
            entry = observation()
            entry["people"][0][key] = value
            values.append(entry)
        for value in values:
            with self.subTest(value=str(value)[:60]), self.assertRaises(ValueError):
                anatomy.interpret(value)

    def test_config_rejects_invalid_paths_flags_and_limits(self):
        for cfg in ({"enabled": "true"}, {"threads": 0}, {"threads": 9}, {"timeout": True},
                    {"timeout": 601}, {"runtime": "relative"}, {"unknown": "value"}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                anatomy.settings(cfg)


class AnatomyProcessTests(unittest.TestCase):
    def setUp(self):
        cache = Path.home() / ".cache/local-image-ai-service"
        cache.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="anatomy-unit-", dir=cache)
        self.root = Path(self.temporary.name)
        self.runtime = self.root / "fake-runtime"
        for name in ("model.gguf", "mmproj.gguf"):
            (self.root / name).write_bytes(b"GGUF")
        self.cfg = {"runtime": str(self.runtime), "model": str(self.root / "model.gguf"),
                    "mmproj": str(self.root / "mmproj.gguf"), "timeout": 2, "threads": 2}

    def tearDown(self):
        self.temporary.cleanup()

    def write_runtime(self, body):
        self.runtime.write_text("#!/usr/bin/python3\n" + body)
        self.runtime.chmod(0o700)

    def test_runtime_is_offline_cpu_only_and_cleans_temporary_images(self):
        self.write_runtime("import json,os,sys\nfrom pathlib import Path\n"
                           "assert os.environ['CUDA_VISIBLE_DEVICES']==''\n"
                           "assert '--offline' in sys.argv and '--no-mmproj-offload' in sys.argv\n"
                           "assert sys.argv[sys.argv.index('--device')+1]=='none'\n"
                           "assert Path(sys.argv[sys.argv.index('--image')+1]).read_bytes()==b'test-image'\n"
                           "print(" + repr(json.dumps(observation())) + ")\n")
        checker = anatomy.AnatomyChecker(self.cfg, self.root / "work")
        report = checker.check(b"test-image")
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertEqual(report["backend"], "local_cpu")
        self.assertIsNone(checker.proc)
        self.assertEqual(list((self.root / "work").iterdir()), [])

    def test_missing_weights_fail_before_starting_a_process(self):
        self.write_runtime("raise RuntimeError('must never run')\n")
        (self.root / "model.gguf").unlink()
        checker = anatomy.AnatomyChecker(self.cfg, self.root / "work")
        with self.assertRaises(anatomy.AnatomyError) as raised:
            checker.check(b"image")
        self.assertEqual(raised.exception.code, "anatomy_unavailable")
        self.assertFalse(checker.health()["ready"])

    def test_invalid_json_never_returns_an_approval(self):
        self.write_runtime("print('{invalid')\n")
        checker = anatomy.AnatomyChecker(self.cfg, self.root / "work")
        with self.assertRaises(anatomy.AnatomyError) as raised:
            checker.check(b"image")
        self.assertEqual(raised.exception.code, "anatomy_failed")
        self.assertTrue(checker.last_error)
        self.assertIsNone(checker.proc)

    def test_timeout_reaps_only_the_owned_process(self):
        pid_file = self.root / "child.pid"
        self.write_runtime("import os,time\nfrom pathlib import Path\n"
                           f"Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
                           "time.sleep(60)\n")
        checker = anatomy.AnatomyChecker(dict(self.cfg, timeout=1), self.root / "work")
        start = time.monotonic()
        with self.assertRaises(anatomy.AnatomyError) as raised:
            checker.check(b"image")
        self.assertEqual(raised.exception.code, "anatomy_timeout")
        self.assertLess(time.monotonic() - start, 5)
        self.assertFalse(Path("/proc/" + pid_file.read_text()).exists())
        self.assertIsNone(checker.proc)

    def test_stop_cancels_check_and_releases_admission_without_orphans(self):
        self.write_runtime("import time\ntime.sleep(60)\n")
        checker = anatomy.AnatomyChecker(self.cfg, self.root / "work")
        errors = []
        def run():
            try:
                checker.check(b"image")
            except anatomy.AnatomyError as error:
                errors.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        deadline = time.monotonic() + 2
        while checker.proc is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIsNotNone(checker.proc)
        pid = checker.proc.pid
        with self.assertRaises(anatomy.AnatomyError) as raised:
            checker.check(b"second image")
        self.assertEqual(raised.exception.code, "anatomy_busy")
        checker.stop()
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors[0].code, "anatomy_cancelled")
        self.assertFalse(Path(f"/proc/{pid}").exists())
        self.assertFalse(checker.health()["busy"])


class AnatomyServiceTests(unittest.TestCase):
    def test_defect_is_withheld_without_stopping_healthy_inference(self):
        backend = service.Backend({"active_model": "moss"})
        result = {"data": [{"b64_json": "aW1hZ2U="}]}
        report = anatomy.interpret(observation(3, 2))
        with patch.object(backend, "_generate_image", return_value=result), \
                patch.object(backend.checker, "check", return_value=report), patch.object(backend, "stop") as stop:
            with self.assertRaises(service.APIError) as raised:
                backend.generate({"prompt": "person"}, 42)
            self.assertEqual(raised.exception.status, 422)
            self.assertEqual(raised.exception.code, "anatomy_rejected")
            self.assertEqual(raised.exception.details["seed"], 42)
            stop.assert_not_called()

    def test_checker_failure_withholds_the_image_without_stopping_gpu(self):
        backend = service.Backend({"active_model": "moss"})
        for code, status in (("anatomy_failed", 503), ("anatomy_timeout", 504)):
            with self.subTest(code=code), patch.object(backend, "_generate_image", return_value={"data": [{"b64_json": "aW1hZ2U="}]}), \
                    patch.object(backend.checker, "check", side_effect=anatomy.AnatomyError(code, "Check failed")), \
                    patch.object(backend, "stop") as stop:
                with self.assertRaises(service.APIError) as raised:
                    backend.generate({}, 42)
                self.assertEqual(raised.exception.status, status)
                stop.assert_not_called()

    def test_uncertain_result_is_returned_with_explicit_review_status(self):
        backend = service.Backend({"active_model": "moss"})
        with patch.object(backend, "_generate_image", return_value={"data": [{"b64_json": "aW1hZ2U="}]}), \
                patch.object(backend.checker, "check", return_value=anatomy.interpret(observation(cropped=True))):
            result = backend.generate({}, 42)
        self.assertEqual(result["anatomy_check"]["status"], "REVIEW_REQUIRED")

    def test_http_rejection_contains_report_and_no_image_bytes(self):
        report = anatomy.interpret(observation(2, 3))
        def reject(body, seed):
            raise service.APIError(422, "Defect detected", "anatomy_rejected",
                                   details={"anatomy_check": report, "seed": seed})
        backend = SimpleNamespace(model="moss", generate=reject)
        server = service.BoundedServer(("127.0.0.1", 0), service.make_handler(backend, None))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            connection.request("POST", "/v1/images/generations", json.dumps({"prompt": "person", "seed": 42}),
                               {"Content-Type": "application/json"})
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 422)
            self.assertEqual(result["error"]["anatomy_check"]["status"], "ISSUE_DETECTED")
            self.assertNotIn("data", result)
        finally:
            connection.close()
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
