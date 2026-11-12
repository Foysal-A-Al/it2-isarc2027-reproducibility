"""Extends 09_stress_reconstruction.py to emit precision, recall, wrong-pairs/survivor
and unresolved-survivor fraction for each method on the two reconstructed stress scenarios,
for the manuscript's comprehensive comparator table. Same driver, seeds and models."""
import json, csv, hashlib
from collections import Counter, defaultdict
import numpy as np
from scipy.optimize import linear_sum_assignment
from _common import IFC, FEAT, RES, IDENTITY_MODELS, dump
import ifcopenshell
import it2.review_matching as rm
rm.MAX_CELLS = 10 ** 8
from it2.graph import build_graph
from it2.features import load_features
from it2.matching import perturb, score, match_hybrid
from it2.review_matching import review_geometry

SEEDS = range(1000, 1020); MODELS = IDENTITY_MODELS

def wl(adj, lab, rounds=2):
    for _ in range(rounds):
        lab = {v: hashlib.sha1((lab[v] + '|' + ','.join(sorted(lab[u] for u in adj.get(v, ())))).encode()).hexdigest()[:12] for v in lab}
    return lab
def signatures(model):
    g = build_graph(ifcopenshell.open(str(IFC / f'{model}.ifc')))
    s = wl(g['adjacency'], {e.id(): e.is_a() for e in g['elements']})
    out = {}
    for e in g['elements']: out.setdefault(e.GlobalId, s[e.id()])
    return out
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
def sig_geo(old, new, gate=.5):
    go, gn = defaultdict(list), defaultdict(list)
    for i, x in enumerate(old): go[x['sig']].append(i)
    for j, y in enumerate(new): gn[y['sig']].append(j)
    P = []
    for s, A in go.items():
        B = gn.get(s, [])
        if not A or not B: continue
        Pa = np.array([old[i]['cen'] for i in A]); Pb = np.array([new[j]['cen'] for j in B])
        C = np.linalg.norm(Pa[:, None] - Pb[None, :], axis=2)
        if len(A) * len(B) <= 6_000_000:
            Da = np.array([old[i]['dim'] for i in A]); Db = np.array([new[j]['dim'] for j in B])
            C = C + np.abs(Da[:, None] - Db[None, :]).sum(2)
        r, c = linear_sum_assignment(C); P += [(A[a], B[b]) for a, b in zip(r, c) if C[a, b] <= gate]
    return P
def wps(pairs, truth):
    tp = sum(1 for i, j in pairs if truth.get(j) == i)
    return (len(pairs) - tp) / len(truth) if truth else 0.0
def unresolved(pairs, truth):
    resolved = {j for i, j in pairs}
    return sum(1 for j in truth if j not in resolved) / len(truth) if truth else 0.0
def shuffle(new, truth, rng):
    o = rng.permutation(len(new)); return [new[k] for k in o], {p: truth[o[p]] for p in range(len(new)) if o[p] in truth}
def build(scn, X, rng):
    if scn == 'combined': new, truth = perturb(X, rng, recreate=0.5, move=0.30, sigma=0.3, noise=0.005)
    else: new, truth = perturb(X, rng, 0.3)
    surv = [j for j in range(len(new)) if j in truth]
    if scn == 'combined':
        for j in surv:
            if rng.random() < 0.40: new[j] = dict(new[j], typ='U%d' % rng.integers(10 ** 9))
        for j in surv:
            if rng.random() < 0.30:
                d = np.array(new[j]['dim'], float); k = int(rng.integers(3)); d[k] *= (0.8 if rng.random() < 0.5 else 1.2); new[j] = dict(new[j], dim=d)
        for j in surv:
            if rng.random() < 0.20: new[j] = dict(new[j], cont='C%d' % rng.integers(10 ** 9))
    if scn in ('combined', 'coincident_decoys'):
        new.extend(dict(new[j], tag='D%d' % rng.integers(10 ** 12)) for j in surv if rng.random() < 0.10)
    return shuffle(new, truth, rng)

def main():
    XS = {}
    for m in MODELS:
        X = load_features(json.load(open(FEAT / f'{m}.json'))); bg = signatures(m)
        for x in X: x['sig'] = bg.get(x['g'], x['cls'])
        XS[m] = X
    methods = {'review': review_full, 'hybrid': match_hybrid, 'sig_geo': sig_geo}
    out = {'seeds': list(SEEDS), 'models': MODELS, 'scenarios': {}}
    for scn in ['combined', 'coincident_decoys']:
        acc = {nm: dict(P=[], R=[], W=[], U=[]) for nm in methods}
        for m in MODELS:
            for s in SEEDS:
                new, truth = build(scn, XS[m], np.random.default_rng(s))
                for nm, fn in methods.items():
                    p = fn(XS[m], new); P, R, _ = score(p, truth)
                    acc[nm]['P'].append(P); acc[nm]['R'].append(R); acc[nm]['W'].append(wps(p, truth)); acc[nm]['U'].append(unresolved(p, truth))
        out['scenarios'][scn] = {nm: dict(precision=float(np.mean(a['P'])), recall=float(np.mean(a['R'])),
                                          wrong_per_survivor=float(np.mean(a['W'])), unresolved=float(np.mean(a['U']))) for nm, a in acc.items()}
        print(f"== {scn} ==")
        for nm in methods:
            e = out['scenarios'][scn][nm]
            print(f"  {nm:8s} P={e['precision']*100:6.2f}  R={e['recall']*100:6.2f}  wrong/surv={e['wrong_per_survivor']*100:5.2f}  unresolved={e['unresolved']*100:5.2f}")
    dump(out, RES / 'comparator_full.json'); print('wrote', RES / 'comparator_full.json')

if __name__ == '__main__': main()
