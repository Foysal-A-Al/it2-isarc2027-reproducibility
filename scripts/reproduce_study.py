"""Reproduce paper outputs in a separate copy; never overwrite the paper snapshot."""
import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODES = ("figures", "saved-features", "raw-ifc")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(root):
    return {str(p.relative_to(root)): digest(p)
            for folder in ("it2", "scripts", "app", "data/features", "results", "figures")
            for p in (root / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


def differences(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = [{"field": path, "reason": "different keys"}] if a.keys() != b.keys() else []
        for key in a.keys() & b.keys():
            out += differences(a[key], b[key], f"{path}/{key}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = [{"field": path, "reason": "different lengths"}] if len(a) != len(b) else []
        for i, (x, y) in enumerate(zip(a, b)):
            out += differences(x, y, f"{path}/{i}")
        return out
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        equal = math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)
    else:
        equal = a == b
    return [] if equal else [{"field": path, "paper": a, "reproduced": b}]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="saved-features")
    parser.add_argument("--output", type=Path,
                        help="New directory outside the repository; must not already exist")
    args = parser.parse_args()
    output = (args.output or ROOT.parent / "it2-reproduction" /
              dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")).resolve()
    if output == ROOT or ROOT in output.parents or output in ROOT.parents:
        parser.error("Output must be outside the repository and cannot contain it")
    if output.exists():
        parser.error("Output already exists; choose a new folder to preserve prior runs")
    # Fingerprint protected inputs before running anything; compare them again at completion.
    before = snapshot(ROOT)
    output.mkdir(parents=True)
    work = output / "workspace"
    ignore = shutil.ignore_patterns(".git", ".idea", "__pycache__", ".venv", "*.pyc")
    def copied_files_only(directory, names):
        skipped = set(ignore(directory, names))
        if args.mode != "raw-ifc" and Path(directory) == ROOT / "data":
            skipped.add("ifc")
        return skipped
    shutil.copytree(ROOT, work, ignore=copied_files_only)
    adaptations = []
    if args.mode == "raw-ifc":
        # Adapt paths only in the temporary reproduction copy, preserving all mathematics.
        p = work / "it2/topology.py"
        old = 'file=path.split("/")[-1],'
        text = p.read_text(encoding="utf-8")
        if old not in text:
            raise RuntimeError("Topology source changed: review the path adaptation")
        p.write_text(text.replace(old, 'file=__import__("pathlib").Path(path).name,'), encoding="utf-8")
        p = work / "scripts/05_roundtrip.py"
        old = 'pathlib.Path("/tmp")'
        text = p.read_text(encoding="utf-8")
        if old not in text:
            raise RuntimeError("Round-trip source changed: review the temporary path adaptation")
        p.write_text(text.replace(old, 'pathlib.Path(__import__("tempfile").gettempdir())'), encoding="utf-8")
        adaptations = ["Windows-safe model basename in copied topology.py",
                       "OS temporary directory in copied 05_roundtrip.py"]
    # Scope determines exactly which stages are rerun; reused results are not claimed as validated.
    commands = []
    if args.mode == "raw-ifc":
        commands += [["data/download.py"], ["scripts/01_topology.py"],
                     ["scripts/02_extract_features.py"]]
    if args.mode != "figures":
        commands += [["scripts/03_identity.py"], ["scripts/04_sensitivity_bv.py"]]
        if args.mode == "raw-ifc":
            commands += [["scripts/05_roundtrip.py", "Duplex_Plumbing_20121113",
                          str(seed), *cfg] for cfg, seeds in
                         [(["0.3", "0.1", "0.15"], range(3)),
                          (["1.0", "0.3", "0.3"], range(3, 6))] for seed in seeds]
        commands += [["scripts/06_eval_roundtrip.py"]]
    commands += [["scripts/07_figures.py"]]
    versions = {}
    for package in ("ifcopenshell", "numpy", "scipy", "matplotlib", "streamlit"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed"
    report = {"mode": args.mode, "python": sys.version, "platform": platform.platform(),
              "packages": versions, "source_sha256": before, "commands": commands,
              "copy_only_adaptations": adaptations,
              "scope": "No raw IFC extraction or new file-level round trips" if args.mode == "saved-features"
                       else "Rendering only; no experiments rerun" if args.mode == "figures"
                       else "Raw IFC extraction and controlled file-level revisions included"}
    env = dict(os.environ, MPLCONFIGDIR=str(output / "matplotlib-cache"), PYTHONUNBUFFERED="1")
    if os.name == "nt":
        # PyCharm may launch python.exe without conda's DLL search directories.
        prefix = Path(sys.prefix)
        conda_paths = [prefix, prefix / "Library/mingw-w64/bin", prefix / "Library/usr/bin",
                       prefix / "Library/bin", prefix / "Scripts", prefix / "bin"]
        env["PATH"] = os.pathsep.join(str(p) for p in conda_paths) + os.pathsep + env.get("PATH", "")
    env["TEMP"] = env["TMP"] = str(output / "temporary")
    Path(env["TEMP"]).mkdir()
    try:
        for command in commands:
            print("RUN:", sys.executable, *command, flush=True)
            subprocess.run([sys.executable, *command], cwd=work, env=env, check=True)
        # Compare only outputs produced by this run, using tight numerical tolerances.
        generated = {Path(command[0]).name for command in commands}
        names = []
        if "01_topology.py" in generated:
            names += ["topology.json"]
        if "03_identity.py" in generated:
            names += [p.name for p in (ROOT / "results").glob("identity_*.json")]
        if "04_sensitivity_bv.py" in generated:
            names += ["extra_Clinic_HVAC.json", "extra_Duplex_Plumbing_20121113.json"]
        if "06_eval_roundtrip.py" in generated:
            names += ["roundtrip_eval.json"]
        report["result_comparisons"] = {
            name: differences(json.loads((ROOT / "results" / name).read_text()),
                              json.loads((work / "results" / name).read_text())) for name in names}
        report["figure_comparisons"] = {
            p.name: {"paper_sha256": digest(p), "reproduced_sha256": digest(work / "figures" / p.name),
                     "byte_identical": digest(p) == digest(work / "figures" / p.name)}
            for p in (ROOT / "figures").glob("*.png")}
        report["input_ifc_sha256"] = {p.name: digest(p) for p in (work / "data/ifc").glob("*.ifc")}
        report["completed"] = True
        report["all_recomputed_numbers_match"] = all(not d for d in report["result_comparisons"].values()) if names else None
    except Exception as exc:
        report["completed"] = False
        report["error"] = str(exc)
        raise
    # Even a failed job writes its report, so the failure and preservation check are inspectable.
    finally:
        report["original_files_unchanged"] = snapshot(ROOT) == before
        (output / "reproduction_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("Report:", output / "reproduction_report.json", flush=True)
    if not report["original_files_unchanged"]:
        raise RuntimeError("Original files changed during reproduction; inspect the report")
    if names and not report["all_recomputed_numbers_match"]:
        print("WARNING: numerical differences found; see report. Paper files were preserved.", flush=True)
        return 2
    print("SUCCESS: selected stages completed; original paper files preserved.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
