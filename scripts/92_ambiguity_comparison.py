"""Ambiguity comparison: IT2 (review-aware, abstaining) vs BIMDelta Core, on IFC revision pairs
containing coincident same-Tag decoys under regenerated GlobalIds. A decoy is a near-coincident
copy of a real element, with the same Tag and no true predecessor, so matching it to any old
element is a wrong match. This tests whether IT2's rejection policy avoids wrong matches where a
forced matcher does not, and MEASURES BIMDelta's actual behaviour (forced match vs abstention)
rather than assuming it. Also reports IfcDiff for reference (GlobalId-based)."""
import os, sys, tempfile, argparse
import numpy as np
import ifcopenshell, ifcopenshell.guid, ifcopenshell.api
import ifcopenshell.util.element as ue
from collections import Counter
from _common import IFC
from it2.features import extract_features, load_features
import it2.review_matching as rm
rm.MAX_CELLS = 10 ** 8
from it2.review_matching import review_geometry

MODELS = {'Duplex_Plumbing': 'Duplex_Plumbing_20121113.ifc', 'Duplex_MEP': 'Duplex_MEP_20110907.ifc'}

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

def translate(f, e, rng, m):
    d = rng.standard_normal(2) * m
    ax = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((float(d[0]), float(d[1]), 0.0)), None, None)
    e.ObjectPlacement = f.createIfcLocalPlacement(e.ObjectPlacement, ax)

def make_ambiguous(src, rng, move_frac=0.30, decoy_frac=0.12, move_m=0.12):
    f = ifcopenshell.open(src)
    base = [e for e in f.by_type('IfcElement') if e.Representation and e.ObjectPlacement]
    old_gid = {e.id(): e.GlobalId for e in base}
    moved_elems = set()
    for e in base:
        if rng.random() < move_frac:
            translate(f, e, rng, move_m); moved_elems.add(e.id())
    decoy_ids = []
    nd = int(len(base) * decoy_frac)
    for i in rng.permutation(len(base))[:nd]:
        s = base[i]
        d = ue.copy_deep(f, s); d.Tag = s.Tag
        translate(f, d, rng, 0.03)                                  # near-coincident
        cont = ue.get_container(s)
        if cont:
            try: ifcopenshell.api.run('spatial.assign_container', f, products=[d], relating_structure=cont)
            except Exception: pass
        decoy_ids.append(d.id())
    for r in f.by_type('IfcRoot'):
        r.GlobalId = ifcopenshell.guid.new()
    truth = {e.GlobalId: old_gid[e.id()] for e in base}
    moved = {e.GlobalId for e in base if e.id() in moved_elems}
    decoys = {f.by_id(i).GlobalId for i in decoy_ids}
    fd, p = tempfile.mkstemp(suffix='.ifc'); os.close(fd); f.write(p)
    return p, truth, moved, decoys

def run_it2(old_path, new_path):
    O = load_features(extract_features(ifcopenshell.open(old_path)))
    N = load_features(extract_features(ifcopenshell.open(new_path)))
    pairs = review_full(O, N)
    return {N[j]['g']: O[i]['g'] for i, j in pairs}, {x['g'] for x in N}

def run_bimdelta(old_path, new_path):
    import bimdelta_core as B
    r = B.run_diff(old_path, 'old.ifc', new_path, 'new.ifc')
    pred, cls = {}, {}
    for e in r.elements:
        cls[e.global_id] = (str(e.change_type).split('.')[-1], str(e.match_method).split('.')[-1] if e.match_method else None)
        if e.change_type in (B.ChangeType.MODIFIED, B.ChangeType.UNCHANGED):
            pred[e.global_id] = e.matched_global_id if e.matched_global_id else e.global_id
    return pred, cls

def score(pred, truth, decoys, moved, common):
    T = [g for g in truth if g in common]                       # true survivors
    D = [g for g in decoys if g in common]                      # decoys (no predecessor)
    predc = {g: o for g, o in pred.items() if g in common}
    correct = sum(1 for g in T if predc.get(g) == truth[g])
    wrong = sum(1 for g, o in predc.items()
                if (g in decoys) or (g in truth and o != truth[g]))
    recall = correct / len(T) if T else 0.0
    precision = correct / len(predc) if predc else 1.0
    wrong_per_surv = wrong / len(T) if T else 0.0
    decoy_falselink = sum(1 for g in D if g in pred) / len(D) if D else 0.0
    mv = [g for g in moved if g in common]
    moved_rec = sum(1 for g in mv if predc.get(g) == truth[g]) / len(mv) if mv else float('nan')
    unresolved = sum(1 for g in T if g not in pred) / len(T) if T else 0.0
    return dict(precision=precision, recall=recall, wrong_per_surv=wrong_per_surv,
                decoy_falselink=decoy_falselink, moved_rec=moved_rec, unresolved=unresolved,
                n_surv=len(T), n_decoy=len(D))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--models', default='Duplex_Plumbing')
    ap.add_argument('--seeds', type=int, default=3); ap.add_argument('--start', type=int, default=4000)
    a = ap.parse_args()
    for mk in a.models.split(','):
        src = str(IFC / MODELS[mk]); agg = {'it2_review': [], 'bimdelta': []}; bdbehav = Counter()
        for s in range(a.start, a.start + a.seeds):
            npath, truth, moved, decoys = make_ambiguous(src, np.random.default_rng(s))
            try:
                pit, common = run_it2(src, npath)
                agg['it2_review'].append(score(pit, truth, decoys, moved, common))
                pbd, cls = run_bimdelta(src, npath)
                agg['bimdelta'].append(score(pbd, truth, decoys, moved, common))
                for g in decoys:                                  # measure BIMDelta behaviour on decoys
                    if g in cls: bdbehav[cls[g][0]] += 1
            finally:
                os.unlink(npath)
        print(f"\n== {mk}  [regenerated ids + coincident same-Tag decoys]  (seeds {a.start}-{a.start+a.seeds-1}) ==")
        n = agg['it2_review'][0]; print(f"  survivors~{n['n_surv']}, decoys~{n['n_decoy']}")
        print(f"  {'method':12s} {'prec':>6s} {'recall':>7s} {'wrong/surv':>10s} {'decoy_falselink':>16s} {'unresolved':>11s}")
        for m, rows in agg.items():
            g = lambda k: np.nanmean([r[k] for r in rows])
            print(f"  {m:12s} {g('precision')*100:6.1f} {g('recall')*100:7.1f} {g('wrong_per_surv')*100:10.2f} {g('decoy_falselink')*100:16.1f} {g('unresolved')*100:10.1f}")
        tot = sum(bdbehav.values())
        print(f"  BIMDelta decoy classification: " + ", ".join(f"{k}={v} ({100*v/tot:.0f}%)" for k, v in bdbehav.most_common()))

if __name__ == '__main__':
    main()
