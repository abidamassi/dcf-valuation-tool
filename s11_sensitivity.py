"""
=============================================================================
SECTION 11 - SENSITIVITY ANALYSIS
=============================================================================
TUJUAN  : Menunjukkan seberapa rapuh fair value terhadap dua variabel yang
          paling menentukan, yaitu WACC dan terminal growth. Satu angka fair
          value tunggal memberi kesan presisi yang menyesatkan. Grid ini
          memperlihatkan rentang yang sebenarnya.

RUMUS   : Untuk setiap kombinasi (WACC_i, g_j)
            1. Hitung ulang Terminal Value  = FCFF_N x (1+g_j) / (WACC_i - g_j)
            2. Diskontokan ulang seluruh arus kas dengan WACC_i
            3. Bangun ulang bridge ke Equity Value
            4. Bagi dengan shares outstanding

          Perhatikan bahwa proyeksi FCFF TIDAK berubah antar sel. Yang
          berubah hanya tingkat diskonto dan terminal growth. Ini disengaja:
          sensitivity mengisolasi pengaruh cost of capital, terpisah dari
          pengaruh asumsi operasional yang ditangani Section 12 (skenario).

          Grid default: 5 x 5
            WACC             : base -100bps sampai +100bps, langkah 50bps
            Terminal growth  : base -50bps sampai +50bps, langkah 25bps

OUTPUT  : DataFrame fair value per saham, DataFrame upside, dan tabel rating.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from s08_terminal import terminal_value
from s09_valuation import discount_and_value


def sensitivity_grid(proj, wacc_base, g_base, snapshot, data, flags):
    """
    Bangun grid sensitivity WACC x terminal growth.
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

    # flags=None supaya grid tidak membanjiri log dengan peringatan berulang
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

    # Statistik ringkas rentang
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
    """Penampung flag kosong agar grid tidak mencatat peringatan berulang."""
    def warn(self, *a, **k): pass
    def missing(self, *a, **k): pass
    def zero(self, *a, **k): pass
    def check_series(self, *a, **k): return True
