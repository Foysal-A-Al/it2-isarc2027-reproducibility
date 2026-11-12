# IT2 — Anonymized Reproducibility Package

This package accompanies a double-blind submission and contains no author-identifying
information. It holds the analysis code and the saved result files that back every
number, figure and table in the paper and supplementary material.

## Contents
- `scripts/` — extraction, metric, matching and comparison code (topology, identity,
  round-trip, graph-signature comparator, contemporary-tool and ambiguity comparisons),
  plus `reproduce_study.py`, the reproduction harness.
- `results/` — saved result files (`*.json`) that the paper reports.
- `environment.yml`, `requirements-lock.txt`, `requirements.txt` — the pinned environment.
- `REPRODUCIBILITY.md` — figure/table provenance.
- `MANIFEST.sha256` — SHA-256 of every file in this package.

## Source data
The three principal IFC exports (Duplex Plumbing/MEP/Electrical, Clinic HVAC/Plumbing,
Simple-Scene) are public example datasets and the 36 authored edit pairs are from the
public BIM-Edit benchmark; they are referenced by name and not redistributed here. Input
SHA-256 hashes are recorded in `results/` so the exact source files can be confirmed.

## Reproduce
Create the environment from `environment.yml`, obtain the named source datasets, then run
`python scripts/reproduce_study.py --mode saved-features` to recompute all headline numbers
from the saved features and confirm they match the saved results.
