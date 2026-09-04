# Security observation evidence

This is an approved non-blocking pilot, not merge enforcement. The observation PR stays open.

- `observe.py dependency` audits manifests from both exact Git revisions in disposable directories.
  npm uses lockfiles; Python resolves each declared requirements target independently and is explicitly
  not production parity. Both audits use the current advisory database, not historical vulnerability dates.
- Identity is package + advisory (CVE preferred for pip aliases), not dependency version.
  New, existing and resolved sets are retained alongside both raw audit reports and exit codes.
- `PASS`, `FINDINGS` and `SCAN_ERROR` distinguish clean evidence, findings/build failures and incomplete
  execution. Missing SARIF/JSON is never replaced with clean-looking empty evidence.
- `effectiveness.py` creates disposable Git fixtures and runs the same installed Gitleaks, Semgrep,
  dependency normalizer and build classifier. Synthetic secrets have no provider validity; vulnerable
  source is never executed, npm fixtures use lock-only/ignore-scripts, and pip-audit uses an isolated resolver.
- The canary's expected findings do not enter real-project alert/false-positive metrics. A failed
  effectiveness check is visible in metadata. Checksums cover nested evidence, including canaries.
- Run regression tests with `python -m unittest discover -s .github/security -p 'test_*.py' -v`.

The 15-minute job timeout is a failure ceiling, not the five-minute p95 acceptance target.
No production credentials, publishing, branch protection, or automatic remediation is introduced.
