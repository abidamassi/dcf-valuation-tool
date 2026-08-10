"""
=============================================================================
MAIN - ORCHESTRATOR
=============================================================================
PURPOSE : Run every section in sequence. This file contains no formulas of
          its own, only the call order.

PIPELINE ORDER (must not be reordered):

    Section 1  Fetch yfinance data and convert to IDR
    Section 2  Line item extraction and data quality checks
    Section 3  Eligibility screening -> STOP if failed
    Section 4  Historical moving-average drivers
    Section 5  Beta
    Section 6  Cost of Equity, Cost of Debt, WACC
    Section 7  FCFF projection
    Section 8  Terminal value
    Section 9  Discounting and bridge to equity value
    Section 10 BUY / HOLD / SELL recommendation
    Section 11 Sensitivity: WACC x terminal growth
    Section 12 Bull / Base / Bear scenarios
    Section 13 Report assembly

USAGE:
    from main import analyze_ticker, print_report, batch_screen

    r = analyze_ticker("BBCA")          # rejected, financial sector issuer
    r = analyze_ticker("mapa")          # automatically becomes MAPA.JK
    print_report(r)

    df = batch_screen()                 # run the entire universe
=============================================================================
"""

import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from config import ASSUMPTIONS, DISCLAIMER
from s01_fetch import fetch_company
from s02_lineitems import build_history, latest_snapshot
from s03_screening import run_screening
from s04_drivers import build_drivers
from s05_beta import compute_beta
from s06_wacc import compute_wacc
from s07_forecast import project_fcff
from s08_terminal import terminal_value
from s09_valuation import discount_and_value
from s10_recommendation import make_recommendation
from s11_sensitivity import sensitivity_grid
from s12_scenario import run_scenarios
from s13_report import render_report
from universe import get_universe, UNIVERSE_WARNING


def fetch_bundle(raw_ticker):
    """
    Run ONLY the stages that need the network: Section 1 (fetch), Section 2
    (line items), and Section 5 (beta). The result can be cached by the UI so
    moving a slider doesn't trigger another yfinance fetch.

    Returns a dict with data, hist, snapshot, beta, and status.
    """
    data = fetch_company(raw_ticker)
    out = {"data": data, "hist": None, "snapshot": None, "beta": None,
           "stage": None, "ok": False}

    if not data.fetch_ok:
        out["stage"] = f"Section 1 - fetch failed: {data.fetch_error}"
        return out

    hist, li_ok = build_history(data)
    out["hist"] = hist
    if not li_ok:
        out["stage"] = "Section 2 - critical financial statement line items unavailable"
        return out

    out["snapshot"] = latest_snapshot(hist)
    out["beta"] = compute_beta(data.ticker, data.flags)
    out["ok"] = True
    return out


def analyze_ticker(raw_ticker, rf=None, erp=None, size_prem=None,
                   years=None, terminal_g=None, verbose=False, bundle=None):
    """
    Run the full pipeline for one issuer.
    The rf, erp, size_prem, years, and terminal_g parameters are the slider
    entry points for the next phase. If None, the config.py defaults are used.
    """
    A = ASSUMPTIONS
    g_term = A["terminal_growth"] if terminal_g is None else terminal_g
    N = int(years or A["forecast_years"])

    out = {"ticker": raw_ticker, "ok": False, "stage": None}

    # ---------------- Section 1, 2, 5 ----------------
    # If the caller (the UI, which caches this) already supplied a bundle, use it.
    if bundle is None:
        bundle = fetch_bundle(raw_ticker)

    data = bundle["data"]
    out["data"] = data
    if not data.fetch_ok:
        out["stage"] = "Section 1 - fetch failed"
        out["screening"] = {
            "passed": False,
            "status": f"CANNOT PROCEED - {data.fetch_error}",
            "detail": pd.DataFrame(),
            "failed_gates": ["Data fetch"],
            "ticker": data.ticker, "name": data.name,
        }
        return out

    hist = bundle["hist"]
    out["history"] = hist
    if hist is None or bundle["snapshot"] is None:
        out["stage"] = "Section 2 - critical line items incomplete"
        out["screening"] = {
            "passed": False,
            "status": "CANNOT PROCEED - critical financial statement line items unavailable",
            "detail": pd.DataFrame(),
            "failed_gates": ["Line item completeness"],
            "ticker": data.ticker, "name": data.name,
        }
        return out

    snapshot = bundle["snapshot"]
    out["snapshot"] = snapshot

    # ---------------- Section 3 ----------------
    scr = run_screening(data, hist)
    out["screening"] = scr
    if not scr["passed"]:
        out["stage"] = "Section 3 - failed screening"
        return out

    # ---------------- Section 4 ----------------
    drv = build_drivers(hist, data.flags)
    out["drivers"] = drv

    # ---------------- Section 5 ----------------
    beta = bundle["beta"]
    out["beta"] = beta

    # ---------------- Section 6 ----------------
    wacc_info = compute_wacc(data, hist, drv, beta, data.flags,
                             rf=rf, erp=erp, size_prem=size_prem)
    if wacc_info is None:
        out["stage"] = "Section 6 - WACC computation failed"
        out["screening"]["passed"] = False
        out["screening"]["status"] = "CANNOT PROCEED - WACC could not be computed"
        return out
    out["wacc"] = wacc_info
    wacc = wacc_info["wacc"]

    # ---------------- Section 7 ----------------
    proj, fsum = project_fcff(hist, drv, snapshot, years=N, terminal_g=g_term)
    out["projection"] = proj
    out["forecast_summary"] = fsum

    # ---------------- Section 8 ----------------
    tv = terminal_value(fsum["fcff_final"], fsum["ebitda_final"], wacc,
                        terminal_g=g_term, flags=data.flags)
    out["terminal"] = tv
    if not tv["valid"]:
        out["stage"] = "Section 8 - terminal value invalid"
        out["screening"]["passed"] = False
        out["screening"]["status"] = "CANNOT PROCEED - " + tv["reason"]
        return out

    # ---------------- Section 9 ----------------
    val = discount_and_value(proj, tv, wacc, snapshot, data, data.flags)
    out["valuation"] = val
    if not val["valid"]:
        out["stage"] = "Section 9 - valuation failed"
        out["screening"]["passed"] = False
        out["screening"]["status"] = "CANNOT PROCEED - " + val.get("reason", "")
        return out

    # ---------------- Section 10 ----------------
    out["recommendation"] = make_recommendation(val, data.flags)

    # ---------------- Section 11 ----------------
    out["sensitivity"] = sensitivity_grid(proj, wacc, g_term, snapshot, data, data.flags)

    # ---------------- Section 12 ----------------
    sc_df, sc_detail = run_scenarios(hist, drv, snapshot, data, wacc,
                                     years=N, g_base=g_term)
    out["scenarios"] = sc_df
    out["scenario_detail"] = sc_detail

    out["ok"] = True
    out["stage"] = "Done"
    return out


def print_report(result):
    """Print the full Section 13 report."""
    print(render_report(result))


# -----------------------------------------------------------------------
# BATCH SCREENING
# -----------------------------------------------------------------------
def batch_screen(universe="sample", rf=None, erp=None, terminal_g=None,
                 years=None, show_progress=True):
    """
    Run the pipeline across the entire universe and return a summary table.
    Issuers that fail still appear in the table, with their rejection reason.
    """
    tickers = get_universe(universe)
    print(f"[UNIVERSE WARNING] {UNIVERSE_WARNING}\n")

    rows = []
    for i, t in enumerate(tickers, 1):
        if show_progress:
            print(f"  ({i}/{len(tickers)}) {t} ...", end=" ", flush=True)
        try:
            r = analyze_ticker(t, rf=rf, erp=erp, terminal_g=terminal_g, years=years)
        except Exception as exc:
            rows.append({
                "Ticker": t, "Name": "", "Sector": "",
                "Price": np.nan, "Fair Value": np.nan, "Upside %": np.nan,
                "Rating": "ERROR", "WACC %": np.nan, "TV/EV %": np.nan,
                "Flag": 0, "Status": f"{type(exc).__name__}: {exc}",
            })
            if show_progress:
                print("ERROR")
            continue

        d = r["data"]
        if not r["ok"]:
            rows.append({
                "Ticker": d.ticker, "Name": d.name or "",
                "Sector": d.sector or "",
                "Price": d.price, "Fair Value": np.nan, "Upside %": np.nan,
                "Rating": "CANNOT PROCEED",
                "WACC %": np.nan, "TV/EV %": np.nan,
                "Flag": len(d.flags.items),
                "Status": r["screening"]["status"],
            })
            if show_progress:
                print("rejected")
            continue

        v, rec, w = r["valuation"], r["recommendation"], r["wacc"]
        rows.append({
            "Ticker": d.ticker, "Name": d.name or "",
            "Sector": d.sector or "",
            "Price": round(v["market_price"], 0),
            "Fair Value": round(v["fair_value_per_share"], 0),
            "Upside %": round(rec["upside"] * 100, 1),
            "Rating": rec["rating"],
            "WACC %": round(w["wacc"] * 100, 2),
            "TV/EV %": round(v["tv_share_of_ev"] * 100, 1) if np.isfinite(v["tv_share_of_ev"]) else np.nan,
            "Flag": len(d.flags.items),
            "Status": "OK",
        })
        if show_progress:
            print(f"{rec['rating']} ({rec['upside']*100:+.0f}%)")

    df = pd.DataFrame(rows)
    if "Upside %" in df.columns:
        df = df.sort_values("Upside %", ascending=False, na_position="last")
    print("\n" + "=" * 78)
    print("DISCLAIMER")
    print("=" * 78)
    print(DISCLAIMER)
    return df.reset_index(drop=True)


if __name__ == "__main__":
    import sys
    tk = sys.argv[1] if len(sys.argv) > 1 else "MAPA"
    print_report(analyze_ticker(tk))
