# Steady-state FiCO₂–PaCO₂ conversion

A reproducible Jupyter companion for a technical note in preparation by M. Kim. It teaches an approximate bidirectional conversion between inspired CO₂ percentage and arterial CO₂ pressure, conditional on physiological steady state.

**Start with [the executed notebook](SSM_FiCO2_PaCO2_tutorial.ipynb).** Its saved outputs include the worked examples, three figures, both conversion directions, literature agreement and supplementary sensitivity scenarios. Download [the HTML preview](SSM_FiCO2_PaCO2_tutorial.html) to read it without Jupyter.

## Start here

The current **0.1.1-dev** teaching revision opens with a short converter example in both directions, followed by one editable input cell. Choose `forward`, `reverse` or `both`. Forward conversion requires baseline and inspired percentage; reverse conversion requires baseline and achieved/target pressure. Leave an unused directional input as `None`. In `both` mode, each direction is checked independently, so an invalid input cannot hide the other valid estimate. Supply known optional parameters or leave them as `None` to keep the displayed model assumptions. The example is separate from the fixed literature reproduction below it.

Section 5a follows [Jain et al. (2011)](https://doi.org/10.1038/jcbfm.2011.34) from its existing raw source record through both conversions. It separates prediction inputs from measured/reported comparators, explains signed errors, and shows why the reported and study-summary values coincide for this single cohort. The paper’s PETCO₂ means remain end-tidal proxies, not arterial measurements.

The `main` branch carries the **0.1.1-dev development version**. It is separate from the fixed [v0.1.0 release](https://github.com/moonsukk/ssm-fico2-paco2/tree/v0.1.0); a commit or push to `main` does not create a new tagged release.

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

On Windows, activate with `.venv\Scripts\activate`. The runner starts a new kernel using that environment, executes all cells, and writes the executed notebook and HTML preview. It requires no Excel, MATLAB, Zotero, credentials or source-PDF downloads. For interactive editing, open the notebook in a Jupyter-capable editor using the same environment and select **Restart Kernel and Run All**. Use the repository root as the kernel working directory. In the author workspace, the project root, `tutorial/` and `tutorial/companion/` are also supported; all select the complete companion package. Setup checks its required code/data files before importing. Keep these folders together, and restart the kernel after switching checkouts.

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
| `release_manifest.json` | Package version, release status, fixed baseline and file hashes |
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

Current development version: **0.1.1-dev** on `main`. Fixed published baseline: [**v0.1.0**](https://github.com/moonsukk/ssm-fico2-paco2/tree/v0.1.0), 24 September 2026, commit `6e306ecb6c844f4626a67e80d5fb44270e93c951`. Cite the release tag or exact development commit actually used. Keep the notebook, inputs and code from the same version together.

`release_status: development` describes the package, not whether your checkout has been committed or pushed. Check the latter in GitHub Desktop, or use `git status` and `git rev-parse HEAD`; compare the commit with the GitHub branch. Local edits are not uploaded automatically. The manifest excludes its own hash to avoid self-reference. Its hashes describe the distributed file bytes: notebook execution can rewrite execution metadata and HTML identifiers without changing the numerical results.

For a future tagged release, set its version consistently in the notebook, `CITATION.cff`, README and manifest; set the release status and citation release date; verify the package hashes and tests; then tag that exact reviewed commit. Never move `v0.1.0` to a newer commit.

Code and original tutorial material use the MIT license in `LICENSE`. Literature tables contain extracted factual values with attribution; source publications retain their respective rights. No source-PDF license is implied.
