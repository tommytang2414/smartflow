"""Regression checks for evidence classification, without network or credentials."""
import json
from pathlib import Path
import tempfile
import unittest
import observe


def npm(*ids):
    return {"vulnerabilities": {"demo": {"via": [
        {"source": i, "severity": "high", "range": "<2"} for i in ids]}}}


class EvidenceTests(unittest.TestCase):
    def test_dependency_new_existing_resolved(self):
        value = observe.dependency_diff("npm", npm(1, 2), npm(2, 3))
        self.assertEqual([x["advisory"] for x in value["new"]], ["3"])
        self.assertEqual([x["advisory"] for x in value["existing"]], ["2"])
        self.assertEqual([x["advisory"] for x in value["resolved"]], ["1"])

    def test_clean_dependency(self):
        self.assertEqual(observe.dependency_diff("npm", npm(), npm())["status"], "PASS")

    def test_pip_alias_and_version_do_not_reopen_same_advisory(self):
        def audit(version, identifier):
            return {"dependencies": [{"name": "demo", "version": version, "vulns": [
                {"id": identifier, "aliases": ["CVE-2026-0000"]}]}]}
        value = observe.dependency_diff("pip", audit("1", "PYSEC-1"), audit("2", "GHSA-1"))
        self.assertEqual(len(value["existing"]), 1)
        self.assertEqual(value["new"], [])

    def test_audit_errors_are_not_empty_findings(self):
        for kind, document in [("npm", {}), ("npm", {"error": {}, "vulnerabilities": []}),
                               ("pip", []), ("pip", {"dependencies": [{"skip_reason": "not auditable"}]})]:
            with self.subTest(kind=kind, document=document):
                with self.assertRaises((ValueError, TypeError, AttributeError)):
                    observe.audit_findings(kind, document)

    def test_missing_malformed_empty_and_failed_sarif(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report"
            self.assertEqual(observe.sarif_status(path, "success")["status"], "SCAN_ERROR")
            for value in ["broken", json.dumps({"version": "2.1.0", "runs": []})]:
                path.write_text(value)
                self.assertEqual(observe.sarif_status(path, "success")["status"], "SCAN_ERROR")
            observe.write(path, {"version": "2.1.0", "runs": [{"results": []}]})
            self.assertEqual(observe.sarif_status(path, "failure")["status"], "SCAN_ERROR")
            self.assertEqual(observe.sarif_status(path, "success")["status"], "PASS")
            observe.write(path, {"version": "2.1.0", "runs": [{"results": [{}]}]})
            self.assertEqual(observe.sarif_status(path, "success")["status"], "FINDINGS")

    def test_sarif_execution_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report"
            observe.write(path, {"version": "2.1.0", "runs": [{"results": [], "invocations": [
                {"executionSuccessful": False}]}]})
            self.assertEqual(observe.sarif_status(path, "success")["status"], "SCAN_ERROR")

    def test_build_failure_is_visible(self):
        self.assertEqual(observe.build_status({"build_exit_code": 7, "npm_ci_exit_code": 0, "lint_exit_code": 0}, "success")["status"], "FINDINGS")
        self.assertEqual(observe.build_status({}, "success")["status"], "SCAN_ERROR")
        self.assertEqual(observe.build_status({"build_exit_code": 0}, "failure")["status"], "SCAN_ERROR")

    def test_partial_build_and_install_failure(self):
        self.assertEqual(observe.build_status({"compileall_exit_code": 0}, "success", "pip")["status"], "SCAN_ERROR")
        self.assertEqual(observe.build_status({"compileall_exit_code": 0, "tests_exit_code": 0},
                         "success", "pip", "failure")["status"], "SCAN_ERROR")

    def test_malformed_sarif_shapes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report"
            for runs in [[None], [{"results": {}}], [{"results": [], "invocations": [None]}],
                         [{"results": [], "invocations": [{"toolExecutionNotifications": {}}]}]]:
                observe.write(path, {"version": "2.1.0", "runs": runs})
                self.assertEqual(observe.sarif_status(path, "success")["status"], "SCAN_ERROR")

    def test_effectiveness_exception_cannot_pass(self):
        checks = {key: True for key in observe.EFFECTIVENESS_KEYS}
        value = {"status": "PASS", "checks": checks}
        self.assertEqual(observe.effectiveness_status(value, "success")["status"], "PASS")
        self.assertEqual(observe.effectiveness_status(value, "failure")["status"], "SCAN_ERROR")
        del checks["build_failure_visible"]
        checks["harness_error"] = True
        self.assertEqual(observe.effectiveness_status(value, "success")["status"], "SCAN_ERROR")

    def test_pip_package_canonicalization(self):
        def audit(name):
            return {"dependencies": [{"name": name, "version": "1", "vulns": [{"id": "CVE-2026-0000"}]}]}
        value = observe.dependency_diff("pip", audit("Demo._Pkg"), audit("demo-pkg"))
        self.assertEqual(len(value["existing"]), 1)
        self.assertEqual(value["new"], [])

    def test_real_build_exit_capture(self):
        import sys
        with tempfile.TemporaryDirectory() as folder:
            commands = {"tests_exit_code": [sys.executable, "-c", "raise SystemExit(7)"],
                        "compileall_exit_code": [sys.executable, "-c", "raise SystemExit(0)"]}
            observe.capture_build("pip", folder, commands)
            value = json.loads((Path(folder) / "build-test.json").read_text())
            self.assertEqual(value["tests_exit_code"], 7)
            self.assertEqual(observe.build_status(value, "success", "pip")["status"], "FINDINGS")


if __name__ == "__main__":
    unittest.main()
