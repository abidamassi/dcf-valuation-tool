"""
=============================================================================
SECTION 9 - DISKONTO, ENTERPRISE VALUE, DAN NILAI PER SAHAM
=============================================================================
TUJUAN  : Mendiskontokan seluruh arus kas ke nilai sekarang, lalu menjembatani
          dari nilai perusahaan (Enterprise Value) ke nilai yang menjadi hak
          pemegang saham biasa (Equity Value), dan membaginya per lembar.

RUMUS   :
  9.1 DISKONTO ARUS KAS EKSPLISIT (konvensi tengah tahun)
      PV(FCFF_t) = FCFF_t / (1 + WACC)^(t - 0.5)

      Konvensi tengah tahun dipakai karena arus kas terjadi merata sepanjang
      tahun, bukan menumpuk di 31 Desember. Kalau memakai konvensi akhir
      tahun, ganti eksponen menjadi t.

  9.2 DISKONTO TERMINAL VALUE
      PV(TV) = TV_N / (1 + WACC)^N

      Terminal value didiskontokan pada akhir tahun N (bukan tengah tahun)
      karena TV merepresentasikan nilai per akhir periode proyeksi.

  9.3 ENTERPRISE VALUE
      EV = Sigma PV(FCFF_t) + PV(TV)

  9.4 BRIDGE KE EQUITY VALUE
      Equity Value = EV
                   + Kas dan setara kas
                   - Total utang berbunga
                   - Kepentingan non-pengendali

      Catatan: aset non-operasional (investasi pada entitas asosiasi,
      properti investasi) TIDAK ditambahkan pada fase ini. Ini membuat hasil
      cenderung konservatif untuk emiten holding. Ditandai sebagai
      keterbatasan, akan ditangani di fase kedua.

  9.5 NILAI PER SAHAM
      Fair Value per Share = Equity Value / Shares Outstanding

      Memakai shares outstanding dasar, bukan fully diluted, karena data
      opsi karyawan tidak tersedia di yfinance. Untuk emiten dengan program
      opsi besar, hasilnya akan overstate.

  9.6 UPSIDE
      Upside = (Fair Value / Harga Pasar) - 1

OUTPUT  : dict lengkap berisi seluruh komponen bridge.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from s08_terminal import check_tv_dependency


def discount_and_value(proj, tv_info, wacc, snapshot, data, flags,
                       mid_year=None):
    """
    Diskontokan proyeksi dan bangun bridge EV ke equity value.
    """
    A = ASSUMPTIONS
    mid = A["mid_year_convention"] if mid_year is None else mid_year
    N = len(proj)

    if not tv_info["valid"]:
        return {"valid": False, "reason": tv_info["reason"]}

    # ---------------- 9.1 diskonto arus kas eksplisit ----------------
    disc_rows = []
    pv_explicit = 0.0
    for t in range(1, N + 1):
        fcff = float(proj.loc[t, "FCFF"])
        exponent = (t - 0.5) if mid else t
        df = 1.0 / ((1 + wacc) ** exponent)
        pv = fcff * df
        pv_explicit += pv
        disc_rows.append({
            "Tahun": t, "FCFF": fcff, "Eksponen": exponent,
            "Discount factor": df, "PV FCFF": pv
        })
    disc = pd.DataFrame(disc_rows).set_index("Tahun")

    # ---------------- 9.2 diskonto terminal value ----------------
    df_tv = 1.0 / ((1 + wacc) ** N)
    pv_tv = tv_info["tv_nominal"] * df_tv

    # ---------------- 9.3 enterprise value ----------------
    ev = pv_explicit + pv_tv
    tv_share = check_tv_dependency(pv_tv, ev, flags)

    # ---------------- 9.4 bridge ----------------
    cash = snapshot["cash"] if np.isfinite(snapshot["cash"]) else 0.0
    debt = snapshot["total_debt"] if np.isfinite(snapshot["total_debt"]) else 0.0
    minority = snapshot["minority"] if np.isfinite(snapshot["minority"]) else 0.0

    equity_value = ev + cash - debt - minority

    if equity_value <= 0:
        flags.warn("Equity Value",
                   "Nilai ekuitas hasil model negatif atau nol. Utang bersih "
                   "melebihi nilai operasional perusahaan menurut asumsi ini.")

    # ---------------- 9.5 per saham ----------------
    shares = data.shares_outstanding
    if not np.isfinite(shares) or shares <= 0:
        flags.missing("Shares outstanding", "Fair value per saham tidak dapat dihitung.")
        fv_share = np.nan
    else:
        fv_share = equity_value / shares

    # ---------------- 9.6 upside ----------------
    price = data.price
    upside = (fv_share / price - 1) if (np.isfinite(fv_share) and np.isfinite(price) and price > 0) else np.nan

    # ---------------- metrik implied ----------------
    ebitda_final = float(proj["EBIT"].iloc[-1] + proj["D&A"].iloc[-1])
    implied_ev_ebitda_now = ev / snapshot["ebitda"] if (np.isfinite(snapshot["ebitda"]) and snapshot["ebitda"] > 0) else np.nan

    return {
        "valid": True,
        "discount_table": disc,
        "pv_explicit": pv_explicit,
        "pv_terminal": pv_tv,
        "tv_nominal": tv_info["tv_nominal"],
        "tv_discount_factor": df_tv,
        "tv_share_of_ev": tv_share,
        "implied_exit_multiple": tv_info["implied_exit_multiple"],
        "enterprise_value": ev,
        "cash": cash,
        "total_debt": debt,
        "minority": minority,
        "equity_value": equity_value,
        "shares_outstanding": shares,
        "fair_value_per_share": fv_share,
        "market_price": price,
        "upside": upside,
        "implied_ev_ebitda_current": implied_ev_ebitda_now,
        "wacc": wacc,
        "mid_year": mid,
    }


def bridge_table(v):
    """Tabel jembatan dari EV ke nilai per saham."""
    rows = [
        ("PV arus kas eksplisit", v["pv_explicit"] / 1e9),
        ("PV terminal value", v["pv_terminal"] / 1e9),
        ("Enterprise Value", v["enterprise_value"] / 1e9),
        ("(+) Kas dan setara kas", v["cash"] / 1e9),
        ("(-) Total utang berbunga", -v["total_debt"] / 1e9),
        ("(-) Kepentingan non-pengendali", -v["minority"] / 1e9),
        ("Equity Value", v["equity_value"] / 1e9),
    ]
    df = pd.DataFrame(rows, columns=["Komponen", "IDR bn"])
    df["IDR bn"] = df["IDR bn"].round(0)
    return df
