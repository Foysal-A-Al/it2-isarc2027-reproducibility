# IT2 validation extension analysis plan

Written 28 October 2026 before running the new benchmark outcomes. This is a timestamped internal plan, not an externally registered study. Results will be labelled exploratory. Existing published simulation results have already been seen. No generalisation to the building population or claim of journal acceptance is planned.

## Question and scope

Does explicit handling of unmatched and ambiguous elements reduce wrong cross-revision correspondences, compared with the supplied IT2 hybrid and stronger geometry baselines, under specified failures of identifiers, names, dimensions and containment? What recall and review workload are sacrificed?

The user's instruction to strengthen the proposed baselines, ablations, difficult scenarios and validation authorises this extension. The original private repository and the reported numerical tables remain unchanged. New code and results are separate and versioned locally. No repository publication or access-policy change is included.

## Relation to prior work

- Oraskari and Törmä (2015), DOI 10.1016/j.autcon.2015.05.008, already address signatures for IFC differences. Anonymous IFC-instance matching is distinct from physical-asset continuity.
- Wang, Du, Liu and Borrmann (2026), BIMdiff preprint, DOI 10.2139/ssrn.6501624, explicitly addresses object-level identifier reconciliation using geometry signatures. Geometry-based recovery under GUID loss is not a new contribution by itself. Its reported accuracy and timings are not directly comparable with this experiment.
- Wang et al. (2026), DOI 10.1016/j.apenergy.2025.127171, already validate HVAC topology completeness. Port coverage is not the first topology-validation method.
- BIM-Edit, Nithyanantham et al. (2026), arXiv:2606.20146v3, supplies independently published input/reference IFC edits. If its IFC assets can be obtained, use these as external constructed-edit validation, not as real consecutive operational MEP revisions. Its language-model editing scores will not be compared with correspondence scores.

The candidate contribution is a failure-oriented validation and review-aware correspondence workflow with explicit risk/coverage reporting. Partial assignment, ambiguity margins and conservative key matching are established techniques; no claim that these constituent algorithms are novel is made.

## Immutable sources and environment

Original code is pinned to Foysal-A-Al/it2-bim-dt commit b09192d5611fc1a63cdb60105d54c54f9ea0aa73. Retain the baseline source and MIT notice. Use the supplied fingerprints for the two Duplex exports. Independently extract Clinic HVAC geometry with IfcOpenShell 0.8.5 from the public source IFC, retaining file hash, counts and extraction omissions. Also extract explicit host-port edges for a topology consistency demonstration. Record Python, NumPy, SciPy, parser and platform versions. Downloads and raw files are separate from derived fingerprints and results.

## Fixed experiments and units

Main feature benchmark: three source models, eight scenarios, seeds 1000–1019. The unit for uncertainty is a seed-level revision of a fixed model. Models and seeds are not independent buildings. Report all scenarios and model-specific results, including deterioration. Do not pool model elements into an industry-confidence interval. No confirmatory p-values are planned.

All scenarios use the supplied perturbation generator's 5% deletion, 5% ordinary decoys, 0.001 m noise, 10% planar movement with standard deviation 0.15 m, and Tag recreation probability 0.3 unless overridden. After transformation, shuffle new-record order and remap truth. Identifiers are not exposed to methods. They remain private evaluation metadata only.

1. Original setting.
2. All Tags lost: recreation probability 1.0.
3. Renaming: replace normalised type names of 40% of survivors by previously unseen labels.
4. Resizing: change one randomly selected sorted dimension of 30% of survivors by factor 0.8 or 1.2; re-sort.
5. Container changes: change container labels for 20% of survivors; preserve geometry to isolate hard-partition failure.
6. Coincident decoys: add copies of 10% of surviving elements with new Tags, exactly the same observable features and no true predecessor. This deliberately creates unidentifiable cases for geometry-only recovery.
7. Reused Tags: add 10% of original-count decoys with a copied class/Tag key and a 2 m planar displacement. Original key-based matching may violate one-to-one correspondence; explicitly report it.
8. Combined stress: Tag recreation 0.5, noise 0.005 m, 30% movement with sigma 0.3 m, and the renaming/resizing/container/coincident-decoy transformations above.

## Methods fixed before outcomes

- Supplied Tag baseline and placement baseline.
- Supplied hybrid with its original cost and defaults.
- Centre-plus-dimensions assignment without Tags or names, using the original class/container partitions and 0.5 m gate.
- Hybrid without the name penalty, retaining the other original settings.
- Gated partial assignment using original costs and partitions, with unique class/Tag matches first. This isolates pre-assignment gating and unmatched decisions.
- Review-aware partial matcher: unique class/Tag candidates must also pass a geometric plausibility check. The residue is partitioned by IFC class, with containment a soft 0.05 m penalty. Cost is centre distance plus 0.1 m times the capped L1 log dimension-ratio (cap 3), plus a 0.15 m name penalty only when both type strings appear in the opposite revision. Gate is 0.5 m. Shape dimensions use a 0.001 m floor. This is a proposed heuristic, not a trained or calibrated probability model.
- Ablation of that matcher with zero ambiguity margin. The full version rejects geometric pairs whose cost is not at least 0.03 m below every competing candidate in both its row and column. Exact ties are rejected even at zero margin. The partial assignment maximises admissible one-to-one pair count before minimising cost, using dummy unmatched choices. It is not claimed that this objective is always the optimal operational decision.

On the coincident-decoy and combined scenarios, also report the full matcher's risk/coverage curve at margins 0, 0.01, 0.03, 0.1 and 0.3 m. These thresholds are fixed heuristics, not selected against results. Check uniqueness and finite values. Do not call an accepted pair physically verified solely because it has low geometric cost.

## Outcomes and interpretation

For each model/scenario/seed/method, save predicted-pair counts, true/false positives, surviving truth count, precision, recall, F1, wrong-pair count per surviving asset, coverage of surviving old assets, unresolved-survivor review fraction, one-to-one validity and runtime. Precision is undefined when no predictions are accepted; preserve that explicitly rather than claiming perfect precision. Independently verify the scorer against hand-labelled examples. Report mean metrics and 95% percentile bootstrap intervals over the 20 seeds using bootstrap seed 20261028 and 2,000 resamples. Finite seed intervals describe only the constructed process.

The proposed approach is useful only if fewer wrong pairs are accompanied by acceptable retained recall; a precision-only improvement obtained by rejecting everything is not success. Report the trade-off without changing the decision rule after results. No automatic new rating of publication readiness will be inferred.

## External published-edit validation

Deduplicate BIM-Edit tasks by (input_ifc, ground_truth_ifc), since the three instruction categories can refer to the same physical edit. Select every unique realistic pair for which both raw IFC assets can be downloaded and parsed; list every exclusion and reason. Extract IfcElement geometry and IfcSpace geometry, with a canonical class alias for IfcWallStandardCase to IfcWall. Keep source IDs exclusively in the evaluator. Use unique common original GlobalIds as a partial reference correspondence, explicitly acknowledging dependence on the benchmark's identity-preserving edit construction. Mask GlobalIds and Tags in every recovery method. Evaluate all surviving reference correspondences and separately the instruction-targeted changed elements, avoiding an unchanged-element-dominated score. Retain target absence or missing geometry as explicit statuses. Do not call the reference labels a physical asset audit. No parameter fitting on this dataset is allowed.

Pre-outcome resource amendment: the IFC assets are in BIM-Edit/BIM-Edit under complex/, not in the Tasks repository's data/realistic/ paths. Map by basename. Require both files to be at most 25,000,000 bytes, using repository file metadata only. This retains 36 of 54 unique realistic pairs (12 create, 12 update, 12 delete), 43 unique files and 353,645,964 source bytes. Eighteen pairs are excluded by size or missing-asset status before outcomes. The exact selection and every excluded pair are retained in external_selection.json. This is a resource-limited subset and must not be described as the complete benchmark.

## Topology demonstration

Starting from the exported Duplex Plumbing graph, swap the endpoints of disjoint edge pairs to preserve vertex degrees and coverage while changing graph adjacency. Use seeds 2000–2019 and 10% edge participation. Compare PC/CC/LC-style structural descriptors with mapped-edge disagreement against the unchanged source graph. This is a controlled corruption demonstration using the export as a reference, not proof of physical correctness or evidence that all revision edge changes are defects. Report legitimate-change confounding explicitly.

## Verification and resources

Before data outcomes, validate the partial solver against exhaustive enumeration on small matrices, including an assignment-then-gate counterexample. Validate empty inputs, duplicate keys, exact ambiguity, row-order changes and scoring. Run no paid APIs or compute. Use no more than three concurrent CPU workers for experimental cases. Per-case watchdog: 120 seconds; a case that exceeds it is recorded as a failure, not silently omitted. Whole main campaign budget is 20 minutes. Downloads/parsing have separate 120-second HTTP timeouts and recorded failures. Preserve all completed and failed cases. Tests, protocol hash, input hashes, per-run outputs, scripts, literature notes and reproduction commands accompany the deliverable.

If a method or dataset cannot be executed, report that limitation; do not replace it with invented results. Before reporting, rerun a selected fixed case and verify deterministic numerical metrics, independently recompute summary statistics from per-run records, and inspect all plots and final document pages.
