# IT2 ISARC 2027: Reproducibility Package

Research companion for **Verifying Cross-Revision Referential Integrity in IFC Models: An Empirical Failure Analysis of Asset Correspondence and Network Topology**.

## Status and scope

This repository is a **private research staging repository** for the ISARC paper. The full supplied `IT2_reproducibility_package.zip` was found, inspected, and its 42-entry inventory verified against its SHA-256 manifest (zero mismatches). Its source scripts and saved JSON outputs have been imported. That does **not** constitute an independent rerun of all manuscript experiments.

The paper evaluates two IFC-side failure modes:
- High aggregate correspondence recall can conceal missed *edited-target* matches (97.90% overall recall, 6/12 edited targets recovered in the reported authored-edit experiment).
- Stable port-network aggregate descriptors can coexist with changed explicit adjacency after controlled rewiring.

The study **does not validate a live digital twin or operational sensor-to-asset mappings**.

## Directory map

- `scripts/`: saved experiment sources; includes `08_comparator_signature.py`, `09_stress_reconstruction.py`, `90_comparator_full.py`, `91_contemporary_comparison.py`, and `92_ambiguity_comparison.py`.
- `it2/`: supporting matching and topology code from the original IT2 project.
- `results/`: saved JSON result files, including comparison and stress results.
- `data/features/`: source-model feature records used in feature-level experiments.
- `data/download.py`: upstream source download paths for publicly released example IFCs.
- `research/validation-2026-10-28/`: summary, provenance, and validation records (not per-case prediction tables).
- `REPRODUCIBILITY.md`: historical reproduction instructions bundled with the ZIP; **parts refer to an older, broader manuscript and figure numbering**.
- `ARCHIVE_MANIFEST.sha256`: manifest of the **original supplied ZIP**, not an overall manifest of this new merged repository.
- `README_ARCHIVE.md`: unchanged original archive README.
- `figures/`: historical source-project figures, not necessarily the current conference figures.

## How to reproduce

Create the pinned environment using `environment.yml` or `requirements-lock.txt`; follow `REPRODUCIBILITY.md` to run the protected reproduction harness. Download source IFC exports with `python data/download.py` only if the original sources and their terms permit it. The controlled scripts require their corresponding feature and/or IFC inputs.

The repository has been assembled and its original ZIP hashes checked. **End-to-end independent execution is a separate validation gate.** Do not claim that all paper numbers have been recomputed from a clean checkout until an execution report confirms it.

## Source data, licenses and limitations

The original buildingSMART IFC exports are not committed here; fetch them from their upstream hosts under the applicable license. The external BIM-Edit benchmark data must likewise be retrieved from the original source with proper attribution and license checking. This repository contains saved derivatives and summaries, but it does not supply all third-party raw inputs or independently adjudicated physical-asset truth.

Published results are constrained by older example MEP source models, authored-edit labels that are not independent physical-asset adjudication, and controlled stress perturbations. BIMdiff was not executed directly.

**Anonymous peer review:** This repository is private until release timing, identifying metadata, citations and the conference's review policy are checked. Do not link an author-identified public repository from a double-blind submission without permission.
