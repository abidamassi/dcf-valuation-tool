"""
=============================================================================
SECTION 9 - DISCOUNTING, ENTERPRISE VALUE, AND PER-SHARE VALUE
=============================================================================
PURPOSE : Discount every cash flow to present value, then bridge from firm
          value (Enterprise Value) to the value belonging to common
          shareholders (Equity Value), and divide it per share.

FORMULA :
  9.1 DISCOUNTING EXPLICIT CASH FLOWS (mid-year convention)
      PV(FCFF_t) = FCFF_t / (1 + WACC)^(t - 0.5)

      The mid-year convention is used because cash flow occurs evenly
      through the year, not piled up on December 31. For the end-of-year
      convention, change the exponent to t.

  9.2 DISCOUNTING TERMINAL VALUE
      PV(TV) = TV_N / (1 + WACC)^N

      Terminal value is discounted at the end of year N (not mid-year)
      because TV represents value as of the end of the projection period.

  9.3 ENTERPRISE VALUE
      EV = Sigma PV(FCFF_t) + PV(TV)

  9.4 BRIDGE TO EQUITY VALUE
      Equity Value = EV
                   + Cash and equivalents
                   - Total interest-bearing debt
                   - Non-controlling interest

      Note: non-operating assets (investments in associates, investment
      property) are NOT added at this stage. This makes the result
      conservative for holding-company issuers. Flagged as a limitation,
      to be addressed in a second phase.

  9.5 PER-SHARE VALUE
      Fair Value per Share = Equity Value / Shares Outstanding

      Uses basic shares outstanding, not fully diluted, because employee
      option data isn't available in yfinance. For issuers with a large
      option program, the result will be overstated.

  9.6 UPSIDE
      Upside = (Fair Value / Market Price) - 1

OUTPUT  : a complete dict with every bridge component.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from s08_terminal import check_tv_dependency


def discount_and_value(proj, tv_info, wacc, snapshot, data, flags,
                       mid_year=None):
    """
    Discount the projection and build the EV-to-equity-value bridge.
    """
    A = ASSUMPTIONS
    mid = A["mid_year_convention"] if mid_year is None else mid_year
    N = len(proj)

    if not tv_info["valid"]:
        return {"valid": False, "reason": tv_info["reason"]}

    # ---------------- 9.1 discount the explicit cash flows ----------------
    disc_rows = []
    pv_explicit = 0.0
    for t in range(1, N + 1):
        fcff = float(proj.loc[t, "FCFF"])
        exponent = (t - 0.5) if mid else t
        df = 1.0 / ((1 + wacc) ** exponent)
        pv = fcff * df
        pv_explicit += pv
        disc_rows.append({
            "Year": t, "FCFF": fcff, "Exponent": exponent,
            "Discount factor": df, "PV FCFF": pv
        })
    disc = pd.DataFrame(disc_rows).set_index("Year")

    # ---------------- 9.2 discount the terminal value ----------------
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
                   "The model's equity value is negative or zero. Net debt "
                   "exceeds the company's operating value under these assumptions.")

    # ---------------- 9.5 per-share value ----------------
    shares = data.shares_outstanding
    if not np.isfinite(shares) or shares <= 0:
        flags.missing("Shares outstanding", "Fair value per share cannot be computed.")
        fv_share = np.nan
    else:
        fv_share = equity_value / shares

    # ---------------- 9.6 upside ----------------
    price = data.price
    upside = (fv_share / price - 1) if (np.isfinite(fv_share) and np.isfinite(price) and price > 0) else np.nan

    # ---------------- implied metrics ----------------
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
    """Bridge table from enterprise value to per-share value."""
    rows = [
        ("PV of explicit cash flows", v["pv_explicit"] / 1e9),
        ("PV of terminal value", v["pv_terminal"] / 1e9),
        ("Enterprise Value", v["enterprise_value"] / 1e9),
        ("(+) Cash and equivalents", v["cash"] / 1e9),
        ("(-) Total interest-bearing debt", -v["total_debt"] / 1e9),
        ("(-) Minority interest", -v["minority"] / 1e9),
        ("Equity Value", v["equity_value"] / 1e9),
    ]
    df = pd.DataFrame(rows, columns=["Component", "IDR bn"])
    df["IDR bn"] = df["IDR bn"].round(0)
    return df
