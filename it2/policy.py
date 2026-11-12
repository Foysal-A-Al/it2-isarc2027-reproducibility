"""Project-declared system acceptance policies; no universal numerical defaults."""
import math


def evaluate_policy(measurements, policy):
    if not policy:
        return dict(passes=None, status='Not evaluated', reason='No project policy declared.')
    if not all(str(policy.get(k, '')).strip() for k in ('name', 'scope', 'rationale')):
        return dict(passes=None, status='Not evaluated', reason='Name, declared scope and engineering rationale are required.')
    if not str(policy['scope']).startswith('system:'):
        return dict(passes=None, status='Not evaluated', reason='Select a named system; whole-model LC is descriptive only.')
    if measurements.get('elements', 0) == 0:
        return dict(passes=None, status='Not applicable', reason='No elements in the declared scope.')
    thresholds = {k: policy[k] for k in ('PC', 'LC') if k in policy}
    if not thresholds:
        return dict(passes=None, status='Not evaluated', reason='Declare at least one threshold.')
    for key, value in thresholds.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Project thresholds must be finite ratios between zero and one.')
    if any(measurements.get(k) is None for k in thresholds):
        return dict(passes=None, status='Not evaluated', reason='A required scoped metric is unavailable.')
    passed = all(measurements[k] >= v for k,v in thresholds.items())
    return dict(passes=passed, status='Meets declared policy' if passed else 'Review required',
                policy=policy, measurements=measurements,
                interpretation='Comparison with user-declared criteria; not engineering certification.')
