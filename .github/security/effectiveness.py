"""Exercise the installed scanners against disposable, never-executed canaries."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import observe


def checked(command, cwd):
    result = observe.run(command, cwd)
    if result.returncode:
        raise ValueError("Fixture preparation failed: " + command[0])
    return result.stdout.strip()


def main(kind):
    project = Path.cwd()
    evidence = project / "evidence" / "effectiveness"
    evidence.mkdir(parents=True, exist_ok=True)
    checks = {}
    try:
        with tempfile.TemporaryDirectory(prefix="devsecops-canary-") as folder:
            root = Path(folder)
            checked(["git", "init", "-q"], root)
            checked(["git", "config", "user.email", "canary@example.invalid"], root)
            checked(["git", "config", "user.name", "Disposable CI canary"], root)
            (root / "README.md").write_text("Synthetic fixtures only. Never execute canary source.\n")
            if kind == "npm":
                observe.write(root / "package.json", {"name": "observation-canary", "version": "1.0.0", "private": True})
                checked(["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit"], root)
            else:
                (root / "requirements.txt").write_text("requests==2.32.5\n")
            checked(["git", "add", "."], root)
            checked(["git", "commit", "-qm", "Clean canary baseline"], root)
            base = checked(["git", "rev-parse", "HEAD"], root)
            # Explicit synthetic rule: not a provider credential and never valid.
            (root / "synthetic.txt").write_text("DEVSECOPS_" + "TEST_ONLY_" + "A1B2C3D4" * 3 + "\n")
            source = "def unsafe(value):\n    return eval(value)\n" if kind == "pip" else "function unsafe(value) { return eval(value); }\n"
            (root / ("canary.py" if kind == "pip" else "canary.js")).write_text(source)
            if kind == "npm":
                observe.write(root / "package.json", {"name": "observation-canary", "version": "1.0.0",
                              "private": True, "dependencies": {"lodash": "4.17.15"}})
                checked(["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit"], root)
            else:
                (root / "requirements.txt").write_text("requests==2.19.1\n")
            checked(["git", "add", "."], root)
            checked(["git", "commit", "-qm", "Known-positive inert fixtures"], root)
            head = checked(["git", "rev-parse", "HEAD"], root)
            secret = observe.run([os.environ["GITLEAKS_BINARY"], "git", "--log-opts=" + base + ".." + head,
                "--redact=100", "--config=" + str(project / ".github/security/gitleaks.toml"),
                "--report-format=sarif", "--report-path=" + str(evidence / "gitleaks.sarif"), "--exit-code=0"], root)
            checks["secret_detected"] = observe.sarif_status(evidence / "gitleaks.sarif",
                "success" if secret.returncode == 0 else "failure")["status"] == "FINDINGS"
            sast = observe.run(["semgrep", "scan", "--config", str(project / ".github/security/semgrep.yml"),
                "--baseline-commit", base, "--sarif", "--output", str(evidence / "semgrep.sarif"), "--metrics=off"], root)
            checks["sast_detected"] = observe.sarif_status(evidence / "semgrep.sarif",
                "success" if sast.returncode == 0 else "failure")["status"] == "FINDINGS"
            previous = Path.cwd()
            try:
                os.chdir(root)
                dep = observe.dependency(kind, base, head, evidence)
            finally:
                os.chdir(previous)
            checks["new_dependency_detected"] = dep["status"] == "FINDINGS" and len(dep["new"]) > 0
            (root / "invalid.yml").write_text("rules: [broken")
            broken = observe.run(["semgrep", "scan", "--config", str(root / "invalid.yml"),
                "--sarif", "--output", str(evidence / "broken.sarif"), "--metrics=off"], root)
            checks["scanner_failure_visible"] = broken.returncode != 0 and observe.sarif_status(
                evidence / "broken.sarif", "failure")["status"] == "SCAN_ERROR"
            failed_build = observe.run([sys.executable, "-c", "raise SystemExit(7)"], root)
            checks["build_failure_visible"] = observe.build_status(
                {"build_exit_code": failed_build.returncode}, "success")["status"] == "FINDINGS"
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        checks["harness_error"] = True
    status = "PASS" if len(checks) == 5 and all(checks.values()) else "FAIL"
    observe.write(evidence / "result.json", {"status": status, "checks": checks,
        "boundary": "Disposable fixture repositories; vulnerable code/dependencies never installed or executed.",
        "note": "Canary effectiveness evidence is excluded from real-project alert/false-positive metrics."})
    print("Known-positive effectiveness:", status, checks)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", required=True, choices=["npm", "pip"])
    sys.exit(main(parser.parse_args().kind))
