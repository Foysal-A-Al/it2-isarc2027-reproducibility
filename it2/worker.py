"""Isolated, bounded IFC analysis jobs; this module never imports Streamlit.

The parent validates provenance and size. Native IFC code runs in a child process.
Docker remains the hard memory ceiling; this is not a distributed worker service.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import BoundedSemaphore
from .runtime import LIMITS

KINDS = frozenset(('audit', 'inventory', 'features'))
_SLOT = BoundedSemaphore(1)


def _write(target, envelope):
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(envelope, allow_nan=False), encoding='utf-8')
    temporary.replace(target)


def run_ifc_job(path, kind, timeout=LIMITS.worker_seconds):
    """Return computed evidence or an explicit error, never saved example results."""
    if kind not in KINDS:
        raise ValueError('Unknown IFC analysis job.')
    path = Path(path).resolve()
    if not path.is_file() or not 0 < path.stat().st_size <= LIMITS.upload_bytes:
        raise ValueError('IFC input is empty, missing or exceeds the 100 MiB input limit.')
    if timeout <= 0 or timeout > LIMITS.worker_seconds:
        raise ValueError('Worker timeout must be positive and at most 90 seconds.')
    if not _SLOT.acquire(blocking=False):
        raise ValueError('Another IFC analysis is running on this host. Retry after it finishes.')
    try:
        data=path.read_bytes()
        if not 0 < len(data) <= LIMITS.upload_bytes:
            raise ValueError('IFC input changed or exceeded the size budget during submission.')
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory(prefix='it2-analysis-') as folder:
            output = Path(folder)/'result.json'
            snapshot=Path(folder)/'input.ifc'
            snapshot.write_bytes(data)
            del data
            command = [sys.executable, '-m', 'it2.worker', str(snapshot), kind, str(output), digest]
            timed_out = False
            try:
                process = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                timed_out = True
                process = None
            if not output.exists():
                if timed_out:
                    raise TimeoutError(f'IFC analysis exceeded {timeout:g} seconds. No substitute results were produced.')
                raise ValueError('IFC analysis worker failed before producing evidence.')
            if output.stat().st_size > LIMITS.worker_output_bytes:
                raise ValueError('IFC analysis output exceeded the 100 MiB result limit.')
            envelope = json.loads(output.read_text(encoding='utf-8'))
            if envelope.get('version') != 1 or envelope.get('kind') != kind or envelope.get('source_sha256') != digest:
                raise ValueError('IFC analysis provenance or format mismatch.')
            if timed_out and kind == 'inventory' and envelope.get('status') == 'metadata_only':
                for row in envelope['data']:
                    row['geometry_error'] = 'Geometry timed out; exact-key inventory remains available.'
                return envelope['data']
            if timed_out:
                raise TimeoutError(f'IFC analysis exceeded {timeout:g} seconds. No complete result is available.')
            if process.returncode or envelope.get('status') != 'complete':
                raise ValueError(envelope.get('error', 'IFC analysis did not complete.'))
            return envelope['data']
    finally:
        _SLOT.release()


def _main(path, kind, output, digest):
    import ifcopenshell
    import ifcopenshell.util.element as ue
    envelope = dict(version=1, kind=kind, source_sha256=digest, status='failed')
    output = Path(output)
    try:
        f = ifcopenshell.open(path)
        elements = f.by_type('IfcDistributionElement')
        if len(elements) > LIMITS.distribution_elements or len(f.by_type('IfcRelConnectsPorts')) > LIMITS.port_relations:
            raise ValueError('IFC analysis scope exceeds this workstation budget. Export a smaller system.')
        if kind == 'audit':
            from .graph import build_graph
            from .reporting import audit_model
            from .inspection import inspect_model
            graph = build_graph(f)
            result = audit_model(path, opened=f, graph=graph)
            result['inspection'] = inspect_model(path, opened=f, graph=graph)
        elif kind == 'inventory':
            from .features import extract_inventory
            metadata = []
            for e in elements:
                c = ue.get_container(e); name = e.Name or ''
                metadata.append(dict(g=e.GlobalId, cls=e.is_a(), cont=c.GlobalId if c else '',
                                     tag=e.Tag or '', typ=name.rsplit(':',1)[0] if ':' in name else name,
                                     cen=None, dim=None, pl=None, has_geometry=False, step_id=e.id()))
            _write(output, dict(envelope, status='metadata_only', data=metadata))
            result = extract_inventory(f, workers=2)
        else:
            from .features import extract_features
            result = extract_features(f, workers=2)
        _write(output, dict(envelope, status='complete', data=result))
        return 0
    except Exception as exc:
        _write(output, dict(envelope, error=str(exc)[:500]))
        return 1


if __name__ == '__main__':
    if len(sys.argv) != 5 or sys.argv[2] not in KINDS:
        raise SystemExit('Invalid worker invocation.')
    raise SystemExit(_main(*sys.argv[1:]))
