"""
=============================================================================
SECTION 6 - COST OF CAPITAL (CAPM, COST OF DEBT, WACC)
=============================================================================
PURPOSE : Determine the discount rate. This is the single most influential
          variable in the DCF result, so every component is shown
          separately so each can be debated on its own.

FORMULA :
  6.1 COST OF EQUITY (CAPM)
      Ke = Rf + Beta x ERP + Size Premium

      Rf   = risk-free rate, default 6.50% (INDOGB 10Y proxy, manual input)
      ERP  = Indonesia equity risk premium, default 7.00% (manual input)
      Beta = Section 5 result (Blume adjusted)

      Methodological note: Rf uses the IDR government bond yield, which
      already embeds country risk. Adding an ERP that also embeds a
      country risk premium is potentially double counting. We accept this
      as a desk convention, but the number should be read as one package,
      not summed again with a separate country premium.

  6.2 COST OF DEBT (from internal data, no external source)
      Kd = Interest Expense_t / Average Total Debt

      Average Total Debt = (Total Debt_t + Total Debt_t-1) / 2

      Computed for every available period, then averaged. If the issuer
      has no debt or interest data is unavailable, Kd is proxied as
      Rf + 200bps and flagged.

      Kd after tax = Kd x (1 - effective tax rate)

  6.3 CAPITAL STRUCTURE WEIGHTS
      E = Market Cap (market price, not book value)
      D = Latest period Total Debt (book value as a proxy for market value)

      w_E = E / (D + E)
      w_D = D / (D + E)

  6.4 WACC
      WACC = w_E x Ke + w_D x Kd x (1 - t)

OUTPUT  : dict with every component, ready to display as a table.
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
    Kd from historical interest expense divided by the average debt balance.
    No external credit spread is used at all.
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
    method = "Interest Expense / average Total Debt"

    last_debt = debt.iloc[-1] if pd.notna(debt.iloc[-1]) else 0.0
    if last_debt <= 0:
        kd = rf + 0.02
        method = "No debt. Kd proxied as Rf + 200bps (zero debt weight)."
        flags.warn("Cost of Debt", method)
    elif not np.isfinite(kd_raw):
        kd = rf + 0.02
        method = "Interest expense unavailable. Kd proxied as Rf + 200bps."
        flags.warn("Cost of Debt", method)
    else:
        # Floor relative to Rf. No corporation borrows below its own
        # government. The Interest Expense / Total Debt formula breaks when
        # yfinance reports interest net, or when Total Debt includes PSAK 73
        # lease liabilities whose expense doesn't appear in interest expense.
        # ASII came out at 3.75% against an Rf of 6.50%.
        floor_rel = rf + A["cod_spread_floor"]
        floor = max(A["cod_floor"], floor_rel)
        if kd_raw < floor_rel:
            flags.warn("Cost of Debt",
                       f"Computed {kd_raw*100:.2f}% is BELOW the risk-free "
                       f"rate + {A['cod_spread_floor']*100:.0f}bps. Economically "
                       f"implausible. Interest expense may be reported net, or "
                       f"Total Debt may include PSAK 73 lease liabilities. "
                       f"Raised to {floor_rel*100:.2f}%.")
            method += " (raised to the Rf + spread floor)"
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
    Combine Ke, Kd, and the capital structure weights into WACC.
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
        flags.warn("Equity weight", "Market cap unavailable. "
                                    "Book value of equity used instead of market value.")

    total_cap = E + D
    if total_cap <= 0:
        flags.warn("WACC", "Total capital is zero. WACC cannot be computed.")
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
    """WACC breakdown table for output."""
    rows = [
        ("Risk-free rate (manual input)", f"{w['rf']*100:.2f}%"),
        ("Equity Risk Premium (manual input)", f"{w['erp']*100:.2f}%"),
        ("Beta raw (regression vs IHSG)", f"{w['beta_raw']:.3f}" if np.isfinite(w['beta_raw']) else "n/a"),
        ("Beta adjusted (Blume)", f"{w['beta_adj']:.3f}"),
        ("Beta regression R-squared", f"{w['beta_r2']:.3f}" if np.isfinite(w['beta_r2']) else "n/a"),
        ("Size premium", f"{w['size_premium']*100:.2f}%"),
        ("Cost of Equity (CAPM)", f"{w['ke']*100:.2f}%"),
        ("Cost of Debt, pre-tax", f"{w['kd_pretax']*100:.2f}%"),
        ("Effective tax rate", f"{w['tax_rate']*100:.2f}%"),
        ("Cost of Debt, after-tax", f"{w['kd_aftertax']*100:.2f}%"),
        ("Equity weight E/(D+E)", f"{w['weight_equity']*100:.1f}%"),
        ("Debt weight D/(D+E)", f"{w['weight_debt']*100:.1f}%"),
        ("WACC", f"{w['wacc']*100:.2f}%"),
    ]
    return pd.DataFrame(rows, columns=["Component", "Value"])
