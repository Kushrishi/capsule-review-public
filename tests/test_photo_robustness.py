"""Synthetic-only tests for reproducible fitting augmentation and input boundaries."""
from pathlib import Path
import importlib.util
import io
import sys
import zipfile

import pytest

pytestmark = pytest.mark.filterwarnings("ignore:Using a non-full backward hook")
torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from capsule_review.photo_robustness import appearance_condition, photometric_jitter

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "train_blood_photo_candidate.py"
spec = importlib.util.spec_from_file_location("color_candidate_script", SCRIPT)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def test_augmentation_seed_replay_and_separation_from_global_rng():
    x = torch.linspace(0, 1, 2 * 3 * 12 * 12).reshape(2, 3, 12, 12)
    before = x.clone()
    torch.manual_seed(987)
    before_global = torch.get_rng_state().clone()
    a = photometric_jitter(x, torch.Generator().manual_seed(25072026))
    b = photometric_jitter(x, torch.Generator().manual_seed(25072026))
    c = photometric_jitter(x, torch.Generator().manual_seed(25072027))
    assert torch.equal(a, b)
    assert not torch.equal(a, c)
    assert not torch.equal(a, x)
    assert torch.equal(x, before)
    assert torch.equal(before_global, torch.get_rng_state())
    assert a.shape == x.shape
    assert torch.isfinite(a).all() and a.min() >= 0 and a.max() <= 1


def test_photometric_augmentation_is_differentiable_and_does_not_use_labels():
    x = torch.full((3, 3, 8, 8), .43, requires_grad=True)
    shifted = photometric_jitter(x, torch.Generator().manual_seed(1))
    shifted.sum().backward()
    assert x.grad is not None
    assert torch.isfinite(x.grad).all()
    assert float(x.grad.abs().sum()) > 0


@pytest.mark.parametrize("bad", [
    torch.empty(0, 3, 8, 8),
    torch.zeros(1, 1, 8, 8),
    torch.zeros(1, 3, 8),
    torch.full((1, 3, 4, 4), 1.2),
    torch.full((1, 3, 4, 4), float("nan")),
    torch.ones(1, 3, 4, 4, dtype=torch.uint8),
])
def test_bad_tensor_fails_closed(bad):
    with pytest.raises(ValueError):
        photometric_jitter(bad, torch.Generator().manual_seed(1))


def test_generator_required_and_conditions_are_fixed():
    x = torch.tensor([[[[0.2, 0.6]], [[0.4, 0.8]], [[0.1, 0.9]]]], dtype=torch.float32)
    with pytest.raises(ValueError):
        photometric_jitter(x, None)
    assert appearance_condition(x, "original").equal(x)
    assert torch.allclose(appearance_condition(x, "brightness_075"), x * .75)
    assert torch.allclose(appearance_condition(x, "brightness_125"), (x * 1.25).clamp(0, 1))
    for name in ("contrast_080", "saturation_070", "saturation_130"):
        modified = appearance_condition(x, name)
        assert modified.shape == x.shape and not modified.equal(x)
        assert modified.min() >= 0 and modified.max() <= 1
    with pytest.raises(ValueError):
        appearance_condition(x, "unknown")
    with pytest.raises(ValueError):
        appearance_condition(torch.tensor([[[[float("inf")]], [[0]], [[0]]]]), "original")


def test_fitting_input_missing_or_changed_manifest_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        candidate.load_fitting_bank(tmp_path)
    with zipfile.ZipFile(tmp_path / "capsule-blood-real-pilot.zip", "w") as archive:
        archive.writestr("private-dataset-manifest/blood-manifest.json", "{}")
    with pytest.raises(ValueError, match="differs from the verified original"):
        candidate.load_fitting_bank(tmp_path)


def test_fixed_training_recipe_and_no_holdout_gate():
    assert candidate.FITTING_EXAMINATIONS == tuple(range(1, 9))
    assert candidate.EPOCHS == 8
    assert candidate.SEED == 17
    assert candidate.AUGMENTATION_SEED == 25072026
    assert candidate.BATCH == 32
    assert candidate.LR == .001
    assert candidate.WEIGHT_DECAY == .0001


def test_single_synthetic_fit_uses_unchanged_cnn_architecture(monkeypatch):
    monkeypatch.setattr(candidate, "EPOCHS", 1)
    monkeypatch.setattr(candidate, "BATCH", 4)
    bank = np.random.default_rng(4).integers(
        0, 256, size=(8, 96, 96, 3), dtype=np.uint8,
    )
    labels = np.array([0, 1] * 4, dtype=np.int64)
    state, losses = candidate.fit(bank, labels)
    assert len(losses) == 1 and losses[0] > 0
    from capsule_review.baseline import AnatomyCNN
    model = AnatomyCNN(2)
    model.load_state_dict(state)
    assert all(torch.isfinite(v).all() for v in state.values())
