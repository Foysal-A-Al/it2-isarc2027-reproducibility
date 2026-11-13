"""Generate ISARC identity figure from committed 20-seed means; not the historical 3-seed plot.
Does not alter original evidence. Usage: python scripts/plot_isarc_identity.py OUTPUT_DIR
"""
import csv
import json
import pathlib
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
MODELS = [
    ("Duplex_Plumbing_20121113", "Duplex Plumbing"),
    ("Duplex_MEP_20110907", "Duplex MEP"),
]
RATES = [0.0, 0.1, 0.2, 0.3, 0.5]
METHODS = [
    ("tag", "Tag only", "o", "--"),
    ("placement", "Placement only", "s", ":"),
    ("hybrid", "Hybrid", "D", "-"),
]
fig, axs = plt.subplots(2, 1, figsize=(6.4, 6.9), sharex=True, layout="constrained")
rows = []
for ax, (stem, title) in zip(axs, MODELS):
    source = ROOT / "results" / f"identity_{stem}.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    for method, label, marker, style in METHODS:
        y = [100 * data[str(r)][method]["R"][0] for r in RATES]
        ax.plot(RATES, y, marker=marker, linestyle=style, label=label)
        for r, value in zip(RATES, y):
            rows.append([title, source.relative_to(ROOT).as_posix(), r, method, value, 20])
    ax.set_title(title)
    ax.set_ylabel("Correspondence recall (%)")
    ax.set_ylim(35, 103)
    ax.grid(alpha=0.2)
axs[0].legend(loc="lower left", frameon=False, ncol=2)
axs[-1].set_xlabel("Tag regeneration rate")
fig.savefig(OUT / "figure2_20seed_traceable.png", dpi=250)
fig.savefig(OUT / "figure2_20seed_traceable.svg")
svg_file = OUT / "figure2_20seed_traceable.svg"
svg_file.write_text("\n".join(line.rstrip() for line in svg_file.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
with (OUT / "figure2_source_values.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["model", "source_json", "tag_regeneration_rate", "method", "recall_pct", "source_seed_count"])
    writer.writerows(rows)
(OUT / "figure2_provenance.json").write_text(json.dumps({
    "status": "regenerated from saved 20-seed identity summaries; NOT an authentication of original 3-seed manuscript image",
    "generator": "scripts/plot_isarc_identity.py", "seed_source": "scripts/03_identity.py: SEEDS=20",
    "input_files": [f"results/identity_{stem}.json" for stem, _ in MODELS],
    "methods": [a for a, _, _, _ in METHODS],
    "figure": "figure2_20seed_traceable.png",
}, indent=2), encoding="utf-8")
print("GENERATED", OUT)
