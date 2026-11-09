"""Synthetic-only unit tests; never fetch source pixels or actual patient records."""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import unittest

spec=spec_from_file_location('ensemble',Path(__file__).with_name('exploratory_seed_ensemble.py'))
mod=module_from_spec(spec);spec.loader.exec_module(mod)

class TestSeedEnsemble(unittest.TestCase):
 def test_three_unanimous(self):
  self.assertEqual(mod.ensemble_outcomes([1,2,3]),(1,1))
  self.assertEqual(mod.ensemble_outcomes([-1,-2,-3]),(0,0))
 def test_majority_and_magnitude_disagree(self):
  self.assertEqual(mod.ensemble_outcomes([1,1,-7]),(1,0))
  self.assertEqual(mod.ensemble_outcomes([-1,-1,7]),(0,1))
 def test_reproducible_ties(self):
  self.assertEqual(mod.ensemble_outcomes([1,-1,0]),(.5,.5))
  self.assertEqual(mod.ensemble_outcomes([0,0,0]),(.5,.5))
  self.assertEqual(mod.ensemble_outcomes([1,0,0]),(.5,1))
 def test_reject_unknown_seed_set(self):
  for x in ([1,2],[1,2,3,4],[float('inf'),1,1]):
   with self.assertRaises(AssertionError):mod.ensemble_outcomes(x)
if __name__=='__main__':unittest.main()