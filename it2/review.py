"""Validated portable review checkpoints; no global cross-user review state."""
import json
STATUSES=('Open','Reviewed','Approved mapping','Replacement asset','Uncertain identity','Accepted exception')
MAX_CHECKPOINT_BYTES=1_000_000

def export_checkpoint(source_sha256,decisions):
    return json.dumps(dict(version=2,source_sha256=source_sha256,decisions=decisions),
                      indent=2,allow_nan=False).encode('utf-8')

def import_checkpoint(raw,source_sha256,allowed_ids):
    """Validate the entire checkpoint before returning any replacement decisions."""
    if len(raw)>MAX_CHECKPOINT_BYTES:
        raise ValueError('Review checkpoint exceeds 1 MB.')
    try:
        payload=json.loads(raw)
    except (ValueError,UnicodeError,TypeError) as exc:
        raise ValueError('Invalid review checkpoint JSON.') from exc
    if not isinstance(payload,dict) or payload.get('version') not in (1,2):
        raise ValueError('Unsupported review checkpoint format.')
    if payload.get('source_sha256')!=source_sha256:
        raise ValueError('Checkpoint belongs to a different model or revision/settings scope.')
    decisions=payload.get('decisions')
    if not isinstance(decisions,dict):
        raise ValueError('Checkpoint decisions must be an object.')
    if set(decisions)-set(allowed_ids):
        raise ValueError('Checkpoint contains findings absent from this analysis.')
    cleaned={}
    for key,value in decisions.items():
        if not isinstance(value,dict) or value.get('status') not in STATUSES:
            raise ValueError('Invalid review status.')
        note=value.get('note','')
        if not isinstance(note,str) or len(note)>4000:
            raise ValueError('Review notes must be text of at most 4000 characters.')
        if value['status']=='Accepted exception' and not note.strip():
            raise ValueError('An accepted exception requires a rationale.')
        cleaned[key]=dict(status=value['status'],note=note)
        if 'reviewer' in value:
            if not isinstance(value['reviewer'],str) or len(value['reviewer'])>200:
                raise ValueError('Reviewer identifier must be text of at most 200 characters.')
            cleaned[key]['reviewer']=value['reviewer']
        if 'reviewed_at_utc' in value:
            from datetime import datetime
            stamp=value['reviewed_at_utc']
            if not isinstance(stamp,str) or len(stamp)>50:
                raise ValueError('Invalid review timestamp.')
            try:
                parsed=datetime.fromisoformat(stamp)
                if parsed.tzinfo is None:raise ValueError('Timezone required.')
            except ValueError as exc:
                raise ValueError('Invalid review timestamp.') from exc
            cleaned[key]['reviewed_at_utc']=stamp
    return cleaned


def approved_mappings(mapping, decisions):
    """Only unchanged unique IDs and explicitly approved inferred pairs may be used."""
    accepted=[]
    for row in mapping:
        approved=decisions.get(row.get('review_id'),{}).get('status')=='Approved mapping'
        rejected=decisions.get(row.get('review_id'),{}).get('status') in ('Replacement asset','Uncertain identity')
        unchanged=row['stage']=='globalid' and not row.get('requires_review',False) and not rejected
        if approved or unchanged:
            accepted.append(dict(row,review_approved=True) if row.get('requires_review') and approved else row)
    return accepted


def blocked_retained_ids(mapping, decisions):
    return {r['old_GlobalId'] for r in mapping if (r.get('suspicion') and decisions.get(r.get('review_id'),{}).get('status')!='Approved mapping') or decisions.get(r.get('review_id'),{}).get('status') in ('Replacement asset','Uncertain identity')}
