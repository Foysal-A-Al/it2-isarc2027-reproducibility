"""Operational safeguards; the published experimental matching functions are unchanged."""
from collections import Counter
import hashlib
from pathlib import Path
from .storage import save_upload, clear_session_uploads  # Backward-compatible public imports.
from .matching import DEFAULT_LAMBDA, DEFAULT_TAU
from .operational import gated_assignment, validate_parameters


def reconcile(old, new, lam=DEFAULT_LAMBDA, tau=DEFAULT_TAU, method="operational-v1", margin=.03):
    """Accept unique exact keys, then use feasible partial geometric assignment.

    Duplicate GlobalIds and Tags never select an arbitrary exact-key successor.
    Geometry may resolve them; remaining candidates enter the review queue.
    """
    from .review_matching import has_geometry, review_geometry
    import math
    validate_parameters(tau, lam)
    if method not in ("operational-v1", "review-v2"):
        raise ValueError("Unknown matching method.")
    if not math.isfinite(margin) or margin < 0:
        raise ValueError("Ambiguity margin must be finite and non-negative.")
    pairs, stage = [], {}
    used_old, used_new = set(), set()
    for label, key in [('globalid', lambda x: ('', x.get('g', ''))),
                       ('tag', lambda x: (x['cls'], x.get('tag', '')))]:
        # Count duplicates over the complete version, including already matched elements.
        a = Counter(key(x) for x in old if key(x)[1])
        b = Counter(key(x) for x in new if key(x)[1])
        index = {key(x): i for i, x in enumerate(old)
                 if key(x)[1] and a[key(x)] == 1 and i not in used_old}
        for j, x in enumerate(new):
            k = key(x)
            i = index.get(k)
            if j not in used_new and i is not None and b[k] == 1 and i not in used_old and old[i]['cls'] == x['cls']:
                if method == 'review-v2' and label == 'tag' and has_geometry(old[i]) and has_geometry(x):
                    import numpy as np
                    if np.linalg.norm(old[i]['cen']-x['cen']) > tau:
                        continue
                pair = (i, j)
                pairs.append(pair)
                stage[pair] = label
                used_old.add(i)
                used_new.add(j)
    remaining_old = [i for i in range(len(old)) if i not in used_old and has_geometry(old[i])]
    remaining_new = [j for j in range(len(new)) if j not in used_new and has_geometry(new[j])]
    a = Counter((old[i]['cls'], old[i]['cont']) for i in remaining_old)
    b = Counter((new[j]['cls'], new[j]['cont']) for j in remaining_new)
    if max((n * b[k] for k, n in a.items()), default=0) > 8_000_000:
        raise ValueError('The unmatched class/container partition exceeds the safe dense-assignment budget. Compare a smaller exported system or use a larger-memory research environment. No partial matches were substituted.')
    geometry_pairs = (review_geometry(old,new,remaining_old,remaining_new,tau,margin) if method == 'review-v2'
                      else gated_assignment(old,new,remaining_old,remaining_new,tau,lam))
    for pair in geometry_pairs:
        pairs.append(pair)
        stage[pair] = 'geometry'
    return pairs, stage


GLOBALID_CHANGED_TAG_STABLE = 'GLOBALID_CHANGED_TAG_STABLE'
DUPLICATE_TAG_NOT_MATCHED = 'DUPLICATE_TAG_NOT_MATCHED'


def identity_findings(old, new, pairs, stages):
    """Name identity events that a reviewer should see, without changing any match.

    GLOBALID_CHANGED_TAG_STABLE: a unique (class, Tag) key carried the element across a GlobalId change.
    DUPLICATE_TAG_NOT_MATCHED: a (class, Tag) key repeats in a version, so reconcile never used it.
    """
    findings = []
    for i, j in pairs:
        a, b = old[i], new[j]
        if stages.get((i, j)) == 'tag' and a.get('g') and b.get('g') and a['g'] != b['g']:
            findings.append(dict(code=GLOBALID_CHANGED_TAG_STABLE, ifc_class=a['cls'], tag=a['tag'],
                                 old_index=i, new_index=j, old_GlobalId=a['g'], new_GlobalId=b['g']))
    for version, records in (('earlier', old), ('later', new)):
        groups = {}
        for i, x in enumerate(records):
            if x.get('tag'):
                groups.setdefault((x['cls'], x['tag']), []).append(i)
        for (cls, tag), members in groups.items():
            if len(members) > 1:
                findings.append(dict(code=DUPLICATE_TAG_NOT_MATCHED, version=version, ifc_class=cls,
                                     tag=tag, indices=members))
    return findings


def key_diagnostics(records):
    """Count elements affected by ambiguous exact keys for transparent user review."""
    out = {}
    for field in ('g', 'tag'):
        counts = Counter((x['cls'] if field == 'tag' else '', x.get(field)) for x in records if x.get(field))
        out[field] = sum(n for n in counts.values() if n > 1)
    return out


def snapshot_manifest(root):
    """Portable hashes of saved study outputs and supplied fingerprints."""
    root = Path(root)
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('results', 'figures', 'data/features')
            for p in sorted((root / folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}
