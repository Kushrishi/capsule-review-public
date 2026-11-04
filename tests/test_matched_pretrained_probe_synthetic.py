"""Synthetic tests: training-fold normalization, examination exclusion and RNG stability."""
from __future__ import annotations
import json
from pathlib import Path
import zipfile
import pytest

np=pytest.importorskip("numpy")
pytest.importorskip("sklearn")
from scripts.matched_pretrained_probe import fit_one_fold, read_verified_private_features


def synthetic_reference_bank():
    rng=np.random.default_rng(321)
    exams=np.repeat([*range(1,9),23,25,27],512).astype(np.int16)
    x=rng.normal(size=(len(exams),12)).astype(np.float32)
    y=np.zeros(len(exams),dtype=np.int8)
    for i in range(1,9):
        positions=np.flatnonzero(exams==i)
        target={1:22,2:1,3:0,4:2,5:0,6:6,7:208,8:0}[i]
        y[rng.choice(positions,size=target,replace=False)]=1
    for ex,n in ((23,4),(25,14),(27,26)):
        positions=np.flatnonzero(exams==ex)
        y[rng.choice(positions,size=n,replace=False)]=1
    assert y[np.isin(exams,range(1,9))].sum()==239
    return x,y,exams


def test_matched_probe_fit_is_deterministic_and_excludes_evaluated_case():
    x,y,exams=synthetic_reference_bank()
    first,private=fit_one_fold(x,y,exams,25)
    second,repeated=fit_one_fold(x,y,exams,25)
    assert first==second
    assert np.array_equal(private["coefficients"],repeated["coefficients"])
    assert first["evaluated_exam"]==25
    assert 25 not in first["fitted_examinations"]
    assert first["training_images"]==5120
    assert first["positive_training_images"]==269
    assert first["test_positive"]==14
    assert private["predictions"].shape==(512,)
    assert set(first["positive_hits"])=={"51","128","256"}


def test_heldout_labels_cannot_change_fitted_coefficients():
    x,y,exams=synthetic_reference_bank()
    _,first=fit_one_fold(x,y,exams,23)
    changed=y.copy()
    # Swap heldout outcomes *without* touching a single training label.
    heldout=np.flatnonzero(exams==23)
    changed[heldout]=np.roll(changed[heldout],12)
    _,second=fit_one_fold(x,changed,exams,23)
    assert np.array_equal(first["coefficients"],second["coefficients"])
    assert np.array_equal(first["mean"],second["mean"])
    assert np.array_equal(first["scale"],second["scale"])


def test_refuse_modified_fitting_population_and_invalid_holdout():
    x,y,exams=synthetic_reference_bank()
    with pytest.raises(ValueError):
        fit_one_fold(x,y,exams,61)
    leaked=exams.copy()
    leaked[0]=25
    with pytest.raises(ValueError):
        fit_one_fold(x,y,leaked,25)
    changed=y.copy()
    positive_27=np.flatnonzero((exams==27)&(y==1))[0]
    changed[positive_27]=0
    with pytest.raises(ValueError):
        fit_one_fold(x,changed,exams,23)


def test_refuse_unverified_private_archives(tmp_path):
    missing=tmp_path/"missing.zip"
    with pytest.raises(FileNotFoundError):
        read_verified_private_features(missing,missing)
