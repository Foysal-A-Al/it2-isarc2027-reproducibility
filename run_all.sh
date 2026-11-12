#!/usr/bin/env bash
# Reproduces every table and figure of the paper. Total runtime roughly 20 to 30 minutes on a laptop.
set -euo pipefail
cd "$(dirname "$0")"
python data/download.py
cd scripts
python 01_topology.py
python 02_extract_features.py                 # skip if data/features/*.json are already present
python 03_identity.py
python 04_sensitivity_bv.py
for s in 0 1 2; do python 05_roundtrip.py Duplex_Plumbing_20121113 $s 0.3 0.1 0.15; done
for s in 3 4 5; do python 05_roundtrip.py Duplex_Plumbing_20121113 $s 1.0 0.3 0.3; done
python 06_eval_roundtrip.py
python 07_figures.py
