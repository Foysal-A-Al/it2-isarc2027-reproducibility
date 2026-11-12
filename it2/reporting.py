"""Evidence reports for arbitrary IFCs, using the paper's existing metric functions."""
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
from html import escape
import importlib.metadata
import io
import json
from pathlib import Path
import zipfile

import ifcopenshell
import ifcopenshell.util.unit
from .topology import topology_metrics, topology_details, _ports_of

METRICS = ('PC', 'CC', 'TF', 'LC', 'SM')
DEFINITIONS = {
    'PC': 'Distribution elements with at least one port / distribution elements',
    'CC': 'Ports participating in an IfcRelConnectsPorts relation / all IFC ports',
    'TF': 'Connected components / distribution elements',
    'LC': 'Distribution elements in largest component / distribution elements',
    'SM': 'Distribution elements assigned to an IfcSystem / distribution elements',
}


def versions():
    from . import __version__
    out = {"it2": __version__}
    for package in ('ifcopenshell', 'numpy', 'scipy', 'streamlit'):
        try:
            out[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            out[package] = 'not installed'
    return out


def audit_model(path, label=None, opened=None, graph=None):
    """Compute auditable metrics; a valid model without MEP is not a zero-score model."""
    path = Path(path)
    f = opened if opened is not None else ifcopenshell.open(str(path))
    from .graph import build_graph, connection_evidence
    graph=graph if graph is not None else build_graph(f)
    elements = graph['elements']
    n = len(elements)
    ids = Counter(x.GlobalId for x in elements if x.GlobalId)
    tags = Counter((x.is_a(), x.Tag) for x in elements if x.Tag)
    owned = {p.id() for x in elements for p in _ports_of(x)}
    ports = f.by_type('IfcPort')
    metrics = topology_metrics(str(path), opened=f, graph=graph) if n else None
    if metrics is not None:
        # Portable display metadata; no change to metric definitions or saved study outputs.
        metrics['file'] = label or path.name
    details = topology_details(str(path), opened=f, graph=graph) if n else []
    connections = connection_evidence(graph)
    counts = Counter(x.is_a() for x in elements)
    missing_ids = sum(not x.GlobalId for x in elements)
    missing_tags = sum(not x.Tag for x in elements)
    findings = []
    if not n:
        findings.append('No IfcDistributionElement instances: MEP topology metrics are not applicable. This may be an architectural model or an export that omits distribution elements.')
    else:
        covered = sum(bool(_ports_of(x)) for x in elements)
        findings.append(f'{covered} of {n} distribution elements expose ports ({metrics["PC"]:.1%}).')
        findings.append(f'{metrics["components"]} exported connected components; {metrics["isolated"]} elements are isolated. The largest contains {metrics["LC"]:.1%} of distribution elements.')
        if metrics['ports'] == 0:
            findings.append('No IFC ports are exported. Connectivity cannot be reconstructed from explicit port connections in this file.')
        elif metrics['CC'] == 0:
            findings.append('Ports exist, but none participate in an exported port connection.')
        if metrics['SM'] > .5 and metrics['PC'] < .5:
            findings.append('System membership is high while port coverage is low. A system label does not establish connectivity.')
        if metrics['PC'] > .5 and metrics['SM'] < .5:
            findings.append('Port coverage is high while system membership is low. Connected components do not establish named-system semantics.')
    duplicate_ids = sum(c for c in ids.values() if c > 1)
    duplicate_tags = sum(c for c in tags.values() if c > 1)
    if duplicate_ids or duplicate_tags:
        findings.append(f'Ambiguous identity keys affect {duplicate_ids} GlobalId occurrences and {duplicate_tags} class/Tag occurrences; inspect before reconciliation.')
    return {
        'kind': 'measured_ifc_topology', 'label': label or path.name,
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'schema': f.schema, 'length_unit_to_metres': float(ifcopenshell.util.unit.calculate_unit_scale(f)),
        'distribution_elements': n, 'metrics': metrics, 'elements': details, 'connections': connections,
        'class_counts': dict(sorted(counts.items())),
        'diagnostics': {'missing_globalids': missing_ids, 'missing_tags': missing_tags,
                        'duplicate_globalid_occurrences': duplicate_ids,
                        'duplicate_class_tag_occurrences': duplicate_tags,
                        'unowned_ports': len(ports) - len(owned)},
        'findings': findings, 'metric_definitions': DEFINITIONS,
        'limits': ['Edges are exported port relations, not inferred proximity.',
                   'Graph connectivity is undirected; it does not prove flow direction or engineering correctness.',
                   'Independent networks can legitimately be separate components.',
                   'Single-file identity continuity and live sensor-binding validity are not measured.'],
        'computed_at_utc': datetime.now(timezone.utc).isoformat(), 'packages': versions(),
    }


def comparison_rows(audits, saved=()):
    """Keep provenance next to every row; never fill uploaded-model cells with paper data."""
    rows = []
    for a in audits:
        m = a['metrics'] or {}
        rows.append(dict(model=a['label'], evidence='Computed from selected IFC',
                         source_sha256=a['source_sha256'], schema=a['schema'],
                         D=a['distribution_elements'], ports=m.get('ports'),
                         components=m.get('components'), isolated=m.get('isolated'),
                         **{k: m.get(k) for k in METRICS}))
    for m in saved:
        rows.append(dict(model=m['file'], evidence='Saved study reference', source_sha256=None,
                         schema=m.get('schema'), D=m['D'], ports=m.get('ports'),
                         components=m['components'], isolated=m.get('isolated'),
                         **{k: m.get(k) for k in METRICS}))
    return rows


def comparison_delta(current, reference):
    """Explicit current-minus-reference differences, including zero and undefined metrics."""
    a, b = current['metrics'], reference['metrics']
    if a is None or b is None:
        return []
    return [dict(metric=k, current=a[k], reference=b[k], difference=a[k] - b[k],
                 unit='ratio' if k in METRICS else 'count',
                 difference_percentage_points=100 * (a[k] - b[k]) if k in METRICS else None)
            for k in ('D', 'ports', 'components', *METRICS)]


def csv_bytes(rows):
    rows = list(rows)
    if not rows:
        return b''
    stream = io.StringIO(newline='')
    columns = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(stream, columns)
    writer.writeheader()
    for row in rows:
        # User IFC labels are untrusted spreadsheet text; avoid formula evaluation in CSV readers.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v
                         for k, v in row.items()})
    return stream.getvalue().encode('utf-8-sig')


def html_report(title, report, tables):
    """Self-contained report with escaped user content and no remote assets or scripts."""
    def table(rows):
        if not rows:
            return '<p>No applicable rows.</p>'
        keys = list(dict.fromkeys(k for row in rows for k in row))
        return '<table><thead><tr>' + ''.join('<th>' + escape(str(k)) + '</th>' for k in keys) + '</tr></thead><tbody>' + ''.join(
            '<tr>' + ''.join('<td>' + escape(str(row.get(k, '') if row.get(k) is not None else 'Not measured')) + '</td>' for k in keys) + '</tr>' for row in rows) + '</tbody></table>'
    body = ''.join('<h2>' + escape(name) + '</h2>' + table(rows) for name, rows in tables.items())
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>' + escape(title) + '</title>'
            '<style>body{font:15px Arial,sans-serif;color:#182b42;background:#f8f7f3;max-width:1200px;margin:40px auto;padding:24px}h1{color:#244e72}table{border-collapse:collapse;background:white;width:100%;font-size:13px}th,td{padding:10px;border:1px solid #dce3eb;text-align:left}pre{white-space:pre-wrap;word-break:break-word;font-size:12px}h2{margin-top:30px}</style>'
            '<h1>' + escape(title) + '</h1>' + body + '<h2>Evidence, settings and limitations</h2><pre>' +
            escape(json.dumps(report, indent=2, allow_nan=False)) + '</pre></html>').encode('utf-8')


def evidence_bundle(title, report, tables, extra_files=None):
    """One ZIP packages a readable HTML report, exact JSON and complete CSV tables."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        html = html_report(title, report, tables)
        if extra_files and 'recall_chart.png' in extra_files:
            html = html.replace(b'</h1>', b'</h1><figure><img alt="Recall by recreated share with seed bootstrap intervals" src="recall_chart.png" style="max-width:100%"></figure>', 1)
        z.writestr('report.html', html)
        z.writestr('evidence.json', json.dumps(report, indent=2, allow_nan=False))
        for filename, content in (extra_files or {}).items():
            if filename not in {'recall_chart.png'}:
                raise ValueError('Unexpected report asset name')
            z.writestr(filename, content)
        for i, (name, rows) in enumerate(tables.items(), 1):
            # Archive entry names are fixed by the app, never by a uploaded filename.
            z.writestr(f'table_{i}.csv', csv_bytes(rows))
    return out.getvalue()


def identity_report(old, new, pairs, stages, sources, lam=.3, tau=.5, truth=None, method="operational-v1", margin=.03):
    """Explain accepted matches and unmatched candidates without inventing real ground truth."""
    import numpy as np
    from .matching import score
    matched_old, matched_new = {i for i, _ in pairs}, {j for _, j in pairs}
    from .operational import candidate_evidence
    from .review_matching import has_geometry, review_geometry
    if method == 'review-v2':
        exact_old={i for i,j in pairs if stages[(i,j)]!='geometry'}
        exact_new={j for i,j in pairs if stages[(i,j)]!='geometry'}
        evidence=review_geometry(old,new,[i for i in range(len(old)) if i not in exact_old],
                                 [j for j in range(len(new)) if j not in exact_new],tau,margin,details=True)
    else:
        evidence=candidate_evidence(old,new,pairs,stages,tau,lam)
    candidates={(r['old_index'],r['new_index']):r for r in evidence}
    mapping = []
    for i, j in pairs:
        a, b = old[i], new[j]
        distance = float(np.linalg.norm(a['cen'] - b['cen'])) if has_geometry(a) and has_geometry(b) else None
        cost = (distance + float(np.abs(a['dim'] - b['dim']).sum()) + lam * (a['typ'] != b['typ'])) if distance is not None else None
        if method == 'review-v2' and stages[(i,j)] == 'geometry':
            cost=candidates[(i,j)]['cost_m']
        suspicious = stages[(i,j)] == 'globalid' and (distance is not None and distance > tau or a.get('typ') != b.get('typ'))
        mapping.append(dict(old_index=i, new_index=j, stage=stages[(i, j)], ifc_class=a['cls'], old_GlobalId=a['g'],
                            new_GlobalId=b['g'], old_tag=a['tag'], new_tag=b['tag'],
                            moved_m=distance, geometric_cost=cost if stages[(i, j)] == 'geometry' else None,
                            requires_review=bool(stages[(i,j)]!='globalid' or suspicious),
                            identity_decision='uncertain' if suspicious else 'not independently verified',
                            suspicion='Retained GlobalId with changed type or displacement beyond the configured gate' if suspicious else None,
                            interpretation='Exact unique key' if stages[(i, j)] != 'geometry' else 'Inferred geometric correspondence; review when consequential'))
    from .checker import identity_findings, GLOBALID_CHANGED_TAG_STABLE
    findings = identity_findings(old, new, pairs, stages)
    flagged = {(f['old_index'], f['new_index']) for f in findings if f['code'] == GLOBALID_CHANGED_TAG_STABLE}
    for row in mapping:
        row['finding'] = GLOBALID_CHANGED_TAG_STABLE if (row['old_index'], row['new_index']) in flagged else None
    for row in mapping:
        row_evidence=candidates.get((row['old_index'],row['new_index']),{})
        row.update({k:row_evidence.get(k) for k in ('feasible_candidates','margin_m','ambiguous','alternatives')})
    review = []
    for label, records, other, used in [('earlier', old, new, matched_old), ('later', new, old, matched_new)]:
        other_groups = {(x['cls'], x['cont']) for x in other}
        tags = Counter((x['cls'], x.get('tag')) for x in records if x.get('tag'))
        gids = Counter(x.get('g') for x in records if x.get('g'))
        for i, x in enumerate(records):
            if i in used:
                continue
            reasons = []
            if (x['cls'], x['cont']) not in other_groups:
                reasons.append('No candidate in the same class/container partition' if method == 'operational-v1' else 'Class/container changed; review mode treats container softly')
            if gids.get(x.get('g'), 0) > 1 or tags.get((x['cls'], x.get('tag')), 0) > 1:
                reasons.append('Duplicate exact key')
            if not has_geometry(x):
                reasons.append('No usable geometry; exact-key checks were still performed')
            reasons.append('No accepted one-to-one match; addition/deletion, ambiguity or cost rejection needs review')
            review.append(dict(version=label, GlobalId=x['g'], ifc_class=x['cls'], container=x['cont'],
                               type=x['typ'], reason='; '.join(reasons)))
    n_guid = sum(v == 'globalid' for v in stages.values())
    return dict(kind='real_revision_reconciliation' if truth is None else 'single_seed_feature_simulation',
                sources=sources, settings=dict(method=method,lambda_name=lam if method=='operational-v1' else None,tau_m=tau,ambiguity_margin_m=margin if method=='review-v2' else None),
                counts=dict(earlier_fingerprints=len(old), later_fingerprints=len(new), accepted_matches=len(pairs),
                            same_globalid=n_guid, recovered_by_tag=sum(v == 'tag' for v in stages.values()),
                            recovered_by_geometry=sum(v == 'geometry' for v in stages.values()),
                            unmatched_earlier=len(old) - len(matched_old), unmatched_later=len(new) - len(matched_new)),
                estimated_continuity=n_guid / len(pairs) if pairs else None,
                simulation_scores=dict(zip(('precision', 'recall', 'f1'), score(pairs, truth))) if truth is not None else None,
                mapping=mapping, review=review, findings=findings, packages=versions(),
                abstained_candidates=[r for r in evidence if r.get('accepted') is False],
                limits=['Estimated continuity uses accepted matches; physical persistence is unknown for real revisions.',
                        'Real-revision precision, recall and correct-binding rates require independently labelled ground truth.',
                        'Method and cost policy are recorded. Review-v2 uses soft containment and abstains on small cost gaps; the original paper baseline is unchanged.',
                        'Identity inventory includes geometry-free elements for exact-key checks; geometric proposals require usable geometry.'])


def resolve_bindings(old_audit, new_audit, mapping, rows, blocked_ids=()):
    """Measure target resolution, not correctness, for an actual supplied point list."""
    if not rows or any(not x.get('point_id') or not x.get('GlobalId') for x in rows):
        raise ValueError('Provide a non-empty CSV with point_id and GlobalId on every row.')
    if len({x['point_id'] for x in rows}) != len(rows):
        raise ValueError('point_id must be unique; review duplicate point identifiers.')
    old_ids = Counter(x['GlobalId'] for x in old_audit['elements'])
    new_ids = Counter(x['GlobalId'] for x in new_audit['elements'])
    blocked_ids=set(blocked_ids) | {x['old_GlobalId'] for x in mapping if x.get('suspicion') and not x.get('review_approved')}
    old_classes={x['GlobalId']:x.get('ifc_class') for x in old_audit['elements']}
    new_classes={x['GlobalId']:x.get('ifc_class') for x in new_audit['elements']}
    blocked_ids |= {g for g in old_classes.keys() & new_classes.keys() if old_classes[g] != new_classes[g]}
    successors = {x['old_GlobalId']: x['new_GlobalId'] for x in mapping if old_ids[x['old_GlobalId']] == 1}
    resolved = []
    for x in rows:
        g = x['GlobalId']
        before = old_ids[g] == 1 and new_ids[g] == 1
        successor = g if before else successors.get(g)
        after = bool(successor and new_ids[successor] == 1 and old_ids[g] == 1 and g not in blocked_ids)
        status = 'Earlier target missing or ambiguous' if old_ids[g] != 1 else (
                 'Unchanged target resolves' if before else 'Inferred rebinding: review required' if after else 'No resolved successor')
        if g in blocked_ids:
            status='Retained identifier requires an explicit same-asset review'
        resolved.append(dict(point_id=x['point_id'], old_GlobalId=g, new_GlobalId=successor if after else None,
                             earlier_resolves=old_ids[g] == 1, later_resolves_without_rebinding=before,
                             later_resolves_after_mapping=after, status=status))
    return dict(kind='supplied_point_list_target_resolution', point_count=len(rows),
                resolution_before=sum(x['later_resolves_without_rebinding'] for x in resolved) / len(rows),
                resolution_after=sum(x['later_resolves_after_mapping'] for x in resolved) / len(rows),
                rows=resolved, interpretation='Syntactic target resolution in distribution-element scope; physical correctness and live BMS quality are not established.')
