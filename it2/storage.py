"""Bounded, content-addressed session upload storage; no UI or matcher dependencies."""
import hashlib
from pathlib import Path
import tempfile


def save_upload(upload, max_bytes=None, namespace=None):
    """Address uploaded IFC bytes by hash; never use a client filename as a path."""
    from .runtime import LIMITS
    limit=LIMITS.upload_bytes if max_bytes is None else max_bytes
    buffer=upload.getbuffer()
    size=getattr(buffer,'nbytes',len(buffer))
    if not 0 < size <= limit:
        raise ValueError('IFC upload is empty or exceeds the permitted size.')
    data = bytes(buffer)
    digest = hashlib.sha256(data).hexdigest()
    folder = Path(tempfile.gettempdir()) / 'it2-uploads'
    folder.mkdir(exist_ok=True)
    if namespace is not None:
        import re
        if not isinstance(namespace,str) or not re.fullmatch(r'[a-f0-9]{32}',namespace):
            raise ValueError('Invalid upload session namespace.')
        folder=folder/namespace
        if folder.is_symlink():
            raise ValueError('Invalid upload session directory.')
        folder.mkdir(exist_ok=True,mode=0o700)
        used=sum(p.stat().st_size for p in folder.glob('*.ifc') if p.is_file())
        if not (folder/(digest+'.ifc')).exists() and used+size>300*1024*1024:
            raise ValueError('Session upload budget of 300 MiB reached. Clear this session in Settings before uploading more files.')
    path = folder / (digest + '.ifc')
    if not path.exists():
        # Atomic replacement prevents concurrent sessions from reading an incomplete IFC.
        with tempfile.NamedTemporaryFile(dir=folder, delete=False, suffix='.tmp') as stream:
            stream.write(data)
            temporary = Path(stream.name)
        temporary.replace(path)
    return str(path)


def clear_session_uploads(namespace):
    """Delete one validated session directory; never clear other users' uploads."""
    import re
    import shutil
    if not isinstance(namespace,str) or not re.fullmatch(r'[a-f0-9]{32}',namespace):
        raise ValueError('Invalid upload session namespace.')
    folder=Path(tempfile.gettempdir())/'it2-uploads'/namespace
    if folder.is_symlink():
        raise ValueError('Invalid upload session directory.')
    if folder.exists():
        shutil.rmtree(folder)


def read_csv_upload(upload, required_columns, max_bytes=5*1024*1024, max_rows=100_000):
    """Bound CSV input before parsing; reject ambiguous headers and ragged rows."""
    import csv
    import io
    buffer=upload.getbuffer()
    if not 0 < getattr(buffer,'nbytes',len(buffer)) <= max_bytes:
        raise ValueError('CSV input is empty or exceeds the 5 MiB import budget.')
    try:
        reader=csv.DictReader(io.StringIO(bytes(buffer).decode('utf-8-sig'),newline=''))
        fields=reader.fieldnames or []
        if len(fields)>64 or len(set(fields))!=len(fields) or not set(required_columns)<=set(fields):
            raise ValueError('CSV headers must be unique and include: '+', '.join(sorted(required_columns)))
        rows=[]
        for row in reader:
            if len(rows)>=max_rows:
                raise ValueError('CSV import exceeds the 100,000-row budget.')
            if None in row or any(v is None for v in row.values()):
                raise ValueError('CSV row width differs from its headers.')
            rows.append(row)
        return rows
    except (csv.Error,UnicodeError) as exc:
        raise ValueError('CSV must be valid UTF-8 with bounded field sizes.') from exc
