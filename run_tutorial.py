"""Execute the companion in a fresh kernel using the current Python environment."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json, os, sys

ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))

def main():
    import nbformat
    from nbclient import NotebookClient
    from nbconvert import HTMLExporter
    path=ROOT/'SSM_FiCO2_PaCO2_tutorial.ipynb'
    notebook=nbformat.read(path,as_version=4)
    for cell in notebook.cells:
        if cell.cell_type=='code':cell.execution_count=None;cell.outputs=[]
    with TemporaryDirectory(prefix='ssm-kernel-') as temp:
        kernel=Path(temp)/'kernels'/'ssm-companion';kernel.mkdir(parents=True)
        (kernel/'kernel.json').write_text(json.dumps({
            'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
            'display_name':'SSM companion verification','language':'python',
            'env':{'PYTHONDONTWRITEBYTECODE':'1','MPLCONFIGDIR':os.environ['MPLCONFIGDIR']}}))
        os.environ['JUPYTER_PATH']=temp+os.pathsep+os.environ.get('JUPYTER_PATH','')
        NotebookClient(notebook,timeout=240,kernel_name='ssm-companion',
            resources={'metadata':{'path':str(ROOT)}}).execute()
    notebook.metadata['validation_status']='fresh_kernel_execution_passed'
    nbformat.validate(notebook)
    output=HTMLExporter().from_notebook_node(notebook)[0]
    nbformat.write(notebook,path)
    path.with_suffix('.html').write_text(output)
    cells=[c for c in notebook.cells if c.cell_type=='code']
    assert all(not any(o.output_type=='error' for o in c.outputs) for c in cells)
    print(f'PASS: {len(cells)} code cells executed in a fresh kernel; notebook and HTML saved.')

if __name__=='__main__':main()
