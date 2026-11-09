"""Research-only synthetic tests; no patient sources or private research artifacts."""
import pytest
pytest.importorskip("numpy", reason="Frozen-representation tests require optional ML dependencies")
pytest.importorskip("torch", reason="Frozen-representation tests require optional ML dependencies")
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

"""Synthetic-only checks that fitting cannot start before a complete immutable lock."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
import zipfile

from frozen_representation_comparison import validate_prefit_lock,sha_file,EXAMS,SEEDS,UPDATES,RANK_WEIGHT

class PrefitLockTests(unittest.TestCase):
    def example(self, root:Path):
        pkg=root/'Short_Event_Foundation_Private_Final_Evidence_20261109.zip'
        manifest=b'{"synthetic_only":true}'
        with zipfile.ZipFile(pkg,'w') as z:z.writestr('foundation/support-manifest-private.json',manifest)
        feat=root/'toy_features.npy';feat.write_bytes(b'fictional features; not a medical image')
        feature_sha=sha_file(feat)
        directory=Path(__file__).resolve().parents[1]/"scripts"
        lock={'status':'PREFIT_LOCKED','feature_sha256':feature_sha,
              'training_code_sha256':sha_file(directory/'frozen_representation_comparison.py'),
              'recovery_code_sha256':sha_file(directory/'recover_frozen_mobilenet.py'),
              'published_controls_sha256':sha_file(directory/'pr72_published_controls.json'),
              'official_backbone_weights_sha256':'047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f',
              'cached_old_feature_bank_sha256':'611ac32ca3b0ada15bba65c5aba564fd2a92bdac4d60d9376af89e429181c9ae',
              'exams':list(EXAMS),'seeds':list(SEEDS),'updates':UPDATES,
              'head':'single 576->2 affine layer','ranking_weight':RANK_WEIGHT,
              'runs':69,'singleton_runs':21,
              'training':'1024 AdamW updates; 16 fitting references, 8 positive and 8 negative pair endpoints per batch; last checkpoint',
              'scaling':'unique fitting images only, excluding whole held-out examination',
              'read_heldout_outcomes_after_seal':True,
              'source_manifest_sha256':hashlib.sha256(manifest).hexdigest(),
              'canary_archive_sha256':'a'*64,'feature_extraction_receipt_sha256':'b'*64,
              'canary_max_abs_difference':0.00001}
        path=root/'lock.json';path.write_text(json.dumps(lock))
        return path,feat,feature_sha,lock
    def test_accept_complete_pinned_lock(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);lock,features,feature_sha,_=self.example(root)
            self.assertEqual(validate_prefit_lock(lock,root,features,feature_sha),sha_file(lock))
    def test_reject_unpinned_training_objective(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);lock,features,feature_sha,d=self.example(root)
            d['ranking_weight']=0.75;lock.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'ranking_weight'):
                validate_prefit_lock(lock,root,features,feature_sha)
    def test_reject_feature_or_code_change(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);lock,features,feature_sha,d=self.example(root)
            features.write_bytes(b'different features')
            with self.assertRaisesRegex(ValueError,'Feature file changed'):
                validate_prefit_lock(lock,root,features,feature_sha)
            features.write_bytes(b'fictional features; not a medical image')
            d['training_code_sha256']='0'*64;lock.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'training_code_sha256'):
                validate_prefit_lock(lock,root,features,feature_sha)
    def test_reject_missing_canary_receipt(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);lock,features,feature_sha,d=self.example(root)
            del d['canary_archive_sha256'];lock.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'missing private provenance'):
                validate_prefit_lock(lock,root,features,feature_sha)

if __name__=='__main__':unittest.main()
