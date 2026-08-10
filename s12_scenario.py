"""
=============================================================================
SECTION 12 - SKENARIO BULL, BASE, BEAR
=============================================================================
TUJUAN  : Membentuk tiga skenario operasional yang koheren, bukan sekadar
          menggeser satu variabel. Berbeda dari Section 11 yang menguji cost
          of capital, section ini menguji asumsi operasional.

RUMUS   : Deviasi diambil dari volatilitas historis emiten itu sendiri,
          bukan dari angka yang ditentukan sembarangan.

          SD_growth = standar deviasi sampel dari pertumbuhan revenue historis
          SD_margin = standar deviasi sampel dari EBIT margin historis

          BULL   growth = base + 1 x SD_growth
                 margin = base + 1 x SD_margin
                 terminal g = base + 50bps

          BASE   growth = base (moving average historis)
                 margin = base
                 terminal g = base

          BEAR   growth = base - 1 x SD_growth
                 margin = base - 1 x SD_margin
                 terminal g = base - 50bps

          WACC ditahan konstan di ketiga skenario. Pergerakan WACC sudah
          diuji terpisah di Section 11, dan mencampurnya di sini akan
          membuat sumber perubahan nilai tidak bisa diurai.

          Margin Bear diberi lantai 1% agar tidak menjadi negatif dan membuat
          terminal value kehilangan makna.

OUTPUT  : DataFrame ringkasan tiga skenario beserta fair value dan rating.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from s07_forecast import project_fcff
from s08_terminal import terminal_value
from s09_valuation import discount_and_value
from s10_recommendation import make_recommendation
from s11_sensitivity import _NullFlags


def run_scenarios(hist, drv, snapshot, data, wacc, years=None, g_base=None):
    A = ASSUMPTIONS
    N = int(years or A["forecast_years"])
    g_term_base = A["terminal_growth"] if g_base is None else g_base
    k = A["scenario_sd_multiple"]
    g_shift = A["scenario_g_shift"]

    sd_g = drv["rev_growth_sd"]
    sd_m = drv["ebit_margin_sd"]
    g0 = drv["rev_growth"]
    m0 = drv["ebit_margin"]

    specs = {
        "BULL": {
            "g1": g0 + k * sd_g,
            "margin": m0 + k * sd_m,
            "g_term": g_term_base + g_shift,
        },
        "BASE": {
            "g1": g0,
            "margin": m0,
            "g_term": g_term_base,
        },
        "BEAR": {
            "g1": g0 - k * sd_g,
            "margin": max(m0 - k * sd_m, 0.01),
            "g_term": max(g_term_base - g_shift, 0.0),
        },
    }

    rows = []
    detail = {}
    for name, s in specs.items():
        proj, summ = project_fcff(
            hist, drv, snapshot,
            years=N, g1=s["g1"], ebit_margin=s["margin"], terminal_g=s["g_term"]
        )
        tv = terminal_value(
            summ["fcff_final"], summ["ebitda_final"], wacc,
            terminal_g=s["g_term"], flags=None
        )
        if not tv["valid"]:
            rows.append({
                "Skenario": name,
                "Rev growth th-1": s["g1"],
                "EBIT margin": s["margin"],
                "Terminal g": s["g_term"],
                "Fair value/shr": np.nan,
                "Upside": np.nan,
                "Rating": "N/A",
                "Catatan": tv["reason"][:60],
            })
            continue

        v = discount_and_value(proj, tv, wacc, snapshot, data, flags=_NullFlags())
        rec = make_recommendation(v)

        detail[name] = {"proj": proj, "val": v, "tv": tv}
        rows.append({
            "Skenario": name,
            "Rev growth th-1": s["g1"],
            "EBIT margin": s["margin"],
            "Terminal g": s["g_term"],
            "Fair value/shr": v["fair_value_per_share"],
            "Upside": v["upside"],
            "Rating": rec["rating"],
            "Catatan": "",
        })

    df = pd.DataFrame(rows)
    df = df.set_index("Skenario").reindex(["BULL", "BASE", "BEAR"])
    return df, detail


def scenario_table(df):
    """Format tabel skenario untuk ditampilkan."""
    out = pd.DataFrame(index=df.index)
    out["Rev growth th-1"] = (df["Rev growth th-1"] * 100).round(2).astype(str) + "%"
    out["EBIT margin"] = (df["EBIT margin"] * 100).round(2).astype(str) + "%"
    out["Terminal g"] = (df["Terminal g"] * 100).round(2).astype(str) + "%"
    out["Fair value (IDR)"] = df["Fair value/shr"].round(0)
    out["Upside"] = (df["Upside"] * 100).round(1).astype(str) + "%"
    out["Rating"] = df["Rating"]
    return out
