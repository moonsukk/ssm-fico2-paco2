"""Keep release identity separate from a checkout's changing Git state."""
from pathlib import Path
import json,re,unittest
ROOT=Path(__file__).resolve().parents[1]
NOTEBOOK=next(p for p in [ROOT/'SSM_FiCO2_PaCO2_tutorial.ipynb',ROOT.parent/'SSM_FiCO2_PaCO2_tutorial.ipynb'] if p.is_file())

class ReleaseMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((ROOT/'release_manifest.json').read_text())
        cls.citation=(ROOT/'CITATION.cff').read_text()
        cls.notebook=json.loads(NOTEBOOK.read_text())

    def test_development_version_agrees_across_artifacts(self):
        version=self.manifest['version']
        self.assertTrue(version.endswith('-dev'))
        self.assertEqual(self.manifest['release_status'],'development')
        self.assertEqual(re.search(r'^version: (.+)$',self.citation,re.M).group(1),version)
        self.assertEqual(self.notebook['metadata']['tutorial_revision'],version)
        self.assertIsNone(re.search(r'^date-released:',self.citation,re.M),'Development metadata must not claim a release date')
        self.assertNotIn('publication_status',self.manifest)
        self.assertNotIn('uncommitted_local_candidate',json.dumps(self.manifest))

    def test_fixed_release_baseline_is_explicit(self):
        released=self.manifest['released_baseline']
        self.assertEqual(released['tag'],self.manifest['based_on'])
        self.assertEqual(released['tag'],'v0.1.0')
        self.assertEqual(released['commit'],'6e306ecb6c844f4626a67e80d5fb44270e93c951')
        self.assertTrue(released['url'].endswith('/tree/'+released['tag']))
        readme=(ROOT/'README.md').read_text()
        self.assertIn(released['url'],readme)
        self.assertIn('git rev-parse HEAD',readme)
        self.assertNotIn('unreleased working copy',readme)

    def test_model_and_analysis_identity_match_provenance(self):
        provenance=json.loads((ROOT/'data/provenance.json').read_text())
        self.assertEqual(self.manifest['source_analysis_sha256'],provenance['source_analysis_sha256'])
        # Resolve the converter setup by identity, not its position in the lesson.
        matches=[c for c in self.notebook['cells'] if c.get('id')=='9e223e73']
        self.assertEqual(len(matches),1,'Expected one converter setup cell: 9e223e73')
        self.assertEqual(matches[0]['cell_type'],'code')
        model_lines=[]
        for output in matches[0].get('outputs',[]):
            if output.get('output_type')=='stream' and output.get('name')=='stdout':
                text=output.get('text','')
                if isinstance(text,list):text=''.join(text)
                model_lines.extend(line.strip() for line in text.splitlines()
                                   if line.strip().startswith('Converter ready: '))
        self.assertEqual(model_lines,[f"Converter ready: {self.manifest['model_version']}"])
        self.assertNotIn('release_manifest.json',self.manifest['files'])

if __name__=='__main__':unittest.main()
