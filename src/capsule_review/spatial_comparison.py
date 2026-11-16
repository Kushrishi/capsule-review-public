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


IMAGENET_V2_SHA256 = "11ad3fa62ca79e40addfd354a8ec4b7c75143b3038b8d2a807fbc68deab379ca"


def load_pair(path: Path, expected_sha256: str = IMAGENET_V2_SHA256):
    raw = path.read_bytes()
    if expected_sha256 != IMAGENET_V2_SHA256 or sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Encoder checkpoint digest mismatch")
    return build_pair(torch.load(BytesIO(raw), map_location="cpu", weights_only=True))


def make_optimizer(model, *, detector):
    encoder = model.backbone.body if detector else model
    pretrained = {id(p) for name, p in encoder.named_parameters() if detector or not name.startswith("fc.")}
    groups = [{"params": [p for p in model.parameters() if (id(p) in pretrained) == is_encoder],
               "lr": lr} for is_encoder, lr in [(True, 1e-4), (False, 1e-3)]]
    return torch.optim.AdamW(groups, weight_decay=1e-4)


def update(model, optimizer, images, annotations, *, detector, microbatch_size=None):
    if len(images) != len(annotations) or not len(images) or images.shape[1:] != (3, 576, 576):
        raise ValueError("Expected aligned full-field 576-square images and targets")
    for target in annotations:
        labels, boxes = target["labels"], target["boxes"]
        if (labels.dtype != torch.int64 or labels.ndim != 1 or boxes.shape != (len(labels), 4)
                or not ((labels >= 1) & (labels <= 2)).all()
                or not ((boxes >= 0) & (boxes <= 576)).all()
                or not (boxes[:, 2:] > boxes[:, :2]).all()):
            raise ValueError("Invalid foreground label or box")
    size = len(images) if microbatch_size is None else microbatch_size
    if size < 1 or len(images) % size:
        raise ValueError("Physical batches must equally partition the effective batch")
    model.train()
    encoder = model.backbone.body if detector else model
    for layer in encoder.modules():
        if isinstance(layer, nn.BatchNorm2d):
            layer.eval()
    optimizer.zero_grad(set_to_none=True)
    total = images.new_zeros(())
    for start in range(0, len(images), size):
        batch = images[start:start + size]
        targets = annotations[start:start + size]
        if detector:
            loss = sum(model(batch, targets).values())
        else:
            flags = images.new_zeros((size, 2))
            for row, item in enumerate(targets):
                flags[row, item["labels"] - 1] = 1
            logits = model(normalize(batch, [.485, .456, .406], [.229, .224, .225]))
            loss = nn.functional.binary_cross_entropy_with_logits(logits, flags)
        loss = loss * (size / len(images))
        if not torch.isfinite(loss):
            raise ValueError("Nonfinite training loss")
        loss.backward()
        total += loss.detach()
    optimizer.step()
    return total


@torch.inference_mode()
def frame_scores(model, images, *, detector):
    model.eval()
    if not detector:
        return model(normalize(images, [.485, .456, .406], [.229, .224, .225])).sigmoid()
    transformed, _ = model.transform(list(images), None)
    features = model.backbone(transformed.tensors)
    proposals, _ = model.rpn(transformed, features, None)
    roi = model.roi_heads
    pooled = roi.box_roi_pool(features, proposals, transformed.image_sizes)
    logits, _ = roi.box_predictor(roi.box_head(pooled))
    return proposal_maxima(logits, [len(p) for p in proposals])


def proposal_maxima(logits, counts):
    """Maximum foreground posterior over fixed RPN proposals before ROI filtering."""
    probabilities = logits.softmax(-1)[:, 1:]
    return torch.stack([p.amax(0) if len(p) else logits.new_zeros(2)
                        for p in probabilities.split(counts)])


def matched_draws(pools, seed, count):
    """One shared plan. Pools contain target-positive and explicit-normal record IDs."""
    import random
    sampler = random.Random(f"draw:{seed}")
    augment = random.Random(f"augment:{seed}")
    for _ in range(count):
        index = sampler.choice(sampler.choice(pools))
        yield (index, augment.randrange(4), bool(augment.randrange(2)),
               augment.uniform(.9, 1.1), augment.uniform(.9, 1.1))


def transform_square(image, boxes, turns, flip, brightness, contrast):
    """Letterbox to 576, then apply identical edge-coordinate and image transforms."""
    from torchvision.transforms import functional as F
    height, width = image.shape[-2:]
    scale = 576 / max(height, width)
    h, w = max(1, round(height * scale)), max(1, round(width * scale))
    top, left = (576-h)//2, (576-w)//2
    image = F.adjust_contrast(F.adjust_brightness(F.resize(image, [h,w]), brightness), contrast)
    image = F.pad(image, [left,top,576-w-left,576-h-top])
    boxes = boxes * boxes.new_tensor([w/width,h/height,w/width,h/height])
    boxes += boxes.new_tensor([left,top,left,top])
    for _ in range(turns):
        image = image.rot90(1, [-2,-1])
        x,y,X,Y = boxes.unbind(1)
        boxes = torch.stack((y,576-X,Y,576-x), 1)
    if flip:
        image = image.flip([-1])
        x,y,X,Y = boxes.unbind(1)
        boxes = torch.stack((576-X,y,576-x,Y), 1)
    return image, boxes


def development_threshold(normal_scores_by_video):
    """Lowest threshold in [0,1] with strict alerts and video-balanced FPR <= 1/40."""
    from fractions import Fraction
    from collections import defaultdict
    videos = list(normal_scores_by_video.values())
    if not videos or any(not len(v) for v in videos):
        raise ValueError("Explicit normal support required")
    weights = defaultdict(Fraction)
    for scores in videos:
        for score in scores:
            if not 0 <= score <= 1:
                raise ValueError("Invalid frame score")
            weights[score] += Fraction(1, len(scores)*len(videos))
    remaining = Fraction(1)
    for threshold in sorted(set(weights) | {0.}):
        remaining -= weights[threshold]
        if remaining <= Fraction(1,40):
            return threshold


def select_checkpoint(recall_by_epoch):
    """Within each seed select highest mean target recall, then earliest epoch."""
    if set(recall_by_epoch) != {4,8,12,16,20}:
        raise ValueError("Incomplete checkpoint schedule")
    return min(recall_by_epoch, key=lambda epoch: (-sum(recall_by_epoch[epoch]), epoch))
