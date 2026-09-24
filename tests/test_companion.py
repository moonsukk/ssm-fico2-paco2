"""Scientific regression and portable-release checks, independent of the workspace."""
from pathlib import Path
from collections import defaultdict
from dataclasses import replace
import hashlib, json, math, sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from ssm import Params, fico2_to_paco2, paco2_to_fico2
from tutorial_analysis import load_analysis,parameters,calculate

class CompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result,cls.payload=load_analysis(ROOT)

    def test_frozen_model_and_selected_evidence(self):
        provenance=json.loads((ROOT/'data/provenance.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT/'code/ssm.py').read_bytes()).hexdigest(),provenance['source_model_sha256'])
        self.assertEqual(len(self.result['reported_points']),40)
        self.assertEqual(len(self.result['weighted_points']),27)
        self.assertEqual(len(self.result['primary_reported']),27)
        self.assertEqual(len(self.result['primary_weighted']),20)
        self.assertEqual(len(self.result['global_metrics']),8)
        for row in self.result['reported_points']:
            self.assertTrue(row['source_url'].startswith('https://'))
            self.assertTrue(row['source_locator'])
            self.assertIn(row['population'],['healthy_adults','healthy_adults_assumed'])
        self.assertTrue(all(x['context']=='pure_HC' for x in self.result['primary_reported']))

    def test_independent_mass_balance_and_inverse(self):
        for row in self.result['reported_points']+self.result['weighted_points']:
            p=parameters(self.result['settings'],row['baseline_mmhg'])
            lo,hi=p.PaCO2_base,p.max_paco2
            for _ in range(90):
                mid=(lo+hi)/2
                f=mid-row['fico2_pct']*p.Pdry/100-p.K*p.VCO2/(p.VA_base+p.S*(mid-p.PaCO2_base))
                if f>0:hi=mid
                else:lo=mid
            self.assertAlmostEqual((lo+hi)/2,row['estimated_paco2_mmhg'],places=10)
            inverse=100*(row['measured_mmhg']-p.K*p.VCO2/(p.VA_base+p.S*(row['measured_mmhg']-p.PaCO2_base)))/p.Pdry
            self.assertAlmostEqual(inverse,row['estimated_fico2_pct'],places=10)

    def test_equal_total_paper_weight(self):
        for metric in self.result['global_metrics']:
            weights=defaultdict(float)
            for c in metric['contributions']:weights[c['study_id']]+=c['weight']
            for w in weights.values():self.assertAlmostEqual(w,1/metric['n_studies'],places=12)
            self.assertAlmostEqual(sum(weights.values()),1,places=12)

    def test_shared_cohort_and_missing_uncertainty(self):
        chawla=next(x for x in self.result['primary_weighted'] if x['study_id']=='Chawla2015')
        self.assertEqual(chawla['subjects_n'],12)
        self.assertEqual(chawla['reported_records'],3)
        self.assertIsNone(chawla['measured_sd_mmhg'])
        ashkanian=next(x for x in self.result['primary_weighted'] if x['study_id']=='Ashkanian2008')
        self.assertIsNone(ashkanian['measured_sd_mmhg'])

    def test_units_roundtrip_and_domain(self):
        for baseline in [35,40,45]:
            p=Params(PaCO2_base=baseline)
            self.assertAlmostEqual(fico2_to_paco2(0,p),baseline)
            for dose in [0,2,5,7]:
                pressure=fico2_to_paco2(dose,p)
                self.assertAlmostEqual(paco2_to_fico2(pressure,p),dose,places=10)
                self.assertAlmostEqual(fico2_to_paco2(dose/100,p,is_percent=False),pressure,places=10)
        p=Params();zero=replace(p,S=0)
        self.assertAlmostEqual(fico2_to_paco2(2,zero),40+0.02*713)
        for pressure in [39,81,float('nan')]:
            with self.assertRaises(ValueError):paco2_to_fico2(pressure,p)

    def test_no_private_workspace_paths(self):
        tokens=['/Users/','/var/folders/','OneDrive-','zotero://','127.0.0.1','audit/01_current_review/']
        paths=list((ROOT/'data').glob('*.json'))+list((ROOT/'code').glob('*.py'))
        paths += list(ROOT.glob('*.ipynb'))+list(ROOT.glob('*.html'))
        for path in paths:
            content=path.read_text()
            for token in tokens:self.assertNotIn(token,content,str(path.relative_to(ROOT)))

if __name__=='__main__':unittest.main()
