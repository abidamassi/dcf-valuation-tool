"""
=============================================================================
MAIN - ORKESTRATOR
=============================================================================
TUJUAN  : Menjalankan seluruh section secara berurutan. File ini tidak berisi
          rumus apa pun, hanya mengatur urutan pemanggilan.

URUTAN ALUR (tidak boleh dibalik):

    Section 1  Fetch data yfinance dan konversi ke IDR
    Section 2  Ekstraksi line item dan pemeriksaan kualitas data
    Section 3  Screening kelayakan  -> kalau gagal, BERHENTI
    Section 4  Driver historis moving average
    Section 5  Beta
    Section 6  Cost of Equity, Cost of Debt, WACC
    Section 7  Proyeksi FCFF
    Section 8  Terminal value
    Section 9  Diskonto dan bridge ke equity value
    Section 10 Rekomendasi BUY / HOLD / SELL
    Section 11 Sensitivity WACC x terminal growth
    Section 12 Skenario Bull / Base / Bear
    Section 13 Perakitan laporan

CARA PAKAI:
    from main import analyze_ticker, print_report, batch_screen

    r = analyze_ticker("BBCA")          # akan ditolak, emiten keuangan
    r = analyze_ticker("mapa")          # otomatis jadi MAPA.JK
    print_report(r)

    df = batch_screen()                 # jalankan seluruh universe
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
    Jalankan HANYA tahap yang butuh jaringan: Section 1 (fetch), Section 2
    (line item), dan Section 5 (beta). Hasilnya bisa di-cache oleh UI supaya
    menggeser slider tidak memicu fetch ulang ke yfinance.

    Mengembalikan dict berisi data, hist, snapshot, beta, dan status.
    """
    data = fetch_company(raw_ticker)
    out = {"data": data, "hist": None, "snapshot": None, "beta": None,
           "stage": None, "ok": False}

    if not data.fetch_ok:
        out["stage"] = f"Section 1 - fetch gagal: {data.fetch_error}"
        return out

    hist, li_ok = build_history(data)
    out["hist"] = hist
    if not li_ok:
        out["stage"] = "Section 2 - pos laporan keuangan kritikal tidak tersedia"
        return out

    out["snapshot"] = latest_snapshot(hist)
    out["beta"] = compute_beta(data.ticker, data.flags)
    out["ok"] = True
    return out


def analyze_ticker(raw_ticker, rf=None, erp=None, size_prem=None,
                   years=None, terminal_g=None, verbose=False, bundle=None):
    """
    Jalankan seluruh pipeline untuk satu emiten.
    Parameter rf, erp, size_prem, years, terminal_g adalah titik masuk
    slider di fase berikutnya. Kalau None, dipakai default dari config.py.
    """
    A = ASSUMPTIONS
    g_term = A["terminal_growth"] if terminal_g is None else terminal_g
    N = int(years or A["forecast_years"])

    out = {"ticker": raw_ticker, "ok": False, "stage": None}

    # ---------------- Section 1, 2, 5 ----------------
    # Kalau bundle sudah disediakan pemanggil (UI yang meng-cache), pakai itu.
    if bundle is None:
        bundle = fetch_bundle(raw_ticker)

    data = bundle["data"]
    out["data"] = data
    if not data.fetch_ok:
        out["stage"] = "Section 1 - fetch gagal"
        out["screening"] = {
            "passed": False,
            "status": f"CANNOT PROCEED - {data.fetch_error}",
            "detail": pd.DataFrame(),
            "failed_gates": ["Fetch data"],
            "ticker": data.ticker, "name": data.name,
        }
        return out

    hist = bundle["hist"]
    out["history"] = hist
    if hist is None or bundle["snapshot"] is None:
        out["stage"] = "Section 2 - pos kritikal tidak lengkap"
        out["screening"] = {
            "passed": False,
            "status": "CANNOT PROCEED - pos laporan keuangan kritikal tidak tersedia",
            "detail": pd.DataFrame(),
            "failed_gates": ["Kelengkapan line item"],
            "ticker": data.ticker, "name": data.name,
        }
        return out

    snapshot = bundle["snapshot"]
    out["snapshot"] = snapshot

    # ---------------- Section 3 ----------------
    scr = run_screening(data, hist)
    out["screening"] = scr
    if not scr["passed"]:
        out["stage"] = "Section 3 - tidak lolos screening"
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
        out["stage"] = "Section 6 - WACC gagal dihitung"
        out["screening"]["passed"] = False
        out["screening"]["status"] = "CANNOT PROCEED - WACC tidak dapat dihitung"
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
        out["stage"] = "Section 8 - terminal value tidak valid"
        out["screening"]["passed"] = False
        out["screening"]["status"] = "CANNOT PROCEED - " + tv["reason"]
        return out

    # ---------------- Section 9 ----------------
    val = discount_and_value(proj, tv, wacc, snapshot, data, data.flags)
    out["valuation"] = val
    if not val["valid"]:
        out["stage"] = "Section 9 - valuasi gagal"
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
    out["stage"] = "Selesai"
    return out


def print_report(result):
    """Cetak laporan lengkap Section 13."""
    print(render_report(result))


# -----------------------------------------------------------------------
# BATCH SCREENING
# -----------------------------------------------------------------------
def batch_screen(universe="sample", rf=None, erp=None, terminal_g=None,
                 years=None, show_progress=True):
    """
    Jalankan pipeline untuk seluruh universe dan kembalikan tabel ringkas.
    Emiten yang gagal tetap masuk tabel dengan alasan penolakannya.
    """
    tickers = get_universe(universe)
    print(f"[PERINGATAN UNIVERSE] {UNIVERSE_WARNING}\n")

    rows = []
    for i, t in enumerate(tickers, 1):
        if show_progress:
            print(f"  ({i}/{len(tickers)}) {t} ...", end=" ", flush=True)
        try:
            r = analyze_ticker(t, rf=rf, erp=erp, terminal_g=terminal_g, years=years)
        except Exception as exc:
            rows.append({
                "Ticker": t, "Nama": "", "Sektor": "",
                "Harga": np.nan, "Fair Value": np.nan, "Upside %": np.nan,
                "Rating": "ERROR", "WACC %": np.nan, "TV/EV %": np.nan,
                "Flag": 0, "Status": f"{type(exc).__name__}: {exc}",
            })
            if show_progress:
                print("ERROR")
            continue

        d = r["data"]
        if not r["ok"]:
            rows.append({
                "Ticker": d.ticker, "Nama": d.name or "",
                "Sektor": d.sector or "",
                "Harga": d.price, "Fair Value": np.nan, "Upside %": np.nan,
                "Rating": "CANNOT PROCEED",
                "WACC %": np.nan, "TV/EV %": np.nan,
                "Flag": len(d.flags.items),
                "Status": r["screening"]["status"],
            })
            if show_progress:
                print("ditolak")
            continue

        v, rec, w = r["valuation"], r["recommendation"], r["wacc"]
        rows.append({
            "Ticker": d.ticker, "Nama": d.name or "",
            "Sektor": d.sector or "",
            "Harga": round(v["market_price"], 0),
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
