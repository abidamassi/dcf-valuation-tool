"""
=============================================================================
SECTION 7 - PROYEKSI FREE CASH FLOW TO FIRM
=============================================================================
TUJUAN  : Memproyeksikan arus kas bebas ke perusahaan (FCFF) selama periode
          eksplisit. FCFF dipilih, bukan FCFE, karena tidak terpengaruh
          perubahan struktur pendanaan dan langsung berpasangan dengan WACC.

RUMUS   : Untuk setiap tahun t = 1 sampai N

  7.1 Revenue dengan fade linear
      g_t      = g_1 - (g_1 - g_terminal) x (t - 1) / (N - 1)
      Rev_t    = Rev_t-1 x (1 + g_t)

      Fade dipakai agar pertumbuhan tidak konstan sampai tahun terakhir lalu
      terjun bebas ke terminal growth. Pertumbuhan meluruh bertahap menuju
      tingkat perpetuitas.

  7.2 Laba operasi
      EBIT_t   = Rev_t x EBIT margin (konstan, rata-rata historis)

  7.3 Laba operasi setelah pajak
      NOPAT_t  = EBIT_t x (1 - tarif pajak efektif)

      Pajak dikenakan pada EBIT, bukan pada laba sebelum pajak, karena FCFF
      adalah arus kas sebelum pendanaan. Tax shield dari bunga sudah
      diperhitungkan di dalam WACC melalui Kd x (1 - t). Memasukkannya di
      kedua tempat adalah double counting.

  7.4 Reinvestasi
      D&A_t    = Rev_t x rasio D&A historis
      Capex_t  = Rev_t x rasio Capex historis
      NWC_t    = Rev_t x rasio NWC historis
      dNWC_t   = NWC_t - NWC_t-1

  7.5 FCFF
      FCFF_t   = NOPAT_t + D&A_t - Capex_t - dNWC_t

  7.6 Pemeriksaan konsistensi internal
      Reinvestment Rate = (Capex - D&A + dNWC) / NOPAT
      ROIC              = NOPAT / Invested Capital periode sebelumnya
      Implied growth    = Reinvestment Rate x ROIC

      Kalau implied growth jauh berbeda dari asumsi revenue growth, model
      tidak konsisten secara internal. Selisihnya dilaporkan, tidak
      disembunyikan.

OUTPUT  : DataFrame proyeksi per tahun dan dict ringkasan.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS


def project_fcff(hist, drv, snapshot, years=None, g1=None,
                 ebit_margin=None, terminal_g=None, ebit_margin_target=None):
    """
    Bangun proyeksi FCFF. Parameter opsional dipakai oleh Section 12
    (skenario) untuk menimpa nilai base tanpa mengubah driver aslinya.
    """
    A = ASSUMPTIONS
    N = int(years or A["forecast_years"])
    g1 = drv["rev_growth"] if g1 is None else g1
    margin = drv["ebit_margin"] if ebit_margin is None else ebit_margin
    g_term = A["terminal_growth"] if terminal_g is None else terminal_g

    # Margin target. Kalau tidak ada operating leverage, target = base
    # sehingga fade-nya datar dan perilakunya identik dengan margin konstan.
    # Kalau pemanggil menimpa margin base (dipakai Section 12 untuk skenario),
    # target digeser dengan selisih yang sama agar skenario tetap koheren.
    if ebit_margin_target is not None:
        m_target = ebit_margin_target
    else:
        base_default = drv["ebit_margin"]
        target_default = drv.get("ebit_margin_target", base_default)
        m_target = target_default + (margin - base_default)

    tax = drv["tax_rate"]
    da_r = drv["da_ratio"]
    cx_r = drv["capex_ratio"]
    nwc_r = drv["nwc_ratio"]

    # Terminal growth tidak boleh melampaui growth tahun pertama. Tanpa ini,
    # fade justru MENGAKSELERASI pertumbuhan menuju perpetuitas. ASII keluar
    # 2.42% naik ke 4.00%, kebalikan dari logika fade.
    if A["cap_terminal_at_g1"] and g_term > g1:
        g_term = max(g1, 0.0)

    # Capex tidak boleh di bawah D&A ketika perusahaan tumbuh. Kalau capex
    # kurang dari beban penyusutan, basis aset menyusut, dan itu perusahaan
    # yang mengecil. MAPA keluar capex 5.81% dengan D&A 6.79%, kombinasi yang
    # jadi mesin pencetak FCFF palsu lewat add-back D&A besar dengan pengurang
    # capex kecil.
    if g1 > 0 and cx_r < da_r:
        cx_r = da_r

    rev0 = snapshot["revenue"]
    nwc0 = rev0 * nwc_r          # basis NWC diselaraskan dengan rasio, bukan angka mentah,
                                 # supaya dNWC tahun pertama tidak melompat karena
                                 # perbedaan definisi NWC historis dan proyeksi.
    ic0 = snapshot["invested_capital"]

    rows = []
    prev_rev = rev0
    prev_nwc = nwc0
    prev_ic = ic0

    for t in range(1, N + 1):
        # 7.1 fade linear
        if N > 1:
            g_t = g1 - (g1 - g_term) * (t - 1) / (N - 1)
        else:
            g_t = g1

        rev = prev_rev * (1 + g_t)

        # 7.2 Margin fade LINEAR dari base (tahun 1) ke target (tahun N).
        #     Tahun 1 memakai margin base, tahun N memakai margin target.
        if N > 1:
            m_t = margin + (m_target - margin) * (t - 1) / (N - 1)
        else:
            m_t = margin

        ebit = rev * m_t
        nopat = ebit * (1 - tax)
        da = rev * da_r
        capex = rev * cx_r
        nwc = rev * nwc_r
        dnwc = nwc - prev_nwc

        fcff = nopat + da - capex - dnwc

        reinvest = capex - da + dnwc
        rr = reinvest / nopat if nopat != 0 else np.nan
        roic = nopat / prev_ic if (prev_ic and prev_ic != 0) else np.nan
        implied_g = rr * roic if (np.isfinite(rr) and np.isfinite(roic)) else np.nan

        rows.append({
            "Tahun": t,
            "Growth": g_t,
            "Revenue": rev,
            "EBIT": ebit,
            "EBIT margin": m_t,
            "NOPAT": nopat,
            "D&A": da,
            "Capex": capex,
            "NWC": nwc,
            "Delta NWC": dnwc,
            "FCFF": fcff,
            "Reinvestment rate": rr,
            "ROIC": roic,
            "Implied growth": implied_g,
        })

        prev_rev = rev
        prev_nwc = nwc
        prev_ic = prev_ic + reinvest if np.isfinite(reinvest) else prev_ic

    proj = pd.DataFrame(rows).set_index("Tahun")

    summary = {
        "years": N,
        "g1": g1,
        "g_terminal": g_term,
        "ebit_margin": margin,
        "ebit_margin_target": m_target,
        "tax_rate": tax,
        "revenue_base": rev0,
        "fcff_final": float(proj["FCFF"].iloc[-1]),
        "ebitda_final": float(proj["EBIT"].iloc[-1] + proj["D&A"].iloc[-1]),
        "avg_reinvest_rate": float(proj["Reinvestment rate"].mean(skipna=True)),
        "avg_roic": float(proj["ROIC"].mean(skipna=True)),
        "avg_implied_growth": float(proj["Implied growth"].mean(skipna=True)),
        "negative_fcff_years": int((proj["FCFF"] < 0).sum()),
    }
    return proj, summary


def projection_table(proj):
    """Format proyeksi ke miliar rupiah untuk ditampilkan."""
    out = pd.DataFrame(index=proj.index)
    out["Growth %"] = (proj["Growth"] * 100).round(2)
    out["Revenue (bn)"] = (proj["Revenue"] / 1e9).round(0)
    out["Margin %"] = (proj["EBIT margin"] * 100).round(2)
    out["EBIT (bn)"] = (proj["EBIT"] / 1e9).round(0)
    out["NOPAT (bn)"] = (proj["NOPAT"] / 1e9).round(0)
    out["D&A (bn)"] = (proj["D&A"] / 1e9).round(0)
    out["Capex (bn)"] = (proj["Capex"] / 1e9).round(0)
    out["dNWC (bn)"] = (proj["Delta NWC"] / 1e9).round(0)
    out["FCFF (bn)"] = (proj["FCFF"] / 1e9).round(0)
    out["ROIC %"] = (proj["ROIC"] * 100).round(1)
    return out
