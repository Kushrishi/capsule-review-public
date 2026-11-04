"""Deterministic fitting-only photometric jitter for exploratory CNN research.

Pure tensor transforms. No labels, model predictions, source IDs, or images
are read by this module. torch is an OPTIONAL ML dependency, not needed by
the ordinary Capsule Review viewer.

The original model, four frozen Galar selection methods, and historical
checkpoints are NOT changed or automatically promoted.
"""
from __future__ import annotations

def photometric_jitter(x, generator):
    """Apply per-image RGB brightness, contrast, saturation perturbations.

    Input must be floating NCHW RGB normalized to [0,1]. The fixed ranges
    are bright [.75,1.25], contrast [.8,1.2], saturation [.7,1.3].
    Operations are differentiable and applied after aspect-preserving
    96x96 model preprocessing. This is a training-only augmentation, not
    a medical enhancement, output probability calibration, or inference fix.

    Accept a caller-owned CPU torch.Generator, allowing seed-isolated
    reproducibility without resetting/sharing the global torch RNG.
    """
    import torch

    if not isinstance(x, torch.Tensor) or x.ndim != 4 or x.shape[1] != 3 or x.shape[0] < 1:
        raise ValueError("Expected nonempty batch of NCHW RGB images.")
    if not x.is_floating_point() or not torch.isfinite(x).all() or torch.any(x < 0) or torch.any(x > 1):
        raise ValueError("Image tensor must contain finite normalized RGB values.")
    if x.device.type != "cpu":
        raise ValueError("This reproducible small-CNN recipe is CPU-only.")
    if not isinstance(generator, torch.Generator) or generator.device.type != "cpu":
        raise ValueError("Provide an explicit CPU torch.Generator.")
    n = x.shape[0]
    b = .75 + .5 * torch.rand((n, 1, 1, 1), generator=generator, dtype=x.dtype)
    c = .8 + .4 * torch.rand((n, 1, 1, 1), generator=generator, dtype=x.dtype)
    s = .7 + .6 * torch.rand((n, 1, 1, 1), generator=generator, dtype=x.dtype)
    image = (x * b).clamp(0, 1)
    mean = image.mean(dim=(1, 2, 3), keepdim=True)
    image = ((image - mean) * c + mean).clamp(0, 1)
    grayscale = image[:, 0:1] * .299 + image[:, 1:2] * .587 + image[:, 2:3] * .114
    return (grayscale + (image - grayscale) * s).clamp(0, 1)


def appearance_condition(x, name: str):
    """Fixed model-input perturbations used in exploratory repeat-inference audit.

    The standard preprocessing is already applied. Do not apply to unverified
    clinical input or treat these test-time variants as recommended processing.
    """
    import torch
    if not isinstance(x, torch.Tensor) or x.ndim != 4 or x.shape[1] != 3 or x.shape[0] < 1:
        raise ValueError("Expected nonempty NCHW RGB.")
    if not x.is_floating_point() or not torch.isfinite(x).all() or torch.any(x < 0) or torch.any(x > 1):
        raise ValueError("Invalid normalized RGB input.")
    if name == "original":
        return x.clone()
    if name == "brightness_075":
        return (x * .75).clamp(0, 1)
    if name == "brightness_125":
        return (x * 1.25).clamp(0, 1)
    if name == "contrast_080":
        mean = x.mean(dim=(1, 2, 3), keepdim=True)
        return ((x - mean) * .8 + mean).clamp(0, 1)
    if name in ("saturation_070", "saturation_130"):
        grayscale = x[:, 0:1] * .299 + x[:, 1:2] * .587 + x[:, 2:3] * .114
        factor = .7 if name == "saturation_070" else 1.3
        return (grayscale + (x - grayscale) * factor).clamp(0, 1)
    raise ValueError("Unknown exploratory appearance perturbation.")
