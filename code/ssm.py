"""SSM-only FiCO2 <-> PaCO2 conversion; FiCO2 medical-air default.

Equations retain the canonical converter's steady-state mass balance and upper
quadratic root. New finite/physical-domain checks reject unsupported numerical
inputs; the S=0 limiting case is explicit. No temporal model is implemented.
Default S=1.7081818181818182 follows Tallon + Peebles PetCO2 minute-ventilation evidence.
The workbook-driven pipeline supplies its recalculated setting explicitly.
Rebreathing is an optional reference parameterization, not the default.

Units: FiCO2 percent by default; PaCO2 mmHg; VCO2 mL/min STPD; VA L/min BTPS;
S L/min/mmHg; K mmHg L/mL. PETCO2 is not an arterial measurement.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

VERSION = 'ssm-2026-09-17-medical-air'
KPA_PER_MMHG = 0.1333224


def _finite(name, value):
    if not math.isfinite(value):
        raise ValueError(f'{name} must be finite')


@dataclass(frozen=True)
class Params:
    S: float = 1.7081818181818182
    VCO2: float = 200.0
    PaCO2_base: float = 40.0
    Patm: float = 760.0
    PH2O: float = 47.0
    K: float = 0.863
    max_paco2: float = 80.0

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            _finite(name, getattr(self, name))
        if self.S < 0 or self.VCO2 <= 0 or self.PaCO2_base <= 0 or self.K <= 0:
            raise ValueError('S must be nonnegative; VCO2, baseline and K must be positive')
        if self.PH2O < 0 or self.Patm <= self.PH2O:
            raise ValueError('Require Patm > PH2O >= 0')
        if self.max_paco2 < self.PaCO2_base:
            raise ValueError('Upper numerical guard must be >= baseline')

    @property
    def VA_base(self):
        return self.K * self.VCO2 / self.PaCO2_base

    @property
    def Pdry(self):
        return self.Patm - self.PH2O

    @property
    def D(self):
        return self.VA_base - self.S * self.PaCO2_base

    def VA(self, paco2):
        return self.VA_base + self.S * (paco2 - self.PaCO2_base)


def _check_pressure(paco2, p):
    _finite('PaCO2', paco2)
    if paco2 < p.PaCO2_base - 1e-9:
        raise ValueError('SSM hypercapnic branch requires PaCO2 >= baseline')
    if paco2 > p.max_paco2 + 1e-9:
        raise ValueError('PaCO2 exceeds the configured upper numerical guard')
    if p.VA(paco2) <= 0:
        raise ValueError('Alveolar ventilation must be positive')


def fico2_to_paco2(fico2, p=None, is_percent=True):
    """Estimate equilibrium PaCO2. Establishment of steady state is assumed.

    The default 80-mmHg software guard is inherited from v7 and is NOT evidence
    of physiological validity up to 80 mmHg; near-linear measured HCVR and
    plausible ventilation must hold at the actual operating point.
    """
    p = p or Params()
    _finite('FiCO2', fico2)
    fraction = fico2 / 100 if is_percent else fico2
    if not 0 <= fraction <= 1:
        raise ValueError('FiCO2 must be in [0,100] percent or [0,1] fraction')
    pico2 = fraction * p.Pdry
    if p.S == 0:
        paco2 = pico2 + p.PaCO2_base
    else:
        b = p.D - p.S * pico2
        c = -(pico2 * p.D + p.K * p.VCO2)
        # Stable evaluation of the same upper root, including small positive S.
        root_disc = math.sqrt(b*b - 4*p.S*c)
        q = -0.5 * (b + math.copysign(root_disc, b))
        paco2 = max(q / p.S, c / q)
    _check_pressure(paco2, p)
    return paco2


def paco2_to_fico2(paco2, p=None, as_percent=True):
    """Estimate inspired CO2 required by the same equilibrium relationship."""
    p = p or Params()
    _check_pressure(paco2, p)
    fraction = (paco2 - p.K * p.VCO2 / p.VA(paco2)) / p.Pdry
    if not -1e-12 <= fraction <= 1:
        raise ValueError('Solution is not a physical inspired CO2 fraction')
    fraction = max(0.0, fraction)
    return 100 * fraction if as_percent else fraction


def params_from_baseline(paco2_base, **kwargs):
    return Params(PaCO2_base=paco2_base, **kwargs)
