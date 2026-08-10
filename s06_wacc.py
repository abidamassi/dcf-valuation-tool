"""
=============================================================================
SECTION 6 - COST OF CAPITAL (CAPM, COST OF DEBT, WACC)
=============================================================================
TUJUAN  : Menentukan tingkat diskonto. Ini variabel tunggal paling
          berpengaruh terhadap hasil DCF, jadi setiap komponennya
          ditampilkan terpisah agar bisa diperdebatkan satu per satu.

RUMUS   :
  6.1 COST OF EQUITY (CAPM)
      Ke = Rf + Beta x ERP + Size Premium

      Rf   = risk-free rate, default 6.50% (proxy INDOGB 10Y, input manual)
      ERP  = equity risk premium Indonesia, default 7.00% (input manual)
      Beta = hasil Section 5 (Blume adjusted)

      Catatan metodologis: Rf memakai yield obligasi pemerintah IDR yang
      sudah mengandung country risk. Menambahkan ERP yang juga mengandung
      country risk premium berpotensi double counting. Kami menerima ini
      sebagai konvensi desk, tapi angkanya harus dibaca sebagai satu paket,
      bukan dijumlahkan lagi dengan premi negara.

  6.2 COST OF DEBT (dari data internal, tanpa sumber eksternal)
      Kd = Interest Expense_t / Rata-rata Total Debt

      Rata-rata Total Debt = (Total Debt_t + Total Debt_t-1) / 2

      Dihitung untuk setiap periode yang tersedia, lalu diambil rata-rata.
      Kalau emiten tidak punya utang atau data bunga tidak tersedia,
      Kd diproksi sebagai Rf + 200bps dan diberi flag.

      Kd setelah pajak = Kd x (1 - tarif pajak efektif)

  6.3 BOBOT STRUKTUR MODAL
      E = Market Cap (harga pasar, bukan nilai buku)
      D = Total Debt periode terakhir (nilai buku sebagai proksi nilai pasar)

      w_E = E / (D + E)
      w_D = D / (D + E)

  6.4 WACC
      WACC = w_E x Ke + w_D x Kd x (1 - t)

OUTPUT  : dict berisi seluruh komponen, siap ditampilkan sebagai tabel.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from utils import clip_flag, nanmean


# -----------------------------------------------------------------------
# 6.1 COST OF EQUITY
# -----------------------------------------------------------------------
def cost_of_equity(beta_adj, rf=None, erp=None, size_prem=None):
    A = ASSUMPTIONS
    rf = A["risk_free_rate"] if rf is None else rf
    erp = A["equity_risk_premium"] if erp is None else erp
    sp = A["size_premium"] if size_prem is None else size_prem
    ke = rf + beta_adj * erp + sp
    return {
        "rf": rf, "erp": erp, "beta": beta_adj,
        "size_premium": sp, "ke": ke,
    }


# -----------------------------------------------------------------------
# 6.2 COST OF DEBT
# -----------------------------------------------------------------------
def cost_of_debt(hist, tax_rate, flags, rf=None):
    """
    Kd dari beban bunga historis dibagi rata-rata saldo utang.
    Tidak memakai credit spread eksternal sama sekali.
    """
    A = ASSUMPTIONS
    rf = A["risk_free_rate"] if rf is None else rf

    debt = pd.to_numeric(hist.loc["total_debt"], errors="coerce")
    intr = pd.to_numeric(hist.loc["interest_exp"], errors="coerce")

    rates = []
    for i in range(1, len(debt)):
        d_now, d_prev, ie = debt.iloc[i], debt.iloc[i - 1], intr.iloc[i]
        if pd.isna(ie) or pd.isna(d_now) or pd.isna(d_prev):
            continue
        avg_debt = (d_now + d_prev) / 2.0
        if avg_debt <= 0:
            continue
        rates.append(ie / avg_debt)

    kd_raw = nanmean(rates)
    method = "Interest Expense / rata-rata Total Debt"

    last_debt = debt.iloc[-1] if pd.notna(debt.iloc[-1]) else 0.0
    if last_debt <= 0:
        kd = rf + 0.02
        method = "Tidak ada utang. Kd proksi = Rf + 200bps (bobot utang nol)."
        flags.warn("Cost of Debt", method)
    elif not np.isfinite(kd_raw):
        kd = rf + 0.02
        method = "Beban bunga tidak tersedia. Kd proksi = Rf + 200bps."
        flags.warn("Cost of Debt", method)
    else:
        # Lantai relatif terhadap Rf. Tidak ada korporasi yang meminjam di
        # bawah pemerintahnya sendiri. Rumus Interest Expense / Total Debt
        # rusak ketika yfinance melaporkan bunga secara neto, atau ketika
        # Total Debt memasukkan liabilitas sewa PSAK 73 yang bebannya tidak
        # masuk baris interest expense. ASII keluar 3.75% dengan Rf 6.50%.
        floor_rel = rf + A["cod_spread_floor"]
        floor = max(A["cod_floor"], floor_rel)
        if kd_raw < floor_rel:
            flags.warn("Cost of Debt",
                       f"Hasil hitung {kd_raw*100:.2f}% berada DI BAWAH risk-free "
                       f"rate + {A['cod_spread_floor']*100:.0f}bps. Secara ekonomi "
                       f"mustahil. Kemungkinan beban bunga dilaporkan neto atau "
                       f"Total Debt memuat liabilitas sewa PSAK 73. "
                       f"Dinaikkan ke {floor_rel*100:.2f}%.")
            method += " (dinaikkan ke lantai Rf + spread)"
        kd = clip_flag(kd_raw, floor, A["cod_cap"], "Cost of Debt", flags)

    return {
        "kd_pretax": float(kd),
        "kd_raw": float(kd_raw) if np.isfinite(kd_raw) else np.nan,
        "kd_aftertax": float(kd * (1 - tax_rate)),
        "tax_rate": float(tax_rate),
        "method": method,
        "n_obs": len(rates),
    }


# -----------------------------------------------------------------------
# 6.3 - 6.4 WACC
# -----------------------------------------------------------------------
def compute_wacc(data, hist, drv, beta_info, flags,
                 rf=None, erp=None, size_prem=None):
    """
    Rangkai Ke, Kd, dan bobot struktur modal menjadi WACC.
    """
    A = ASSUMPTIONS
    tax = drv["tax_rate"]

    ke_parts = cost_of_equity(beta_info["beta_adj"], rf, erp, size_prem)
    kd_parts = cost_of_debt(hist, tax, flags, rf=ke_parts["rf"])

    E = data.market_cap
    D = float(hist.loc["total_debt"].iloc[-1]) if pd.notna(hist.loc["total_debt"].iloc[-1]) else 0.0
    D = max(D, 0.0)

    if not np.isfinite(E) or E <= 0:
        E = float(hist.loc["equity"].iloc[-1])
        flags.warn("Bobot ekuitas", "Market cap tidak tersedia. "
                                    "Dipakai nilai buku ekuitas, bukan nilai pasar.")

    total_cap = E + D
    if total_cap <= 0:
        flags.warn("WACC", "Total kapital nol. WACC tidak dapat dihitung.")
        return None

    w_e = E / total_cap
    w_d = D / total_cap

    wacc_raw = w_e * ke_parts["ke"] + w_d * kd_parts["kd_aftertax"]
    wacc = clip_flag(wacc_raw, A["wacc_floor"], A["wacc_cap"], "WACC", flags)

    return {
        "rf": ke_parts["rf"],
        "erp": ke_parts["erp"],
        "beta_raw": beta_info["beta_raw"],
        "beta_adj": beta_info["beta_adj"],
        "beta_r2": beta_info["r_squared"],
        "beta_nobs": beta_info["n_obs"],
        "size_premium": ke_parts["size_premium"],
        "ke": ke_parts["ke"],
        "kd_pretax": kd_parts["kd_pretax"],
        "kd_aftertax": kd_parts["kd_aftertax"],
        "kd_method": kd_parts["method"],
        "tax_rate": tax,
        "equity_value_mkt": E,
        "debt_book": D,
        "weight_equity": w_e,
        "weight_debt": w_d,
        "wacc_raw": wacc_raw,
        "wacc": wacc,
    }


def wacc_table(w):
    """Tabel rincian WACC untuk output."""
    rows = [
        ("Risk-free rate (input manual)", f"{w['rf']*100:.2f}%"),
        ("Equity Risk Premium (input manual)", f"{w['erp']*100:.2f}%"),
        ("Beta raw (regresi vs IHSG)", f"{w['beta_raw']:.3f}" if np.isfinite(w['beta_raw']) else "n/a"),
        ("Beta adjusted (Blume)", f"{w['beta_adj']:.3f}"),
        ("R-squared regresi beta", f"{w['beta_r2']:.3f}" if np.isfinite(w['beta_r2']) else "n/a"),
        ("Size premium", f"{w['size_premium']*100:.2f}%"),
        ("Cost of Equity (CAPM)", f"{w['ke']*100:.2f}%"),
        ("Cost of Debt sebelum pajak", f"{w['kd_pretax']*100:.2f}%"),
        ("Tarif pajak efektif", f"{w['tax_rate']*100:.2f}%"),
        ("Cost of Debt setelah pajak", f"{w['kd_aftertax']*100:.2f}%"),
        ("Bobot ekuitas E/(D+E)", f"{w['weight_equity']*100:.1f}%"),
        ("Bobot utang D/(D+E)", f"{w['weight_debt']*100:.1f}%"),
        ("WACC", f"{w['wacc']*100:.2f}%"),
    ]
    return pd.DataFrame(rows, columns=["Komponen", "Nilai"])
