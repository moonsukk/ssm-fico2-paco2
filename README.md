# Steady-state FiCO₂–PaCO₂ conversion

A reproducible Jupyter companion for a technical note in preparation by M. Kim. It teaches an approximate bidirectional conversion between inspired CO₂ percentage and arterial CO₂ pressure, conditional on physiological steady state.

**Start with [the executed notebook](SSM_FiCO2_PaCO2_tutorial.ipynb).** Its saved outputs include the worked examples, three figures, both conversion directions, literature agreement and supplementary sensitivity scenarios. Download [the HTML preview](SSM_FiCO2_PaCO2_tutorial.html) to read it without Jupyter.

## Scope and results

The operating slope is **1.7081818181818182 L min⁻¹ mmHg⁻¹**, calculated from the selected FiCO₂-in-medical-air evidence (Tallon 2020 and Peebles 2007; N = 33). The **2.4515884476534295** rebreathing slope is a labelled reference, never used for the validation residuals.

The pure-HC comparison contains 11 papers across 2–7% inspired CO₂. Primary study summaries give pressure RMSE **2.65 mmHg**, bias **−1.14 mmHg**; the reverse conversion gives FiCO₂ RMSE **0.73 percentage points**, bias **+0.33**. Each paper has equal total influence within a metric. These are descriptive agreement statistics for aggregate published observations, not individual prediction errors or direct arterial validation of end-tidal measurements.

The companion preserves reported observations and study summaries as two representations of the **same evidence**. It keeps pure versus mixed conditions, PaCO₂ versus PETCO₂, repeated participant groups, missing SD and incomplete duration information explicit.

## Run from a fresh environment

Tested with Python 3.12. Download the repository or clone it, then run:

```bash
git clone https://github.com/moonsukk/ssm-fico2-paco2.git
cd ssm-fico2-paco2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_tutorial.py
```

On Windows, activate with `.venv\Scripts\activate`. The runner starts a new kernel using that environment, executes all cells, and writes the executed notebook and HTML preview. It requires no Excel, MATLAB, Zotero, credentials or source-PDF downloads. For interactive editing, open the notebook in a Jupyter-capable editor using the same environment and select **Restart Kernel and Run All**.

Run the independent numerical and package checks with:

```bash
python -m unittest discover -s tests -v
```

## Use the converter directly

```python
import sys
sys.path.insert(0, "code")
from ssm import Params, fico2_to_paco2, paco2_to_fico2

p = Params(PaCO2_base=40.0)
fico2_to_paco2(5.0, p)   # 46.6553... mmHg; FiCO2 is percent by default
paco2_to_fico2(50.0, p)  # 5.88126... percent
```

Supply known baseline and physiological parameters where appropriate. Unchanged defaults are assumptions. The worked examples are model estimates; they do not prescribe an individual challenge protocol.

## Files and provenance

| File | Purpose |
|---|---|
| `SSM_FiCO2_PaCO2_tutorial.ipynb` | Current executed tutorial, with editable code and plots |
| `code/ssm.py` | Frozen SSM conversion implementation |
| `code/tutorial_analysis.py` | Recalculate normalized inputs, study summaries, slopes and agreement |
| `data/validation_inputs.json` | Selected exact published observations, source units, cohort identity, uncertainty and citations |
| `data/hcvr_inputs.json` | Selected slope evidence, sample counts, protocol details and source uncertainty |
| `data/settings.json`, `data/parameter_evidence.json` | Operating constants and their evidence/conventions |
| `data/analysis_policy.json` | Reviewed inclusion, weighting and display policy |
| `data/supplement_sensitivity_inputs.json` | Explicit optional sensitivity assumptions and source slope |
| `data/expected_results.json` | Frozen regression expectations; never used to supply predictions |
| `data/provenance.json` | Frozen-input origin and version identifiers |
| `release_manifest.json` | File hashes for this companion release |
| `CITATION.cff` | Software citation metadata; the technical note is not yet published |

The public data are a fixed, curated export of selected literature inputs from the author's reviewed analysis. They are not an exhaustive literature search, the entire editable workbook, or newly collected participant data. The engine reconstructs summaries and predictions from the input records, then compares them with the separate expected results. Changing the source selection is a new analysis; do not replace expected values merely to make a failed check pass.

DOI links and extraction locations accompany the observations. Original papers and PDFs are not redistributed. The model code is preserved from the reviewed SSM implementation; publication packaging and teaching changes do not refit it. Plot coordinates and statistics match the technical-note analysis, although Python font/layout rendering can differ from its MATLAB figure export.

## Assumptions and limits

- Physiological steady state must already have been established. The model does not determine the required duration or predict onset, transitions, recovery or breath-by-breath values.
- Published minute-ventilation/PETCO₂ slopes approximate the model's alveolar-ventilation/PaCO₂ response. The finite-duration source protocols do not independently establish ventilatory steady state.
- PETCO₂ is a proxy, not an arterial measurement. A constant arterial–end-tidal offset cancels in a change score, but not in the absolute-pressure mass balance; a changing gradient also affects change scores.
- Standard pressure, water vapour and metabolic assumptions may differ from actual study conditions. Combined participant SD and study-mean slope ranges are sensitivity descriptions, not confidence or prediction intervals.
- The 80-mmHg software guard and wider illustrated curves are not validated accuracy or safety boundaries. The exact pure-HC evaluation spans 2–7% inspired CO₂.
- Adult-eligibility assumptions and unavailable source quantities remain disclosed in the data. Duration alone is not a steady-state criterion.

The separate dynamic-model research and tutorial are outside this repository. No historical-priority or individual-accuracy claim is made.

## Version and license

Initial companion release: **v0.1.0**, 24 September 2026. Cite this version or its commit when reporting results. Use the same version of the notebook, inputs and code together.

Code and original tutorial material use the MIT license in `LICENSE`. Literature tables contain extracted factual values with attribution; source publications retain their respective rights. No source-PDF license is implied.
