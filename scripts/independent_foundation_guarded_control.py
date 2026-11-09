"""Independent policy and run-hit replay; no production selectors/evaluators."""
import argparse,csv,io,json,zipfile
from pathlib import Path

def guarded(scores,k):
 n=len(scores);original=[(2*j+1)*n//(2*k) for j in range(k)];selected=original[:];bounds=[-1]+original+[n];gap=max(b-a-1 for a,b in zip(bounds,bounds[1:]));cuts=[0]+[(a+b+1)//2 for a,b in zip(original,original[1:])]+[n]
 for order in (list(range(k)),list(range(k-1,-1,-1))):
  for j in order:
   lo=max(cuts[j],(selected[j+1] if j+1<k else n)-gap-1);hi=min(cuts[j+1],(selected[j-1] if j else -1)+gap+2);current=selected[j]
   best=min(range(lo,hi),key=lambda i:(-scores[i],i))
   if scores[best]>scores[current]:selected[j]=best
 return sorted(selected,key=lambda i:(-scores[i],i))

def replay(source,outcomes):
 source=Path(source);outcomes=Path(outcomes);out=json.load(open(outcomes/'aggregate.json'));queues=json.load(open(outcomes/'queues-private.json'));checked=0
 for e in (31,34,37):
  entries=json.load(open(source/f'galar{e}-scores.json'))['complete_original_scores'];frames=[r['source_frame'] for r in entries];scores=[r['original_cnn_score'] for r in entries]
  with zipfile.ZipFile(source/'labels.zip') as z:rows=list(csv.DictReader(io.StringIO(z.read(f'{e}.csv').decode('utf-8-sig'))))
  y=[int(r['blood']) for r in rows];groups=[]
  for j,v in enumerate(y):
   if v:
    if j==0 or not y[j-1] or frames[j]-frames[j-1]!=5:groups.append([])
    groups[-1].append(j)
  for pct in (10,25):
   n=len(y);k=(n*pct+50)//100;uniform=[(2*j+1)*n//(2*k) for j in range(k)];bins=[max(range(j*n//k,(j+1)*n//k),key=lambda i:(scores[i],-i)) for j in range(k)]
   pol={'uniform':uniform,'score_bin':bins,'score_guarded':guarded(scores,k)}
   record=next(r for r in out['records'] if (r['exam'],r['percent'])==(e,pct))
   for name,qq in pol.items():
    assert set(qq)==set(queues[f'{e}:{pct}'][name]);q=set(qq);ref=record['policies'][name]
    assert ref['runs_reached']==sum(bool(q.intersection(g)) for g in groups)
    assert ref['singleton_hits']==sum(len(g)==1 and bool(q.intersection(g)) for g in groups)
    assert ref['positive_images']==sum(y[i] for i in q)
    checked+=1
 print(json.dumps({'selected_sets_and_counts_verified':checked,'all_match':True},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--outcomes',type=Path,required=True);a=p.parse_args();replay(a.source,a.outcomes)
