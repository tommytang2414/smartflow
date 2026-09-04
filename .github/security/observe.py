"""Portable, fail-closed evidence for the two approved observation pilots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(command, cwd=None):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)


def audit_findings(kind, document):
    findings = {}
    if not isinstance(document, dict):
        raise ValueError("Audit response must be an object")
    if kind == "npm":
        if document.get("error") or not isinstance(document.get("vulnerabilities"), dict):
            raise ValueError("npm audit has no valid vulnerabilities object")
        for package, record in document["vulnerabilities"].items():
            for advisory in record["via"]:
                if isinstance(advisory, str):
                    continue  # transitive edges are not duplicate advisories
                identity = str(advisory["source"])
                findings[package + ":" + identity] = {
                    "package": package, "advisory": identity,
                    "severity": advisory["severity"], "affected_range": advisory["range"],
                }
    else:
        if not isinstance(document, dict) or not isinstance(document.get("dependencies"), list):
            raise ValueError("pip-audit has no valid dependencies array")
        for package in document["dependencies"]:
            if package.get("skip_reason"):
                raise ValueError("pip-audit skipped a dependency")
            for advisory in package["vulns"]:
                aliases = sorted(set([advisory["id"]] + advisory.get("aliases", [])))
                identity = next((v for v in aliases if v.startswith("CVE-")), aliases[0])
                findings[package["name"].lower().replace("_", "-") + ":" + identity] = {
                    "package": package["name"], "version": package["version"],
                    "advisory": identity, "aliases": aliases,
                }
    return findings


def dependency_diff(kind, base, head):
    before = audit_findings(kind, base)
    after = audit_findings(kind, head)
    return {
        "status": "FINDINGS" if after else "PASS",
        "new": [after[k] for k in sorted(after.keys() - before.keys())],
        "existing": [after[k] for k in sorted(after.keys() & before.keys())],
        "resolved": [before[k] for k in sorted(before.keys() - after.keys())],
        "base_count": len(before), "head_count": len(after),
    }


def audit_at(kind, root, evidence, label):
    command = (["npm", "audit", "--json", "--ignore-scripts"] if kind == "npm" else
               ["pip-audit", "-r", "requirements.txt", "--format", "json",
                "--progress-spinner", "off"])
    completed = run(command, root)
    (evidence / (label + "-audit.json")).write_text(completed.stdout, encoding="utf-8")
    write(evidence / (label + "-audit-exit.json"), {"exit_code": completed.returncode})
    if completed.returncode not in (0, 1):
        raise ValueError(label + " audit command failed")
    result = json.loads(completed.stdout)
    findings = audit_findings(kind, result)
    if (completed.returncode == 1) != bool(findings):
        raise ValueError(label + " audit exit/findings mismatch")
    return result


def dependency(kind, base, head, evidence):
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    result = {"status": "SCAN_ERROR", "base_sha": base, "head_sha": head,
              "boundary": "NPM_LOCK" if kind == "npm" else "UNLOCKED_SOURCE_TARGET_NOT_PRODUCTION_PARITY"}
    names = ["package.json", "package-lock.json"] if kind == "npm" else ["requirements.txt"]
    try:
        with tempfile.TemporaryDirectory(prefix="dependency-observation-") as temporary:
            documents = []
            for label, revision in [("base", base), ("head", head)]:
                root = Path(temporary) / label
                root.mkdir()
                for name in names:
                    content = run(["git", "show", revision + ":" + name])
                    if content.returncode:
                        raise ValueError(label + " manifest missing")
                    (root / name).write_text(content.stdout, encoding="utf-8")
                documents.append(audit_at(kind, root, evidence, label))
            result.update(dependency_diff(kind, *documents))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        result["error"] = "Audit failed, timed out, or produced incomplete/malformed evidence; inspect audit files and exit codes."
    write(evidence / "dependency-changes.json", result)
    return result


def sarif_status(path, outcome):
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        runs = document["runs"]
        if outcome != "success" or document["version"] != "2.1.0" or not runs:
            raise ValueError("invalid SARIF or failed step")
        count = 0
        for item in runs:
            for invocation in item.get("invocations", []):
                if invocation.get("executionSuccessful") is False:
                    raise ValueError("scanner invocation failed")
                if any(n.get("level") == "error" for n in invocation.get("toolExecutionNotifications", [])):
                    raise ValueError("scanner reported errors")
            count += len(item["results"])
        return {"status": "FINDINGS" if count else "PASS", "count": count}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "SCAN_ERROR", "count": None}


def build_status(document, outcome):
    if outcome != "success" or not document:
        return {"status": "SCAN_ERROR"}
    if any(type(value) is not int for value in document.values()):
        return {"status": "SCAN_ERROR"}
    return {"status": "FINDINGS" if any(document.values()) else "PASS", "exit_codes": document}


def summarize(evidence):
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in ("gitleaks", "semgrep"):
        results[name] = sarif_status(evidence / (name + ".sarif"), os.getenv(name.upper() + "_OUTCOME"))
    for name, filename in [("dependency", "dependency-changes.json"), ("build_test", "build-test.json")]:
        try:
            result = json.loads((evidence / filename).read_text(encoding="utf-8"))
            if name == "build_test":
                result = build_status(result, os.getenv("BUILD_TEST_OUTCOME"))
            elif os.getenv("DEPENDENCY_OUTCOME") != "success" or result.get("status") not in ("PASS", "FINDINGS", "SCAN_ERROR"):
                result = {"status": "SCAN_ERROR"}
        except (OSError, ValueError, TypeError):
            result = {"status": "SCAN_ERROR"}
        results[name] = result
    try:
        effectiveness = json.loads((evidence / "effectiveness/result.json").read_text(encoding="utf-8"))
        results["effectiveness"] = {"status": effectiveness["status"], "checks": effectiveness["checks"]}
    except (OSError, ValueError, KeyError, TypeError):
        results["effectiveness"] = {"status": "SCAN_ERROR"}
    write(evidence / "metadata.json", {
        "schema_version": 2, "mode": "NON_BLOCKING_OBSERVATION",
        "repository": os.getenv("GITHUB_REPOSITORY"), "run_id": os.getenv("GITHUB_RUN_ID"),
        "base_sha": os.getenv("BASE_SHA"), "head_sha": os.getenv("HEAD_SHA"),
        "controls": results,
    })
    summary = "\n".join("- " + name + ": " + value["status"] for name, value in results.items()) + "\n"
    print(summary)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write("### Non-blocking security observation\n\n" + summary)
    # No missing report is fabricated. Only real evidence files enter the manifest.
    (evidence / "sha256sums.txt").write_text("".join(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(evidence).as_posix() + "\n"
        for path in sorted(evidence.rglob("*")) if path.is_file() and path.name != "sha256sums.txt"
    ), encoding="utf-8")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["dependency", "summarize"])
    parser.add_argument("--kind", choices=["npm", "pip"])
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--evidence", default="evidence")
    args = parser.parse_args()
    if args.mode == "dependency":
        sys.exit(2 if dependency(args.kind, args.base, args.head, args.evidence)["status"] == "SCAN_ERROR" else 0)
    summarize(args.evidence)
