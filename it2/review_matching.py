"""Review-aware heuristic matching from the manuscript's exploratory validation.

Established partial assignment and abstention, not a novel solver or probability.
The source geometry gate and ambiguity margin are study choices in metres.
"""
from collections import defaultdict
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import min_weight_full_bipartite_matching
from .operational import MAX_CELLS


def has_geometry(x):
    return all(x.get(k) is not None and np.shape(x[k]) == (3,) and np.isfinite(x[k]).all() for k in ('cen', 'dim'))


def review_cost(old, new, I, J):
    a, b = [old[i] for i in I], [new[j] for j in J]
    ca, cb = np.array([x['cen'] for x in a]), np.array([x['cen'] for x in b])
    da, db = np.array([x['dim'] for x in a]), np.array([x['dim'] for x in b])
    cost = np.linalg.norm(ca[:,None,:] - cb[None,:,:], axis=2)
    shape = np.abs(np.log(np.maximum(da,.001))[:,None,:] - np.log(np.maximum(db,.001))[None,:,:]).sum(2)
    cost += .1 * np.minimum(shape,3.)
    ta, tb = np.array([x['typ'] for x in a],object), np.array([x['typ'] for x in b],object)
    knowna, knownb = np.array([x in set(tb) for x in ta]), np.array([x in set(ta) for x in tb])
    cost += .15 * ((ta[:,None] != tb[None,:]) & knowna[:,None] & knownb[None,:])
    cost += .05 * (np.array([x['cont'] for x in a],object)[:,None] != np.array([x['cont'] for x in b],object)[None,:])
    return cost


def partial_pairs(cost, tau):
    n,m = cost.shape
    r,c = np.nonzero(np.isfinite(cost) & (cost <= tau))
    if not len(r):
        return []
    penalty = (min(n,m)+1)*(tau+1)
    graph = coo_matrix((np.concatenate([cost[r,c]+1,np.full(n,penalty)]),
                       (np.concatenate([r,np.arange(n)]),np.concatenate([c,m+np.arange(n)]))),shape=(n,m+n)).tocsr()
    rows,cols = min_weight_full_bipartite_matching(graph)
    return [(int(i),int(j)) for i,j in zip(rows,cols) if j<m]


def review_geometry(old, new, I, J, tau=.5, margin=.03, details=False):
    groups = defaultdict(lambda:([],[]))
    for i in I:
        if has_geometry(old[i]):groups[old[i]['cls']][0].append(i)
    for j in J:
        if has_geometry(new[j]):groups[new[j]['cls']][1].append(j)
    out=[]
    for A,B in groups.values():
        if not A or not B:continue
        if len(A)*len(B)>MAX_CELLS:
            raise ValueError('Review-aware class partition exceeds the 2,000,000-cell budget. Select a smaller system.')
        C=review_cost(old,new,A,B)
        for i,j in partial_pairs(C,tau):
            row=np.delete(C[i,:],j);col=np.delete(C[:,j],i)
            gap=min(float(row.min()) if row.size else float('inf'),float(col.min()) if col.size else float('inf'))-float(C[i,j])
            alternatives=sorted((float(v),B[k]) for k,v in enumerate(C[i]) if v<=tau)
            out.append(dict(old_index=A[i],new_index=B[j],cost_m=float(C[i,j]),
                            margin_m=gap if np.isfinite(gap) else None,
                            accepted=gap>max(margin,1e-12),ambiguous=gap<=max(margin,1e-12),
                            feasible_candidates=len(alternatives),
                            alternatives=[dict(new_index=k,new_GlobalId=new[k]['g'],cost_m=v,selected=k==B[j]) for v,k in alternatives[:5]]))
    return out if details else [(r['old_index'],r['new_index']) for r in out if r['accepted']]
