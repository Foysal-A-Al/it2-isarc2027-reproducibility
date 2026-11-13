"""Validate IfcDiff directly on stable and regenerated GlobalIds for one controlled IFC pair.
Requires ifcdiff==0.9.0. Does not modify source, manuscript, or result snapshots.
Usage: python scripts/94_ifcdiff_direct_check.py path/to/source.ifc path/to/output.json
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import ifcopenshell
import numpy as np
from ifcdiff import IfcDiff

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("comparison", ROOT / "scripts" / "91_contemporary_comparison.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def run(source: Path, seed: int):
    report = {}
    for regen in (False, True):
        new_path, truth, moved = comparison.make_revision(str(source), regen, np.random.default_rng(seed))
        try:
            oldf = ifcopenshell.open(str(source))
            newf = ifcopenshell.open(new_path)
            actual = IfcDiff(oldf, newf, relationships=["attributes"])
            actual.diff()
            old_ids = {x.GlobalId for x in oldf.by_type("IfcElement")}
            new_ids = {x.GlobalId for x in newf.by_type("IfcElement")}
            overlap = old_ids & new_ids
            row = {
                "source_IfcElement": len(old_ids),
                "revised_IfcElement": len(new_ids),
                "matched_IfcElement_GlobalIds": len(overlap),
                "ifcdiff_added_elements_including_spatial": len(actual.added_elements),
                "ifcdiff_deleted_elements_including_spatial": len(actual.deleted_elements),
                "ifcdiff_changed": len(actual.change_register),
                "correspondence_recall_for_IfcElement": len(overlap) / len(new_ids) if new_ids else None,
            }
            if regen and overlap:
                raise AssertionError("Regenerated IDs unexpectedly overlap")
            if not regen and len(overlap) != len(new_ids):
                raise AssertionError("Stable IDs unexpectedly absent")
            report["regenerated" if regen else "stable"] = row
        finally:
            os.unlink(new_path)
    return {"seed": seed, "source": source.name, "tool": "IfcDiff 0.9.0 actual library execution",
            "scope_note": "IfcDiff counts can include spatial elements, but recall denominator is IfcElement",
            "results": report}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--seed", type=int, default=3000)
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    report = run(a.source.resolve(), a.seed)
    a.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
