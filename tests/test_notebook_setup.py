"""Run the real notebook setup cell in fresh processes across package layouts."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json,os,shutil,subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
NOTEBOOK=next(p for p in [ROOT/'SSM_FiCO2_PaCO2_tutorial.ipynb',ROOT.parent/'SSM_FiCO2_PaCO2_tutorial.ipynb'] if p.is_file())
SETUP=''.join(json.loads(NOTEBOOK.read_text())['cells'][2]['source'])

class NotebookSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)

    def package(self,destination):
        for folder in ('code','data'):
            shutil.copytree(ROOT/folder,destination/folder,ignore=shutil.ignore_patterns('__pycache__','.cache'))
        return destination.resolve()

    def run_setup(self,cwd,prelude='',postlude=''):
        code=prelude+'\nexec('+repr(SETUP)+')\n'+postlude+'\nprint("SELECTED="+str(DATA_ROOT))'
        return subprocess.run([sys.executable,'-B','-c',code],cwd=cwd,text=True,capture_output=True,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})

    def selected(self,cwd,expected,**kwargs):
        result=self.run_setup(cwd,**kwargs)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('SELECTED='+str(expected),result.stdout)

    def test_supported_layouts(self):
        public=self.package(self.base/'public')
        local=self.package(self.base/'author/tutorial/companion')
        for cwd,expected in [(public,public),(self.base/'author',local),(local.parent,local),(local,local)]:
            with self.subTest(cwd=str(cwd)):self.selected(cwd,expected)

    def test_incomplete_workspace_converter_is_skipped(self):
        local=self.package(self.base/'author/tutorial/companion')
        decoy=self.base/'author/code';decoy.mkdir()
        (decoy/'ssm.py').write_text('raise AssertionError("wrong converter imported")')
        self.selected(self.base/'author',local)

    def test_missing_code_rejected_before_import(self):
        public=self.package(self.base/'public')
        (public/'code/tutorial_analysis.py').unlink()
        result=self.run_setup(public)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Complete SSM companion not found',result.stderr)
        self.assertIn('code/tutorial_analysis.py',result.stderr)
        self.assertNotIn('Converter ready',result.stdout)

    def test_each_missing_data_file_is_reported(self):
        public=self.package(self.base/'public')
        for path in (public/'data').glob('*.json'):
            with self.subTest(name=path.name):
                data=path.read_bytes();path.unlink()
                result=self.run_setup(public)
                path.write_bytes(data)
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertIn('data/'+path.name,result.stderr)

    def test_unrelated_working_directory_has_actionable_error(self):
        result=self.run_setup(self.base)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Keep the supplied code/ and data/ together',result.stderr)

    def test_cached_module_from_another_checkout_requires_restart(self):
        public=self.package(self.base/'public')
        prelude="import sys,types\nold=types.ModuleType('ssm');old.__file__='/another/checkout/code/ssm.py'\nsys.modules['ssm']=old"
        result=self.run_setup(public,prelude=prelude)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Restart Kernel and Run All',result.stderr)

    def test_same_package_rerun_is_allowed_and_path_is_unique(self):
        public=self.package(self.base/'public')
        self.selected(public,public,postlude='exec('+repr(SETUP)+')\nassert sys.path.count(str(DATA_ROOT/"code"))==1')

    def test_complete_package_code_precedes_unrelated_sys_path(self):
        public=self.package(self.base/'public');decoy=self.base/'other';decoy.mkdir()
        (decoy/'ssm.py').write_text('raise AssertionError("wrong converter imported")')
        self.selected(public,public,prelude='import sys\nsys.path.insert(0,'+repr(str(decoy))+')',
            postlude='import ssm\nassert Path(ssm.__file__).resolve()==DATA_ROOT/"code/ssm.py"')

if __name__=='__main__':unittest.main()
