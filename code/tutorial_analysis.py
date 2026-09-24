"""Portable recalculation of the fixed SSM literature comparison.

Numerical conversion, within-paper aggregation, uncertainty and equal-paper
metric functions retain the frozen analysis equations. Inputs are the selected
public JSON export, not a workbook, a database, or cached prediction tables.
Expected values are used only to verify results, never to supply predictions.
The retained selection and assumptions are fixed for this companion release.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import copy
import json
import math
from ssm import Params, fico2_to_paco2, paco2_to_fico2, VERSION as MODEL_VERSION

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'ssm-workbook-analysis-2026-09-17-two-slopes'
PARAM_FIELDS = ('S', 'VCO2', 'Patm', 'PH2O', 'K', 'max_paco2')


class InputError(ValueError):
    """A companion literature input is invalid; no partial analysis is returned."""


def text(value):
    return '' if value is None else str(value).strip()


def number(value, field, rid, *, optional=False, nonnegative=False, positive=False):
    if text(value) == '' and optional:
        return None
    if isinstance(value, bool):
        raise InputError(f'{rid}: {field} must be numeric, not a Boolean')
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise InputError(f'{rid}: {field} requires a numeric value') from None
    if not math.isfinite(value) or (nonnegative and value < 0) or (positive and value <= 0):
        raise InputError(f'{rid}: {field} is outside its finite physical domain')
    return value


def mean(values, weights=None):
    if not values:
        raise InputError('Cannot average an empty group')
    if weights is None:
        weights = [1.0] * len(values)
    if len(values) != len(weights) or any(not math.isfinite(w) or w <= 0 for w in weights):
        raise InputError('Finite positive weights and matching vectors required')
    return math.fsum(v*w for v,w in zip(values,weights)) / math.fsum(weights)


def parameters(settings, baseline, slope=None):
    kwargs = {k: settings[k] for k in PARAM_FIELDS}
    if slope is not None:
        kwargs['S'] = slope
    return Params(PaCO2_base=baseline, **kwargs)


def context(row):
    oxygen, co = row['oxygen_group'], row['coexposure']
    if oxygen == 'ambient' and co == 'none':
        return 'pure_HC'
    if oxygen == 'hyperoxic' and co == 'none':
        return 'HC_hyperoxia'
    if oxygen == 'hypoxic':
        return 'HC_hypoxia'
    if co == 'N2O_15pct':
        return 'HC_N2O_15pct'
    return 'other_mixed'


def source_sd(row, scale):
    rid = row['record_id']
    kind = text(row.get('uncertainty_type')) or 'none'
    if kind not in ('SD','SEM','undefined','none'):
        raise InputError(f'{rid}: uncertainty_type must be SD, SEM, undefined or none')
    base = number(row.get('baseline_uncertainty_value'), 'baseline_uncertainty_value', rid,
                  optional=True, nonnegative=True)
    end = number(row.get('endpoint_uncertainty_value'), 'endpoint_uncertainty_value', rid,
                 optional=True, nonnegative=True)
    if kind == 'none' and (base is not None or end is not None):
        raise InputError(f'{rid}: numerical uncertainty cannot have type none')
    n = number(row.get('uncertainty_n'), 'uncertainty_n', rid, optional=True, positive=True)
    if n is not None and int(n) != n:
        raise InputError(f'{rid}: uncertainty_n must be an integer')
    if kind == 'SEM' and (base is not None or end is not None) and n is None:
        raise InputError(f'{rid}: SEM requires its explicit uncertainty_n denominator')
    factor = scale * (math.sqrt(n) if kind == 'SEM' and n is not None else 1)
    sd = lambda v: None if v is None or kind in ('undefined','none') else v*factor
    return dict(baseline_sd_mmhg=sd(base), measured_sd_mmhg=sd(end),
                uncertainty_status=('SD_derived_from_reported_SEM' if kind == 'SEM' else
                    'reported_SD' if kind == 'SD' else 'unavailable_' + kind),
                uncertainty_note=text(row.get('uncertainty_note')),
                uncertainty_source_locator=text(row.get('uncertainty_source_locator')),
                source_uncertainty_type=kind)


def normalize(row, settings):
    r = dict(row)
    rid = r['record_id']
    required = ('study_id','condition_id','participant_group_id','exposure_id',
                'population','method','fico2_status','baseline_endpoint','endpoint',
                'baseline_status','endpoint_status','oxygen_group','record_level','subjects_n')
    for field in required:
        if not text(r.get(field)):
            raise InputError(f'{rid}: missing {field}')
    if text(r['population']) not in ('healthy_humans','healthy_adults','healthy_adults_assumed') or text(r['method']) != 'inspired_CO2':
        raise InputError(f'{rid}: included comparisons require healthy humans receiving inspired CO2')
    if r['analysis_tier'] != 'graphical' and r['population'] not in ('healthy_adults','healthy_adults_assumed'):
        raise InputError(f'{rid}: exact figure comparisons require source-supported or explicitly assumed healthy adults; otherwise mark pending')
    r['adult_eligibility_status']=('user_assumed' if r['population']=='healthy_adults_assumed' else
                                   'source_supported' if r['population']=='healthy_adults' else 'unverified_graphical')
    if r['adult_eligibility_status']=='user_assumed' and not text(r.get('eligibility_reason')):
        raise InputError(f'{rid}: assumed adult eligibility requires an explicit eligibility note')
    if r['baseline_endpoint'] != r['endpoint'] or r['endpoint'] not in ('PaCO2','PETCO2'):
        raise InputError(f'{rid}: matching arterial/end-tidal baseline and achieved compartments required')
    graph = r['analysis_tier'] == 'graphical'
    accepted = 'graph_digitized' if graph else 'reported_exact'
    if r['baseline_status'] != accepted or r['endpoint_status'] != accepted:
        raise InputError(f'{rid}: baseline/achieved evidence status does not match its analysis tier')
    if r['fico2_status'] != 'reported_mixture':
        raise InputError(f'{rid}: included fixed-dose comparison requires reported_mixture, not target, stock or range')
    if r['oxygen_group'] not in ('ambient','hyperoxic','hypoxic','unknown'):
        raise InputError(f'{rid}: invalid oxygen_group')
    r['coexposure'] = text(r.get('coexposure')) or 'none'
    r['smoking_status'] = text(r.get('smoking_status')) or 'unknown'
    if r['smoking_status'] not in ('nonsmoker','smoker','mixed','unknown'):
        raise InputError(f'{rid}: invalid smoking_status')
    declared_context = text(r.get('context'))
    r['context'] = context(r)
    if declared_context and declared_context != r['context']:
        raise InputError(f'{rid}: context contradicts oxygen_group/coexposure')
    if (r['analysis_tier']=='primary') != (r['context']=='pure_HC') and not graph:
        raise InputError(f'{rid}: primary/mixed tier contradicts oxygen/coexposure context')
    r['fico2_pct'] = number(r.get('fico2_pct'),'fico2_pct',rid,positive=True)
    if r['fico2_pct'] > 100:
        raise InputError(f'{rid}: FiCO2 must be an inspired percentage no greater than 100')
    unit = text(r.get('source_pressure_unit'))
    if unit not in ('mmHg','kPa'):
        raise InputError(f'{rid}: source_pressure_unit must be mmHg or kPa')
    scale = 1 if unit == 'mmHg' else 1/settings['kpa_per_mmhg']
    for dest,src in [('baseline_mmhg','baseline_source_value'),('measured_mmhg','endpoint_source_value')]:
        r[dest] = number(r.get(src),src,rid,positive=True)*scale
    n = number(r.get('subjects_n'),'subjects_n',rid,positive=True)
    if int(n)!=n:
        raise InputError(f'{rid}: subjects_n must be a positive integer')
    r['subjects_n'] = int(n)
    if r['record_level'] in ('individual','individual_cycle') and n != 1:
        raise InputError(f'{rid}: individual records must have subjects_n=1')
    r['technical_duplicate_of'] = text(r.get('technical_duplicate_of'))
    r['source_data_rows'] = rid  # Stable source-record identity; no private workbook coordinates.
    r['input_mode'] = 'reported_graphical' if graph else 'reported'
    r['representation_label'] = 'Reported observations'
    r['analysis_role'] = 'sensitivity_reported'
    r['record_level'] = text(r['record_level'])
    if r['record_level'] not in ('group_mean','individual','individual_cycle'):
        raise InputError(f'{rid}: unsupported record_level')
    r.update(source_sd(r,scale))
    if graph:
        for dest,lo,hi in [('baseline_mmhg','baseline_lower','baseline_upper'),
                           ('measured_mmhg','endpoint_lower','endpoint_upper')]:
            low = number(r.get(lo),lo,rid,positive=True)*scale
            high = number(r.get(hi),hi,rid,positive=True)*scale
            if not low <= r[dest] <= high:
                raise InputError(f'{rid}: source graphical reading lies outside its bounds')
            r[dest+'_low'],r[dest+'_high'] = low,high
    return convert(r,settings)


def convert(row, settings):
    r = dict(row)
    p = parameters(settings,r['baseline_mmhg'])
    try:
        prediction = fico2_to_paco2(r['fico2_pct'],p)
        inverse = paco2_to_fico2(r['measured_mmhg'],p)
    except ValueError as e:
        raise InputError(f"{r['record_id']}: model domain: {e}") from e
    r.update(estimated_paco2_mmhg=prediction,estimated_fico2_pct=inverse,
             pressure_error_mmhg=prediction-r['measured_mmhg'],
             fico2_error_pct_points=inverse-r['fico2_pct'],
             validation_release=VERSION,model_release=MODEL_VERSION,
             S=settings['S'],max_pressure_mmhg=settings['max_paco2'])
    if r.get('baseline_mmhg_low') is not None:
        forwards, reverses = [],[]
        for b in (r['baseline_mmhg_low'],r['baseline_mmhg_high']):
            pp = parameters(settings,b)
            try:
                forwards.append(fico2_to_paco2(r['fico2_pct'],pp))
                for y in (r['measured_mmhg_low'],r['measured_mmhg_high']):
                    reverses.append(paco2_to_fico2(y,pp))
            except ValueError as e:
                raise InputError(f"{r['record_id']}: graphical bounds violate model domain: {e}") from e
        r.update(estimated_paco2_low=min(forwards),estimated_paco2_high=max(forwards),
                 pressure_error_low=min(forwards)-r['measured_mmhg_high'],
                 pressure_error_high=max(forwards)-r['measured_mmhg_low'],
                 estimated_fico2_low=min(reverses),estimated_fico2_high=max(reverses),
                 fico2_error_low=min(reverses)-r['fico2_pct'],fico2_error_high=max(reverses)-r['fico2_pct'])
    return r


def pooled_sd(parts, field, mean_field):
    """Between-participant sample SD; never combine repeated-measure SDs."""
    if len(parts)==1:
        return parts[0].get(field)
    total=sum(p['N'] for p in parts)
    if total<2 or any(p['N']>1 and p.get(field) is None for p in parts):
        return None
    grand=mean([p[mean_field] for p in parts],[p['N'] for p in parts])
    ss=math.fsum((p['N']-1)*(p.get(field) or 0)**2 + p['N']*(p[mean_field]-grand)**2 for p in parts)
    return math.sqrt(ss/(total-1))


def weighted_inputs(rows,settings):
    groups=defaultdict(list)
    for r in rows:
        groups[(r['study_id'],r['context'],r['endpoint'],r['fico2_pct'])].append(r)
    out=[]
    for key,rs in sorted(groups.items()):
        people=defaultdict(list)
        for r in rs:people[r['participant_group_id']].append(r)
        fields=['baseline_mmhg','measured_mmhg']
        if all(r.get('baseline_mmhg_low') is not None for r in rs):
            fields+=['baseline_mmhg_low','baseline_mmhg_high','measured_mmhg_low','measured_mmhg_high']
        parts=[]
        for pid,repeats in people.items():
            ns={r['subjects_n'] for r in repeats}
            if len(ns)!=1:
                raise InputError(f'{pid}: repeated participant group has inconsistent subjects_n')
            part=dict(N=ns.pop(),**{f:mean([r[f] for r in repeats]) for f in fields})
            for f in ['baseline_sd_mmhg','measured_sd_mmhg']:
                part[f]=repeats[0].get(f) if len(repeats)==1 else None
            parts.append(part)
        weights=[r['N'] for r in parts]
        r=dict(zip(['study_id','context','endpoint','fico2_pct'],key),
            **{f:mean([p[f] for p in parts],weights) for f in fields})
        note=('One reported cohort mean; the study summary coincides. No additional individual data are available.' if len(rs)==1 else
              'Repeated means from the same participant group averaged; N counted once. This is acquisition averaging, not recovered individual data.' if len(parts)==1 else
              'Repeated observations averaged within each participant/group, then independent input means weighted by group N.')
        baseline_sd=pooled_sd(parts,'baseline_sd_mmhg','baseline_mmhg')
        measured_sd=pooled_sd(parts,'measured_sd_mmhg','measured_mmhg')
        uncertainty_status=(rs[0]['uncertainty_status'] if len(rs)==1 else
            'unavailable_repeated_covariance' if len(parts)==1 else
            'derived_group_SD' if baseline_sd is not None and measured_sd is not None else
            'unavailable_incomplete_group_SD')
        r.update(record_id='|'.join(map(str,key))+'|weighted_inputs',record_ids=';'.join(x['record_id'] for x in rs),
            input_mode='within_paper_weighted_graphical' if rs[0]['analysis_tier']=='graphical' else 'within_paper_weighted',
            subjects_n=sum(weights),participant_groups=len(parts),reported_records=len(rs),aggregation_note=note,
            population=rs[0]['population'],method=rs[0]['method'],
            adult_eligibility_status=rs[0]['adult_eligibility_status'],
            representation_label='Study summary',analysis_role='primary_summary',
            source_data_rows=';'.join(sorted(set(n for x in rs for n in x['source_data_rows'].split(';')))),
            record_level='within_paper_input_mean',baseline_endpoint=rs[0]['baseline_endpoint'],analysis_tier=rs[0]['analysis_tier'],
            baseline_sd_mmhg=baseline_sd,
            measured_sd_mmhg=measured_sd,
            uncertainty_status=uncertainty_status,
            uncertainty_note=rs[0]['uncertainty_note'] if len(rs)==1 else 'Repeated-measure covariance is not imputed. Independent participant/group summaries are pooled only when their SDs or individual values support it.',
            uncertainty_source_locator='; '.join(sorted({x['uncertainty_source_locator'] for x in rs})),
            endpoint_n_status='; '.join(sorted({text(x.get('endpoint_n_status')) for x in rs})),
            source_record_ids=';'.join(x['record_id'] for x in rs))
        out.append(convert(r,settings))
    return out


def equal_paper_weights(rows):
    """One total vote per paper in this stratum, shared over its retained rows."""
    counts=defaultdict(int)
    for r in rows:counts[r['study_id']]+=1
    return [1/(len(counts)*counts[r['study_id']]) for r in rows]


def metrics_for(rows,combined=False,per_paper=False):
    groups=defaultdict(list)
    fields=(['study_id'] if per_paper else [])+['context']+([] if combined else ['endpoint'])+['fico2_pct','input_mode']
    for r in rows:groups[tuple(r[k] for k in fields)].append(r)
    out=[]
    for key,rs in sorted(groups.items()):
        for direction,error,unit in [('FiCO2_to_pressure','pressure_error_mmhg','mmHg'),
                                      ('pressure_to_FiCO2','fico2_error_pct_points','percentage points FiCO2')]:
            errors=[r[error] for r in rs];n=len(errors);weights=equal_paper_weights(rs)
            bias=mean(errors,weights);mse=mean([e*e for e in errors],weights)
            m=dict(zip(fields,key),direction=direction,n_points=n,n_studies=len({r['study_id'] for r in rs}),
                   rmse=math.sqrt(mse),bias=bias,
                   sd_residual=math.sqrt(max(0,mse-bias*bias)) if n>1 else None,
                   residual_spread_definition='Weighted descriptive population spread, sqrt(MSE - bias^2); not a sample SD or individual precision estimate.',
                   units=unit,record_ids=';'.join(r['record_id'] for r in rs),study_ids=';'.join(sorted({r['study_id'] for r in rs})),
                   weighting='equal_paper_within_dose_context',
                   representation_label='Study summary' if 'weighted' in key[-1] else 'Reported observations',
                   analysis_role='primary_summary' if 'weighted' in key[-1] else 'sensitivity_reported',
                   contributions=[dict(record_id=r['record_id'],study_id=r['study_id'],endpoint=r['endpoint'],
                       weight=w,error=e,bias_contribution=w*e,mse_contribution=w*e*e) for r,w,e in zip(rs,weights,errors)],
                   interpretation='Each paper has equal total influence within this dose/context/endpoint stratum. Bias averages paper mean residuals; RMSE takes the square root of the average paper mean squared residual. Reported observations and study summaries reuse the same evidence.')
            if combined:
                m.update(scope=m['context'],n_PaCO2=sum(r['endpoint']=='PaCO2' for r in rs),n_PETCO2=sum(r['endpoint']=='PETCO2' for r in rs))
                m['interpretation']+=' Combined PaCO2/PETCO2 agreement is descriptive; PETCO2 remains a proxy, not direct arterial validation.'
            out.append(m)
    return out


def reported_study_balanced_metrics(rows):
    groups=defaultdict(lambda:defaultdict(list))
    for r in rows:groups[(r['context'],r['endpoint'],r['fico2_pct'])][r['study_id']].append(r)
    out=[]
    for key,papers in sorted(groups.items()):
        for direction,error,unit in [('FiCO2_to_pressure','pressure_error_mmhg','mmHg'),('pressure_to_FiCO2','fico2_error_pct_points','percentage points FiCO2')]:
            out.append(dict(zip(['context','endpoint','fico2_pct'],key),direction=direction,
                input_mode='reported_equal_paper_sensitivity',n_points=sum(map(len,papers.values())),n_studies=len(papers),
                bias=mean([mean([r[error] for r in rs]) for rs in papers.values()]),
                rmse=math.sqrt(mean([mean([r[error]**2 for r in rs]) for rs in papers.values()])),units=unit))
    return out


def duration_summary(rows, issues):
    papers=defaultdict(list)
    for r in rows:papers[r['study_id']].append(r)
    durations=[]
    for study,rs in papers.items():
        values=[];statuses=set();locators=set()
        for r in rs:
            status=text(r.get('duration_status')) or 'unknown'
            raw=number(r.get('duration_value'),'duration_value',r['record_id'],optional=True,positive=True)
            unit=text(r.get('duration_unit'))
            if status not in ('exact','approximate','unknown','range'):
                raise InputError(f"{r['record_id']}: duration_status must be exact, approximate, unknown or range")
            if status in ('exact','approximate'):
                if raw is None or unit not in ('s','min'):
                    raise InputError(f"{r['record_id']}: exact/approximate duration requires value and s/min unit")
                values.append(raw*(60 if unit=='min' else 1));statuses.add(status)
            elif raw is not None:
                raise InputError(f"{r['record_id']}: unknown/range duration must not supply a point value")
            locators.add(text(r.get('duration_source_locator')))
        unique=set(values)
        if values and len(values)<len(rs):
            seconds=None;status='partial'
            issues.append(dict(record_id=';'.join(r['record_id'] for r in rs),severity='warning',code='duration_incomplete',
                message=f'{study}: duration at the analyzed dose is missing for one or more included comparisons; do not assign another cohort or condition duration to the whole paper.'))
        elif len(unique)>1:
            seconds=None;status='heterogeneous'
            issues.append(dict(record_id=';'.join(r['record_id'] for r in rs),severity='warning',code='duration_heterogeneous',
                message=f'{study}: different durations at the analyzed dose; no ungoverned paper-level duration average is imposed.'))
        elif unique:
            seconds=unique.pop();status='approximate' if 'approximate' in statuses else 'exact'
        else:
            seconds=None;status='unknown'
        durations.append(dict(study_id=study,duration_seconds=seconds,duration_minutes=None if seconds is None else seconds/60,
            duration_status=status,record_ids=';'.join(r['record_id'] for r in rs),source_locator='; '.join(sorted(locators))))
    available=[r for r in durations if r['duration_seconds'] is not None]
    exact=[r for r in available if r['duration_status']=='exact']
    m=mean([r['duration_minutes'] for r in available]) if available else None
    ext=mean([r['duration_minutes'] for r in exact]) if exact else None
    count=len(papers);n=len(available)
    note=(f'A–C: mean time at dose ≈{m:.1f} min ({n}/{count} studies)' if available else f'A–C: time at dose unavailable (0/{count} studies)')
    summary=dict(status='PASS',scope='Primary pure-HC papers only; mixed and graphical sensitivity records excluded.',
        estimand='Equal-paper arithmetic mean of continuous exposure duration at the analyzed inspired dose. A paper contributes only when every retained pure-HC comparison has the same available duration. Other doses, baseline and recovery are excluded. This is not a steady-state criterion.',
        mean_duration_minutes=m,mean_duration_seconds=None if m is None else m*60,n_available_studies=n,n_primary_studies=count,
        range_minutes=[min(r['duration_minutes'] for r in available),max(r['duration_minutes'] for r in available)] if available else None,
        figure_note=note,included_studies=[r['study_id'] for r in available],missing_studies=[r['study_id'] for r in durations if r['duration_seconds'] is None],
        approximate_duration_studies=[r['study_id'] for r in available if r['duration_status']=='approximate'],
        exact_protocol_only_sensitivity=dict(mean_minutes=ext,mean_seconds=None if ext is None else ext*60,n_available_studies=len(exact),n_primary_studies=count),
        uncertainty=dict(missingness='Available-case mean does not identify the mean for all studies. Missing, partial or heterogeneous dose durations are not imputed.',
                         physiology='Exposure duration does not establish equilibrium or impose a universal eligibility threshold.'))
    return durations,summary


def implied_slope(baseline, achieved, dose, settings):
    A=settings['K']*settings['VCO2']; inspired=dose*(settings['Patm']-settings['PH2O'])/100
    if not achieved>max(baseline,inspired):
        raise InputError('Positive pressure rise and achieved pressure greater than inspired pressure required for an implied slope')
    s=(A/(achieved-inspired)-A/baseline)/(achieved-baseline)
    if not math.isfinite(s) or s<=0:
        raise InputError('Data do not identify a positive finite implied slope')
    return s


def model_curve(ident,label,slope,baseline,settings):
    p=parameters(settings,baseline,slope);end=paco2_to_fico2(settings['max_paco2'],p)
    doses=[i*end/600 for i in range(601)]
    return dict(id=ident,label=label,slope=slope,baseline_mmhg=baseline,fico2_pct=doses,
        paco2_mmhg=[fico2_to_paco2(f,p) for f in doses],
        role='fixed_reference' if ident=='fixed' else 'data_derived_descriptive_summary')


def slope_summaries(reported,weighted,settings,issues):
    curves=[model_curve('fixed','Steady-state model',settings['S'],settings['reference_baseline_mmhg'],settings)]
    papers=defaultdict(list)
    for r in weighted:papers[r['study_id']].append(r)
    reason=None
    if not papers:
        reason='No primary papers are included.'
    elif any(len(v)!=1 for v in papers.values()):
        reason='A primary paper has multiple endpoint/dose strata; a cross-stratum paper slope/weight policy is not defined.'
    elif len({r['fico2_pct'] for r in weighted})>1:
        reason='Primary papers have different inspired doses; descriptive aggregate curves are suppressed rather than pooling doses.'
    inputs=[dict(study_id=r['study_id'],endpoint=r['endpoint'],baseline_mmhg=r['baseline_mmhg'],achieved_mmhg=r['measured_mmhg'],
                 fico2_pct=r['fico2_pct'],cohort_n=r['subjects_n'],record_ids=r['record_ids'],source_data_rows=r['source_data_rows'],
                 endpoint_n_status=r.get('endpoint_n_status',''),within_paper_input_aggregation=r['aggregation_note']) for r in weighted]
    record_slopes=[];paper_slopes=[]
    for r in reported:
        try:s=implied_slope(r['baseline_mmhg'],r['measured_mmhg'],r['fico2_pct'],settings)
        except InputError as e:
            s=None;reason=reason or str(e)
            issues.append(dict(record_id=r['record_id'],severity='warning',code='implied_slope_not_identified',
                message=str(e)+'. Source observation remains in fixed-model agreement; do not discard it to obtain a positive fitted slope.'))
        record_slopes.append(dict(record_id=r['record_id'],study_id=r['study_id'],baseline_mmhg=r['baseline_mmhg'],achieved_mmhg=r['measured_mmhg'],fico2_pct=r['fico2_pct'],implied_slope_l_min_mmhg=s))
    if reason is None:
        for r in inputs:
            rr=[x for x in record_slopes if x['study_id']==r['study_id']]
            try:s=implied_slope(r['baseline_mmhg'],r['achieved_mmhg'],r['fico2_pct'],settings)
            except InputError as e:
                reason=str(e);break
            paper_slopes.append(dict(study_id=r['study_id'],endpoint=r['endpoint'],cohort_n=r['cohort_n'],n_reported_records=len(rr),
                reported_slope_l_min_mmhg=mean([x['implied_slope_l_min_mmhg'] for x in rr]),weighted_input_slope_l_min_mmhg=s,
                endpoint_n_status=r['endpoint_n_status'],record_ids=r['record_ids']))
    if reason is not None:
        issues.append(dict(record_id='',severity='warning',code='descriptive_slopes_unavailable',message=reason+' Fixed-model comparisons remain available.'))
        return dict(curves=curves,paper_inputs=inputs,paper_slopes=paper_slopes,reported_record_slopes=record_slopes,
                    aggregates=[],slope_summary=dict(status='unavailable',reason=reason,n_papers=len(papers)),slope_first_comparison={})
    n=[r['cohort_n'] for r in inputs];total=sum(n)
    equal_s=mean([r['reported_slope_l_min_mmhg'] for r in paper_slopes])
    weighted_s=mean([r['weighted_input_slope_l_min_mmhg'] for r in paper_slopes],n)
    aggregates=[]
    for ident,label,weights,s in [('equal_study','Reported mean slope',[1.0]*len(inputs),equal_s),
                                   ('participant_weighted','Participant-weighted mean',n,weighted_s)]:
        b=mean([r['baseline_mmhg'] for r in inputs],weights);y=mean([r['achieved_mmhg'] for r in inputs],weights);f=inputs[0]['fico2_pct']
        c=model_curve(ident,label,s,b,settings)
        c['corresponding_mean_achieved_mmhg']=y;c['predicted_at_dose_mmhg']=fico2_to_paco2(f,parameters(settings,b,s))
        if f==5:c['predicted_at_5pct_mmhg']=c['predicted_at_dose_mmhg']
        curves.append(c)
        ag=dict(method='Reported record slopes averaged within paper, then equally across papers' if ident=='equal_study' else
                      'Slope from each within-paper weighted input pair, then cohort-N weighting across papers',
            baseline_mmhg=b,achieved_mmhg=y,fico2_pct=f,implied_slope_l_min_mmhg=s,n_papers=len(inputs),sum_weights=sum(weights),weights=weights,
            unit_of_aggregation='One baseline/achieved input-mean pair per paper',curve_predicted_at_dose_mmhg=c['predicted_at_dose_mmhg'])
        if f==5:ag['curve_predicted_at_5pct_mmhg']=c['predicted_at_dose_mmhg']
        aggregates.append(ag)
    comparison=dict(reported_slopes_equal_papers=equal_s,
        reported_slopes_cohort_weighted=mean([r['reported_slope_l_min_mmhg'] for r in paper_slopes],n),
        weighted_input_slopes_equal_papers=mean([r['weighted_input_slope_l_min_mmhg'] for r in paper_slopes]),weighted_input_slopes_cohort_weighted=weighted_s)
    summary=dict(status='available',equal_study=aggregates[0],participant_weighted=aggregates[1],n_papers=len(inputs),sum_cohort_n=total,units='L/min/mmHg',
        weights='Published cohort N once per paper; not necessarily endpoint-specific N.',
        method='Reported slopes receive equal paper weights; slopes from within-paper weighted input pairs receive cohort-N weights across papers.',
        inference='Descriptive model-implied slopes calculated from the same observed outcomes, not independent validation or measured HCVR.')
    return dict(curves=curves,paper_inputs=inputs,paper_slopes=paper_slopes,reported_record_slopes=record_slopes,
                aggregates=aggregates,slope_summary=summary,slope_first_comparison=comparison)


def global_metrics_for(rows):
    """Equal-paper agreement over each complete panel; no input averaging across doses."""
    out=[]
    for panel in ('C','D'):
        selected=[r for r in rows if panel=='D' or r['context']=='pure_HC']
        for mode in sorted({r['input_mode'] for r in selected}):
            rr=[r for r in selected if r['input_mode']==mode]
            weights=equal_paper_weights(rr)
            for direction,field,units in [('FiCO2_to_pressure','pressure_error_mmhg','mmHg'),
                                         ('pressure_to_FiCO2','fico2_error_pct_points','percentage points FiCO2')]:
                errors=[r[field] for r in rr]
                out.append(dict(panel=panel,scope='pure_HC' if panel=='C' else 'pure_and_mixed_HC',
                    input_mode=mode,representation_label='Study summary' if 'weighted' in mode else 'Reported observations',
                    direction=direction,units=units,n_points=len(rr),n_studies=len({r['study_id'] for r in rr}),
                    rmse=math.sqrt(math.fsum(w*e*e for w,e in zip(weights,errors))),
                    bias=math.fsum(w*e for w,e in zip(weights,errors)),
                    weighting='equal_paper_over_complete_panel',
                    n_PaCO2=sum(r['endpoint']=='PaCO2' for r in rr),n_PETCO2=sum(r['endpoint']=='PETCO2' for r in rr),
                    contributions=[dict(record_id=r['record_id'],study_id=r['study_id'],endpoint=r['endpoint'],
                        context=r['context'],fico2_pct=r['fico2_pct'],weight=w,error=e,
                        bias_contribution=w*e,mse_contribution=w*e*e) for r,w,e in zip(rr,weights,errors)],
                    interpretation='Each paper has total weight 1/J across its retained panel comparisons, shared equally over doses, endpoints and gas contexts. Reported and study-summary representations are scored separately. This descriptive mixture depends on available doses and conditions; it is not individual arterial accuracy or a causal mixed-gas comparison.'))
    return out


def make_payload(result,settings,issues):
    primary=result['primary_reported'];weighted=result['primary_weighted'];reported=result['reported_points'];allw=result['weighted_points']
    slopes=slope_summaries(primary,weighted,settings,issues)
    reference=settings['reference_baseline_mmhg'];guard=settings['max_paco2']
    evidence=result.get('slope_evidence')
    if evidence:
        slopes['curves']=[model_curve('fixed','FiCO₂ in medical air',settings['S'],reference,settings),
                          model_curve('rebreathing_reference','Rebreathing (reference)',evidence['rebreathing']['slope'],reference,settings)]
        slopes['curves'][1]['role']='literature_reference_only'
    curves=slopes['curves']
    doses=[r['fico2_pct'] for r in primary]
    bx=[max(0,min(doses)-1),max(doses)+1] if doses else [4,6]
    by=[min(40,5*math.floor(min([r['measured_mmhg'] for r in primary] or [40])/5)),
        max(60,5*math.ceil(max([r['measured_mmhg'] for r in primary] or [60])/5))]
    def identity_limits(rows,base):
        values=[v for r in rows for v in (r['estimated_paco2_mmhg'],r['measured_mmhg']-(r.get('measured_sd_mmhg') or 0),r['measured_mmhg']+(r.get('measured_sd_mmhg') or 0))]
        return [min(base[0],math.floor(min(values)-.5)),max(base[1],math.ceil(max(values)+.5))] if values else base
    cl=identity_limits(primary+weighted,[40,56]);dl=identity_limits(reported+allw,[40,63])
    primary_studies={r['study_id'] for r in primary};allstudies={r['study_id'] for r in reported}
    membership=[]
    for study,co,dose in sorted({(r['study_id'],r['context'],r['fico2_pct']) for r in reported}):
        rr=[r for r in reported if (r['study_id'],r['context'],r['fico2_pct'])==(study,co,dose)]
        ww=[r for r in allw if (r['study_id'],r['context'],r['fico2_pct'])==(study,co,dose)]
        membership.append(dict(study_id=study,context=co,fico2_pct=dose,reported_points=len(rr),subject_weighted_points=len(ww),paper_in_ABC=study in primary_studies,condition_in_ABC=co=='pure_HC',record_ids=';'.join(r['record_id'] for r in rr)))
    styles=[dict(color='#202326',linestyle='-',linewidth=1.5),dict(color='#7B2D8D',linestyle='-',linewidth=1.1),dict(color='#7F8C00',linestyle='--',linewidth=1.1)]
    if evidence:styles=[dict(color='#202326',linestyle='-',linewidth=1.5),dict(color='#7B2D8D',linestyle='--',linewidth=1.1)]
    counts={key:dict(total=len(rows),with_sd=sum(r.get('measured_sd_mmhg') is not None for r in rows)) for key,rows in
            [('reported',primary),('subject_weighted',weighted),('comparison_reported',reported),('comparison_subject_weighted',allw)]}
    return dict(presentation_version='current',analysis_version=VERSION,model_version=MODEL_VERSION,
        agreement_policy=result['agreement_policy'],agreement_metric_records=result['combined_metrics'],global_metric_records=result['global_metrics'],
        method_fingerprint='method_specific_literature_slopes_v1' if evidence else 'slope_first_reported_vs_subject_weighted',**slopes,curve=curves[0],
        reported=primary,subject_weighted=weighted,comparison_reported=reported,comparison_subject_weighted=allw,
        metrics={key:next(m for m in result['global_metrics'] if m['panel']=='C' and m['input_mode']==mode and m['direction']=='FiCO2_to_pressure') for key,mode in [('reported','reported'),('subject_weighted','within_paper_weighted')]},
        reference=dict(baseline_mmhg=reference,slope=settings['S'],max_paco2_mmhg=guard,
            curve_purpose='Fixed reference curve uses the configured illustration baseline; fixed-model errors use each record baseline. Descriptive curves are not independent validation.'),
        plotting=dict(A=dict(xlim=[0,max(12,3*math.ceil(max(c['fico2_pct'][-1] for c in curves)/3))],ylim=[min(30,reference),max(95,guard+15)]),
            B=dict(xlim=bx,ylim=by),C=dict(xlim=cl,ylim=cl),D=dict(xlim=dl,ylim=dl),jitter=False),
        notation=dict(arterial='PaCO₂',end_tidal='PETCO₂',inspired='FiCO₂',rule='a, ET and i inline; only chemical 2 is subscript.'),
        display_names=dict(reported='Reported observations',within_paper_weighted='Study summary'),
        comparison_membership=membership,
        comparison_scope=dict(n_papers=len(allstudies),n_reported=len(reported),n_subject_weighted=len(allw),primary_papers=sorted(primary_studies),
            additional_papers=sorted(allstudies-primary_studies),mixed_arms_in_primary_papers=sorted({r['study_id'] for r in result['mixed_reported']} & primary_studies),
            interpretation='Secondary descriptive comparison; pure-HC points repeat A-C. Conditions and representations are not independent samples. Panel D global metrics include all retained conditions with equal paper influence; dose/context-specific metrics are retained.'),
        comparison_metrics_by_condition=result['combined_mixed_metrics'],duration_summary=result['duration_summary'],
        uncertainty_records=[{key:r.get(key) for key in ('record_id','study_id','input_mode','context','endpoint','fico2_pct','subjects_n','baseline_mmhg','measured_mmhg','baseline_sd_mmhg','measured_sd_mmhg','uncertainty_status','uncertainty_note','uncertainty_source_locator')} for r in reported+allw],
        uncertainty=dict(error_bar='Vertical ±1 measured between-participant SD where source-reported or reconstructable.',
            no_x_error='Horizontal uncertainty is not shown; most studies lack paired individual data. Group-input predictions do not identify individual prediction dispersion.',
            counts=counts,missing='Undefined source uncertainty and unavailable repeated-measure covariance remain missing.',
            duplicate_policy='Coincident reported and study-summary representations share a bar; both markers remain.',
            metric_policy='Measured SD is descriptive, not a model weighting factor.',curve_style=styles),
        visual_design=dict(panel_B_title='Enlarged boxed region',curve_styles=styles,
            D_context_colors=dict(pure_HC='#008C95',HC_hyperoxia='#CC3D5C',HC_N2O_15pct='#545B66',HC_hypoxia='#A6761D',other_mixed='#777777'),
            D_reported_marker='o',D_reported_marker_size=2.6,D_reported_edge='white',D_reported_edge_width=.45,
            D_weighted_marker='D',D_weighted_marker_size=5.0,D_weighted_face='none',coordinate_policy='Original coordinates; no jitter.',
            zoom_connectors=[dict(from_A=[bx[1],by[1]],to_B=[bx[0],by[1]],color='#929ca3',linestyle=':',linewidth=.65),
                             dict(from_A=[bx[1],by[0]],to_B=[bx[0],by[0]],color='#929ca3',linestyle=':',linewidth=.65)]),
        settings=settings,model_parameters=dict(PaCO2_base=reference,**{k:settings[k] for k in PARAM_FIELDS}),
        sensitivity_slopes=dict(low=settings['slope_low'],fixed=settings['S'],high=settings['slope_high']),
        slope_evidence=evidence,provenance=result['provenance'])


def package_path(package_root=None):
    """Resolve the public package root (the directory containing ``data``)."""
    path = ROOT if package_root is None else Path(package_root).resolve()
    if not (path / 'data' / 'validation_inputs.json').is_file():
        raise InputError('Package root must contain data/validation_inputs.json')
    return path


def read_json(root, name):
    return json.loads((root / 'data' / name).read_text(encoding='utf-8'))


def slope_evidence_from_inputs(inputs):
    """Rebuild participant-weighted means and the two distinct scenario ranges.

    Independent selected subgroup records are pooled within a paper first.
    Repeated/overlapping cohorts are already represented once in the declared
    fixed selection; no eligible source is inferred here from a title or N.
    """
    evidence = {}
    for method in ('fico2', 'rebreathing'):
        item = inputs[method]
        selected = copy.deepcopy(item['source_records'])
        ids = [r['record_id'] for r in selected]
        if len(set(ids)) != len(ids) or not selected:
            raise InputError('HCVR source-record identifiers must be unique and nonempty')
        metadata = {r['study_id']: r for r in item['study_metadata']}
        groups = defaultdict(list)
        for row in selected:
            if row['method'] != method or row['health'] != 'Healthy':
                raise InputError('HCVR protocol/health differs from the selected evidence')
            n = number(row['n_subjects'], 'n_subjects', row['record_id'], positive=True)
            if int(n) != n:
                raise InputError('HCVR participant count must be an integer')
            slope = number(row['slope'], 'slope', row['record_id'], positive=True)
            row['n_times_s'] = n * slope
            groups[row['study_id']].append(row)
        contributions = []
        for study, rows in groups.items():
            n = math.fsum(r['n_subjects'] for r in rows)
            numerator = math.fsum(r['n_times_s'] for r in rows)
            contributions.append(dict(study_id=study, n_subjects=n, slope=numerator/n,
                n_times_s=numerator, source_record_ids=[r['record_id'] for r in rows],
                source_locator='; '.join(dict.fromkeys(str(r['source_locator']) for r in rows)),
                source_url=rows[0]['source_url'], **{k:v for k,v in metadata[study].items() if k!='study_id'}))
        n = math.fsum(c['n_subjects'] for c in contributions)
        numerator = math.fsum(c['n_times_s'] for c in contributions)
        result = dict(label=item['label'], slope=numerator/n, unit=item['unit'],
            n_papers=len(contributions), n_subjects=n, sum_n_s=numerator,
            study_contributions=contributions, source_records=selected,
            source_record_ids=ids, method='Sum of eligible participant N × source slope divided by sum of eligible N; compatible disjoint inputs combined within each paper first.',
            eligibility=item['eligibility'], basis=item['basis'], role=item['role'])
        if method == 'fico2':
            moments = []
            for row in selected:
                if row['uncertainty_type'] != 'SD' or row['n_subjects'] <= 1:
                    raise InputError('FiCO2 dispersion requires an identified sample SD and N > 1')
                sd = number(row['uncertainty'], 'source SD', row['record_id'], nonnegative=True)
                moments.append(dict(record_id=row['record_id'],
                    within_group_ss=(row['n_subjects']-1)*sd**2,
                    between_group_ss=row['n_subjects']*(row['slope']-result['slope'])**2))
            sd = math.sqrt(math.fsum(x['within_group_ss']+x['between_group_ss'] for x in moments)/(n-1))
            if result['slope']-sd <= 0:
                raise InputError('FiCO2 mean ± SD scenarios must retain positive slopes')
            result.update(sd=sd, sd_workings=moments,
                sd_method='sqrt(sum((N_i-1)*SD_i^2 + N_i*(S_i-S_mean)^2)/(N_total-1))',
                range=[result['slope']-sd, result['slope']+sd],
                range_kind='combined_participant_mean_plus_minus_sd',
                range_label='FiCO₂ participant-weighted mean ± combined participant SD; descriptive dispersion, not SE or a confidence interval',
                user_confirmed_adult_studies=sorted({r['study_id'] for r in selected if r['adult_eligibility_basis']=='user_confirmed'}),
                limitation='Ventilatory equilibrium is not independently established. The minute-to-alveolar ventilation transfer and Peebles adult eligibility remain explicit assumptions; the published minimum age remains unreported.')
        else:
            result.update(range=[min(c['slope'] for c in contributions), max(c['slope'] for c in contributions)],
                range_kind='eligible_study_mean_min_max',
                range_label='Range of eligible rebreathing study means; not individual extrema or a confidence interval',
                limitation='Descriptive participant-weighted mean across differing oxygen/rebreathing protocols. Cross-paper participant independence is assumed, not established.')
        evidence[method] = result
    return evidence


def calculate(package_root=None):
    """Calculate the selected public JSON dataset; does not read a workbook.

    Returns ``(validation, plot_payload)``. This function does not compare with
    stored expected answers; call :func:`load_analysis` for release verification.
    Independent explorations should be clearly separated from the fixed release.
    """
    root = package_path(package_root)
    settings_input = read_json(root, 'settings.json')
    settings = settings_input['values'].copy()
    evidence = slope_evidence_from_inputs(read_json(root, 'hcvr_inputs.json'))
    recalculated = dict(S=evidence['fico2']['slope'], slope_low=evidence['fico2']['range'][0],
                        slope_high=evidence['fico2']['range'][1])
    for key, value in recalculated.items():
        if not math.isclose(settings[key], value, rel_tol=0, abs_tol=1e-12):
            raise InputError(f'{key}: exported setting does not match recalculated HCVR source evidence')
        settings[key] = value
    # Params validates all physical model constants, including the pressure guard.
    parameters(settings, settings['reference_baseline_mmhg'])
    if settings['kpa_per_mmhg'] <= 0:
        raise InputError('The pressure unit conversion must be positive')
    source = read_json(root, 'validation_inputs.json')['records']
    ids = [r['record_id'] for r in source]
    if not ids or len(ids) != len(set(ids)):
        raise InputError('Selected validation record identifiers must be unique and nonempty')
    exact = [normalize(row, settings) for row in source]
    exposures = [(r['study_id'], r['participant_group_id'], r['exposure_id'], r['endpoint']) for r in exact]
    if len(exposures) != len(set(exposures)):
        raise InputError('A duplicate retained exposure would count the same measurement twice')
    if any(r['analysis_tier'] not in ('primary', 'mixed') for r in exact):
        raise InputError('The exact companion release contains only primary or mixed comparisons')
    weighted = weighted_inputs(exact, settings)
    primary = [r for r in exact if r['analysis_tier']=='primary']
    pw = [r for r in weighted if r['analysis_tier']=='primary']
    if not primary:
        raise InputError('No pure-HC comparison remains')
    issues = []
    durations, timing = duration_summary(primary, issues)
    combined = metrics_for(exact+weighted, combined=True)
    result = dict(validation_version=VERSION, model_version=MODEL_VERSION,
        settings=settings, setting_sources=settings_input['source_record_ids'],
        slope_evidence=evidence, agreement_policy=read_json(root, 'analysis_policy.json'),
        parameter_evidence=read_json(root, 'parameter_evidence.json'),
        reported_points=exact, weighted_points=weighted, primary_reported=primary, primary_weighted=pw,
        mixed_reported=[r for r in exact if r['analysis_tier']=='mixed'],
        mixed_weighted=[r for r in weighted if r['analysis_tier']=='mixed'],
        graph_reported=[], graph_weighted=[], graph_metrics=[],
        metrics=metrics_for(exact+weighted), paper_metrics=metrics_for(exact+weighted, per_paper=True),
        reported_equal_paper_sensitivity=reported_study_balanced_metrics(exact),
        global_metrics=global_metrics_for(exact+weighted), combined_metrics=combined,
        combined_primary_metrics=[m for m in combined if m['scope']=='pure_HC'],
        combined_mixed_metrics=[m for m in combined if m['scope']!='pure_HC'],
        issues=issues, durations=durations, duration_summary=timing,
        source_rows=copy.deepcopy(source), selection=copy.deepcopy(source), calculations=exact+weighted,
        provenance=read_json(root, 'provenance.json'))
    payload = make_payload(result, settings, issues)
    return result, payload


def verify_frozen_results(validation, plot_payload, package_root=None):
    """Assert every exported numerical expectation, including missing SD values.

    Expectations are read only after independently calculating the public input
    records. They cannot affect the model, row selection, summaries or metrics.
    """
    expected = read_json(package_path(package_root), 'expected_results.json')
    observed = dict(validation, curves=plot_payload['curves'])
    checked = [0]
    def compare(actual, wanted, path):
        if isinstance(wanted, dict):
            if not isinstance(actual, dict):
                raise AssertionError(path + ': expected mapping')
            for key, value in wanted.items():
                if key not in actual:
                    raise AssertionError(path + ': missing ' + key)
                compare(actual[key], value, path+'.'+key)
        elif isinstance(wanted, list):
            if not isinstance(actual, list) or len(actual) != len(wanted):
                raise AssertionError(path + ': list length differs')
            for i, (a, b) in enumerate(zip(actual, wanted)):
                compare(a, b, path+f'[{i}]')
        elif isinstance(wanted, (int, float)) and not isinstance(wanted, bool):
            if not isinstance(actual, (int, float)) or not math.isfinite(actual) or not math.isclose(actual, wanted, rel_tol=1e-12, abs_tol=1e-12):
                raise AssertionError(f'{path}: {actual!r} != {wanted!r}')
            checked[0] += 1
        elif actual != wanted:
            raise AssertionError(f'{path}: {actual!r} != {wanted!r}')
        else:
            checked[0] += 1
    compare(observed, expected, 'frozen')
    return dict(status='PASS', scalar_checks=checked[0],
        reported_points=len(validation['reported_points']), study_summaries=len(validation['weighted_points']),
        pure_reported=len(validation['primary_reported']), pure_summaries=len(validation['primary_weighted']),
        global_metrics=len(validation['global_metrics']),
        comparison='Recalculated selected inputs against frozen expectations; tolerance 1e-12 absolute/relative. Missing uncertainty remains missing.')


def load_analysis(package_root=None, *, verify=True):
    """Load and recalculate the public release, checking frozen parity by default."""
    validation, payload = calculate(package_root)
    if verify:
        validation['reproduction_check'] = verify_frozen_results(validation, payload, package_root)
    return validation, payload


if __name__ == '__main__':
    validation, _ = load_analysis()
    print(json.dumps(validation['reproduction_check'], indent=2))
