"""Synthetic objective and exact exposure controls; no medical inputs."""
import importlib.util
from pathlib import Path
import pytest
torch=pytest.importorskip('torch')
spec=importlib.util.spec_from_file_location('localrank',Path(__file__).parents[1]/'scripts/local_short_event_ranking.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_exact_pair_and_reference_exposure_schedule():
    for seed in m.SEEDS:
        c,p=m.schedule(seed)
        assert c.shape==(1024,16) and p.shape==(1024,8)
        assert torch.all(torch.bincount(c.flatten(),minlength=4096)==4)
        assert torch.all(torch.bincount(p.flatten(),minlength=32)==256)
        cc,pp=m.schedule(seed)
        assert torch.equal(cc,c) and torch.equal(pp,p)

def test_local_term_changes_gradients_and_rewards_correct_margin():
    y=torch.tensor([0]*16+[1]*8+[0]*8);w=torch.ones(2)
    logits=torch.zeros((32,2),requires_grad=True)
    total,ce,rank=m.objective(logits,y,w,.5)
    base,_,_=m.objective(logits,y,w,0.)
    assert total.item()>base.item()
    g=torch.autograd.grad(total,logits,retain_graph=True)[0]
    gb=torch.autograd.grad(base,logits)[0]
    assert torch.equal(g[:16],gb[:16])
    assert torch.all(g[16:24,1]<gb[16:24,1]) and torch.all(g[24:,1]>gb[24:,1])
    better=torch.zeros((32,2));better[16:24,1]=2.;better[24:,1]=-2.
    _,_,br=m.objective(better,y,w,.5)
    assert br.item()<rank.item()

def test_unknown_or_reversed_pair_cannot_enter_objective():
    with pytest.raises(ValueError,match='explicit'):
        m.objective(torch.zeros((32,2)),torch.zeros(32,dtype=torch.long),torch.ones(2),.5)
