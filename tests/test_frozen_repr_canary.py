"""Research-only synthetic tests; no patient sources or private research artifacts."""
import pytest
pytest.importorskip("numpy", reason="Frozen-representation tests require optional ML dependencies")
pytest.importorskip("torch", reason="Frozen-representation tests require optional ML dependencies")
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

"""Synthetic-only pinned-backbone canary tests; no patient/source images."""
from pathlib import Path
import hashlib
import io
import json
import tempfile
import unittest
import zipfile

import numpy as np
from PIL import Image
import torch
from recover_frozen_mobilenet import prepare_rgb_png, verify_cached_canaries


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class ToyBackbone(torch.nn.Module):
    def forward(self, x):
        return x.mean(dim=1, keepdim=True).repeat(1, 576, 1, 1)


class CanaryValidationTests(unittest.TestCase):
    def make_sample(self, directory):
        samples=[]; rows=[]; feats=[]
        net=ToyBackbone()
        for k in range(3):
            px=np.empty((9,12,3), dtype=np.uint8)
            px[:]=[30+40*k, 100+20*k, 210-35*k]
            buf=io.BytesIO()
            Image.fromarray(px, 'RGB').save(buf, format='PNG')
            raw=buf.getvalue()
            rgb=prepare_rgb_png(raw)
            x=torch.from_numpy(rgb).permute(2,0,1).unsqueeze(0).contiguous().float().div_(255)
            mu=x.new_tensor([.485,.456,.406]).view(1,3,1,1)
            sd=x.new_tensor([.229,.224,.225]).view(1,3,1,1)
            with torch.inference_mode():feature=net((x-mu)/sd).mean(dim=(2,3)).cpu().numpy()[0].astype('<f4')
            feats.append(feature)
            rows.append({'exam':23, 'frame':100+k*5, 'blood':0})
            samples.append((raw, {'archive_member':f'originals/canary_{k}.PNG', 'exam':23, 'frame':100+k*5,
                 'old_bank_row_index':k, 'source_original_sha256':digest(raw),'source_original_bytes':len(raw),
                 'resized_rgb_uint8_sha256':digest(rgb.tobytes()), 'old_feature_row_sha256':digest(feature.tobytes())}))
        bank=np.stack(feats)
        manifest={'feature_bank_sha256':digest(bank.tobytes()),'backbone_weights_sha256':'synthetic-test-only',
                  'canaries':[d for _,d in samples]}
        path=Path(directory)/'synthetic_canaries.zip'
        with zipfile.ZipFile(path,'w') as z:
            for raw,d in samples:z.writestr(d['archive_member'],raw)
            z.writestr('canary-manifest-private.json',json.dumps(manifest))
        return path,rows,bank,{(v['exam'],v['frame']):i for i,v in enumerate(rows)},manifest

    def test_three_canaries_reproduce_cached_features(self):
        with tempfile.TemporaryDirectory() as d:
            f,rows,bank,lookup,contract=self.make_sample(d)
            result=verify_cached_canaries(f,rows,bank,lookup,ToyBackbone(),
                contract['feature_bank_sha256'],contract['backbone_weights_sha256'])
            self.assertTrue(result['frozen_bank_consistent'])
            self.assertLess(result['max_abs_feature_difference'], 1e-5)

    def test_modified_backbone_fails(self):
        class WrongBackbone(ToyBackbone):
            def forward(self,x):return super().forward(x)+0.03
        with tempfile.TemporaryDirectory() as d:
            f,rows,bank,lookup,contract=self.make_sample(d)
            with self.assertRaisesRegex(ValueError,'failed frozen-feature canaries'):
                verify_cached_canaries(f,rows,bank,lookup,WrongBackbone(),
                    contract['feature_bank_sha256'],contract['backbone_weights_sha256'])

    def test_wrong_source_identity_fails(self):
        with tempfile.TemporaryDirectory() as d:
            f,rows,bank,lookup,contract=self.make_sample(d)
            rows[0]['frame']+=1
            with self.assertRaisesRegex(ValueError,'mismatches source-identity bank'):
                verify_cached_canaries(f,rows,bank,lookup,ToyBackbone(),
                    contract['feature_bank_sha256'],contract['backbone_weights_sha256'])

    def test_wrong_pinned_weights_digest_fails(self):
        with tempfile.TemporaryDirectory() as d:
            f,rows,bank,lookup,contract=self.make_sample(d)
            with self.assertRaisesRegex(ValueError,'Wrong private prefit canary population'):
                verify_cached_canaries(f,rows,bank,lookup,ToyBackbone(),
                    contract['feature_bank_sha256'],'changed-checkpoint-sha')

    def test_corrupted_png_byte_fails(self):
        with tempfile.TemporaryDirectory() as d:
            f,rows,bank,lookup,contract=self.make_sample(d)
            with zipfile.ZipFile(f) as z:contents={n:z.read(n) for n in z.namelist()}
            contents['originals/canary_1.PNG']=b'corrupt'+contents['originals/canary_1.PNG']
            with zipfile.ZipFile(f,'w') as z:
                for name,data in contents.items():z.writestr(name,data)
            with self.assertRaisesRegex(ValueError,'source original SHA or size mismatch'):
                verify_cached_canaries(f,rows,bank,lookup,ToyBackbone(),
                    contract['feature_bank_sha256'],contract['backbone_weights_sha256'])

if __name__=='__main__':unittest.main()
