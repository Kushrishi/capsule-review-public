"""Research-only synthetic tests; no patient sources or private research artifacts."""
import pytest
pytest.importorskip("numpy", reason="Frozen-representation tests require optional ML dependencies")
pytest.importorskip("torch", reason="Frozen-representation tests require optional ML dependencies")
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

"""Synthetic guards only. Contains no medical pixels or private source identifiers."""
import sys
from pathlib import Path
import unittest
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from frozen_representation_comparison import balanced_pair_schedule,cycles,EXAMS,SEEDS

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.pairs=[{'exam':e,'run_id':i} for e,n in ((23,23),(25,20),(29,11),(30,15)) for i in range(n)]
    def test_schedule_no_leak_and_balance(self):
        for held in EXAMS:
            for seed in SEEDS:
                arr=balanced_pair_schedule(self.pairs,held,seed)
                counts=Counter(self.pairs[int(i)]['exam'] for i in arr)
                self.assertEqual(len(arr),8192)
                self.assertNotIn(held,counts)
                self.assertEqual(len(counts),3)
                self.assertLessEqual(max(counts.values())-min(counts.values()),1)
    def test_determinism(self):
        a=balanced_pair_schedule(self.pairs,23,17)
        b=balanced_pair_schedule(self.pairs,23,17)
        self.assertTrue((a==b).all())
    def test_empty_schedule_forbidden(self):
        with self.assertRaises(ValueError): cycles(0,32,17)
    def test_no_insufficient_four_folds(self):
        # Unsupported small-fold population must fail, not silently relabel data.
        minimal=[p for p in self.pairs if p['exam']!=30]
        with self.assertRaises(ValueError):balanced_pair_schedule(minimal,23,17)
if __name__=='__main__':unittest.main()
