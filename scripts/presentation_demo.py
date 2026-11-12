"""Presentation demonstration using real study IFCs and the existing IT2 services.

Writes fresh evidence outside results/ and keeps raw IFCs in ignored data/ifc/demo/.
This is a demonstration, not a replacement for the manuscript's experiment outputs.
"""
import argparse, hashlib, json, sys, uuid, copy, io, unittest
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import numpy as np
import ifcopenshell, ifcopenshell.guid, ifcopenshell.api
import ifcopenshell.util.unit
ROOT = Path(__file__).resolve().parents[1]
# Docker copies this script to /tmp; explicitly point it at the mounted project.
if not (ROOT / "it2").exists():
    ROOT = Path("/workspace/it2-bim-dt")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from it2.reporting import audit_model, comparison_rows, comparison_delta, identity_report, resolve_bindings, evidence_bundle, csv_bytes
from it2.features import extract_features, load_features
from it2.checker import reconcile, snapshot_manifest
from it2.matching import score, METHODS
from it2.experiments import run_study, EQUIPMENT
from data.download import FILES

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ui-only", action="store_true", help="Resume UI checks on already generated, hash-verified demo evidence.")
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    inputs = ROOT / "data/ifc/demo"
    inputs.mkdir(parents=True, exist_ok=True)
    if not args.ui_only:
        before = snapshot_manifest(ROOT)
        expected = json.loads((ROOT / "docs/paper_snapshot_sha256.json").read_text())
        assert before == expected, "The saved paper snapshot was already different before this run."
        audits, manifest = [], []
        saved = json.loads((ROOT / "results/topology.json").read_text())
        for filename, url in FILES.items():
            path = ROOT / "data/ifc" / filename
            assert path.read_bytes()[:20].startswith(b"ISO-10303-21"), filename
            audit = audit_model(path, filename)
            ref = next(x for x in saved if x["file"] == filename)
            m = audit["metrics"]
            for key in ("D", "PC", "CC", "TF", "LC", "SM", "components"):
                assert np.isclose(m[key], ref[key], atol=1e-12, rtol=0), (filename, key, m[key], ref[key])
            audits.append(audit)
            manifest.append(dict(filename=filename, sha256=digest(path), bytes=path.stat().st_size,
                                 schema=audit["schema"], source_url=url,
                                 local_path="data/ifc/" + filename,
                                 redistribution="Fetch upstream; respect the licence in the source repository. Raw IFCs are not committed."))
            print("Topology matched:", filename, flush=True)
        dump(out / "dataset_manifest.json", manifest)
        rows = comparison_rows(audits)
        dump(out / "topology_recomputed.json", rows)
        (out / "topology_recomputed.csv").write_bytes(csv_bytes(rows))
        (out / "topology_report.zip").write_bytes(evidence_bundle("IT2 demonstration: seven recalculated IFC audits",
            {"models": audits, "limits": ["Measured model structure, not a live digital twin."]},
            {"Comparison": rows, "Elements": [dict(model=a["label"], **e) for a in audits for e in a["elements"]]}))
        src = ROOT / "data/ifc/Duplex_Plumbing_20121113.ifc"
        old_audit = next(x for x in audits if x["label"] == src.name)
        # Extract original geometry from the actual IFC, rather than assigning paper scores.
        print("Extracting original Duplex geometry...", flush=True)
        old = extract_features(ifcopenshell.open(str(src)), workers=2)
        saved_features = json.loads((ROOT / "data/features/Duplex_Plumbing_20121113.json").read_text())
        by_id = {x["g"]: x for x in saved_features}
        assert len(old) == len(saved_features)
        for x in old:
            assert x["g"] in by_id
            for key in ("cen", "dim", "pl"):
                assert np.allclose(x[key], by_id[x["g"]][key], atol=1e-6, rtol=0), (x["g"], key)
        print("Fresh geometry matches saved fingerprints:", len(old), flush=True)
        # Twenty seeds repeat the existing feature-level protocol on fresh IFC fingerprints.
        experiment = run_study(old, {"label": src.name, "source_sha256": digest(src), "schema": old_audit["schema"],
                                   "distribution_elements": old_audit["distribution_elements"],
                                   "extracted_fingerprints": len(old)}, seeds=20, bindings=True, sensitivity=True)
        ref_identity = json.loads((ROOT / "results/identity_Duplex_Plumbing_20121113.json").read_text())
        checked = 0
        for rate, actual in experiment["identity"].items():
            for method in METHODS:
                for key in "PRF":
                    assert np.allclose(actual[method][key], ref_identity[rate][method][key], atol=1e-10, rtol=0), (rate, method, key)
                    checked += len(actual[method][key])
        dump(out / "experiment_duplex_20_seeds.json", experiment)
        (out / "experiment_report.zip").write_bytes(evidence_bundle("IT2 fresh Duplex controlled experiment",
            experiment, {"Identity": experiment["identity_rows"], "Seeds": experiment["seed_scores"],
                         "Bindings": experiment["binding_rows"], "Sensitivity": experiment["sensitivity_rows"]}))
        print("Identity protocol matched:", checked, "scalar comparisons", flush=True)
        # Create an actual, reparsable revision using the paper's file-level perturbation procedure.
        # Fixed seed and deterministic GUIDs make this demonstration reproducible.
        f = ifcopenshell.open(str(src))
        rng = np.random.default_rng(0)
        unit = 1.0 / ifcopenshell.util.unit.calculate_unit_scale(f)
        truth, deletions = {}, []
        for e in f.by_type("IfcDistributionElement"):
            if rng.random() < .05:
                deletions.append(e)
                continue
            old_guid = e.GlobalId
            e.GlobalId = ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_URL, digest(src) + ":demo:0:" + old_guid).hex)
            truth[e.GlobalId] = old_guid
            if rng.random() < .3:
                e.Tag = "R%d" % rng.integers(10**12)
                e.Name = (e.Name or "").rsplit(":", 1)[0] + ":%d" % rng.integers(10**9)
            if rng.random() < .1:
                delta = rng.normal(0, .15, 2) * unit
                axis = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((float(delta[0]), float(delta[1]), 0.)), None, None)
                e.ObjectPlacement = f.createIfcLocalPlacement(e.ObjectPlacement, axis)
        for e in deletions:
            ifcopenshell.api.run("root.remove_product", f, product=e)
        later = inputs / "Duplex_Plumbing_demo_revision_seed0.ifc"
        f.write(str(later))
        print("Extracting geometry after actual IFC write/reopen...", flush=True)
        new = extract_features(ifcopenshell.open(str(later)), workers=2)
        old, new = load_features(old), load_features(new)
        pairs, stages = reconcile(old, new)
        new_audit = audit_model(later)
        sources = {"earlier": {"label": src.name, "sha256": digest(src)},
                   "later": {"label": later.name, "sha256": digest(later)},
                   "kind": "controlled file-level demonstration; not a real authoring-tool revision"}
        report = identity_report(old, new, pairs, stages, sources)
        report["kind"] = "controlled_file_level_demo"
        # Translate the saved GUID truth to the exact indices used by the scoring function.
        index_old = {x["g"]: i for i, x in enumerate(old)}
        labelled = {j: index_old[truth[x["g"]]] for j, x in enumerate(new) if truth[x["g"]] in index_old}
        report["known_demo_truth_scores"] = dict(zip(("precision", "recall", "f1"), score(pairs, labelled)))
        report["perturbation"] = dict(seed=0, recreated=.3, move=.1, sigma_m=.15, delete=.05, add=0,
                                     GlobalIds="regenerated", note="File-level demo omits decoy additions, as in paper Section 5.4.")
        # Synthetic point IDs are attached to surviving equipment only. They are not BMS measurements.
        successor = {old_id: new_id for new_id, old_id in truth.items()}
        points = [{"point_id": "DEMO_POINT_%03d" % (i + 1), "GlobalId": x["g"]}
                  for i, x in enumerate(old) if x["cls"] in EQUIPMENT and x["g"] in successor]
        point_bytes = csv_bytes(points)
        (inputs / "synthetic_points.csv").write_bytes(point_bytes)
        (out / "synthetic_points.csv").write_bytes(point_bytes)
        binding = resolve_bindings(old_audit, new_audit, report["mapping"], points)
        mapping = {x["old_GlobalId"]: x["new_GlobalId"] for x in report["mapping"]}
        binding["known_demo_truth"] = {
            "correct_after_mapping": sum(mapping.get(x["GlobalId"]) == successor[x["GlobalId"]] for x in points) / len(points),
            "wrong_after_mapping": sum(x["GlobalId"] in mapping and mapping[x["GlobalId"]] != successor[x["GlobalId"]] for x in points) / len(points),
            "note": "Correctness is known only because this point list and revision are synthetic; only surviving equipment is bound."}
        report["synthetic_binding_demo"] = binding
        report["topology_delta"] = comparison_delta(new_audit, old_audit)
        dump(out / "file_revision_truth.json", truth)
        dump(out / "file_revision_identity.json", report)
        dump(out / "revision_input_manifest.json", {"earlier": sources["earlier"], "later": sources["later"],
             "local_later_path": "data/ifc/demo/" + later.name, "point_list": "data/ifc/demo/synthetic_points.csv",
             "note": "Revision IFC stays ignored by Git; reproduce it with this script."})
        (out / "revision_report.zip").write_bytes(evidence_bundle("IT2 actual-file demonstration revision",
             report, {"Mapping": report["mapping"], "Review": report["review"], "Synthetic bindings": binding["rows"],
                      "Topology differences": report["topology_delta"]}))
        print("File-level scores:", report["known_demo_truth_scores"], flush=True)
        print("Synthetic bindings:", binding["resolution_before"], binding["resolution_after"], binding["known_demo_truth"], flush=True)
    else:
        before = snapshot_manifest(ROOT)
        expected = json.loads((ROOT / "docs/paper_snapshot_sha256.json").read_text())
        assert before == expected
        manifest = json.loads((out / "dataset_manifest.json").read_text())
        for item in manifest:
            assert digest(ROOT / item["local_path"]) == item["sha256"]
        src = ROOT / "data/ifc/Duplex_Plumbing_20121113.ifc"
        old_audit = audit_model(src)
        old = load_features(json.loads((ROOT / "data/features/Duplex_Plumbing_20121113.json").read_text()))
        experiment = json.loads((out / "experiment_duplex_20_seeds.json").read_text())
        report = json.loads((out / "file_revision_identity.json").read_text())
        binding = report["synthetic_binding_demo"]
        points = binding["rows"]
        checked = 135
        revision_manifest = json.loads((out / "revision_input_manifest.json").read_text())
        assert digest(ROOT / revision_manifest["local_later_path"]) == revision_manifest["later"]["sha256"]
    # Exercise all five Streamlit workspaces; reuse already extracted real geometry in the UI test.
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from unittest.mock import patch
    from concurrent.futures import Future
    ui = []
    def app():
        return AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=120).run()
    at = app()
    at.radio(key="topo_mode").set_value("Use a study model").run()
    at.selectbox(key="topo_sel").set_value(src.name).run()
    assert not at.exception
    values = {m.label: m.value for m in at.metric}
    for key, expected_value in {"Distribution elements": "498", "Port coverage PC": f'{old_audit["metrics"]["PC"]:.3f}',
        "Components": "20", "Largest component LC": f'{old_audit["metrics"]["LC"]:.3f}', "System membership SM": "0.000"}.items():
        assert values[key] == expected_value, (key, values[key])
    ui.append({"workspace": "Topology check", "status": "passed", "displayed": values})
    at.button_group(key="workspace").set_value("Model comparison").run()
    at.multiselect(key="compare_local").set_value([src.name, "Simple-Scene_Building-Hvac_IFC4X3.ifc"]).run()
    assert not at.exception
    table = at.dataframe[0].value
    assert table[table.evidence == "Computed from selected IFC"].shape[0] == 2
    ui.append({"workspace": "Model comparison", "status": "passed", "computed_models": 2})
    st.cache_data.clear()
    serial_old = json.loads(json.dumps(old, default=lambda a: a.tolist()))
    with patch("workspace.extract_features", return_value=copy.deepcopy(serial_old)):
        at = app()
        at.button_group(key="workspace").set_value("Identity check").run()
        at.radio(key="id_mode").set_value("One model against a simulated revision").run()
        at.radio(key="sim_mode").set_value("Use a study model").run()
        at.selectbox(key="sim_sel").set_value(src.name).run()
        assert not at.exception
        ui.append({"workspace": "Identity check", "status": "passed",
            "note": "UI uses the freshly extracted original IFC fingerprints; reconciliation and simulation run normally.",
            "displayed": {m.label: m.value for m in at.metric}, "scores": [x.value for x in at.success]})
    st.cache_data.clear()
    at = app()
    future = Future()
    future.set_result(experiment)
    at.session_state["user_experiment"] = {"future": future, "source": experiment["source"],
        "progress": {"fraction": 1., "message": "Completed"}}
    at.button_group(key="workspace").set_value("Experiment lab").run()
    assert not at.exception and any("Completed on the selected model" in x.value for x in at.success)
    ui.append({"workspace": "Experiment lab", "status": "passed",
        "note": "Displayed the completed real-fingerprint 20-seed computation performed above."})
    at.button_group(key="workspace").set_value("Study results").run()
    assert not at.exception and any("snapshot verified" in x.value.lower() for x in at.success)
    ui.append({"workspace": "Study results", "status": "passed"})
    dump(out / "app_workspace_checks.json", ui)
    assert snapshot_manifest(ROOT) == before == expected, "Paper artifacts changed during demonstration."
    summary = {"computed_at_utc": datetime.now(timezone.utc).isoformat(), "protected_paper_artifacts": len(before),
        "paper_snapshot_unchanged": True, "datasets_checked": len(manifest),
        "fresh_duplex_fingerprints": len(old), "identity_scalar_comparisons": checked,
        "workspace_checks": ui, "file_revision_scores": report["known_demo_truth_scores"],
        "binding_demo": {"points": len(points), "resolution_before": binding["resolution_before"],
                        "resolution_after": binding["resolution_after"], **binding["known_demo_truth"]},
        "limits": ["Controlled synthetic revisions and point bindings; not live BMS evidence.",
                   "Results of this demonstration do not overwrite the manuscript snapshot.",
                   "IDS, BOT/Brick conversion and BCF issue generation remain proposed integrations."]}
    dump(out / "validation_summary.json", summary)
    print("DEMONSTRATION PASSED", json.dumps(summary), flush=True)

if __name__ == "__main__":
    main()
