"""CR-SP-01 model construction for full-field 576-pixel RGB inputs."""
from pathlib import Path
from hashlib import sha256
from io import BytesIO

import torch
from torch import nn
from torchvision.models import resnet50
from torchvision.models.detection import fasterrcnn_resnet50_fpn_v2
from torchvision.transforms.functional import normalize


def build_pair(encoder_state):
    classifier = resnet50(weights=None)
    classifier.load_state_dict(encoder_state, strict=True)
    detector = fasterrcnn_resnet50_fpn_v2(
        weights=None, weights_backbone=None, num_classes=3,
        min_size=576, max_size=576,
    )
    detector.backbone.body.load_state_dict(
        {key: value for key, value in encoder_state.items() if not key.startswith("fc.")},
        strict=True,
    )
    classifier.fc = nn.Linear(classifier.fc.in_features, 2)
    return classifier, detector


def load_pair(path: Path, expected_sha256: str):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Encoder checkpoint digest mismatch")
    return build_pair(torch.load(BytesIO(raw), map_location="cpu", weights_only=True))


def update(model, optimizer, images, annotations, *, detector):
    model.train()
    encoder = model.backbone.body if detector else model
    for layer in encoder.modules():
        if isinstance(layer, nn.BatchNorm2d):
            layer.eval()
    optimizer.zero_grad(set_to_none=True)
    if detector:
        loss = sum(model(images, annotations).values())
    else:
        flags = images.new_zeros((len(images), 2))
        for row, item in enumerate(annotations):
            flags[row, item["labels"] - 1] = 1
        logits = model(normalize(images, [.485, .456, .406], [.229, .224, .225]))
        loss = nn.functional.binary_cross_entropy_with_logits(logits, flags)
    if not torch.isfinite(loss):
        raise ValueError("Nonfinite training loss")
    loss.backward()
    optimizer.step()
    return loss.detach()


@torch.inference_mode()
def frame_scores(model, images, *, detector):
    model.eval()
    if not detector:
        return model(normalize(images, [.485, .456, .406], [.229, .224, .225])).sigmoid()
    scores = images.new_zeros((len(images), 2))
    for row, prediction in enumerate(model(images)):
        for column in range(2):
            retained = prediction["scores"][prediction["labels"] == column + 1]
            if retained.numel():
                scores[row, column] = retained.max()
    return scores
