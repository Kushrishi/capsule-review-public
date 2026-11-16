"""Generated inputs only; no research fitting, private data or model weights."""
from fractions import Fraction
from pathlib import Path
import sys
import pytest
pytest.importorskip('numpy')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_cr_ma01 import metrics,select_step,write,verify_seal,sha,inputs

CLASSES=['Angiectasia','Erosion','Normal']


def test_video_balancing_is_distinct_from_pooled_frame_recall():
    rows=[{'label':'Angiectasia','video':'A'}]*9+[{'label':'Angiectasia','video':'B'},
          {'label':'Erosion','video':'A'},{'label':'Normal','video':'B'}]
    logits=[[4.,0.,0.]]*9+[[0.,0.,4.],[0.,4.,0.],[0.,0.,4.]]
    out=metrics(logits,rows,CLASSES)
    assert out['category_video_macro_recalls']['Angiectasia']==.5
    assert out['category_pooled_frame_recalls']['Angiectasia']==.9
    assert out['class_then_video_macro_recall']==pytest.approx(5/6)
    assert out['confusion_matrix']==[[9,0,1],[0,1,0],[0,0,1]]
    assert out['exact_recalls']['Angiectasia']==[1,2]


def test_logits_ties_choose_lowest_category_and_loss_is_stable():
    rows=[{'label':c,'video':'V'} for c in CLASSES]
    out=metrics([[0.,0.,0.],[0.,10000.,0.],[0.,0.,10000.]],rows,CLASSES)
    assert out['confusion_matrix']==[[1,0,0],[0,1,0],[0,0,1]]
    import math
    assert out['multiclass_log_loss']==pytest.approx(math.log(3)/3)
    with pytest.raises(ValueError,match='Nonfinite'):metrics([[float('nan')]*3]*3,rows,CLASSES)


def test_validation_selection_primary_then_loss_then_earliest():
    def row(step,recall,loss):
        return {'step':step,'metrics':{'exact_recalls':{c:[recall,10] for c in CLASSES},'multiclass_log_loss':loss}}
    assert select_step([row(128,5,.1),row(256,6,10)])==256
    assert select_step([row(128,5,.2),row(256,5,.1)])==256
    assert select_step([row(256,5,.1),row(128,5,.1)])==128


def test_seals_reject_tampering_and_outputs_never_overwrite(tmp_path):
    write(tmp_path/'data.json',{'generated':True})
    record={'files':{'data.json':{'sha256':sha(tmp_path/'data.json')}}}
    write(tmp_path/'seal.json',record)
    (tmp_path/'seal.json.sha256').write_text(sha(tmp_path/'seal.json'))
    verify_seal(tmp_path,'seal.json')
    with pytest.raises(FileExistsError):write(tmp_path/'data.json',{})
    (tmp_path/'data.json').write_text('{}')
    with pytest.raises(ValueError,match='Sealed file'):verify_seal(tmp_path,'seal.json')


def test_separate_stdlib_metrics_on_synthetic_known_counts():
    from verify_cr_ma01 import calculate,compare
    rows=[{'label':c,'video':'generated'} for c in CLASSES]
    logits=[[0.,0.,0.],[0.,3.,0.],[0.,1.,2.]]
    independent=calculate(logits,rows,CLASSES)
    assert independent['primary']==Fraction(1)
    compare(independent,metrics(logits,rows,CLASSES))


def test_preprocessing_full_field_padding_and_byte_guard(tmp_path):
    pytest.importorskip('torch')
    from PIL import Image
    from run_cr_ma01 import Images
    Image.new('RGB',(448,224),(255,0,0)).save(tmp_path/'generated.png')
    rows=[{'local_image':'generated.png','source_sha256':sha(tmp_path/'generated.png')}]
    out=Images(tmp_path,rows).get(0)
    assert tuple(out.shape)==(3,224,224)
    assert out[0,0,0].item()==pytest.approx(-.485/.229)
    assert out[0,112,112].item()==pytest.approx((1-.485)/.229)
    assert out[1,112,112].item()==pytest.approx(-.456/.224)
    rows[0]['source_sha256']='0'*64
    with pytest.raises(ValueError,match='Source mismatch'):Images(tmp_path,rows).get(0)


def test_independent_verifier_rejects_optimized_python():
    import subprocess
    verifier = Path(__file__).resolve().parents[1] / 'scripts' / 'verify_cr_ma01.py'
    result = subprocess.run([sys.executable, '-O', str(verifier), '--help'],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'verification requires assertions' in result.stderr
