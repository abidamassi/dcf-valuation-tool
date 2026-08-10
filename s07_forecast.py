"""
=============================================================================
SECTION 7 - FREE CASH FLOW TO FIRM PROJECTION
=============================================================================
PURPOSE : Project free cash flow to the firm (FCFF) across the explicit
          period. FCFF is chosen over FCFE because it's unaffected by
          changes in funding structure and pairs directly with WACC.

FORMULA : For every year t = 1 to N

  7.1 Revenue with a linear fade
      g_t      = g_1 - (g_1 - g_terminal) x (t - 1) / (N - 1)
      Rev_t    = Rev_t-1 x (1 + g_t)

      The fade is used so growth doesn't stay constant until the final year
      and then free-fall into terminal growth. Growth decays gradually
      toward the perpetuity rate.

  7.2 Operating income
      EBIT_t   = Rev_t x EBIT margin (constant, historical average)

  7.3 Net operating profit after tax
      NOPAT_t  = EBIT_t x (1 - effective tax rate)

      Tax is applied to EBIT, not to pretax income, because FCFF is a
      pre-financing cash flow. The interest tax shield is already accounted
      for inside WACC via Kd x (1 - t). Including it in both places would
      be double counting.

  7.4 Reinvestment
      D&A_t    = Rev_t x historical D&A ratio
      Capex_t  = Rev_t x historical Capex ratio
      NWC_t    = Rev_t x historical NWC ratio
      dNWC_t   = NWC_t - NWC_t-1

  7.5 FCFF
      FCFF_t   = NOPAT_t + D&A_t - Capex_t - dNWC_t

  7.6 Internal consistency check
      Reinvestment Rate = (Capex - D&A + dNWC) / NOPAT
      ROIC              = NOPAT / prior period Invested Capital
      Implied growth    = Reinvestment Rate x ROIC

      If implied growth differs greatly from the assumed revenue growth,
      the model is not internally consistent. The gap is reported, not hidden.

OUTPUT  : a per-year projection DataFrame and a summary dict.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS


def project_fcff(hist, drv, snapshot, years=None, g1=None,
                 ebit_margin=None, terminal_g=None, ebit_margin_target=None):
    """
    Build the FCFF projection. Optional parameters are used by Section 12
    (scenarios) to override the base values without changing the original drivers.
    """
    A = ASSUMPTIONS
    N = int(years or A["forecast_years"])
    g1 = drv["rev_growth"] if g1 is None else g1
    margin = drv["ebit_margin"] if ebit_margin is None else ebit_margin
    g_term = A["terminal_growth"] if terminal_g is None else terminal_g

    # Margin target. If there's no operating leverage, target = base, so the
    # fade is flat and behaves identically to a constant margin. If the
    # caller overrides the base margin (used by Section 12 for scenarios),
    # the target is shifted by the same delta so the scenario stays coherent.
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

    # Terminal growth may not exceed year-one growth. Without this, the
    # fade actually ACCELERATES growth toward the perpetuity rate. ASII came
    # out at 2.42% rising to 4.00%, the opposite of the fade logic.
    if A["cap_terminal_at_g1"] and g_term > g1:
        g_term = max(g1, 0.0)

    # Capex may not fall below D&A while the company is growing. If capex
    # is less than the depreciation charge, the asset base is shrinking,
    # which is a company in decline. MAPA came out with capex at 5.81%
    # against D&A of 6.79%, a combination that becomes a fake FCFF-printing
    # machine via a large D&A add-back paired with a small capex deduction.
    if g1 > 0 and cx_r < da_r:
        cx_r = da_r

    rev0 = snapshot["revenue"]
    nwc0 = rev0 * nwc_r          # the NWC base is aligned to the ratio, not the raw
                                 # figure, so year-one dNWC doesn't jump because of a
                                 # definitional mismatch between historical and projected NWC.
    ic0 = snapshot["invested_capital"]

    rows = []
    prev_rev = rev0
    prev_nwc = nwc0
    prev_ic = ic0

    for t in range(1, N + 1):
        # 7.1 linear fade
        if N > 1:
            g_t = g1 - (g1 - g_term) * (t - 1) / (N - 1)
        else:
            g_t = g1

        rev = prev_rev * (1 + g_t)

        # 7.2 Margin fades LINEARLY from base (year 1) to target (year N).
        #     Year 1 uses the base margin, year N uses the target margin.
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
            "Year": t,
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

    proj = pd.DataFrame(rows).set_index("Year")

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
    """Format the projection into IDR billions for display."""
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
