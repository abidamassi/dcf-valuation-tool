"""
=============================================================================
SECTION 11 - SENSITIVITY ANALYSIS
=============================================================================
PURPOSE : Show how fragile fair value is against the two most decisive
          variables, WACC and terminal growth. A single fair value number
          gives a misleading impression of precision. This grid shows the
          actual range.

FORMULA : For every combination (WACC_i, g_j)
            1. Recompute Terminal Value  = FCFF_N x (1+g_j) / (WACC_i - g_j)
            2. Re-discount every cash flow at WACC_i
            3. Rebuild the bridge to Equity Value
            4. Divide by shares outstanding

          Note that the FCFF projection does NOT change between cells. Only
          the discount rate and terminal growth change. This is deliberate:
          sensitivity isolates the effect of the cost of capital, separate
          from the effect of operational assumptions handled by Section 12
          (scenarios).

          Default grid: 5 x 5
            WACC             : base -100bps to +100bps, 50bps steps
            Terminal growth  : base -50bps to +50bps, 25bps steps

OUTPUT  : a fair-value-per-share DataFrame, an upside DataFrame, and a rating table.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from s08_terminal import terminal_value
from s09_valuation import discount_and_value


def sensitivity_grid(proj, wacc_base, g_base, snapshot, data, flags):
    """
    Build the WACC x terminal growth sensitivity grid.
    """
    A = ASSUMPTIONS
    steps = A["sens_steps"]
    wacc_step = A["sens_wacc_step"]
    g_step = A["sens_g_step"]

    wacc_axis = [wacc_base + i * wacc_step for i in range(-steps, steps + 1)]
    g_axis = [g_base + j * g_step for j in range(-steps, steps + 1)]

    fv_grid = pd.DataFrame(index=[f"{w*100:.2f}%" for w in wacc_axis],
                           columns=[f"{g*100:.2f}%" for g in g_axis],
                           dtype=float)
    up_grid = fv_grid.copy()

    fcff_final = float(proj["FCFF"].iloc[-1])
    ebitda_final = float(proj["EBIT"].iloc[-1] + proj["D&A"].iloc[-1])

    # flags=None so the grid doesn't flood the log with repeated warnings
    for w in wacc_axis:
        for g in g_axis:
            tv = terminal_value(fcff_final, ebitda_final, w, terminal_g=g, flags=None)
            if not tv["valid"]:
                continue
            v = discount_and_value(proj, tv, w, snapshot, data, flags=_NullFlags())
            if not v["valid"]:
                continue
            fv = v["fair_value_per_share"]
            fv_grid.loc[f"{w*100:.2f}%", f"{g*100:.2f}%"] = fv
            up_grid.loc[f"{w*100:.2f}%", f"{g*100:.2f}%"] = v["upside"]

    fv_grid.index.name = "WACC \\ Terminal g"
    up_grid.index.name = "WACC \\ Terminal g"

    # Summary range statistics
    flat = fv_grid.values.astype(float).ravel()
    flat = flat[np.isfinite(flat)]
    stats = {
        "min": float(flat.min()) if flat.size else np.nan,
        "max": float(flat.max()) if flat.size else np.nan,
        "median": float(np.median(flat)) if flat.size else np.nan,
        "n_valid": int(flat.size),
        "n_cells": int(fv_grid.size),
    }
    return {"fair_value": fv_grid.round(0),
            "upside": (up_grid.astype(float) * 100).round(1),
            "stats": stats,
            "wacc_axis": wacc_axis,
            "g_axis": g_axis}


class _NullFlags:
    """An empty flag sink so the grid doesn't log repeated warnings."""
    def warn(self, *a, **k): pass
    def missing(self, *a, **k): pass
    def zero(self, *a, **k): pass
    def check_series(self, *a, **k): return True
