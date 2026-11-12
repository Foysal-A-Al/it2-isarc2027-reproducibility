"""Identity reconciliation: baselines, the two-stage IT2 hybrid matcher, perturbation and scoring."""
import collections
import numpy as np
from scipy.optimize import linear_sum_assignment

DEFAULT_LAMBDA = 0.3   # weight of the type-name disagreement penalty
DEFAULT_TAU = 0.5      # rejection gate in metres


def perturb(X, rng, recreate, move=0.10, sigma=0.15, delete=0.05, add=0.05, noise=0.001):
    """Simulate a model revision. All GlobalIds are regenerated implicitly (never used for matching).

    recreate: share of surviving elements that also receive a new Tag (redrawn / copied elements)
    move, sigma: share of elements moved in plan, and the std of the move in metres
    delete, add: shares of deleted elements and of decoy additions
    Returns (new_records, truth) with truth mapping new index -> old index.
    """
    n = len(X)
    # Decide survival first. Keep the RNG draw order fixed: it defines the published simulations.
    keep = rng.random(n) > delete
    new, truth = [], {}
    for i, o in enumerate(X):
        if not keep[i]:
            continue
        # Start with small measurement noise; selected elements also receive a planar move.
        d = rng.normal(0, noise, 3)
        if rng.random() < move:
            d[:2] += rng.normal(0, sigma, 2)
        # Shift centre and placement together. Dimensions and type names remain unchanged.
        # The g field remains metadata here; METHODS deliberately never matches on GlobalId.
        x = dict(o, cen=o["cen"] + d, pl=o["pl"] + d)
        if rng.random() < recreate:
            x["tag"] = "R%d" % rng.integers(10**12)
        # Ground truth maps each surviving new index back to its original element.
        # Decoy additions below have no entry, so matching them counts as a false positive.
        truth[len(new)] = i
        new.append(x)
    # Add plausible distractors copied from existing classes/containers, with new Tags.
    for _ in range(int(add * n)):
        o = X[rng.integers(n)]
        d = rng.normal(0, 2, 3)
        d[2] = 0
        new.append(dict(o, cen=o["cen"] + d, pl=o["pl"] + d, tag="A%d" % rng.integers(10**12)))
    return new, truth


def _assign(old, new, I, J, mode, gate, lam):
    """Hungarian assignment within (class, container) partitions."""
    pairs = []
    groups = collections.defaultdict(lambda: ([], []))
    # Hard partitions prevent cross-class or cross-container candidates.
    # A real revision that changes either attribute can therefore remain unmatched.
    for i in I:
        groups[(old[i]["cls"], old[i]["cont"])][0].append(i)
    for j in J:
        groups[(new[j]["cls"], new[j]["cont"])][1].append(j)
    key = "cen" if mode == "geo" else "pl"
    for A, B in groups.values():
        if not A or not B:
            continue
        Pa = np.array([old[i][key] for i in A])
        Pb = np.array([new[j][key] for j in B])
        # Pairwise distances are in metres: placement for the baseline, centre for geometry.
        C = np.linalg.norm(Pa[:, None, :] - Pb[None, :, :], axis=2)
        if mode == "geo":
            Da = np.array([old[i]["dim"] for i in A])
            Db = np.array([new[j]["dim"] for j in B])
            # Sorted box dimensions supply a shape cue; they do not encode orientation.
            C = C + np.abs(Da[:, None, :] - Db[None, :, :]).sum(2)
            Ta = np.array([old[i]["typ"] for i in A], dtype=object)
            Tb = np.array([new[j]["typ"] for j in B], dtype=object)
            # A different type-name string adds lambda to the cost; it is a soft penalty.
            C = C + lam * (Ta[:, None] != Tb[None, :])
        # Hungarian assignment minimizes total cost with at most one partner per element.
        # The gate is applied afterwards, so this is not a gated partial-assignment solver.
        r, c = linear_sum_assignment(C)
        pairs += [(A[a], B[b]) for a, b in zip(r, c) if C[a, b] <= gate]
    return pairs


def match_tag(old, new):
    """Baseline: exact (class, Tag) key. Revit writes its ElementId into the IFC Tag."""
    # Exact keys assume unique (class, Tag) values. Duplicate keys need review on other models.
    idx = {(o["cls"], o["tag"]): i for i, o in enumerate(old) if o["tag"]}
    return [(idx[(x["cls"], x["tag"])], j) for j, x in enumerate(new) if (x["cls"], x["tag"]) in idx]


def match_placement(old, new, gate=1.0):
    """Baseline: placement origin only (metres), Hungarian within partitions."""
    return _assign(old, new, range(len(old)), range(len(new)), "pl", gate, 0.0)


def match_hybrid(old, new, lam=DEFAULT_LAMBDA, tau=DEFAULT_TAU, use_tag=True):
    """IT2 matcher: stage 1 exact Tag key, stage 2 bounding-box centre + dimensions + soft type name."""
    p = match_tag(old, new) if use_tag else []
    # Remove elements already recovered by Tag before solving the geometric remainder.
    ui, uj = {i for i, _ in p}, {j for _, j in p}
    # Only unrecovered old/new elements enter the final geometric assignment.
    I = [i for i in range(len(old)) if i not in ui]
    J = [j for j in range(len(new)) if j not in uj]
    return p + _assign(old, new, I, J, "geo", tau, lam)


def score(pairs, truth):
    """Precision, recall and F1 of predicted (old, new) pairs against truth (new -> old)."""
    # A pair is correct only when its new index maps to that old index in the known truth.
    tp = sum(1 for i, j in pairs if truth.get(j) == i)
    # Convention: no predictions gives precision 1, but recall is 0 when truth is nonempty.
    P = tp / len(pairs) if pairs else 1.0
    R = tp / len(truth) if truth else 1.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    return P, R, F


def bootstrap_ci(values, B=2000, seed=0):
    """Mean and 95% percentile bootstrap interval."""
    v = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    # Resample seed-level scores, not IFC elements. This CI describes simulation variation.
    bs = rng.choice(v, (B, len(v))).mean(1)
    return float(v.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


METHODS = {"tag": match_tag, "placement": match_placement, "hybrid": match_hybrid}


def reconcile(old, new, lam=DEFAULT_LAMBDA, tau=DEFAULT_TAU):
    """Full IT2 reconciliation for real use: GlobalId, then Tag, then geometry.

    Returns (pairs, stage) where pairs is a list of (i_old, j_new) and stage maps
    each pair to 'globalid', 'tag' or 'geometry'. Unpaired elements go to review.
    """
    stage = {}
    # Real-use reconciliation starts with unchanged GlobalIds, unlike the paper baselines.
    gi = {o["g"]: i for i, o in enumerate(old) if o.get("g")}
    pairs = []
    for j, x in enumerate(new):
        i = gi.get(x.get("g"))
        if i is not None and old[i]["cls"] == x["cls"]:
            pairs.append((i, j)); stage[(i, j)] = "globalid"
    ui, uj = {i for i, _ in pairs}, {j for _, j in pairs}
    # Exact keys assume unique (class, Tag) values. Duplicate keys need review on other models.
    idx = {(o["cls"], o["tag"]): i for i, o in enumerate(old) if o["tag"] and i not in ui}
    for j, x in enumerate(new):
        if j in uj:
            continue
        i = idx.get((x["cls"], x["tag"])) if x["tag"] else None
        if i is not None and i not in ui:
            pairs.append((i, j)); stage[(i, j)] = "tag"; ui.add(i); uj.add(j)
    # Only unrecovered old/new elements enter the final geometric assignment.
    I = [i for i in range(len(old)) if i not in ui]
    J = [j for j in range(len(new)) if j not in uj]
    for p in _assign(old, new, I, J, "geo", tau, lam):
        pairs.append(p); stage[p] = "geometry"
    return pairs, stage
