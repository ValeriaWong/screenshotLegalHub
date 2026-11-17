"""Cross-platform commands using the current Conda Python and Node installations."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def environment():
    prefix = Path(sys.prefix).resolve()
    if not (prefix / "conda-meta").is_dir():
        raise RuntimeError("Run this script with the screenshotlegal-v1 Conda Python.")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Python 3.12 is required.")
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm or not Path(node).resolve().is_relative_to(prefix):
        raise RuntimeError("Node 22 must come from this Conda environment; use conda activate or conda run.")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    if not version.startswith("v22."):
        raise RuntimeError("Node 22 is required.")
    npm_path = Path(npm).resolve()
    candidates = [npm_path] if npm_path.suffix == ".js" else []
    candidates += [npm_path.parent / "node_modules/npm/bin/npm-cli.js",
                   npm_path.parent.parent / "lib/node_modules/npm/bin/npm-cli.js"]
    npm_cli = next((p for p in candidates if p.is_file()), None)
    if npm_cli is None:
        raise RuntimeError("Cannot locate npm-cli.js in the Conda environment.")
    return node, [node, str(npm_cli)], {
        "platform": platform.platform(), "python": platform.python_version(),
        "python_executable": sys.executable, "conda_prefix": str(prefix),
        "node": version, "node_executable": node,
        "npm": subprocess.check_output([node, str(npm_cli), "--version"], text=True).strip(),
    }


def checked(command, cwd=ROOT):
    print("Running: " + subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def junit_counts(path):
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    counts = {k: sum(int(s.get(k, "0")) for s in suites)
              for k in ("tests", "failures", "errors", "skipped")}
    counts["passed"] = counts["tests"] - sum(counts[k] for k in ("failures", "errors", "skipped"))
    return counts


def test_report(npm, info, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Do not mistake reports from an earlier invocation for fresh test results.
    for name in ("backend-unit.xml", "frontend-unit.xml"):
        (output / name).unlink(missing_ok=True)
    jobs = [
        ("backend-unit", [sys.executable, "-m", "pytest", "-q", "--junitxml=" + str(output / "backend-unit.xml")], ROOT / "backend"),
        ("frontend-unit", npm + ["run", "test", "--", "--reporter=default", "--reporter=junit", "--outputFile=" + str(output / "frontend-unit.xml")], ROOT / "frontend"),
        ("frontend-typecheck", npm + ["run", "typecheck"], ROOT / "frontend"),
        ("frontend-lint", npm + ["run", "lint"], ROOT / "frontend"),
        ("frontend-build", npm + ["run", "build"], ROOT / "frontend"),
    ]
    results = []
    for name, command, cwd in jobs:
        print("Running " + name, flush=True)
        start = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=300)
            code, log = completed.returncode, completed.stdout + completed.stderr
        except (OSError, subprocess.TimeoutExpired) as error:
            code, log = 1, str(error)
        (output / (name + ".log")).write_text(log, encoding="utf-8")
        counts = junit_counts(output / (name + ".xml")) if name.endswith("-unit") else None
        if name.endswith("-unit") and (counts is None or not counts["tests"] or counts["failures"] or counts["errors"]):
            code = code or 1
        results.append(dict(check=name, exit_code=code, seconds=round(time.monotonic()-start, 3), counts=counts))
        print(log, flush=True)
    report = dict(timestamp=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                  environment=info, status="PASS" if all(r["exit_code"] == 0 for r in results) else "FAIL",
                  results=results, scope="Existing unit tests, TypeScript, lint/architecture guard, production build. No browser E2E or live model calls.")
    (output / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Conda test report", "", f"- Time: {report['timestamp']}", f"- Result: **{report['status']}**"]
    lines += [f"- {key}: `{value}`" for key, value in info.items()]
    lines += ["", "| Check | Result | Tests / passed / failures / errors / skipped | Seconds | Log |",
              "| --- | --- | --- | --- | --- |"]
    for result in results:
        counts = result["counts"]
        totals = " / ".join(str(counts[k]) for k in ("tests", "passed", "failures", "errors", "skipped")) if counts else "—"
        name = result["check"]
        lines.append(f"| {name} | {'PASS' if result['exit_code'] == 0 else 'FAIL'} | {totals} | {result['seconds']} | [{name}.log]({name}.log) |")
    lines += ["", report["scope"], "", "A passing result covers the collected tests and checks only.", ""]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("Report: " + str(output / "REPORT.md"), flush=True)
    return 0 if report["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "backend", "frontend", "seed", "test"])
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports/latest")
    args = parser.parse_args()
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if args.command == "test":
        os.environ["ENABLE_REAL_MODEL"] = "false"
        os.environ["ALLOW_EXTERNAL_EGRESS"] = "false"
    _, npm, info = environment()
    if args.command == "setup":
        if os.environ.get("NODE_TLS_REJECT_UNAUTHORIZED") == "0":
            del os.environ["NODE_TLS_REJECT_UNAUTHORIZED"]
        checked([sys.executable, "-m", "pip", "install", "-r", "backend/requirements.lock"])
        checked([sys.executable, "-m", "pip", "install", "--no-deps", "--no-build-isolation", "-e", "backend"])
        checked(npm + ["ci", "--no-audit", "--no-fund"], ROOT / "frontend")
        checked([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"])
    elif args.command == "backend":
        # Service commands retain the user's model configuration.
        backend_args = [sys.executable, "-m", "uvicorn", "screenshotlegal.api.main:app", "--host", "0.0.0.0", "--port", "18430"]
        network_env = ROOT / ".env.network"
        if network_env.exists():
            backend_args += ["--env-file", str(network_env)]
        checked(backend_args)
    elif args.command == "frontend":
        checked(npm + ["run", "dev"], ROOT / "frontend")
    elif args.command == "seed":
        checked([sys.executable, "-m", "screenshotlegal.cli.seed"])
    else:
        return test_report(npm, info, args.report_dir)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
