# How the IT2 paper results and figures were produced

The saved `results/` and `figures/` directories are the paper snapshot. The Study results tab displays that snapshot, not an experiment performed on the currently selected IFC model. Use the **Reproduce the study** sidebar page to inspect the source code and run protected reproduction jobs.

## Problem and solution

A revised IFC may change element identifiers and break model-to-sensor links. Independently, system membership does not establish a connected port network. IT2 audits network integrity and reconciles identity using class/Tag keys followed by geometry-based assignment. In real use the app first checks GlobalIds. Experimental correctness is assessed against known mappings from controlled revisions of real IFC geometry.

The matching cost is centre distance plus the L1 difference of sorted bounding-box dimensions, plus lambda times a type-name disagreement indicator. Assignment is performed within class/container partitions, then pairs exceeding tau are rejected. This is the implemented algorithm; it is not a learned model or a calibrated probability of correctness.

## Figure provenance

| Figure | Evidence | Pipeline |
| --- | --- | --- |
| 1: loops | Authored conceptual explanation | `07_figures.py` |
| 2: design | Authored research design | `07_figures.py` |
| 3: protocol | Proposed operational workflow | `07_figures.py` |
| 4: quadrant | Measured topology metrics on seven IFC models | `download.py` → `01_topology.py` → `topology.json` → `07_figures.py` |
| 5: recall | Controlled simulated revisions on three models | `02_extract_features.py` → `03_identity.py` → `identity_*.json` → `07_figures.py` |
| 6: sensitivity | Controlled lambda/tau grid on two models | `04_sensitivity_bv.py` → `extra_*.json` → `07_figures.py` |
| 7: roadmap | Proposed future research schedule | `07_figures.py` |

Figures 1–3 and 7 are design/explanation diagrams. They are not measurements. Figure 3 includes IDS, BOT/Brick and BCF stages that the repository does not implement.

## Experiment settings and assumptions

- Identity: three supplied model fingerprint tables; 20 seeds per recreated share (0, 0.1, 0.2, 0.3, 0.5); 5% deletion, 5% decoy additions, 10% moved in plan with sigma 0.15 m, plus position noise with sigma 0.001 m. The simulator preserves dimensions and type names. Confidence intervals are percentile bootstrap intervals over the seed scores; Wilcoxon compares hybrid and Tag recall at nonzero recreated shares.
- Sensitivity: five lambda values and four tau values; five seeds per cell, all Tags recreated, 30% moved with sigma 0.3 m. Figure 6 displays mean F1.
- Binding validity: simulated bindings to equipment classes, 20 seeds; not live BMS telemetry. The GlobalId-only baseline is set to no recovered bindings under the assumption that all IDs are regenerated; it is not an actual identifier lookup experiment.
- File-level round trips: three seeds per configuration (0.3/0.1/0.15 and 1.0/0.3/0.3 for recreated/moved/sigma); new IFCs are written and re-extracted. The comparison uses 20 feature-level seeds with no decoy additions. These are two related simulation designs, not identical paired perturbations.
- Geometry extraction omits elements for which no geometry is returned. The three supplied fingerprint tables contain 3704, 926 and 498 elements respectively; other models should report any extraction losses.
- The downloaded files represent a small set of sample/exported models, not seven independent buildings. Controlled results do not establish performance on every exporter or consecutive real-world revisions.

## Protected reproduction on Windows

Run from Anaconda Prompt inside the repository:

```bat
run_reproduce_windows.bat figures
run_reproduce_windows.bat saved-features
run_reproduce_windows.bat raw-ifc
```

Each invocation uses a new sibling `it2-reproduction/<timestamp>/workspace` folder. The paper snapshot is never overwritten. The JSON report records source/input hashes, package versions, commands, scope, numerical comparisons and figure hashes. Fixed seeds alone do not guarantee identical results across library versions. Figures may have different bytes because of fonts/rendering versions even when their input numbers agree.

Fingerprint mode reuses the saved geometry and file-level round-trip records. It validates downstream calculations, not raw extraction or newly generated IFC revisions. Figure mode only renders the saved results.

Raw mode adapts two paths in its copied source: Windows-safe model basenames in `topology.py`, and the OS temporary directory in `05_roundtrip.py`. These adaptations do not alter the mathematics. The original scripts use a forward-slash filename split and `/tmp`, which can prevent direct Windows reproduction. The original `run_all.sh` is a Bash runner; the added batch file provides a Windows entrypoint.

## Reading a report

`completed` means the selected commands finished. `all_recomputed_numbers_match` compares only the result files regenerated by that scope, at relative tolerance 1e-10 and absolute tolerance 1e-12. It is null for figure-only runs. `original_files_unchanged` verifies the protected source and paper snapshot. A mismatch is reported, never silently copied over the paper values. Raw round-trip GlobalIds are generated afresh, so byte-identical intermediate IFC/JSON files are not expected.

## Remaining technical limitations

Exact Tag matching assumes unique class/Tag keys; the three supplied tables meet that assumption, but arbitrary IFC models may not. Matching uses hard class/container partitions, so changing those attributes can prevent recovery. Assignment happens before gate rejection, which can discard a pair even when a different admissible assignment exists. Topology metrics describe the exported IFC network and do not establish the intended engineering connectivity. Multiple components may be legitimate separate networks. The app's acceptance thresholds are operational defaults, not universally validated safety criteria.

Regeneration code exists for all seven figures and all included numerical result categories. This supporting workflow adds inspectable provenance and Windows execution without modifying the original paper files.

## External-method comparison (Table 3b)

`scripts/08_comparator_signature.py` reproduces the graph-signature comparator in Section 5.3.1.
It builds a two-round Weisfeiler-Lehman signature over the explicit-port adjacency graph of each
real IFC model (via `it2.graph.build_graph`), then runs two signature matchers through the same
`perturb()`/`score()` harness and the same 20 seeds as `scripts/03_identity.py`. Object GlobalIds
and Tags are never used. Requires `data/ifc/<model>.ifc` (run `data/download.py` first) and
`data/features/<model>.json`. Output: `results/comparator_signature.json`. Deterministic.
