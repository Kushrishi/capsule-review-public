import pytest


def test_matched_encoder_update_and_inference_on_generated_images():
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from torchvision.models import resnet50
    from capsule_review.spatial_comparison import build_pair, update, frame_scores, make_optimizer

    with torch.random.fork_rng():
        torch.manual_seed(19)
        control, spatial = build_pair(resnet50(weights=None).state_dict())
        for name, value in spatial.backbone.body.state_dict().items():
            assert torch.equal(value, control.state_dict()[name])
        images = torch.rand(2, 3, 576, 576)
        annotations = [{"boxes": torch.tensor([[40.,50.,90.,110.],[1.,2.,9.,12.],[200.,220.,250.,270.]]),
                        "labels": torch.tensor([1,2,2])}, {"boxes":torch.empty(0,4),"labels":torch.empty(0,dtype=torch.long)}]
        for model, detector in ((control, False), (spatial, True)):
            optimizer = make_optimizer(model, detector=detector)
            bn = spatial.backbone.body.bn1 if detector else control.bn1
            before = bn.running_mean.clone()
            assert update(model, optimizer, images, annotations, detector=detector, microbatch_size=1).isfinite()
            assert torch.equal(before, bn.running_mean)
            scores = frame_scores(model, images, detector=detector)
            assert scores.shape == (2, 2)
            assert ((scores >= 0) & (scores <= 1)).all()


def test_uncensored_scores_and_threshold_ties():
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from capsule_review.spatial_comparison import proposal_maxima, development_threshold
    logits = torch.tensor([[0.,8.,-9.]]*110 + [[8.,0.,4.]])
    scores = proposal_maxima(logits,[111,0])
    assert 0 < scores[0,1] < .05
    assert scores[0,1] == logits[-1].softmax(0)[2]
    assert scores[1].tolist() == [0,0]
    assert development_threshold({"a":[.2]*39+[.8],"b":[.2]}) == .2


def test_draws_geometry_and_invalid_labels():
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from capsule_review.spatial_comparison import matched_draws, transform_square, update
    pools = [[2,3],[4]]
    assert list(matched_draws(pools,37,16)) == list(matched_draws(pools,37,16))
    img, boxes = transform_square(torch.zeros(3,100,200),torch.tensor([[0.,0.,100.,100.]]),1,True,1,1)
    assert boxes.tolist() == [[144.,288.,432.,576.]]
    with pytest.raises(ValueError,match="foreground"):
        update(None,None,img[None],[{"boxes":boxes,"labels":torch.tensor([0])}],detector=False)
