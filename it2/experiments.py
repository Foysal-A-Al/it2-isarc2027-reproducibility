"""Run the published feature-level protocols on a user's extracted fingerprints."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import numpy as np
from scipy.stats import wilcoxon
from .matching import perturb, score, bootstrap_ci, METHODS, match_hybrid
from .features import load_features
from .reporting import versions

RATES = (0., .1, .2, .3, .5)
EQUIPMENT = ('IfcFlowTerminal', 'IfcFlowController', 'IfcEnergyConversionDevice',
             'IfcFlowMovingDevice', 'IfcFlowStorageDevice', 'IfcFlowTreatmentDevice')
MAX_PAIR_CELLS = 8_000_000


def candidate_cells(records):
    groups = Counter((x['cls'], x['cont']) for x in records)
    return max((n * n for n in groups.values()), default=0)


def run_study(records, source, seeds=20, rates=RATES, bindings=True, sensitivity=False,
              bound_classes=EQUIPMENT, progress=None):
    """Defaults reproduce paper protocols. All user outputs are feature-level simulations.

    Original METHODS, RNG draw order, matching parameters and bootstrap implementation
    are reused. Undefined experiments are explained rather than assigned made-up scores.
    """
    if not 3 <= int(seeds) <= 50 or not rates or any(not 0 <= r <= 1 for r in rates):
        raise ValueError('Use 3 to 50 seeds and recreation shares between 0 and 1.')
    X = load_features([dict(x) for x in records])
    if not X:
        raise ValueError('No distribution-element geometry is available for an identity experiment.')
    if candidate_cells(X) * 1.1 > MAX_PAIR_CELLS:
        raise ValueError('The largest class/container partition exceeds this checker\'s safe dense-assignment budget. Export a smaller system or use the research scripts on a machine with more memory. No sampled or invented results were substituted.')
    tags = Counter((x['cls'], x['tag']) for x in X if x['tag'])
    if any(v > 1 for v in tags.values()):
        raise ValueError('The published Tag baseline assumes unique class/Tag keys. This file contains duplicate keys. Review them or use operational reconciliation; the app will not silently change the paper baseline to score this model.')
    for x in X:
        if any(len(x[k]) != 3 or not np.isfinite(x[k]).all() for k in ('cen', 'dim', 'pl')):
            raise ValueError('Fingerprints contain non-finite or invalid geometry.')
    seeds = int(seeds)
    settings = dict(seeds=seeds, recreation_rates=list(rates), move=.1, sigma_m=.15,
                    delete=.05, add=.05, noise_m=.001, lambda_name=.3, tau_m=.5,
                    seed_start=0, bootstrap_resamples=2000,
                    binding_seed_start=200, binding_recreate=.3,
                    bound_classes=list(bound_classes), sensitivity_seeds=5,
                    sensitivity_seed_start=100, sensitivity_move=.3, sensitivity_sigma_m=.3)
    total = len(rates) * seeds + (seeds if bindings else 0) + (100 if sensitivity else 0)
    completed = 0
    def advance(message):
        nonlocal completed
        completed += 1
        if progress is not None:
            progress.update(fraction=completed / total, message=message)
    keys = Counter((x['cls'], x['cont'], tuple(np.round(x['pl'], 4))) for x in X)
    shared = sum(keys[(x['cls'], x['cont'], tuple(np.round(x['pl'], 4)))] > 1 for x in X)
    out = dict(kind='user_feature_level_controlled_experiment', source=source, settings=settings,
               n=len(X), shared_placement_share=shared / len(X), identity={},
               identity_rows=[], seed_scores=[], bindings={}, binding_rows=[], sensitivity_rows=[],
               packages=versions(), computed_at_utc=datetime.now(timezone.utc).isoformat(),
               limits=['All GlobalIds are assumed regenerated; the simulated recreated share controls Tags.',
                       'Precision, recall and F1 use known simulated truth, not an authored real revision.',
                       'Dimensions and type names are preserved by the published simulator.',
                       'Bootstrap intervals describe seed variation, not performance across buildings.',
                       'No new IFC file-level round trips or live BMS validation are performed.'])
    for r in rates:
        scores = defaultdict(list)
        for seed in range(seeds):
            new, truth = perturb(X, np.random.default_rng(seed), float(r))
            for name, fn in METHODS.items():
                p, recall, f = score(fn(X, new), truth)
                scores[name].append((p, recall, f))
                out['seed_scores'].append(dict(recreated=r, seed=seed, method=name,
                                               precision=p, recall=recall, f1=f, surviving_elements=len(truth)))
            advance(f'Identity: recreated {r:.0%}, seed {seed + 1}/{seeds}')
        summary = {name: {k: bootstrap_ci(np.asarray(v)[:, i]) for i, k in enumerate('PRF')}
                   for name, v in scores.items()}
        a, b = np.asarray(scores['hybrid'])[:, 1], np.asarray(scores['tag'])[:, 1]
        summary['wilcoxon_p_hybrid_vs_tag'] = float(wilcoxon(a, b).pvalue) if r > 0 and np.any(a != b) else None
        out['identity'][str(float(r))] = summary
        for name in METHODS:
            m = summary[name]
            out['identity_rows'].append(dict(recreated=r, method=name, precision=m['P'][0],
                                            recall=m['R'][0], f1=m['F'][0],
                                            recall_ci_low=m['R'][1], recall_ci_high=m['R'][2], seeds=seeds))
    if bindings:
        bound = [i for i, x in enumerate(X) if x['cls'] in bound_classes]
        observed, survival_counts = defaultdict(list), []
        if bound:
            for seed in range(seeds):
                new, truth = perturb(X, np.random.default_rng(200 + seed), .3)
                inv = {i: j for j, i in truth.items()}
                alive = [i for i in bound if i in inv]
                survival_counts.append(len(alive))
                if alive:
                    for name, fn in [('guid', lambda a, b: []), *METHODS.items()]:
                        mapping = dict(fn(X, new))
                        observed[name].append((sum(mapping.get(i) == inv[i] for i in alive) / len(alive),
                                               sum(i in mapping and mapping[i] != inv[i] for i in alive) / len(alive)))
                advance(f'Simulated bindings: seed {seed + 1}/{seeds}')
            out['bindings'] = dict(bound_elements=len(bound), valid_seeds=sum(n > 0 for n in survival_counts),
                                   surviving_bound_counts=survival_counts,
                                   status='simulated' if observed else 'not applicable: no bound elements survived')
            for name, values in observed.items():
                correct = bootstrap_ci(np.asarray(values)[:, 0])
                wrong = bootstrap_ci(np.asarray(values)[:, 1])
                out['binding_rows'].append(dict(method=name, correct=correct[0], wrong=wrong[0],
                                               correct_ci_low=correct[1], correct_ci_high=correct[2],
                                               seeds=len(values), bound_elements=len(bound)))
        else:
            out['bindings'] = dict(bound_elements=0, status='not applicable: no fingerprints match the selected bound classes')
            completed += seeds
    if sensitivity:
        for lam in (0., .15, .3, .6, 1.):
            for tau in (.25, .5, 1., 2.):
                scores = []
                for seed in range(5):
                    new, truth = perturb(X, np.random.default_rng(100 + seed), 1., move=.3, sigma=.3)
                    scores.append(score(match_hybrid(X, new, lam, tau, use_tag=False), truth))
                    advance(f'Sensitivity: lambda {lam}, tau {tau}, seed {seed + 1}/5')
                p, r, f = np.mean(scores, axis=0)
                out['sensitivity_rows'].append(dict(lambda_name=lam, tau_m=tau, precision=float(p),
                                                    recall=float(r), f1=float(f), seeds=5))
    if progress is not None:
        progress.update(fraction=1., message='Experiment completed')
    return out
