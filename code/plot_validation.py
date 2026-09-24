"""Four-panel validation with the FiCO2 slope as the operating model.

A–B show the FiCO2-in-medical-air curve and a rebreathing reference. Identity
coordinates and every validation metric use only the FiCO2 slope. Panel D
adds eligible mixed conditions without changing the A–C validation set.
"""
from pathlib import Path
import json, sys, math
import numpy as np
from plot_style import style, draw_points, decor, COLORS, P, F
from tutorial_analysis import calculate as calculate_figure
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
CONTEXTS = {"pure_HC":"#008C95", "HC_hyperoxia":"#CC3D5C", "HC_N2O_15pct":"#545B66", "HC_hypoxia":"#A6761D", "other_mixed":"#777777"}


def draw_sd(ax,rows,colors=COLORS,color_key='endpoint'):
    """One source SD bar per coincident representation; never zero-fill missing SD."""
    seen=set()
    for row in rows:
        sd=row['measured_sd_mmhg']
        if sd is None: continue
        group=row[color_key]
        key=(group,row['endpoint'],row['estimated_paco2_mmhg'],row['measured_mmhg'],sd)
        if key in seen: continue
        seen.add(key)
        container=ax.errorbar(row['estimated_paco2_mmhg'],row['measured_mmhg'],yerr=sd,
            fmt='none',ecolor=colors[group],elinewidth=.65,capsize=2,capthick=.65,zorder=2.8)
        container.set_label('Measured SD: '+row['record_id'])
    return seen

def draw_comparison_points(ax,rows,mode):
    reported=mode=='reported'
    for group,color in CONTEXTS.items():
        selected=[r for r in rows if r['context']==group]
        ax.plot([r['estimated_paco2_mmhg'] for r in selected],[r['measured_mmhg'] for r in selected],
            linestyle='none',marker='o' if reported else 'D',markersize=2.6 if reported else 5,
            markerfacecolor=color if reported else 'none',markeredgecolor='white' if reported else color,
            markeredgewidth=.45 if reported else .65,zorder=4 if reported else 5)

def publication_metric_rows(payload, mixed=False):
    """Global metrics for the complete C or D panel, separate representations."""
    panel='D' if mixed else 'C'
    out=[]
    for direction in ('FiCO2_to_pressure','pressure_to_FiCO2'):
        pair={m['input_mode']:m for m in payload['global_metric_records'] if m['panel']==panel and m['direction']==direction}
        r,w=pair['reported'],pair['within_paper_weighted']
        assert r['n_studies']==w['n_studies']
        out.append(dict(panel=panel,direction=direction,n_studies=r['n_studies'],
            reported_rmse=r['rmse'],reported_bias=r['bias'],summary_rmse=w['rmse'],summary_bias=w['bias']))
    return out

def draw_metric_table(fig,payload,position,mixed=False):
    rows=publication_metric_rows(payload,mixed)
    ax=fig.add_axes(position);ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    ax.text(0,1.05,f"Global RMSE / bias · {rows[0]['n_studies']} papers",fontsize=8.4,weight='bold')
    xs=[.015,.57,.88]
    for i,(x,label) in enumerate(zip(xs,['Estimated quantity','Reported','Study summary'])):
        ax.text(x,.76,label,ha='left' if i==0 else 'center',va='center',fontsize=7.6)
    ax.plot([0,1],[.63,.63],color='#92999e',lw=.5)
    for y,row,label in zip([.40,.10],rows,['Pressure (mmHg)',r'FiCO$_2$ (% points)']):
        vals=[label,f"{row['reported_rmse']:.2f} / {row['reported_bias']:+.2f}",f"{row['summary_rmse']:.2f} / {row['summary_bias']:+.2f}"]
        for i,(x,value) in enumerate(zip(xs,vals)):
            ax.text(x,y,value,ha='left' if i==0 else 'center',va='center',fontsize=8,color='#202326')


def combined(result, print_size=True, payload=None):
    style()
    plt.rcParams['svg.hashsalt'] = 'ssm-presentation-current'
    p = payload if payload is not None else calculate_figure()[1]
    width, height = 7.4, 8.8
    fig = plt.figure(figsize=(width, height))
    axes = [fig.add_axes(pos) for pos in [
        [.100,.768,.350,.184], [.590,.768,.350,.184],
        [.100,.385,.350,.350*width/height], [.590,.385,.350,.350*width/height]]]
    a,b,c,d = axes
    curve_labels={'fixed':r'FiCO$_2$ in medical air','rebreathing_reference':'Rebreathing (reference)'}
    assert [curve['id'] for curve in p['curves']]==['fixed','rebreathing_reference']
    assert abs(p['curves'][0]['slope']-p['model_parameters']['S'])<1e-12
    assert abs(p['curves'][1]['slope']-p['slope_evidence']['rebreathing']['slope'])<1e-12
    styles = [(spec['color'],spec['linestyle'],spec['linewidth'],curve_labels[curve['id']])
              for spec,curve in zip(p['visual_design']['curve_styles'],p['curves'])]
    assert len(styles)==2 and styles[1][2]<=styles[0][2]
    for curve,(colour,ls,lw,label) in zip(p['curves'],styles):
        for ax in (a,b):
            ax.plot(curve['fico2_pct'],curve['paco2_mmhg'],color=colour,linestyle=ls,linewidth=lw,zorder=2)
    guard=p.get('model_parameters',{}).get('max_paco2',80)
    xA,yA=p['plotting']['A']['xlim'],p['plotting']['A']['ylim']
    xB,yB=p['plotting']['B']['xlim'],p['plotting']['B']['ylim']
    a.axhspan(guard,yA[1],color='#f5f5f5',linewidth=0,zorder=0)
    a.axhline(guard,color='#aaaaaa',linewidth=.5,linestyle=':')
    a.text(.98,.95,f'Not applied above {guard:g} mmHg',transform=a.transAxes,ha='right',va='top',fontsize=8,color='#666666')
    a.add_patch(Rectangle((xB[0],yB[0]),xB[1]-xB[0],yB[1]-yB[0],fill=False,edgecolor='#929ca3',linewidth=.65,linestyle=':',zorder=1))
    for dose in sorted({r['fico2_pct'] for r in p['reported']}):
        b.axvline(dose,color='#bbbbbb',linestyle=':',linewidth=.5,zorder=1)
    draw_sd(c,p['reported']+p['subject_weighted'])
    draw_sd(d,p['comparison_reported']+p['comparison_subject_weighted'],CONTEXTS,'context')
    for ax in (a,b,c):
        for mode,rows in [('reported',p['reported']),('within_paper_weighted',p['subject_weighted'])]:
            draw_points(ax,rows,'estimated_paco2_mmhg' if ax is c else 'fico2_pct',mode)
    for mode,rows in [('reported',p['comparison_reported']),('within_paper_weighted',p['comparison_subject_weighted'])]:
        draw_comparison_points(d,rows,mode)
    a.set(xlim=xA,ylim=yA,xticks=[xA[0]+i*(xA[1]-xA[0])/4 for i in range(5)])
    b.set(xlim=xB,ylim=yB,xticks=list(range(2*math.ceil(xB[0]/2),2*math.floor(xB[1]/2)+1,2)))
    for ax,panel in [(c,'C'),(d,'D')]:
        lo,hi=p['plotting'][panel]['ylim']; ticks=list(range(math.ceil(lo/5)*5,math.floor(hi/5)*5+1,5))
        ax.plot([lo,hi],[lo,hi],'--',color='#909ba3',linewidth=.8,zorder=1)
        ax.set(xlim=(lo,hi),ylim=(lo,hi),xticks=ticks,yticks=ticks)
        ax.set_aspect('equal',adjustable='box')
    for ax,title,xlabel,ylabel in [(a,'A   Steady-state model',F,P),(b,'B   Enlarged boxed region',F,P),
        (c,'C   Predicted versus measured',r'Predicted PaCO$_2$ (mmHg)','Measured '+P),
        (d,'D   Pure and mixed hypercapnia',r'Predicted PaCO$_2$ (mmHg)','Measured '+P)]:
        decor(ax,title,xlabel,ylabel);ax.xaxis.grid(ax in (c,d));ax.title.set_fontsize(9.5)
    # Inline notebook rendering adds slightly more space to axis labels than
    # MATLAB; reserve a clear gap between C/D labels and the shared key.
    draw_metric_table(fig,p,[.09,.170,.365,.112])
    draw_metric_table(fig,p,[.58,.170,.365,.112],mixed=True)
    key=fig.add_axes([.09,.018,.86,.110]);key.set(xlim=(0,1),ylim=(0,1));key.axis('off')
    for x,curve,(colour,ls,lw,label) in zip([.08,.56],p['curves'],styles):
        key.plot([x,x+.05],[.95,.95],color=colour,linestyle=ls,linewidth=lw)
        key.text(x+.065,.95,f"{label}: S = {curve['slope']:.3f}",fontsize=8,va='center')
    key.text(.005,.60,'A–C:',fontsize=8.5,va='center',fontweight='bold')
    for x,colour,label in [(.095,COLORS['PETCO2'],r'PETCO$_2$'),(.27,COLORS['PaCO2'],r'PaCO$_2$')]:
        key.plot(x,.60,'o',color=colour,markersize=3);key.text(x+.018,.60,label,fontsize=8.5,va='center')
    key.text(.405,.60,'D:',fontsize=8.5,va='center',fontweight='bold')
    present=[(k,v) for k,v in CONTEXTS.items() if any(r['context']==k for r in p['comparison_reported'])]
    labels={'pure_HC':'Pure HC','HC_hyperoxia':'HC + hyperoxia','HC_N2O_15pct':r'HC + N$_2$O','HC_hypoxia':'HC + hypoxia','other_mixed':'Other mixed'}
    many=len(present)>3
    for i,(context,colour) in enumerate(present):
        x=(.10+.30*(i%3)) if many else (.46+.385*i/max(1,len(present)-1))
        y=(.52-.09*(i//3)) if many else .60;label=labels[context]
        key.plot(x,y,'o',color=colour,markersize=3);key.text(x+.018,y,label,fontsize=8.5,va='center')
    for x,marker,face,label in [(.105,'o','#333333','Reported observations'),(.555,'D','none','Study summary (primary)')]:
        ky=.32 if many else .40
        key.plot(x,ky,marker=marker,markersize=3 if marker=='o' else 4.3,markerfacecolor=face,markeredgecolor='#333333',markeredgewidth=.65)
        key.text(x+.022,ky,label,fontsize=8.5,va='center')
    key.text(.5,.17,'Equal paper weights across each panel; bias = predicted − measured. Bars: ±1 SD.',ha='center',va='center',fontsize=7.3,color='#444444')
    key.text(.5,-.02,p['duration_summary']['figure_note'],ha='center',va='center',fontsize=7.3,color='#444444')
    # Join the exact zoom corners graphically. White label backgrounds mask
    # tiny portions of the guide so axis labels remain readable.
    for text in [b.yaxis.label, *b.get_yticklabels()]:
        text.set_bbox(dict(facecolor='white',edgecolor='none',pad=0.5))
    fig.canvas.draw()
    for spec in p['visual_design']['zoom_connectors']:
        start=fig.transFigure.inverted().transform(a.transData.transform(spec['from_A']))
        end=fig.transFigure.inverted().transform(b.transData.transform(spec['to_B']))
        guide=Line2D([start[0],end[0]],[start[1],end[1]],transform=fig.transFigure,
            color=spec['color'],linestyle=spec['linestyle'],linewidth=spec['linewidth'],zorder=0.5)
        guide.set_gid('A-to-B-zoom-connector')
        # Axes patches are below these guides; artists and labels are above them.
        for ax in (a,b):
            ax.set_zorder(1)
            ax.patch.set_visible(False)
        fig.add_artist(guide)
    return fig

def make_figures(result,output_dir=None,payload=None):
    p = payload if payload is not None else calculate_figure()[1]
    figures={'fig3_validation':combined(result,payload=p)}
    if output_dir is not None:
        out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
        for name,fig in figures.items():
            for ext in ['png','pdf','svg']:
                metadata={'Date':None} if ext=='svg' else {'CreationDate':None,'ModDate':None} if ext=='pdf' else {}
                fig.savefig(out/(name+'.'+ext),dpi=600,metadata=metadata)
        (out/'figure_data_checks.json').write_text(json.dumps(dict(presentation_version='current',panel_count=4,
            primary_reported=len(p['reported']),primary_subject_weighted=len(p['subject_weighted']),D_reported=len(p['comparison_reported']),D_subject_weighted=len(p['comparison_subject_weighted']),
            source='data/validation_inputs.json',D_excluded_from_primary_metrics_slopes_duration=True,
            primary_model_slope=p['model_parameters']['S'],
            reference_only_rebreathing_slope=p['slope_evidence']['rebreathing']['slope'],
            validation_uses_fico2_slope_only=True,
            displayed_metric_rows=publication_metric_rows(p)+publication_metric_rows(p,mixed=True),
            metric_display='Global panel-specific RMSE and bias in both directions; equal paper weights',
            all_coordinates_unjittered=True,mean_HC_duration_minutes=p['duration_summary']['mean_duration_minutes'],
            duration_available_studies=p['duration_summary'].get('n_available_studies'),duration_primary_studies=len({r['study_id'] for r in p['reported']})),indent=2)+'\n')
    return figures

if __name__=='__main__':
    result,payload=calculate_figure()
    make_figures(result,ROOT/'figures/python',payload=payload)
    print('Exported Figure 3: four-panel validation figure.')
