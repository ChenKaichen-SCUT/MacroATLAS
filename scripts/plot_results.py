#!/usr/bin/env python3
"""Regenerate reviewer-facing SVGs and tables from checked observations."""
import argparse
import csv
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import check_results as checks

COLORS=('#555555','#28738D')
MARKERS=('s','o')


def finish(fig,path):
    fig.savefig(path,bbox_inches='tight',pad_inches=.035,metadata={'Date':None})
    plt.close(fig)


def runtime(ax,data,xfield):
    for method,color,marker in zip(checks.METHODS,COLORS,MARKERS):
        rr=sorted((r for r in data if r['algorithm']==method),key=lambda r:int(r[xfield]))
        x=[int(r[xfield]) for r in rr]
        # NaN is a plotting gap, never a replacement for a missing observation.
        y=[float(r['totalSec']) if r['status'] in checks.DECISIVE else np.nan for r in rr]
        ax.plot(x,y,color=color,marker=marker,label=method)
        censored=[int(r[xfield]) for r in rr if r['status']=='TIMEOUT']
        ax.scatter(censored,[180]*len(censored),marker='^',facecolors='none',edgecolors=color,s=25,zorder=4)
    ax.set_yscale('log');ax.set_ylim(.4,250)
    ax.set_ylabel('Runtime (s)');ax.axhline(180,color='.55',ls='--',lw=.6)
    ax.set_yticks([1,10,100,180],['1','10','100','180'])


def table(output,name,columns,data,caption):
    # One source supplies both text and embeddable LaTeX; no hand-entered values.
    md=['# '+caption,'','| '+' | '.join(columns)+' |','| '+' | '.join(['---']*len(columns))+' |']
    md += ['| '+' | '.join(map(str,r))+' |' for r in data]
    (output/(name+'.md')).write_text('\n'.join(md)+'\n')
    def esc(x):return str(x).replace('_',r'\_').replace('%',r'\%').replace('&',r'\&')
    lines=[r'\begin{table*}[t]',r'\centering',r'\small',r'\caption{'+caption+'}',
           r'\begin{tabular}{l'+('r'*(len(columns)-1))+'}',r'\toprule',
           ' & '.join(map(esc,columns))+r' \\',r'\midrule']
    lines += [' & '.join(map(esc,r))+r' \\' for r in data]
    lines += [r'\bottomrule',r'\end{tabular}',r'\end{table*}']
    (output/(name+'.tex')).write_text('\n'.join(lines)+'\n')


def main(output):
    checks.main()  # Every assertion must pass before any presentation is written.
    output.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.labelsize':8,
                         'axes.spines.top':False,'axes.spines.right':False,
                         'axes.linewidth':.65,'lines.linewidth':1.1,'lines.markersize':4,
                         'xtick.major.width':.6,'ytick.major.width':.6,'svg.fonttype':'path'})
    one=checks.rq1();two,obs=checks.rq2();three,_=checks.rq3()
    table(output,'rq1_correctness',['Setting','Status agreements','Optimum agreements'],
          [(r['group'],f"{r['status_agreements']}/{r['joint_decisive']}",f"{r['optimum_agreements']}/{r['joint_sat']}") for r in one],
          'Verification against the independent SMT oracle')
    table(output,'rq2_encoding',['Group','Paired/N','ATLAS-B success','MacroATLAS success','Macro variables smaller','Macro clauses smaller','Median C_V','Median C_C'],
          [(r['group'],f"{r['paired']}/{r['N']}",r['translation_atlas'],r['translation_macro'],r['macro_variables_smaller'],r['macro_clauses_smaller'],f"{r['median_C_V']:.2f}",f"{r['median_C_C']:.2f}") for r in two],
          'Translation success and encoding size of MacroATLAS and ATLAS-B')
    table(output,'rq3_performance',['Group','Method','SAT','UNSAT','Timeout','Error','Solved','PAR-2 (s)'],
          [(r['group'],r['method'],r['SAT'],r['UNSAT'],r['TIMEOUT'],r['ERROR'],r['solved'],f"{r['par2_mean']:.2f}") for r in three],
          'Solving performance on the 623 benchmark instances')
    labels=['Unconstrained','Constrained','Peterson','Robot','Voting','Weakening']
    groups=[[r for r in obs if r['group']==label] if i<2 else [r for r in obs if r['family']==['peterson','robot','voting_machine','weakening'][i-2]] for i,label in enumerate(labels)]
    positions=[0,1.6,3.05,4.25,5.45,6.7]
    values=[math.log2(r[k]) for r in obs for k in ['C_V','C_C']]
    lo,hi=math.floor(min(values)),math.ceil(max(values))
    fig,axes=plt.subplots(1,2,figsize=(8,2.65),sharey=True)
    for ax,metric,title in zip(axes,['C_V','C_C'],['(a) Variable ratio $C_V$','(b) Clause ratio $C_C$']):
        ax.boxplot([[math.log2(r[metric]) for r in g] for g in groups],positions=positions,widths=.45,patch_artist=True,
                   boxprops={'facecolor':'#EDF3F5','edgecolor':COLORS[1],'linewidth':.8},
                   medianprops={'color':'#222222','linewidth':1.1},
                   whiskerprops={'linewidth':.65},capprops={'linewidth':.65},
                   flierprops={'markersize':1.7,'markeredgecolor':'.5','alpha':.45})
        ax.axhline(0,color='.4',ls='--',lw=.8)
        ax.set_xticks(positions,['Unconstrained\nfamilies','Constrained\nfamilies',*labels[2:]],fontsize=7)
        ax.set_ylim(lo-.25,hi+.25);ax.set_yticks(np.arange(lo,hi+1,2))
        ax.text(.17,-.25,'OVERALL GROUPS',transform=ax.transAxes,ha='center',fontsize=6.6,color='.4')
        ax.text(.68,-.25,'CONSTRAINED FAMILIES',transform=ax.transAxes,ha='center',fontsize=6.6,color='.4')
        ax.text(.5,-.42,title,transform=ax.transAxes,ha='center',fontsize=9)
    axes[0].set_ylabel(r'$\log_2$(ATLAS-B / MacroATLAS)')
    fig.subplots_adjust(bottom=.29,wspace=.12)
    finish(fig,output/'rq2-encoding-ratios.svg')
    fig,ax=plt.subplots(figsize=(4.1,2.25))
    runtime(ax,checks.raw('rq4_unary.csv'),'axisValue');ax.set_xlabel('Unary depth')
    handles,legend=ax.get_legend_handles_labels()
    handles.append(Line2D([],[],color='.3',marker='^',mfc='none',ls='none',label='Timeout'))
    ax.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,1.01),ncol=3,frameon=False)
    finish(fig,output/'rq4-scalability.svg')
    data=checks.rows(checks.ROOT/'results/discussion/certified_controls.csv')
    fig,axes=plt.subplots(1,2,figsize=(7.5,2.3))
    runtime(axes[0],[r for r in data if r['family']=='rq4c_binary'],'certifiedMinBinary')
    axes[0].set_xlabel('Minimum binary nodes');axes[0].legend(frameon=False,fontsize=7)
    profile=sorted((r for r in data if r['family']=='rq4c_profile'),key=lambda r:int(r['actualQ']))
    for key,label,marker,style in [('fiberCount','Fiber catalog','o','-'),('vars','Variables','s','--'),('backendTotalClauses','Clauses','^','-.'),('totalSec','Runtime','D',':')]:
        axes[1].plot([int(r['actualQ']) for r in profile],[float(r[key])/float(profile[0][key]) for r in profile],label=label,marker=marker,ls=style)
    axes[1].set_yscale('log',base=2);axes[1].set_yticks([1,2,4,8,16,32,64],['1x','2x','4x','8x','16x','32x','64x'])
    axes[1].set_ylabel('Relative to q=1');axes[1].set_xlabel('Number of profile states q');axes[1].legend(frameon=False,fontsize=6.7)
    for ax,title in zip(axes,['(a) Binary branching control','(b) Constraint-profile overhead']):ax.text(.5,-.32,title,transform=ax.transAxes,ha='center')
    fig.subplots_adjust(wspace=.38,bottom=.26)
    finish(fig,output/'discussion-controls.svg')
    print('Wrote checked SVG, Markdown, and LaTeX outputs to',output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path('output/presentation'))
    main(p.parse_args().output)
