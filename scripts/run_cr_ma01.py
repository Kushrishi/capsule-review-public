"""Execute the fixed private CR-MA-01 protocol; never download or publish inputs.

Separate fit, prediction-seal and evaluation phases prevent test-based selection.
Only two fresh fit processes are launched. Existing destinations are refused.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import importlib.metadata
from io import BytesIO
import json
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
COMMITMENT='ac9b6615c69d7f31a9f26ea8d114188fbc681885e0c74e7495ffec138f8e8a18'
IMAGENET='047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f'
ARMS=('scratch','mobilenet')


def sha(path):
    h=sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(4<<20):h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def inputs(frozen):
    folder=frozen/'qualified'
    if sha(folder/'COMMITMENT.json')!=COMMITMENT:raise ValueError('Private commitment changed')
    commitment=read(folder/'COMMITMENT.json')
    for name,entry in commitment['files'].items():
        if sha(folder/name)!=entry['sha256']:raise ValueError('Committed input changed: '+name)
    protocol=read(folder/'FINAL_PROTOCOL_PRIVATE.json')
    records=read(folder/'IMAGE_BACKED_CANDIDATE_SPLIT.json')['records_private']
    batches=read(folder/'SHARED_TRAINING_ORDER_PRIVATE.json')['batches']
    if len(records)!=5560 or len(batches)!=512 or any(len(b)!=32 for b in batches):raise ValueError('Frozen count/budget differs')
    if any(type(i)is not int or not 0<=i<len(records) or records[i]['split']!='train' for b in batches for i in b):raise ValueError('Training batch references a non-training image')
    groups={s:{r['video'] for r in records if r['split']==s} for s in ('train','validation','test')}
    if any(groups[a]&groups[b] for a,b in (('train','validation'),('train','test'),('validation','test'))):raise ValueError('Compromised source split')
    return protocol,records,batches


class Budget:
    def __init__(self,seconds=3600):self.start=time.monotonic();self.seconds=seconds
    def check(self):
        used=resource.getrusage(resource.RUSAGE_SELF)
        if time.monotonic()-self.start>self.seconds:raise RuntimeError('Frozen wall-time cap exceeded')
        if used.ru_maxrss*1024>4*1024**3:raise RuntimeError('Frozen 4-GiB RSS cap exceeded')
        return {'wall_seconds':time.monotonic()-self.start,'peak_RSS_bytes':used.ru_maxrss*1024,'cpu_user_seconds':used.ru_utime,'cpu_system_seconds':used.ru_stime}


def metrics(logits,records,classes):
    import numpy as np
    x=np.asarray(logits,dtype=np.float64)
    if x.shape!=(len(records),3) or not np.isfinite(x).all():raise ValueError('Nonfinite/misaligned logits')
    truth=np.array([classes.index(r['label']) for r in records]);pred=x.argmax(1)
    confusion=np.zeros((3,3),dtype=np.int64);np.add.at(confusion,(truth,pred),1)
    cells=defaultdict(list)
    for r,y,p in zip(records,truth,pred):cells[int(y),r['video']].append(int(y==p))
    recalls={classes[c]:float(np.mean([np.mean(v) for (k,_),v in cells.items() if k==c])) for c in range(3)}
    exact={classes[c]:sum((Fraction(sum(v),len(v)) for (k,_),v in cells.items() if k==c),Fraction())/sum(k==c for k,_ in cells) for c in range(3)}
    lse=x.max(1)+np.log(np.exp(x-x.max(1,keepdims=True)).sum(1))
    loss=float(np.mean(lse-x[np.arange(len(x)),truth]))
    f1=[];pooled={}
    for c in range(3):
        support=int(confusion[c].sum());den=support+int(confusion[:,c].sum())
        f1.append(2*int(confusion[c,c])/den if den else 0.)
        pooled[classes[c]]=int(confusion[c,c])/support
    videos={}
    for video in sorted({r['video'] for r in records}):
        ids=[i for i,r in enumerate(records) if r['video']==video]
        videos[video]={'frames':len(ids),'accuracy':float(np.mean(truth[ids]==pred[ids])),
                      'category_recalls':{classes[c]:sum(v)/len(v) for (c,v_id),v in cells.items() if v_id==video}}
    return {'class_then_video_macro_recall':float(np.mean(list(recalls.values()))),'category_video_macro_recalls':recalls,
            'category_pooled_frame_recalls':pooled,'macro_F1':float(np.mean(f1)),'confusion_matrix':confusion.tolist(),
            'multiclass_log_loss':loss,'frames':len(records),'videos_private':videos,
            'exact_recalls':{k:[v.numerator,v.denominator] for k,v in exact.items()}}


def select_step(measurements):
    return min(measurements,key=lambda r:(-sum((Fraction(*v) for v in r['metrics']['exact_recalls'].values()),Fraction())/3,r['metrics']['multiclass_log_loss'],r['step']))['step']


def setup_torch():
    import torch
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.set_default_dtype(torch.float32)
    torch.set_float32_matmul_precision('highest')
    torch.use_deterministic_algorithms(True)
    return torch


def model_for(arm,checkpoint=None,pretrained=None):
    import torch
    from capsule_review.baseline import AnatomyCNN
    torch.manual_seed(37)
    if arm=='scratch':model=AnatomyCNN(classes=3)
    elif arm=='mobilenet':
        from torchvision.models import mobilenet_v3_small
        model=mobilenet_v3_small(weights=None)
        if pretrained is not None:
            if sha(pretrained)!=IMAGENET:raise ValueError('Missing/changed required ImageNet checkpoint')
            model.load_state_dict(torch.load(pretrained,map_location='cpu',weights_only=True),strict=True)
        if model.classifier[3].in_features!=1024:raise ValueError('MobileNet head differs')
        model.classifier[3]=torch.nn.Linear(1024,3)
    else:raise ValueError('Unknown arm')
    if checkpoint is not None:
        state=torch.load(checkpoint,map_location='cpu',weights_only=True)
        if state['arm']!=arm:raise ValueError('Checkpoint architecture identity differs')
        model.load_state_dict(state['state_dict'],strict=True)
    if any(p.dtype!=torch.float32 or p.device.type!='cpu' for p in model.parameters()):raise ValueError('Expected CPU float32 model')
    return model


class Images:
    def __init__(self,root,records):self.root=root;self.records=records
    @lru_cache(maxsize=128)
    def get(self,i):
        import numpy as np
        import torch
        from PIL import Image,ImageOps
        r=self.records[i];path=(self.root/r['local_image']).resolve()
        if not path.is_relative_to(self.root.resolve()):raise ValueError('Image path escapes committed root')
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=r['source_sha256']:raise ValueError('Source mismatch at runtime')
        with Image.open(BytesIO(raw)) as im:
            im=ImageOps.exif_transpose(im).convert('RGB')
            im=ImageOps.pad(im,(224,224),method=Image.Resampling.BILINEAR,color=(0,0,0))
            x=np.asarray(im,dtype=np.float32).copy()/np.float32(255.)
        x=(x-np.array([.485,.456,.406],dtype=np.float32))/np.array([.229,.224,.225],dtype=np.float32)
        return torch.from_numpy(x.transpose(2,0,1).copy())
    def batch(self,indices):
        import torch
        return torch.stack([self.get(i) for i in indices])


def predict(model,bank,indices,budget):
    import torch
    model.eval();out=[]
    with torch.inference_mode():
        for start in range(0,len(indices),32):
            budget.check();y=model(bank.batch(indices[start:start+32]))
            if not torch.isfinite(y).all():raise RuntimeError('Nonfinite inference output')
            out.extend(y.tolist())
    return out


def fit(args):
    budget=Budget();torch=setup_torch();protocol,records,batches=inputs(args.frozen)
    arm=args.arm;folder=args.output/arm;folder.mkdir()
    write(folder/'FIT_STARTED.json',{'arm':arm,'seed':37,'committed_updates':512,'started_unix':time.time()})
    model=model_for(arm,pretrained=args.pretrained if arm=='mobilenet' else None);model.requires_grad_(True)
    parameter_count=sum(p.numel() for p in model.parameters())
    optimizer=torch.optim.AdamW(model.parameters(),lr=protocol['optimizer']['lr_baseline' if arm=='scratch' else 'lr_challenger'],
        betas=(.9,.999),eps=1e-8,weight_decay=.0001,amsgrad=False,foreach=False)
    bank=Images(args.images,records);classes=protocol['class_order'];validation=[i for i,r in enumerate(records) if r['split']=='validation']
    measurements=[]
    with (folder/'TRAINING_TRACE.jsonl').open('x') as trace:
        for step,batch in enumerate(batches,1):
            budget.check();model.train();optimizer.zero_grad(set_to_none=True)
            targets=torch.tensor([classes.index(records[i]['label']) for i in batch],dtype=torch.long)
            logits=model(bank.batch(batch));loss=torch.nn.functional.cross_entropy(logits,targets)
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite training loss')
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):raise RuntimeError('Nonfinite training gradient')
            optimizer.step();usage=budget.check()
            trace.write(json.dumps({'step':step,'batch_sha256':sha256(json.dumps(batch,separators=(',',':')).encode()).hexdigest(),
                                    'loss':float(loss.detach()),'resources':usage},allow_nan=False)+'\n');trace.flush()
            if step in protocol['validation_steps']:
                values=predict(model,bank,validation,budget)
                prediction_path=folder/f'validation-{step}.json'
                write(prediction_path,{'split':'validation','indices':validation,'logits':values})
                measured=metrics(values,[records[i] for i in validation],classes)
                path=folder/f'checkpoint-{step}.pt'
                with path.open('xb') as file:torch.save({'arm':arm,'step':step,'seed':37,'state_dict':model.state_dict()},file)
                row={'step':step,'metrics':measured,'checkpoint':path.name,'checkpoint_sha256':sha(path),
                     'validation_predictions':prediction_path.name,'validation_predictions_sha256':sha(prediction_path),'resources':budget.check()}
                measurements.append(row)
                write(folder/f'validation-measurement-{step}.json',row)
                print(json.dumps({'arm':arm,'step':step,'validation_macro_recall':measured['class_then_video_macro_recall'],'resources':budget.check()}),flush=True)
    selected=select_step(measurements);chosen=next(r for r in measurements if r['step']==selected)
    write(folder/'FIT_COMPLETE.json',{'status':'COMPLETE','arm':arm,'updates':512,'parameter_count':parameter_count,
        'validation_schedule':measurements,'selected_step':selected,'selected_checkpoint':chosen['checkpoint'],
        'selected_checkpoint_sha256':chosen['checkpoint_sha256'],'resources':budget.check()})


def seal(output,name,paths,extra):
    record={'schema':'capsule-review-cr-ma01-seal-v1','created_unix':time.time(),
            'files':{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths},**extra}
    write(output/name,record)
    digest=sha(output/name)
    with (output/(name+'.sha256')).open('x') as f:f.write(digest+'\n')
    for p in paths:p.chmod(0o444)
    print(json.dumps({'seal':name,'sha256':digest}),flush=True)
    return digest


def verify_seal(output,name):
    if sha(output/name)!=(output/(name+'.sha256')).read_text().strip():raise ValueError('Seal changed')
    record=read(output/name)
    for name,item in record['files'].items():
        if sha(output/name)!=item['sha256']:raise ValueError('Sealed file changed')
    return record


def controller(args):
    started=time.monotonic();args.output.mkdir()
    try:
        protocol,records,batches=inputs(args.frozen)
        if shutil.disk_usage(args.output).free < 4*1024**3:raise RuntimeError('Frozen 4-GiB disk headroom unavailable')
        if sha(args.pretrained)!=IMAGENET:raise ValueError('Missing required pretrained checkpoint')
        commitment=read(args.frozen/'qualified/COMMITMENT.json')
        for name,item in commitment['source_archives'].items():
            if sha(args.archives/name)!=item['sha256']:raise ValueError('Source archive mismatch')
        for r in records:
            if sha(args.images/r['local_image'])!=r['source_sha256']:raise ValueError('Runtime image mismatch')
        import torch,torchvision,numpy,PIL,inspect
        from capsule_review import baseline
        source_paths=[Path(__file__),Path(baseline.__file__),Path(inspect.getfile(torchvision.models.mobilenet_v3_small))]
        runtime={'python':platform.python_version(),'platform':platform.platform(),'packages':{p:importlib.metadata.version(p) for p in ('torch','torchvision','numpy','pillow','psutil')},'torch_config':torch.__config__.show()}
        resolutions={'source_commitment':COMMITMENT,'precision':'CPU float32, deterministic algorithms, four threads, interop one, highest float32 matmul precision',
            'inference_batch_size':32,'log_loss':'float64 logsumexp of saved float32 logits, mean over frames; no clipping',
            'training_data':'exact committed 512 batches, no DataLoader shuffling or random resampling','cache':'up to 128 pure preprocessed tensors, no changes to pixels/numerics',
            'advancement':'strict improvement in class-then-video macro recall and no decline in either lesion-category video-macro recall; exact rational count comparison; original pre-fit PR96 criterion',
            'no_extra_optimization':'no scheduler, augmentation, clipping, label smoothing, early stopping or retry',
            'resource_scope':'one hour per fit process including validation/checkpointing; two hours entire execution; 4 GiB peak RSS per process',
            'sources':{str(p):sha(p) for p in source_paths}}
        write(args.output/'RUNTIME.json',runtime);write(args.output/'IMPLEMENTATION_RESOLUTIONS.json',resolutions)
        write(args.output/'RUN_STARTED.json',{'source_commitment':COMMITMENT,'arms':ARMS,'started_unix':time.time()})
        import psutil
        for arm in ARMS:
            command=[sys.executable,str(Path(__file__).resolve()),'fit','--frozen',str(args.frozen),'--images',str(args.images),'--pretrained',str(args.pretrained),'--output',str(args.output),'--arm',arm]
            with (args.output/f'{arm}-process.log').open('x') as log:
                process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                begin=time.monotonic();cursor=0
                while process.poll() is None:
                    if time.monotonic()-begin>3600 or time.monotonic()-started>7200:
                        process.kill();process.wait();raise RuntimeError('Frozen wall-time cap exceeded; no retry')
                    try:
                        if psutil.Process(process.pid).memory_info().rss>4*1024**3:
                            process.kill();process.wait();raise RuntimeError('Frozen RSS cap exceeded; no retry')
                    except psutil.NoSuchProcess:pass
                    with (args.output/f'{arm}-process.log').open() as reader:
                        reader.seek(cursor);new=reader.read();cursor=reader.tell()
                        if new:print(new,end='',flush=True)
                    time.sleep(.1)
            if process.returncode:raise RuntimeError(f'{arm} failed with exit code {process.returncode}; no replacement fit')
        for p,digest in resolutions['sources'].items():
            if sha(p)!=digest:raise RuntimeError('Method source changed during fitting')
        sealed_paths=[args.output/'RUNTIME.json',args.output/'IMPLEMENTATION_RESOLUTIONS.json']
        for arm in ARMS:sealed_paths.extend(sorted((args.output/arm).glob('*')))
        seal(args.output,'FIT_SELECTION_SEAL.json',sealed_paths,{'source_commitment':COMMITMENT})
        # Test prediction production: no labels, metrics or decisions are computed.
        setup_torch();indices=[i for i,r in enumerate(records) if r['split']=='test'];bank=Images(args.images,records)
        for arm in ARMS:
            selected=read(args.output/arm/'FIT_COMPLETE.json')
            model=model_for(arm,checkpoint=args.output/arm/selected['selected_checkpoint'])
            values=predict(model,bank,indices,Budget(seconds=max(1,7200-(time.monotonic()-started))))
            write(args.output/f'{arm}-test-logits.json',{'indices':indices,'logits':values,'model_sha256':selected['selected_checkpoint_sha256']})
            del model
        verify_seal(args.output,'FIT_SELECTION_SEAL.json')
        paths=[args.output/f'{arm}-test-logits.json' for arm in ARMS]+[args.output/'FIT_SELECTION_SEAL.json']
        seal(args.output,'PRE_EVALUATION_SEAL.json',paths,{'source_commitment':COMMITMENT,'test_metrics_computed':False})
        write(args.output/'PREDICTION_STAGE_COMPLETE.json',{'wall_seconds':time.monotonic()-started,'test_metrics_computed':False,'fit_processes_started':2})
    except BaseException as error:
        if not (args.output/'TECHNICAL_FAILURE.json').exists():write(args.output/'TECHNICAL_FAILURE.json',{'status':'FAIL','reason':str(error),'type':type(error).__name__,'wall_seconds':time.monotonic()-started})
        raise


def evaluate(args):
    if (args.output/'TECHNICAL_FAILURE.json').exists():raise RuntimeError('Technical failure cannot be promoted')
    verify_seal(args.output,'FIT_SELECTION_SEAL.json');verify_seal(args.output,'PRE_EVALUATION_SEAL.json')
    protocol,records,_=inputs(args.frozen);result={}
    for arm in ARMS:
        values=read(args.output/f'{arm}-test-logits.json')
        result[arm]=metrics(values['logits'],[records[i] for i in values['indices']],protocol['class_order'])
    exact={arm:{k:Fraction(*v) for k,v in result[arm]['exact_recalls'].items()} for arm in ARMS}
    delta=sum(exact['mobilenet'].values(),Fraction())/3-sum(exact['scratch'].values(),Fraction())/3
    advance=delta>0 and all(exact['mobilenet'][c]>=exact['scratch'][c] for c in protocol['class_order'][:2])
    result['advancement']={'decision':'ADVANCE_EXPLORATORY_SYSTEM' if advance else 'DO_NOT_ADVANCE_FIXED_CONFIGURATION',
        'exact_macro_recall_difference':[delta.numerator,delta.denominator],
        'criterion':'strict macro improvement with neither lesion-category video-macro recall declining'}
    result['per_video_differences_private']={v:{'accuracy_difference':result['mobilenet']['videos_private'][v]['accuracy']-m['accuracy'],
        'category_recall_differences':{c:result['mobilenet']['videos_private'][v]['category_recalls'][c]-r for c,r in m['category_recalls'].items()}} for v,m in result['scratch']['videos_private'].items()}
    write(args.output/'TEST_RESULTS_PRIVATE.json',result)
    print(json.dumps({arm:{k:v for k,v in result[arm].items() if k not in ('videos_private','exact_recalls')} for arm in ARMS}|{'advancement':result['advancement']},indent=2))


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('stage',choices=['run','fit','evaluate'])
    cli.add_argument('--frozen',type=Path,required=True);cli.add_argument('--images',type=Path,required=True)
    cli.add_argument('--archives',type=Path);cli.add_argument('--pretrained',type=Path);cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--arm',choices=ARMS)
    args=cli.parse_args()
    for name in ('frozen','images','archives','pretrained','output'):
        if getattr(args,name,None) is not None:setattr(args,name,getattr(args,name).resolve())
    {'run':controller,'fit':fit,'evaluate':evaluate}[args.stage](args)
