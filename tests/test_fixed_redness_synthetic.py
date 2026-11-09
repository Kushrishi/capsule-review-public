"""Synthetic-only fixed-redness regression tests; never reads private medical images."""
import io, sys
from pathlib import Path
from PIL import Image
import pytest
np = pytest.importorskip("numpy", reason="Redness pixel tests require the optional ML dependency")
script_dir=Path(__file__).resolve().parents[1]/'scripts'
if not script_dir.is_dir():script_dir=Path(__file__).resolve().parent
sys.path.insert(0,str(script_dir))
from evaluate_fixed_redness import fixed_score, CIRCLE

def png(color):
    im=Image.new('RGB',(160,160),color)
    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()

def test_red_greater_than_green_and_grayscale():
    assert fixed_score(png((170,50,40)))>0.35
    assert fixed_score(png((60,180,60)))<0
    assert abs(fixed_score(png((127,127,127))))<1e-15

def test_neutral_border_ignored():
    x=np.zeros((160,160,3),dtype=np.uint8);x[:]=[240,30,30]
    x[:5]=0;x[-5:]=0;x[:,:5]=0;x[:,-5:]=0
    im=Image.fromarray(x);b=io.BytesIO();im.save(b,format='PNG')
    assert fixed_score(b.getvalue())>0.5

def test_black_image_stops():
    with pytest.raises(ValueError,match='No non-border pixels'):
        fixed_score(png((0,0,0)))

def test_non_png_stops():
    im=Image.new('RGB',(160,160),(170,50,40));b=io.BytesIO();im.save(b,format='JPEG')
    with pytest.raises(ValueError,match='Not an original PNG'):
        fixed_score(b.getvalue())

def test_aperture_is_inside_frame():
    assert CIRCLE.shape==(160,160)
    assert CIRCLE[80,80]
    assert not CIRCLE[0,0]


def fake_inputs():
    from evaluate_fixed_redness_pairs import evaluate
    counts={23:23,25:20,29:11,30:15}
    singletons={23:10,25:6,29:2,30:3}
    images=[]
    for i in range(137):
        images.append({'sha256':f'synthetic-{i}','blood':int(i<69)})
    pairs=[];index=0
    for ex,n in counts.items():
        for j in range(n):
            pairs.append({'exam':ex,'run_id':j,'run_length':1 if j<singletons[ex] else 2,
                          'positive_index':index,'negative_index':69+(index if index<68 else 0)})
            index+=1
    features=[{'image_index':i,'sha256':v['sha256'],'redness':float(0.6 if i<69 else 0.2)} for i,v in enumerate(images)]
    return evaluate,{'images':images,'pairs':pairs},{'n_images':137,'image_scores':features}


def test_aggregate_does_not_multiply_seeds_or_runs():
    evaluate,manifest,scores=fake_inputs()
    result=evaluate(manifest,scores)
    assert result['n_distinct_runs']==69 and result['n_distinct_singletons']==21
    assert result['pooled_correct']==69 and result['pooled_correct_singletons']==21
    assert result['macro_ordering']==1 and result['macro_singleton_ordering']==1
    assert not result['clinical_model_promoted'] and not result['downstream_10pct_event_recall_assessed']


def test_aggregate_rejects_false_source_labels():
    evaluate,manifest,scores=fake_inputs()
    manifest['images'][0]['blood']=0
    with pytest.raises(AssertionError):evaluate(manifest,scores)
