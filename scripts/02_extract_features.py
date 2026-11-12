"""Fingerprint extraction for the identity models -> data/features/<model>.json (a few minutes per model)"""
import sys, time, ifcopenshell
from _common import IFC, FEAT, IDENTITY_MODELS, dump
from it2.features import extract_features

models = sys.argv[1:] or IDENTITY_MODELS
for m in models:
    t = time.time()
    # These saved fingerprints make downstream experiments possible without IFC downloads.
    recs = extract_features(ifcopenshell.open(str(IFC / f"{m}.ifc")))
    dump(recs, FEAT / f"{m}.json")
    print(f"{m}: {len(recs)} elements, {time.time()-t:.0f} s")
