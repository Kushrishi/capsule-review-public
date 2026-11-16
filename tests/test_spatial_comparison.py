import pytest


def test_matched_encoder_update_and_inference_on_generated_images():
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from torchvision.models import resnet50
    from capsule_review.spatial_comparison import build_pair, update, frame_scores

    with torch.random.fork_rng():
        torch.manual_seed(19)
        control, spatial = build_pair(resnet50(weights=None).state_dict())
        for name, value in spatial.backbone.body.state_dict().items():
            assert torch.equal(value, control.state_dict()[name])
        images = torch.rand(1, 3, 576, 576)
        annotations = [{"boxes": torch.tensor([[40., 50., 90., 110.]]),
                        "labels": torch.tensor([2])}]
        for model, detector in ((control, False), (spatial, True)):
            optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
            assert update(model, optimizer, images, annotations, detector=detector).isfinite()
            scores = frame_scores(model, images, detector=detector)
            assert scores.shape == (1, 2)
            assert ((scores >= 0) & (scores <= 1)).all()
