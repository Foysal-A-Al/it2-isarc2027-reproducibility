"""Evaluate imported, partial asset-identity labels without inventing ground truth."""
from collections import Counter


def evaluate_labels(labels, mapping):
    if not labels:
        raise ValueError('Provide at least one labelled correspondence.')
    references={};new_truth=set();uncertain=0
    for row in labels:
        if not all(row.get(k) for k in ('old_GlobalId','new_GlobalId','identity')):
            raise ValueError('Labels require old_GlobalId, new_GlobalId and identity.')
        a,b,state=row['old_GlobalId'],row['new_GlobalId'],row['identity']
        if state not in ('same_asset','replacement','uncertain'):
            raise ValueError('identity must be same_asset, replacement or uncertain.')
        if a in references:
            raise ValueError('Each earlier asset must have one adjudicated reference label.')
        if state=='same_asset' and b in new_truth:
            raise ValueError('Same-asset reference labels must be one-to-one.')
        if state=='same_asset':new_truth.add(b)
        changed=str(row.get('changed','')).lower()
        if changed not in ('true','false','1','0',''):
            raise ValueError('changed must be true, false or blank (unknown).')
        references[a]=(b,state,changed in ('true','1') if changed else None)
        uncertain+=state=='uncertain'
    for key in ('old_GlobalId','new_GlobalId'):
        if any(n>1 for n in Counter(r[key] for r in mapping).values()):
            raise ValueError('Predicted mappings must be one-to-one before benchmarking.')
    tp=fp=unlabelled=changed_tp=unchanged_tp=0
    for r in mapping:
        ref=references.get(r['old_GlobalId'])
        if ref is None or ref[1]=='uncertain':
            unlabelled+=1;continue
        correct=ref[1]=='same_asset' and ref[0]==r['new_GlobalId']
        tp+=correct;fp+=not correct
        changed_tp+=correct and ref[2] is True
        unchanged_tp+=correct and ref[2] is False
    positives=sum(s=='same_asset' for _,s,_ in references.values())
    changed_n=sum(s=='same_asset' and c is True for _,s,c in references.values())
    unchanged_n=sum(s=='same_asset' and c is False for _,s,c in references.values())
    return dict(kind='user_supplied_partial_identity_labels',true_pairs=tp,false_pairs=fp,
                scored_predictions=tp+fp,unlabelled_predictions=unlabelled,reference_same_assets=positives,
                uncertain_labels=uncertain,precision=tp/(tp+fp) if tp+fp else None,recall=tp/positives if positives else None,
                f1=2*tp/(tp+fp+positives) if tp+fp+positives else None,
                changed_target_recall=changed_tp/changed_n if changed_n else None,
                unchanged_target_recall=unchanged_tp/unchanged_n if unchanged_n else None,
                changed_reference_count=changed_n,unchanged_reference_count=unchanged_n,
                interpretation='Scores concern imported labels only. Unknown and uncertain identities are excluded; reviewer independence and correctness are not established by upload.')
