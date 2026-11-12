"""Fingerprint extraction: class, container, Tag, type name, placement origin, world bounding box."""
import multiprocessing
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.placement as up
import ifcopenshell.util.unit as uu


def extract_features(f, workers=None, include_empty=False):
    """f: an opened ifcopenshell file. Returns a list of dicts, all lengths in metres."""
    # Placements use the IFC length unit; convert them before comparing with metre geometry.
    scale = uu.calculate_unit_scale(f)          # file length unit -> metres (placements)
    D = f.by_type("IfcDistributionElement")
    if not D:
        return []
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)             # geometry is returned in metres
    geo = {}
    # Extract all available distribution-element geometry in parallel.
    it = ifcopenshell.geom.iterator(s, f, workers or multiprocessing.cpu_count(), include=D)
    if it.initialize():
        while True:
            sh = it.get()
            v = np.array(sh.geometry.verts).reshape(-1, 3)
            # World-coordinate extrema define an axis-aligned box for the matching fingerprint.
            if len(v):
                geo[sh.id] = (v.min(0), v.max(0))
            if not it.next():
                break
    out = []
    for e in D:
        # Skip elements without returned geometry; they cannot enter geometry-based matching.
        if e.id() not in geo:
            if include_empty:
                c = ue.get_container(e)
                name = e.Name or ''
                out.append(dict(g=e.GlobalId, cls=e.is_a(), cont=c.GlobalId if c else '',
                                tag=e.Tag or '', typ=name.rsplit(':',1)[0] if ':' in name else name,
                                cen=None, dim=None, pl=None, has_geometry=False, step_id=e.id()))
            continue
        lo, hi = geo[e.id()]
        c = ue.get_container(e)
        name = e.Name or ""
        # Resolve nested placements, then convert units. A missing placement uses the box centre.
        pl = up.get_local_placement(e.ObjectPlacement)[:3, 3] * scale if e.ObjectPlacement else (lo + hi) / 2
        # Store identifier/key fields alongside the centre, sorted dimensions and placement.
        # Revit instance suffixes are removed from the Name to obtain the type-name cue.
        out.append(dict(
            g=e.GlobalId, cls=e.is_a(), cont=c.GlobalId if c else "", tag=e.Tag or "",
            typ=name.rsplit(":", 1)[0] if ":" in name else name,
            cen=((lo + hi) / 2).tolist(), dim=sorted((hi - lo).tolist()), pl=[float(x) for x in pl],
        ))
    if include_empty:
        from collections import defaultdict
        # Match geometry records back to STEP ids even when GUIDs repeat.
        groups = defaultdict(list)
        for e in D:
            if e.id() in geo: groups[e.GlobalId].append(e.id())
        for x in out:
            if 'has_geometry' not in x:
                x.update(has_geometry=True, step_id=groups[x['g']].pop(0))
    return out


def extract_inventory(f, workers=None):
    """Every distribution element is eligible for exact-key checks, with or without shape."""
    try:
        return extract_features(f, workers=workers, include_empty=True)
    except (RuntimeError, ValueError) as exc:
        out=[]
        for e in f.by_type('IfcDistributionElement'):
            c=ue.get_container(e);name=e.Name or ''
            out.append(dict(g=e.GlobalId,cls=e.is_a(),cont=c.GlobalId if c else '',tag=e.Tag or '',
                            typ=name.rsplit(':',1)[0] if ':' in name else name,cen=None,dim=None,pl=None,
                            has_geometry=False,step_id=e.id(),geometry_error=str(exc)))
        return out


def load_features(records):
    """Convert list-valued fields to numpy arrays (in place) and return the list."""
    # JSON stores vectors as lists; numerical matchers need NumPy arrays for arithmetic.
    for x in records:
        for field in ("cen", "dim", "pl"):
            if x.get(field) is not None:
                x[field] = np.asarray(x[field], float)
    return records
