from pathlib import Path
import pytest
from capsule_review.spatial_training import learning_rate_factor, seal, verify_selection


def test_scheduler_and_seal(tmp_path):
    assert learning_rate_factor(0, 2000) == .002
    assert learning_rate_factor(499, 2000) == 1
    assert learning_rate_factor(2000, 2000) == 0
    p = tmp_path / "generated.json"
    p.write_text("{}")
    commitment = seal(tmp_path, [p])
    verify_selection(tmp_path, commitment)
    p.write_text("changed")
    with pytest.raises(ValueError, match="artifact"):
        verify_selection(tmp_path, commitment)


def test_strict_operating_point():
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from capsule_review.spatial_training import development_metrics
    records = [{"video":"n","label":"Normal"},
               {"video":"a","label":"Angiectasia"},
               {"video":"e","label":"Erosion"}]
    result = development_metrics([[.2,.3],[.2,.4],[.4,.3]], records)
    assert result["thresholds"] == [.2,.3]
    assert result["recalls"] == [0,0]


def test_scheduled_orchestration_with_generated_loader(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    import capsule_review.spatial_comparison as comparison
    from capsule_review.spatial_training import run_arm
    model = torch.nn.Linear(1, 1)
    calls = []
    def batch(plan):
        calls.append(plan)
        return torch.zeros(16, 1), [{} for _ in plan]
    monkeypatch.setattr(comparison, "update", lambda *args, **kwargs: torch.tensor(0.))
    records = [{"video":"n","label":"Normal"},
               {"video":"a","label":"Angiectasia"},
               {"video":"e","label":"Erosion"}]
    def development(model, detector):
        torch.rand(1)  # Validation randomness is restored by the orchestration.
        return {"scores":[[.1,.1],[.9,.1],[.1,.9]],"records":records}
    folder = tmp_path / "arm"
    commitment = run_arm(model, detector=False, seed=19, pools=[[0],[1],[2]],
        population_size=416, load_batch=batch, evaluate_development=development,
        output=folder, device="cpu")
    import json
    result = json.loads((folder / "selection.json").read_text())
    assert result["selected"]["epoch"] == 4
    assert result["selected"]["thresholds"] == [.1,.1]
    assert len(calls) == 520
    assert len(list(folder.glob("epoch-*.pt"))) == 5
    verify_selection(folder, commitment)


def test_six_seal_checks_nested_checkpoints(tmp_path):
    import json
    from capsule_review.spatial_training import SEEDS, verify_six, write_new
    selections = {}
    for seed in SEEDS:
        for arm in ("classifier", "detector"):
            name = f"{seed}-{arm}"
            child = tmp_path / name
            child.mkdir()
            checkpoint = child / "generated.txt"
            checkpoint.write_text("generated")
            selections[name] = seal(child, [checkpoint])
    write_new(tmp_path / "six-selections.json", selections)
    commitment = seal(tmp_path, [tmp_path / "six-selections.json"])
    verify_six(tmp_path, commitment)
    checkpoint.write_text("changed")
    with pytest.raises(ValueError, match="artifact"):
        verify_six(tmp_path, commitment)
