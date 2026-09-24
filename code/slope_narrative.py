"""Source-driven slope prose shared by Word and the runnable tutorial.

This module describes the selected evidence; it never selects sources or fits
parameters. Inconsistent summaries fail instead of producing plausible prose.
"""
from collections import defaultdict
import math
import re

UNIT = 'L min⁻¹ mmHg⁻¹'


def number(value):
    return f'{value:.9g}'


def papers(count):
    return f'{count} paper' + ('' if count == 1 else 's')


def citation(study, url=None, markdown=False):
    text = re.sub(r'(\d{4})$', r' (\1)', study)
    return f'[{text}]({url})' if markdown and url else text


def close(actual, expected, label):
    if not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError('Slope narrative/evidence mismatch: ' + label)


def pool_facts(item, method):
    source = item['source_records']; contributions = item['study_contributions']
    if not source or not contributions:
        raise ValueError('Slope narrative requires selected source records: ' + method)
    ids = [r['record_id'] for r in source]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate source record in slope narrative')
    groups = defaultdict(list)
    for row in source:
        if row['n_subjects'] <= 0 or row['method'] != method:
            raise ValueError('Unselected or wrong-method slope record')
        groups[row['study_id']].append(row)
    if len(contributions) != len(groups) or {c['study_id'] for c in contributions} != set(groups):
        raise ValueError('Slope narrative paper membership mismatch')
    study_rows = []
    for c in contributions:
        rows = groups[c['study_id']]
        if set(c['source_record_ids']) != {x['record_id'] for x in rows}:
            raise ValueError('Slope narrative source-record membership mismatch')
        n = math.fsum(x['n_subjects'] for x in rows)
        numerator = math.fsum(x['n_subjects'] * x['slope'] for x in rows)
        close(c['n_subjects'], n, 'paper N'); close(c['slope'], numerator/n, 'paper S')
        close(c['n_times_s'], numerator, 'paper numerator')
        if not c.get('source_url'):
            raise ValueError('A contributing slope paper needs its source URL: ' + c['study_id'])
        row = dict(study_id=c['study_id'], n=n, slope=numerator/n,
                   source_url=c['source_url'], protocol=c.get('protocol') or 'Protocol not supplied',
                   source_record_ids=c['source_record_ids'])
        if method == 'fico2':
            if any(x['uncertainty_type'] != 'SD' or x['uncertainty'] is None or x['uncertainty'] < 0 or x['n_subjects'] <= 1 for x in rows):
                raise ValueError('FiCO2 narrative requires identified sample SD and N > 1')
            row['sd'] = math.sqrt(math.fsum((x['n_subjects']-1)*x['uncertainty']**2 +
                                    x['n_subjects']*(x['slope']-row['slope'])**2 for x in rows)/(n-1))
            row['sd_label'] = 'SD' if len(rows) == 1 else 'combined participant SD'
        study_rows.append(row)
    n = math.fsum(x['n'] for x in study_rows)
    numerator = math.fsum(x['n_subjects'] * x['slope'] for x in source)
    mean = numerator/n
    if item['n_papers'] != len(study_rows):
        raise ValueError('Slope narrative paper count mismatch')
    close(item['n_subjects'], n, 'total N'); close(item['sum_n_s'], numerator, 'total numerator')
    close(item['slope'], mean, 'pooled S')
    out = dict(method=method, label=item['label'], n_papers=len(study_rows), n=n,
               numerator=numerator, slope=mean, studies=study_rows, range=item['range'])
    if method == 'fico2':
        within = math.fsum((x['n_subjects']-1)*x['uncertainty']**2 for x in source)
        between = math.fsum(x['n_subjects']*(x['slope']-mean)**2 for x in source)
        sd = math.sqrt((within+between)/(n-1))
        close(item['sd'], sd, 'combined participant SD')
        close(item['range'][0], mean-sd, 'FiCO2 lower bound')
        close(item['range'][1], mean+sd, 'FiCO2 upper bound')
        out.update(sd=sd, df=n-1, within_ss=within, between_ss=between,
                   adult_assumptions=sorted({x['study_id'] for x in source if x.get('adult_eligibility_basis') == 'user_confirmed'}))
    else:
        close(item['range'][0], min(x['slope'] for x in study_rows), 'rebreathing minimum')
        close(item['range'][1], max(x['slope'] for x in study_rows), 'rebreathing maximum')
    return out


def build(result, markdown=False):
    ev = result['slope_evidence']
    f = pool_facts(ev['fico2'], 'fico2'); rb = pool_facts(ev['rebreathing'], 'rebreathing')
    close(result['settings']['S'], f['slope'], 'operating model S')
    retained = result['reported_points']
    overlap = sorted({x['study_id'] for x in f['studies']} & {x['study_id'] for x in retained})
    independence = ('The operating-slope sources do not enter the current exact validation set.' if not overlap else
        'Operating-slope and exact validation evidence share ' + ', '.join(citation(x) for x in overlap) +
        '; cohort independence must be assessed before describing that comparison as external validation.')
    assumptions = ('Adult eligibility is explicitly assumed for ' + ', '.join(citation(x) for x in f['adult_assumptions']) +
                   '; unreported minimum ages remain missing.' if f['adult_assumptions'] else
                   'The selected adult eligibility classifications use the recorded source age evidence.')
    source_parts = []
    for c in f['studies']:
        protocol=str(c['protocol']).replace('CO2','CO₂').replace('O2','O₂').replace('N2','N₂')
        source_parts.append(f"{citation(c['study_id'], c['source_url'], markdown)}: N = {number(c['n'])}, "
                            f"S = {number(c['slope'])} ± {number(c['sd'])} ({c['sd_label']}); {protocol}")
    sources = (f"The FiCO₂ selection contains {papers(f['n_papers'])}: " + '; '.join(source_parts) + '. ' + assumptions +
               ' Only the selected independent source records contribute; overlapping summaries and alternative endpoints from the same cohort are not added again. '
               'The reported participant-slope means are used; ratios of group mean changes are different calculations. '
               'Finite exposure alone does not establish the ventilatory steady state required by the model.')
    terms = ' + '.join(f"{number(c['n'])} × {number(c['slope'])}" for c in f['studies'])
    calculation = (f"The FiCO₂ estimate is ({terms}) / {number(f['n'])} = {f['slope']:.8f} {UNIT} "
                   f"(ΣNᵢSᵢ = {number(f['numerator'])}; {papers(f['n_papers'])}). Conversions and validation use the full-precision source-derived value rather than the displayed rounding. "
                   f"The combined participant SD is {f['sd']:.5f}, calculated from within-source and between-source sums of squares "
                   f"({number(f['within_ss'])} + {number(f['between_ss'])}) divided by {number(f['df'])} degrees of freedom, then taking the square root. "
                   'It describes participant dispersion, not uncertainty in the mean. '
                   f"The rebreathing estimate is {number(rb['numerator'])} / {number(rb['n'])} = {rb['slope']:.8f} {UNIT}, "
                   f"from {papers(rb['n_papers'])}. Rebreathing is reference only. " + independence +
                   ' Participant independence across papers is assumed, and the model default is not an individual ventilatory-response estimate.')
    method = 'For each protocol, the participant-count-weighted slope is calculated as S = Σ(NᵢSᵢ)/ΣNᵢ, after combining compatible independent subgroups within a paper and counting repeated cohorts once. '
    sensitivity = (f"The FiCO₂-in-medical-air sensitivity bounds are {f['range'][0]:.2f}–{f['range'][1]:.2f} {UNIT}, "
                   f"representing the participant-weighted mean ± combined participant SD from {papers(f['n_papers'])}. "
                   f"The rebreathing bounds span eligible study-level means from {papers(rb['n_papers'])}, "
                   f"{rb['range'][0]:.2f}–{rb['range'][1]:.2f}. These are different descriptive sensitivity scenarios, "
                   'not confidence or individual prediction intervals. Published minute-ventilation slopes are used as first-order alveolar-ventilation proxies.')
    references = [dict(study_id=c['study_id'], source_url=c['source_url']) for p in (f, rb) for c in p['studies']]
    return dict(facts=dict(fico2=f, rebreathing=rb, validation_overlap=overlap),
                sources=sources, calculation=calculation, method_calculation=method+calculation,
                supplement='S = Σ(NᵢSᵢ)/ΣNᵢ. Compatible independent subgroups are combined within each paper before participant-count weighting across papers. '+sources+' '+calculation,
                sensitivity=sensitivity, references=references)
