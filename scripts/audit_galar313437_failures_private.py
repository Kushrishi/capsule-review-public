"""Ancillary post-outcome failure diagnostics; all inputs/outputs stay private."""
from pathlib import Path
import json,collections,bisect
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--private-dir',type=Path,required=True)
args=parser.parse_args()
p=args.private_dir.resolve()
if p.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Private evidence must stay outside public Git.')
report=json.loads((p/'aggregate.json').read_text());out={}
for e in (31,34):
 s=json.loads((p/f'galar{e}-scores.json').read_text());rows=json.loads((p/f'galar{e}-outcome-join.json').read_text());scores=[x['original_cnn_score'] for x in rows];y=[x['blood_label'] for x in rows];n=len(y)
 runs=[]
 for i,v in enumerate(y):
  if v:
   if i==0 or not y[i-1]:runs.append([])
   runs[-1].append(i)
 rid={pos:j for j,run in enumerate(runs) for pos in run}
 def stratum(j):return '1-5' if len(runs[j])<=5 else '6-25' if len(runs[j])<=25 else '26+'
 out[str(e)]={}
 for percent in (10,25):
  q=next(x for x in s['frozen_queues'] if x['review_percent']==percent);k=q['k'];policies={**q['policies'],'temporal_window3_score_bin':q['temporal_window3_score_bin']};v={}
  for method,positions in policies.items():
   c=collections.Counter(rid[i] for i in positions if y[i]);positive=sum(c.values())
   v[method]={'positive_images_by_run_stratum':{z:sum(a for j,a in c.items() if stratum(j)==z) for z in ('1-5','6-25','26+')},'maximum_positive_hits_in_one_run':max(c.values(),default=0),'fraction_positive_hits_in_most_selected_run':max(c.values(),default=0)/positive if positive else None}
  rawset=set(policies['score_bin']);tempset=set(policies['temporal_window3_score_bin']);lost=[run for run in runs if rawset.intersection(run) and not tempset.intersection(run)]
  starts=[i*n//k for i in range(k)];tempbybin={bisect.bisect_right(starts,i)-1:i for i in tempset};smooth=[max(scores[max(0,i-1):min(n,i+2)]) for i in range(n)]
  plateau=0
  for run in lost:
   if len(run)>5:continue
   explained=False
   for raw in rawset.intersection(run):
    t=tempbybin[bisect.bisect_right(starts,raw)-1]
    if t==raw-1 and y[t]==0 and smooth[t]==smooth[raw] and smooth[t]==scores[raw]:explained=True
   plateau+=explained
  v['temporal_mechanism']={'short_runs_lost':sum(len(r)<=5 for r in lost),'short_runs_lost_with_adjacent_leftward_max_plateau_tie':plateau}
  c=report['examinations'][str(e)][str(percent)]['controls']
  v['control_summaries']={z:{'mean_runs':c[z]['runs_reached']['mean'],'reference_95_interval':c[z]['runs_reached']['reference_95_interval']} for z in ('within_bin_permuted_scores','geometry_uniform_in_bin','systematic_phase_sensitivity','coarse16_circular_shift')}
  out[str(e)][str(percent)]=v
with (p/'supplemental-failure-aggregate.json').open('x') as f:json.dump(out,f,indent=2)
for e,budgets in out.items():
 for b,v in budgets.items():print(e,b,'GLOBAL',v['score'],'TEMPORAL',v['temporal_mechanism'],'COARSE',v['control_summaries']['coarse16_circular_shift'])
