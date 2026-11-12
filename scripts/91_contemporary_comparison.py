"""Contemporary comparison: IT2 vs BIMDelta Core vs IfcDiff on controlled IFC revision pairs.

Builds a revised IFC from a source model with KNOWN ground-truth correspondence, under two
conditions: stable GlobalIds and regenerated GlobalIds. Runs each method on the (old, new) file
pair and scores correspondence recovery on a common denominator (the geometry-bearing, tagged
survivors IT2 tracks). Demonstrates that GlobalId-based change detection (IfcDiff) collapses when
identifiers are regenerated, while Tag/geometry methods (IT2, BIMDelta) survive, and compares their
wrong-match vs abstention behaviour.
"""
import os, sys, tempfile, argparse
import numpy as np
import ifcopenshell, ifcopenshell.guid
from collections import Counter
from _common import IFC
from it2.features import extract_features, load_features
import it2.review_matching as rm
rm.MAX_CELLS = 10 ** 8
from it2.matching import match_hybrid
from it2.review_matching import review_geometry

MODELS = {'Duplex_Plumbing': 'Duplex_Plumbing_20121113.ifc',
          'Duplex_MEP': 'Duplex_MEP_20110907.ifc',
          'Clinic_HVAC': 'Clinic_HVAC.ifc'}

# ---------- IT2 review-aware matcher (same policy as scripts/09) ----------
def review_full(old, new, tau=.5, margin=.03):
    ok = Counter((o['cls'], o['tag']) for o in old if o['tag']); nk = Counter((x['cls'], x['tag']) for x in new if x['tag'])
    oidx = {(o['cls'], o['tag']): i for i, o in enumerate(old) if o['tag']}
    pairs, ui, uj = [], set(), set()
    for j, x in enumerate(new):
        k = (x['cls'], x['tag'])
        if x['tag'] and ok[k] == 1 and nk[k] == 1 and np.linalg.norm(old[oidx[k]]['cen'] - x['cen']) <= tau:
            pairs.append((oidx[k], j)); ui.add(oidx[k]); uj.add(j)
    I = [i for i in range(len(old)) if i not in ui]; J = [j for j in range(len(new)) if j not in uj]
    return pairs + review_geometry(old, new, I, J, tau, margin)

# ---------- controlled revision writer ----------
def make_revision(src_path, regen, rng, move_frac=0.30, move_m=0.12):
    """Write a revised IFC. Returns (new_path, truth new_gid->old_gid, moved set of new_gid)."""
    f = ifcopenshell.open(src_path)
    truth, moved = {}, set()
    for e in f.by_type('IfcElement'):
        old_gid = e.GlobalId
        # small controlled move on a fraction (an 'updated' target), within the 0.5 m gate
        if getattr(e, 'ObjectPlacement', None) and rng.random() < move_frac:
            d = (rng.standard_normal(2) * move_m)
            ax = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((float(d[0]), float(d[1]), 0.0)), None, None)
            e.ObjectPlacement = f.createIfcLocalPlacement(e.ObjectPlacement, ax)
            is_moved = True
        else:
            is_moved = False
        if regen:
            e.GlobalId = ifcopenshell.guid.new()
        truth[e.GlobalId] = old_gid
        if is_moved: moved.add(e.GlobalId)
    # regenerate ids on all other rooted objects too, so nothing leaks a stable id
    if regen:
        for r in f.by_type('IfcRoot'):
            if not r.is_a('IfcElement'):
                r.GlobalId = ifcopenshell.guid.new()
    fd, new_path = tempfile.mkstemp(suffix='.ifc'); os.close(fd)
    f.write(new_path)
    return new_path, truth, moved

# ---------- method adapters: each returns predicted {new_gid: old_gid} over a common id space ----------
def run_it2(old_path, new_path, matcher):
    O = load_features(extract_features(ifcopenshell.open(old_path)))
    N = load_features(extract_features(ifcopenshell.open(new_path)))
    pairs = matcher(O, N)
    pred = {N[j]['g']: O[i]['g'] for i, j in pairs}
    return pred, {x['g'] for x in N}, {x['g'] for x in O}

def run_bimdelta(old_path, new_path):
    import bimdelta_core as B
    r = B.run_diff(old_path, 'old.ifc', new_path, 'new.ifc')
    pred = {}
    for e in r.elements:
        if e.change_type in (B.ChangeType.MODIFIED, B.ChangeType.UNCHANGED):
            # UNCHANGED => matched by identical GlobalId; MODIFIED => matched_global_id is the old id
            pred[e.global_id] = e.matched_global_id if e.matched_global_id else e.global_id
    return pred

def run_ifcdiff(old_path, new_path):
    # IfcDiff matches elements by GlobalId; its added/deleted sets are the GlobalId set difference.
    # Validated against the tool on Duplex Plumbing (stable: 0 added / 504 common; regenerated:
    # 504 added / 0 common), so correspondence equals the GlobalId intersection, computed directly
    # here to avoid the tool's geometry change-classification, which does not affect id-based recovery.
    oldf = ifcopenshell.open(old_path); newf = ifcopenshell.open(new_path)
    old_ids = {e.GlobalId for e in oldf.by_type('IfcElement')}
    return {e.GlobalId: e.GlobalId for e in newf.by_type('IfcElement') if e.GlobalId in old_ids}

# ---------- scoring on common denominator ----------
def score(pred, truth, common_new, moved):
    surv = [g for g in truth if g in common_new]                   # true survivors IT2 can see
    tp = sum(1 for g in surv if pred.get(g) == truth[g])
    predicted = {g: pred[g] for g in pred if g in common_new}      # restrict to common space
    correct = sum(1 for g, o in predicted.items() if truth.get(g) == o)
    precision = correct / len(predicted) if predicted else 1.0
    recall = tp / len(surv) if surv else 0.0
    mv = [g for g in moved if g in common_new]
    moved_rec = sum(1 for g in mv if pred.get(g) == truth[g]) / len(mv) if mv else float('nan')
    unresolved = sum(1 for g in surv if g not in pred) / len(surv) if surv else 0.0
    return dict(precision=precision, recall=recall, moved_recovery=moved_rec, unresolved=unresolved,
                n_surv=len(surv), n_moved=len(mv))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--models', default='Duplex_Plumbing')
    ap.add_argument('--seeds', type=int, default=1); ap.add_argument('--start', type=int, default=3000)
    a = ap.parse_args()
    models = a.models.split(','); seeds = range(a.start, a.start + a.seeds)
    for mk in models:
        src = str(IFC / MODELS[mk])
        for regen in (False, True):
            agg = {m: [] for m in ('it2_review', 'bimdelta', 'ifcdiff')}
            for s in seeds:
                npath, truth, moved = make_revision(src, regen, np.random.default_rng(s))
                try:
                    pr, cn, co = run_it2(src, npath, review_full)
                    agg['it2_review'].append(score(pr, truth, cn, moved))
                    agg['bimdelta'].append(score(run_bimdelta(src, npath), truth, cn, moved))
                    agg['ifcdiff'].append(score(run_ifcdiff(src, npath), truth, cn, moved))
                finally:
                    os.unlink(npath)
            cond = 'REGENERATED ids' if regen else 'STABLE ids'
            print(f"\n== {mk}  [{cond}]  (seeds {a.start}-{a.start+a.seeds-1}) ==")
            print(f"  {'method':12s} {'precision':>9s} {'recall':>7s} {'moved_rec':>9s} {'unresolved':>10s}")
            for m, rows in agg.items():
                f = lambda k: np.nanmean([r[k] for r in rows])
                print(f"  {m:12s} {f('precision')*100:8.1f} {f('recall')*100:7.1f} {f('moved_recovery')*100:9.1f} {f('unresolved')*100:9.1f}")

if __name__ == '__main__':
    main()
