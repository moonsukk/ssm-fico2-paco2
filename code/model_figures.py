"""Model illustrations from source-derived FiCO2 and rebreathing evidence.

Only the FiCO2-in-medical-air slope supplies the operating model. Rebreathing
is an explicitly labelled reference. Evidence ranges are sensitivity scenarios,
not confidence intervals or prediction intervals.
"""
from pathlib import Path
from dataclasses import replace
import os
import textwrap
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
from ssm import Params, fico2_to_paco2

PRIMARY='#202326'
REFERENCE='#7B2D8D'


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.labelsize':10,'axes.titlesize':11,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'ps.fonttype':42,'savefig.facecolor':'white','svg.hashsalt':'ssm-workbook-model'})


def save(fig,name,out):
    out.mkdir(parents=True,exist_ok=True)
    for ext in ('png','pdf','svg'):
        metadata={'Date':None} if ext=='svg' else {'CreationDate':None,'ModDate':None} if ext=='pdf' else {}
        fig.savefig(out/(name+'.'+ext),dpi=300,bbox_inches='tight',metadata=metadata)
    plt.close(fig)


def conversion_curve(grid,params):
    """Retain the numerical guard; unsupported pressures are missing, not clipped."""
    output=[]
    for dose in grid:
        try: output.append(fico2_to_paco2(float(dose),params))
        except ValueError: output.append(float('nan'))
    return np.asarray(output)


def make_figures(params=None,slope_scenarios=None,output_dir=None,*,slope_evidence=None):
    """Render Figures 1–2 from the same reviewed slope evidence as validation.

    ``slope_scenarios`` remains a compatibility argument only. Supplying it
    cannot substitute generic bounds for the method-specific source evidence.
    """
    if params is None or slope_evidence is None:
        from tutorial_analysis import calculate
        _,payload=calculate()
        params=params or Params(**payload['model_parameters'])
        slope_evidence=slope_evidence or payload['slope_evidence']
    p=params;out=Path(output_dir) if output_dir else ROOT/'figures';style()
    evidence=[slope_evidence[key] for key in ('fico2','rebreathing')]
    assert abs(float(evidence[0]['slope'])-p.S)<1e-12, 'The FiCO2 slope must be the operating-model slope.'
    colours=[PRIMARY,REFERENCE];linestyles=['-','--'];widths=[1.5,1.1]
    labels=['FiCO$_2$ in medical air','Rebreathing (reference)']
    top=min(p.PaCO2_base+10,p.max_paco2)
    grid=np.linspace(p.PaCO2_base,top,101)
    fig,ax=plt.subplots(figsize=(6.4,3.9),layout='constrained')
    maximum=p.VA_base
    for item,colour,linestyle,width,label in zip(evidence,colours,linestyles,widths,labels):
        scenario=replace(p,S=float(item['slope']))
        values=np.asarray([scenario.VA(v) for v in grid]);maximum=max(maximum,float(values.max()))
        ax.plot(grid,values,color=colour,ls=linestyle,lw=width,
                label=f'{label}: S = {scenario.S:.3f}')
    ax.scatter([p.PaCO2_base],[p.VA_base],color=PRIMARY,s=22,zorder=3)
    ax.annotate(f'Baseline: {p.PaCO2_base:g} mmHg; {p.VA_base:.2f} L min$^{{-1}}$',
                (p.PaCO2_base,p.VA_base),(p.PaCO2_base+2,p.VA_base),fontsize=9,
                arrowprops=dict(arrowstyle='-',color='0.45',lw=.7),va='center')
    ax.set(xlabel='Arterial CO$_2$, PaCO$_2$ (mmHg)',
           ylabel='Alveolar ventilation, $\\dot V_A$ (L min$^{-1}$)',
           xlim=(p.PaCO2_base-.5,top+.5),ylim=(0,maximum*1.12))
    ax.legend(loc='upper left',frameon=False,title='S in L min$^{-1}$ mmHg$^{-1}$',title_fontsize=9)
    ax.grid(alpha=.18);save(fig,'fig1_hcvr',out)

    save(sensitivity_figure(p,slope_evidence),'fig2_conversion_sensitivity',out)


def sensitivity_figure(p,slope_evidence):
    """Editable shared-axis sensitivity illustration used by figure and tutorial."""
    style()
    evidence=[slope_evidence[key] for key in ('fico2','rebreathing')]
    colours=[PRIMARY,REFERENCE];linestyles=['-','--'];widths=[1.5,1.1]
    labels=['FiCO$_2$ in medical air','Rebreathing (reference)']
    # One shared axis; hatch the reference envelope to distinguish overlapping
    # sensitivity regions without implying that they have the same meaning.
    fig,ax=plt.subplots(figsize=(6.4,4.35),layout='constrained')
    doses=np.linspace(0,8,241);maximum=p.PaCO2_base
    handles=[]
    for item,colour,linestyle,width,label in zip(evidence,colours,linestyles,widths,labels):
        slope=float(item['slope']);central=conversion_curve(doses,replace(p,S=slope))
        finite=central[np.isfinite(central)]
        if len(finite): maximum=max(maximum,float(finite.max()))
        handles.append(Line2D([],[],color=colour,ls=linestyle,lw=width,label=f'{label}: S = {slope:.3f}'))
        bounds=item.get('range')
        range_label={
            'combined_participant_mean_plus_minus_sd':f"Mean ± combined participant SD ({item.get('n_papers',0):g} papers)",
            'source_mean_plus_minus_sd':f"Source mean ± SD ({item.get('n_papers',1):g} paper)",
            'eligible_study_mean_min_max':f"Study-mean range ({item.get('n_papers',0):g} papers)",
        }.get(item.get('range_kind'),item.get('range_label','No between-study range available'))
        if bounds is not None:
            assert len(bounds)==2 and 0<=bounds[0]<=slope<=bounds[1], 'Invalid literature sensitivity bounds.'
            curves=np.asarray([conversion_curve(doses,replace(p,S=float(bound))) for bound in bounds])
            valid=np.all(np.isfinite(curves),axis=0)
            low=np.min(curves,axis=0);high=np.max(curves,axis=0)
            reference=item is evidence[1]
            hatch='////' if reference else None
            ax.fill_between(doses,low,high,where=valid,facecolor='none' if reference else colour,
                            edgecolor=colour,alpha=.28 if reference else .12,hatch=hatch,linewidth=0,zorder=1)
            for curve in curves:
                ax.plot(doses,curve,color=colour,lw=.7,alpha=.60,zorder=2)
            finite=curves[np.isfinite(curves)]
            if len(finite):maximum=max(maximum,float(finite.max()))
            handles.append(Patch(facecolor='none' if reference else colour,alpha=.28 if reference else .12,
                edgecolor=colour if reference else 'none',hatch=hatch,
                label=f'{range_label}: S = {bounds[0]:.2f}–{bounds[1]:.2f}'))
        ax.plot(doses,central,color=colour,ls=linestyle,lw=width,zorder=3)
    ax.set(xlabel='FiCO$_2$ (%)',ylabel='Steady-state model PaCO$_2$ estimate (mmHg)',
           xlim=(0,8),ylim=(p.PaCO2_base-1,min(p.max_paco2+1,maximum+2)))
    ax.legend(handles=handles,loc='upper left',frameon=False,fontsize=8.5,labelspacing=.7)
    ax.grid(alpha=.18)
    fig.supxlabel('S in L min$^{-1}$ mmHg$^{-1}$; bands are sensitivity scenarios',fontsize=8,color='0.35')
    return fig



if __name__=='__main__':make_figures()
