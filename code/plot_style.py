"""Shared current scientific figure style and point encodings."""
from pathlib import Path
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
COLORS = {'PETCO2': '#2875ad', 'PaCO2': '#c16631'}
CONTEXTS = {'pure_HC': '#2875ad', 'HC_hyperoxia': '#c16631', 'HC_N2O_15pct': '#7c559a'}
P = r'PaCO$_2$ / PETCO$_2$ (mmHg)'
F = r'FiCO$_2$ (%)'

def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
        'mathtext.fontset': 'dejavusans', 'axes.labelsize': 9,
        'axes.titlesize': 10, 'axes.linewidth': .65,
        'xtick.major.width': .65, 'ytick.major.width': .65,
        'xtick.major.size': 3, 'ytick.major.size': 3,
        'axes.spines.top': False, 'axes.spines.right': False,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
        'svg.hashsalt': 'ssm-presentation-v7', 'savefig.facecolor': 'white'})

def draw_points(ax, rows, xkey, mode, colors=COLORS, color_key='endpoint'):
    for group, color in colors.items():
        group_rows = [x for x in rows if x[color_key] == group]
        if not group_rows:
            continue
        reported = mode == 'reported'
        ax.plot([x[xkey] for x in group_rows], [x['measured_mmhg'] for x in group_rows],
            linestyle='none', marker='o' if reported else 'D',
            markersize=3 if reported else 4.3,
            markerfacecolor=color if reported else 'none',
            markeredgecolor=color, markeredgewidth=.65,
            zorder=4 if reported else 5)

def decor(ax, title, xlabel, ylabel):
    ax.set_title(title, loc='left', fontweight='bold', pad=7)
    ax.set_xlabel(xlabel, labelpad=4)
    ax.set_ylabel(ylabel, labelpad=4)
    ax.grid(True, color='#e6e9eb', linewidth=.45)
    ax.set_axisbelow(True)

