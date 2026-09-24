"""Regression checks for the actual editable notebook cells and their outputs."""
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
import json, math, sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from ssm import Params,fico2_to_paco2,paco2_to_fico2
# Supports the public root and the author's notebook beside companion/.
NOTEBOOK=next(p for p in [ROOT/'SSM_FiCO2_PaCO2_tutorial.ipynb',ROOT.parent/'SSM_FiCO2_PaCO2_tutorial.ipynb'] if p.is_file())
CELLS={c['id']:''.join(c['source']) for c in json.loads(NOTEBOOK.read_text())['cells']}

class NotebookInputTests(unittest.TestCase):
    def prepare(self,**changes):
        env=dict(replace=replace,Params=Params,fico2_to_paco2=fico2_to_paco2,paco2_to_fico2=paco2_to_fico2)
        exec(CELLS['known-inputs-code'],env)
        env.update(changes)
        env['supplied_inputs']={key:env[name] for key,name in [
            ('Patm','known_atmospheric_pressure_mmhg'),('VCO2','known_co2_production_ml_min_stpd'),
            ('S','known_slope_l_min_mmhg'),('PH2O','known_water_vapour_pressure_mmhg')]
            if env[name] is not None}
        return env

    def run_results(self,env):
        captured=[]
        with patch('IPython.display.display',lambda value:captured.append(value.data)):
            exec(CELLS['known-inputs-results'],env)
        return '\n'.join(captured)

    def test_forward_without_achieved_input(self):
        env=self.prepare(conversion_direction='forward',achieved_or_target_mmhg=None)
        shown=self.run_results(env)
        self.assertAlmostEqual(env['example_forward'],47.86575313423322)
        self.assertIsNone(env['example_reverse'])
        self.assertEqual(env['example_errors'],{})
        self.assertIn('47.87 mmHg',shown)
        self.assertNotIn('**Reverse:**',shown)

    def test_reverse_without_inspired_input(self):
        env=self.prepare(conversion_direction='reverse',inspired_co2_percent=None)
        shown=self.run_results(env)
        self.assertAlmostEqual(env['example_reverse'],5.650732250535462)
        self.assertIsNone(env['example_forward'])
        self.assertEqual(env['example_errors'],{})
        self.assertIn('5.65%',shown)
        self.assertNotIn('**Forward:**',shown)

    def test_both_valid_keeps_original_answers(self):
        env=self.prepare();self.run_results(env)
        self.assertAlmostEqual(env['example_forward'],47.86575313423322)
        self.assertAlmostEqual(env['example_reverse'],5.650732250535462)
        self.assertEqual(env['example_errors'],{})

    def test_each_missing_input_preserves_other_direction(self):
        for key,error_key,valid_key in [
            ('inspired_co2_percent','forward','reverse'),('achieved_or_target_mmhg','reverse','forward')]:
            with self.subTest(key=key):
                env=self.prepare(**{key:None});shown=self.run_results(env)
                self.assertIn('this input is required',shown)
                self.assertIn(error_key,env['example_errors'])
                self.assertIsNone(env['example_'+error_key])
                self.assertIsNotNone(env['example_'+valid_key])

    def test_invalid_opposite_inputs_preserve_valid_result(self):
        cases=[({'baseline_mmhg':55},'reverse','forward'),
               ({'achieved_or_target_mmhg':81},'reverse','forward'),
               ({'inspired_co2_percent':-1},'forward','reverse')]
        for values,bad,good in cases:
            with self.subTest(values=values):
                env=self.prepare(**values);self.run_results(env)
                self.assertIn(bad,env['example_errors'])
                self.assertIsNone(env['example_'+bad])
                self.assertIsNotNone(env['example_'+good])

    def test_unused_malformed_input_is_not_required(self):
        env=self.prepare(conversion_direction='reverse',inspired_co2_percent='unknown')
        self.run_results(env)
        self.assertAlmostEqual(env['example_reverse'],5.650732250535462)
        self.assertEqual(env['example_errors'],{})

    def test_missing_and_invalid_shared_inputs_clear_prior_results(self):
        for key,value in [('baseline_mmhg',None),('baseline_mmhg',float('nan')),
                          ('pressure_endpoint','unknown'),('conversion_direction','typo')]:
            with self.subTest(key=key,value=value):
                env=self.prepare();self.run_results(env);env[key]=value
                self.run_results(env)
                self.assertIsNone(env['example_forward']);self.assertIsNone(env['example_reverse'])
                self.assertIsNone(env['example_params']);self.assertIn('shared',env['example_errors'])

    def test_direction_change_clears_unselected_previous_result(self):
        env=self.prepare();self.run_results(env)
        env.update(conversion_direction='forward',achieved_or_target_mmhg=None)
        self.run_results(env)
        self.assertIsNone(env['example_reverse']);self.assertEqual(env['example_errors'],{})
        self.assertIsNotNone(env['example_forward'])

    def test_nonfinite_boolean_and_text_required_values_are_rejected(self):
        for bad in [float('inf'),float('nan'),True,'unknown']:
            with self.subTest(bad=bad):
                env=self.prepare(inspired_co2_percent=bad);self.run_results(env)
                self.assertIn('forward',env['example_errors']);self.assertIsNone(env['example_forward'])
                self.assertIsNotNone(env['example_reverse'])

    def test_optional_known_values_and_proxy_labels(self):
        env=self.prepare(pressure_endpoint='PETCO2',known_slope_l_min_mmhg=0.0)
        shown=self.run_results(env)
        self.assertEqual(env['example_params'].S,0.0)
        self.assertAlmostEqual(env['example_forward'],42+0.05*713)
        self.assertIn('Proxy assumption',shown);self.assertIn('Baseline PETCO₂',shown)
        self.assertIn('estimated PaCO₂',shown);self.assertIn('Supplied',shown)
        self.assertIn('Default assumption',shown)
        env=self.prepare(known_co2_production_ml_min_stpd=-1)
        self.run_results(env)
        self.assertIn('shared',env['example_errors'])
        self.assertIsNone(env['example_params']);self.assertEqual(env['example_results'],{})

if __name__=='__main__':unittest.main()
