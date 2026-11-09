"""Research-only synthetic tests; no patient sources or private research artifacts."""
import pytest
pytest.importorskip("numpy", reason="Frozen-representation tests require optional ML dependencies")
pytest.importorskip("torch", reason="Frozen-representation tests require optional ML dependencies")
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

"""Standalone synthetic-only regression tests; no private patient data."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from independent_representation_verification import published_controls,effects,replay_one

FILE=Path(__file__).resolve().parents[1]/'scripts'/'pr72_published_controls.json'

class PublicComparatorTests(unittest.TestCase):
    def setUp(self): self.c=published_controls(FILE)
    def test_published_baselines(self):
        z=effects(self.c,self.c)
        self.assertAlmostEqual(z['macro_pair_ordering_pct']['published_cnn']['classification'],63.7719587176,places=7)
        self.assertAlmostEqual(z['macro_pair_ordering_pct']['published_cnn']['ranking'],72.2908432148,places=7)
        self.assertEqual(z['paired_comparisons']['mobilenet_ranking_minus_pr72_cnn_ranking']['macro_pp'],0)
    def test_missing_or_repeated_baseline_cell_rejected(self):
        j=json.loads(FILE.read_text()); j['cells'].append(j['cells'][0])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'controls.json';p.write_text(json.dumps(j))
            with self.assertRaises(ValueError):published_controls(p)
    def test_no_advance_from_singletons_regressing(self):
        rows={k:dict(v) for k,v in self.c.items()}
        for (e,s,arm),r in rows.items():
            if arm=='ranking':
                r['pair_accuracy']=min(1.,r['pair_accuracy']+.09)
                r['singleton_accuracy']=max(0.,r['singleton_accuracy']-.2)
        z=effects(rows,self.c)
        self.assertGreater(z['paired_comparisons']['mobilenet_ranking_minus_mobilenet_classification']['macro_pp'],0)
        self.assertFalse(z['consistency_checks']['ranking_eligible_for_further_benchmark'])
    def test_synthetic_logits_and_ties(self):
        p=[{'positive_index':0,'negative_index':1,'run_length':1},
           {'positive_index':2,'negative_index':3,'run_length':2}]
        # Correct singleton, tied two-frame run
        a=replay_one(p,[0,1,2,3],[[0,1],[1,0],[0,1],[0,1]])
        self.assertEqual(a['ordered'],1.5)
        self.assertEqual(a['singleton_ordered'],1)
        self.assertEqual(a['ties'],1)
    def test_duplicate_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            replay_one([{'positive_index':0,'negative_index':1,'run_length':1}], [0,0], [[0,0],[0,1]])
    def test_nonfinite_logits_rejected(self):
        with self.assertRaises(ValueError):
            replay_one([{'positive_index':0,'negative_index':1,'run_length':1}], [0,1], [[0,float('nan')],[0,1]])

if __name__=='__main__':unittest.main()
