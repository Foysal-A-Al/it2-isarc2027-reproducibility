# ISARC evidence audit — 13 November 2026

This folder contains **new, independently generated audit evidence**, not the original source files used to construct the manuscript. The manuscript and historical saved outputs have not been overwritten. A result is labelled verified only to the extent indicated below.

## 1. Figure 2 identity sweep (verified source, replacement candidate)

- Generator: `scripts/plot_isarc_identity.py`.
- Input: `results/identity_Duplex_Plumbing_20121113.json` and `results/identity_Duplex_MEP_20110907.json`.
- Experiment source: `scripts/03_identity.py`, 20 seeds (0–19), Tag-regeneration rates 0, 0.1, 0.2, 0.3, 0.5.
- Outputs: `figure2_20seed_traceable.png`, `.svg`, source values CSV and provenance JSON.
- **Important:** The historic ISARC Figure 2 says “three seeds”; this generator does not authenticate that historic figure. The baseline stored as `placement` is a placement-origin matcher, not the separate geometric centre-and-dimension stage. The new chart labels this baseline precisely.
- If adopting this replacement, update the manuscript's experimental seed description and captions only after deciding which experiment is authoritative.

## 2. Topology negative control (verified independent re-execution)

- Generator: `scripts/93_topology_negative_control.py`.
- Source IFC: public Duplex Plumbing model, with SHA-256 `abfaf5c0979b6b4b05182aec7ada8945374bdb414db76c763724d549b41b212b`, matching `research/validation-2026-10-28/raw_sources.json`.
- 20 independent deterministic trials, seeds 0–19; degree-preserving relation endpoint swaps within a source connected component. Each run checks **the exact same component partition**, not only the number of components.
- 49–50 of 485 edges removed/replaced per trial (10.10–10.31%). Each run preserves element degree, edge count and connected-component membership.
- Seed 0 was written back to `IfcRelConnectsPorts` in a **separate** IFC, then reopened. All 49 changed element edges were recovered as expected; D, PC, port count, CC, component count, TF, LC, SM and system count were unchanged.
- Outputs: `topology_rewiring_20seed_audit.json` and CSV. The raw third-party IFC and modified IFC are NOT redistributed.
- **Important:** This is a new independent reproduction of the *negative-control claim*, not a claim to have recovered the original 20 historical trial files or their unrecorded random seeds. Physical topology correctness is not established.

## 3. Saved-features numerical reproduction (verified numeric outputs; protection warning explained)

- `scripts/reproduce_study.py --mode saved-features` completed the identity, sensitivity, round-trip evaluation and historical plot commands in an independent external working directory.
- **All six newly computed JSON result files agreed with the saved JSON values**, under the harness's numerical comparison.
- The original-file preservation check returned false because the two new audit scripts were added to the repository *during* the long-running snapshot check. A subsequent key-by-key SHA-256 reconciliation found **0 changes among the 64 original files** and **exactly 2 newly added audit scripts**.
- Historical PNG files were **not byte-identical** after regeneration, so do not claim binary-image reproducibility. Scientific numeric comparisons are separate from rendered PNG identity.
- The detailed machine-specific log stays outside this public repository because it contains local absolute paths.

## 4. Manuscript and code distinctions still requiring reconciliation

- `it2/matching.py` implements the original hybrid (hard IFC class+container groups, centre distance plus absolute dimension difference, type penalty); `it2/review_matching.py` implements a different review-aware partial matcher (class groups, logarithmic dimension term, conditional type and soft containment penalties, 0.03 m abstention margin). Do not combine them as if one tested algorithm.
- `scripts/91_contemporary_comparison.py` invokes BIMDelta Core but substitutes GlobalId intersection for the repeated IfcDiff execution. Direct-tool validation must be reported separately from this adapter.
- Table 4's saved comparison includes three plumbing seeds and one seed each for Duplex MEP and Clinic HVAC; equal 100%/0% results do not imply equal trial counts.
- Authored-edit aggregate 97.90%/6-of-12 and the related baselines agree with `research/validation-2026-10-28/external_summary.json`, but a fresh raw BIM-Edit reproduction still requires the upstream benchmark and its pinned revision.
- Table 6 has a displayed rounding ambiguity near 99.74945%; use a documented rounding rule.
- The cited literature's negative capability claims, and anonymous-review treatment of this public author-identifying repo, are not certified by these software checks.

## How to regenerate these audit outputs

From the repository root, in the environment defined by `environment.yml`:

```powershell
python scripts/plot_isarc_identity.py C:\path\to\fresh-audit-output
python data/download.py
python scripts/93_topology_negative_control.py data/ifc/Duplex_Plumbing_20121113.ifc C:\path\to\fresh-audit-output
```

Generate into a fresh external directory; **never overwrite the historical `results/` or `figures/`** as part of an audit.

## 5. Direct IfcDiff 0.9.0 check (verified on one actual IFC pair)

- Reproduction script: `scripts/94_ifcdiff_direct_check.py`, executed successfully with seed 3000 on the hashed Duplex Plumbing source.
- Real `IfcDiff` library execution using the `attributes` relationship option, not the historical correspondence adapter.
- Stable IDs: 498/498 IFC elements overlap; zero added/deleted by IfcDiff.
- Regenerated IDs: 0/498 IFC elements overlap; IfcDiff reports 504 added and 504 deleted objects, including six spatial entities beyond the 498 distribution elements. The different count scopes must not be confused.
- Full results: `ifcdiff_direct_seed3000.json`.
- A single direct check supports the adapter assumption in this condition, but does **not** certify that the full IfcDiff executable was rerun for all models and seeds.

## 6. Comparator execution status

- Optional packages `bimdelta-core==0.9.0` and `ifcdiff==0.9.0` were installed under a separate audit folder, not into operational applications.
- The original Table 4 BIMDelta saved results have not yet been independently reproduced across all models and seeds. Treat that test as **open** until direct run records complete.
