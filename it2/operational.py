"""Feasible partial assignments and candidate evidence for the operational checker.

The published experimental matcher in matching.py is intentionally unchanged.
"""
from collections import defaultdict
import math
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import min_weight_full_bipartite_matching

from .runtime import LIMITS
MAX_CELLS = LIMITS.assignment_cells

def validate_parameters(tau, lam):
    if not math.isfinite(tau) or not math.isfinite(lam) or tau < 0 or lam < 0:
        raise ValueError('Matching gate and name weight must be finite and non-negative.')

def _cost(old, new):
    a = np.asarray([x['cen'] for x in old], dtype=float)
    b = np.asarray([x['cen'] for x in new], dtype=float)
    da = np.asarray([x['dim'] for x in old], dtype=float)
    db = np.asarray([x['dim'] for x in new], dtype=float)
    if not all(np.isfinite(x).all() for x in (a,b,da,db)):
        raise ValueError('Matching fingerprints must contain finite coordinates and dimensions.')
    return np.linalg.norm(a[:,None,:]-b[None,:,:],axis=2) + np.abs(da[:,None,:]-db[None,:,:]).sum(2)

def _matrix(old,new,A,B,lam):
    cost = _cost([old[i] for i in A],[new[j] for j in B])
    cost += lam * (np.asarray([old[i]['typ'] for i in A],dtype=object)[:,None] !=
                   np.asarray([new[j]['typ'] for j in B],dtype=object)[None,:])
    return cost

def _groups(old,new,I,J):
    groups=defaultdict(lambda:([],[]))
    for i in I:
        groups[(old[i]['cls'],old[i]['cont'])][0].append(i)
    for j in J:
        groups[(new[j]['cls'],new[j]['cont'])][1].append(j)
    return groups.values()

def _budget(A,B):
    if len(A)*len(B) > MAX_CELLS:
        raise ValueError('Unmatched class/container partition exceeds the safe 2,000,000-cell assignment budget. Compare a smaller exported system; no partial results were substituted.')

def gated_assignment(old,new,I,J,tau,lam):
    """Maximum feasible cardinality, then minimum cost, within class/container.

    A private dummy column for each earlier element permits rejection. Its cost
    dominates all feasible costs, so a cheap invalid pair can never displace a
    feasible match. Sparse dummy edges avoid an N-by-N dummy matrix.
    """
    validate_parameters(tau,lam)
    pairs=[]
    for A,B in _groups(old,new,I,J):
        if not A or not B:
            continue
        _budget(A,B)
        cost=_matrix(old,new,A,B,lam)
        r,c=np.nonzero(cost<=tau)
        penalty=(min(len(A),len(B))+1)*(tau+1)
        rows=np.concatenate([r,np.arange(len(A))])
        cols=np.concatenate([c,len(B)+np.arange(len(A))])
        weights=np.concatenate([cost[r,c]+1,np.full(len(A),penalty)])
        graph=coo_matrix((weights,(rows,cols)),shape=(len(A),len(B)+len(A))).tocsr()
        rr,cc=min_weight_full_bipartite_matching(graph)
        pairs.extend((A[i],B[j]) for i,j in zip(rr,cc) if j<len(B))
    return pairs

def candidate_evidence(old,new,pairs,stages,tau,lam):
    """Show competing geometric candidates and cost margins, never probabilities."""
    validate_parameters(tau,lam)
    exact_old={i for i,j in pairs if stages[(i,j)]!='geometry'}
    exact_new={j for i,j in pairs if stages[(i,j)]!='geometry'}
    chosen={i:j for i,j in pairs if stages[(i,j)]=='geometry'}
    from .review_matching import has_geometry
    evidence=[]
    for A,B in _groups(old,new,[i for i in range(len(old)) if i not in exact_old and has_geometry(old[i])],
                       [j for j in range(len(new)) if j not in exact_new and has_geometry(new[j])]):
        if not A or not B:
            continue
        _budget(A,B)
        cost=_matrix(old,new,A,B,lam)
        pos={j:k for k,j in enumerate(B)}
        for row,i in enumerate(A):
            if i not in chosen:
                continue
            col=pos[chosen[i]]
            alternatives=[float(v) for k,v in enumerate(cost[row]) if k!=col and v<=tau]
            alternatives += [float(v) for k,v in enumerate(cost[:,col]) if k!=row and v<=tau]
            margin=min(alternatives)-float(cost[row,col]) if alternatives else None
            ranked=sorted((float(cost[row,k]),B[k]) for k in range(len(B)) if cost[row,k]<=tau)
            evidence.append(dict(old_index=i,new_index=chosen[i],
                feasible_candidates=len(ranked),margin_m=margin,
                ambiguous=margin is not None and margin<=.05,
                alternatives=[dict(new_index=j,new_GlobalId=new[j]['g'],cost_m=c,
                                   selected=j==chosen[i]) for c,j in ranked[:5]]))
    return evidence
