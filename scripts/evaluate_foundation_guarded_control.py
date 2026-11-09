"""Prespecified exploratory policy control using frozen original-CNN scores."""
import argparse,csv,io,json,hashlib,zipfile
from pathlib import Path
from capsule_review.priority import select_positions
from capsule_review.geometry_control import annotation_runs,metrics
from exam_heldout_pair_transfer import private,sha

HASHES={31:'c4cc7e58dda3540537df1ca78ba78f3724ccc4f059d501578aa2cdf7e2531a63',34:'9c524e4b486253f455fafee1b3c356fa50e2576fd80c164e1fc75b23bff57ace',37:'fbe8b44540d51f3fdf967fed7775d39e56046a504a4988503682d19714820052'}

def run(source,output):
 source=private(source);output=private(output)
 if output.exists():raise FileExistsError('Never overwrite policy outcomes.')
 labels=source/'labels.zip';assert sha(labels)=='2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
 result={'exploratory_already_inspected_sources':True,'no_new_inference':True,'model_promoted':False,'records':[]};queues={}
 for e in (31,34,37):
  p=source/f'galar{e}-scores.json';assert sha(p)==HASHES[e];entries=json.loads(p.read_text())['complete_original_scores'];frames=[x['source_frame'] for x in entries];scores=[x['original_cnn_score'] for x in entries]
  with zipfile.ZipFile(labels) as z:rr=list(csv.DictReader(io.StringIO(z.read(f'{e}.csv').decode('utf-8-sig'))))
  assert frames==[int(r['frame']) for r in rr];assert all(r['blood'] in ('0','1') for r in rr);y=[int(r['blood']) for r in rr];runs=annotation_runs(y,frames,5)
  for pct in (10,25):
   k=(len(y)*pct+50)//100;pol={};qq={}
   for method in ('uniform','score_bin','score_guarded'):
    q=select_positions(scores,k,method);chosen=set(q);assert len(chosen)==k;out=metrics(y,runs,q);out['singleton_hits']=sum(len(r)==1 and bool(chosen&set(r)) for r in runs);out['singleton_runs']=sum(len(r)==1 for r in runs)
    b=[-1,*sorted(q),len(y)];out['max_omitted_gap']=max(v-u-1 for u,v in zip(b,b[1:]));out['moved_vs_uniform']=len(chosen-set(select_positions(scores,k,'uniform')));pol[method]=out;qq[method]=list(q)
   assert pol['score_guarded']['max_omitted_gap']<=pol['uniform']['max_omitted_gap']
   result['records'].append({'exam':e,'percent':pct,'n':len(y),'k':k,'positive_runs':len(runs),'policies':pol});queues[f'{e}:{pct}']=qq
 result['macro']={}
 for pct in (10,25):
  rows=[r for r in result['records'] if r['percent']==pct and r['positive_runs']]
  result['macro'][str(pct)]={method:sum(r['policies'][method]['run_recall'] for r in rows)/len(rows) for method in ('uniform','score_bin','score_guarded')}
 output.mkdir();(output/'aggregate.json').write_text(json.dumps(result,indent=2));(output/'queues-private.json').write_text(json.dumps(queues));print(json.dumps(result['macro'],indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.source,a.output)
