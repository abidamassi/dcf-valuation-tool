"""
=============================================================================
SECTION 2 - LINE ITEM EXTRACTION AND DATA QUALITY CHECKS
=============================================================================
PURPOSE : Pull the financial statement line items the DCF needs into one
          uniform structure, and FLAG every item that is empty (NaN) or
          zero. This flagging is not cosmetic. A NaN Interest Expense will
          make Cost of Debt wrong, and the user needs to know.

FORMULA : Derived figures computed here
            EBITDA           = EBIT + D&A
            Net Debt         = Total Debt - Cash & Equivalents
            NWC              = Receivables + Inventory - Payables
            Effective Tax    = Tax Provision / Pretax Income
            Interest Coverage= EBIT / Interest Expense
            D/(D+E)          = Total Debt / (Total Debt + Total Equity)
            Invested Capital = Total Debt + Total Equity - Cash

OUTPUT  : `hist` DataFrame (rows = line items, columns = years, in IDR),
          with flags recorded in data.flags.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from utils import pick_row, safe_div


# -----------------------------------------------------------------------
# 2.1 YFINANCE LABEL DICTIONARY
# -----------------------------------------------------------------------
# yfinance is inconsistent about row naming. Candidate order = priority order.
LABELS = {
    # Income statement
    "revenue":      ["Total Revenue", "Operating Revenue", "Revenue"],
    "cogs":         ["Cost Of Revenue", "Cost Of Goods Sold"],
    "gross_profit": ["Gross Profit"],
    "ebit":         ["Operating Income", "EBIT", "Operating Revenue"],
    "pretax":       ["Pretax Income", "Income Before Tax"],
    "tax":          ["Tax Provision", "Income Tax Expense"],
    "net_income":   ["Net Income", "Net Income Common Stockholders",
                     "Net Income From Continuing Operation Net Minority Interest"],
    "interest_exp": ["Interest Expense", "Interest Expense Non Operating",
                     "Net Interest Income"],

    # Cash flow
    "dep_amort":    ["Depreciation And Amortization",
                     "Depreciation Amortization Depletion",
                     "Depreciation",
                     "Depreciation Depletion And Amortization",
                     "Depreciation Income Statement",
                     "Depreciation And Amortization In Income Statement",
                     "Amortization Of Intangibles"],
    "capex":        ["Capital Expenditure", "Purchase Of PPE",
                     "Net PPE Purchase And Sale", "Purchase Of Business"],

    # Extra row used ONLY for the D&A fallback derivation (EBITDA - EBIT)
    "ebitda_reported": ["EBITDA", "Normalized EBITDA"],

    # Balance sheet
    "cash":         ["Cash And Cash Equivalents",
                     "Cash Cash Equivalents And Short Term Investments",
                     "Cash Financial"],
    "total_debt":   ["Total Debt"],
    "short_debt":   ["Current Debt", "Current Debt And Capital Lease Obligation",
                     "Short Term Debt"],
    "long_debt":    ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "equity":       ["Stockholders Equity", "Common Stock Equity",
                     "Total Equity Gross Minority Interest"],
    "minority":     ["Minority Interest"],
    "receivable":   ["Accounts Receivable", "Receivables",
                     "Gross Accounts Receivable"],
    "inventory":    ["Inventory"],
    "payable":      ["Accounts Payable", "Payables",
                     "Payables And Accrued Expenses"],
    "net_ppe":      ["Net PPE", "Net Property Plant And Equipment"],
    "total_assets": ["Total Assets"],
}

# Line items whose absence makes the DCF unable to run at all.
# dep_amort is DELIBERATELY excluded here. If it's missing, there are two
# safety nets: (1) derivation from EBITDA - EBIT when EBITDA is reported, and
# (2) a fallback to 0% of revenue in Section 4 with an explicit flag.
# dep_amort used to be in CRITICAL and would halt the entire pipeline just
# because one cash flow row's label wasn't found, even though a safe
# fallback existed below it. That bug has since been fixed.
CRITICAL = ["revenue", "ebit", "capex", "equity", "cash"]


# -----------------------------------------------------------------------
# 2.2 EXTRACTION
# -----------------------------------------------------------------------
def build_history(data):
    """
    Build the historical DataFrame from the CompanyData object produced by
    Section 1. Returns (hist, ok). `ok` is False if a critical item is missing.
    """
    flags = data.flags
    src = {
        "income":   data.income,
        "balance":  data.balance,
        "cashflow": data.cashflow,
    }
    where = {
        "revenue": "income", "cogs": "income", "gross_profit": "income",
        "ebit": "income", "pretax": "income", "tax": "income",
        "net_income": "income", "interest_exp": "income",
        "dep_amort": "cashflow", "capex": "cashflow",
        "cash": "balance", "total_debt": "balance", "short_debt": "balance",
        "long_debt": "balance", "equity": "balance", "minority": "balance",
        "receivable": "balance", "inventory": "balance", "payable": "balance",
        "net_ppe": "balance", "total_assets": "balance",
        "ebitda_reported": "income",
    }

    # The year axis is taken from the income statement
    if data.income is None or data.income.empty:
        flags.missing("Income statement")
        return None, False
    years = list(data.income.columns)

    rows = {}
    for key, candidates in LABELS.items():
        series = pick_row(src[where[key]], candidates)
        if series is None:
            rows[key] = pd.Series([np.nan] * len(years), index=years)
            if key in CRITICAL:
                flags.missing(key, "Critical line item not found in yfinance")
            elif key in ("dep_amort", "ebitda_reported"):
                pass    # handled by the D&A fallback flow, flag recorded there
            else:
                flags.missing(key)
        else:
            rows[key] = series.reindex(years)

    hist = pd.DataFrame(rows).T
    hist = hist[sorted(hist.columns)]           # chronological

    # ---- drop periods with empty revenue ----
    # yfinance sometimes returns one extra year column that's almost
    # entirely NaN (an oldest period out of coverage, or a partial TTM
    # column). Columns like this corrupt the moving average if left in.
    empty_years = hist.columns[hist.loc["revenue"].isna()]
    if len(empty_years) > 0:
        flags.warn("Empty period",
                   f"{len(empty_years)} period(s) dropped for missing revenue: "
                   f"{[str(c)[:10] for c in empty_years]}")
        hist = hist.drop(columns=empty_years)

    # ---- sign normalisation ----
    # Capex in yfinance is signed negative (an outflow). We store it positive.
    hist.loc["capex"] = hist.loc["capex"].abs()
    # Interest expense is sometimes negative, sometimes positive. Store it positive.
    hist.loc["interest_exp"] = hist.loc["interest_exp"].abs()
    hist.loc["dep_amort"] = hist.loc["dep_amort"].abs()

    # ---- total debt fallback ----
    td = hist.loc["total_debt"]
    if td.isna().all():
        sd = hist.loc["short_debt"].fillna(0)
        ld = hist.loc["long_debt"].fillna(0)
        combined = sd + ld
        if combined.abs().sum() > 0:
            hist.loc["total_debt"] = combined
            flags.warn("total_debt", "Summed from Current Debt + Long Term Debt.")
        else:
            hist.loc["total_debt"] = 0.0
            flags.zero("total_debt", "No debt data. Assumed zero, please verify.")

    hist.loc["minority"] = hist.loc["minority"].fillna(0.0)

    # ---- layered D&A fallback ----
    # The "EBITDA" row in yfinance is NOT always pure EBIT + D&A. It's often
    # a normalized version that has already absorbed non-operating items.
    # The EBITDA-minus-EBIT derivation MUST therefore be cross-validated.
    #
    # Test: D&A / Net PP&E must fall within a reasonable range. Too high
    # means the derivation absorbed non-depreciation expense. Too low means
    # the EBITDA row is empty or wrong.
    #
    # Empirical evidence that triggered this fix:
    #   MAPA  the derivation gave D&A/Revenue of 6.79%, reality is around 2.8%
    #   INDF  the derivation gave D&A/Revenue of 0.22%, implausible for a
    #         manufacturer of that size
    if hist.loc["dep_amort"].isna().all():
        eb_rep = hist.loc["ebitda_reported"]
        derived_ok = False

        if not eb_rep.isna().all():
            derived = (eb_rep - hist.loc["ebit"]).clip(lower=0)
            ppe = hist.loc["net_ppe"]
            ratio = (derived / ppe).replace([np.inf, -np.inf], np.nan).dropna()

            if len(ratio) > 0:
                med = float(ratio.median())
                lo = ASSUMPTIONS["da_over_netppe_floor"]
                hi = ASSUMPTIONS["da_over_netppe_cap"]
                if lo <= med <= hi:
                    hist.loc["dep_amort"] = derived
                    derived_ok = True
                    flags.warn("dep_amort",
                               f"No D&A line in the cash flow statement. Derived from "
                               f"EBITDA minus EBIT. Passed the cross-check: "
                               f"D&A/Net PP&E = {med*100:.1f}% (reasonable).")
                else:
                    flags.warn("dep_amort",
                               f"EBITDA-minus-EBIT derivation REJECTED. "
                               f"Derived D&A/Net PP&E = {med*100:.1f}%, outside the "
                               f"reasonable range of {lo*100:.0f}-{hi*100:.0f}%. "
                               f"The yfinance EBITDA line is likely a normalized "
                               f"figure that absorbs non-operating items.")

        if not derived_ok:
            # Steady-state assumption: maintenance capex roughly equals D&A.
            # As a result D&A and Capex cancel out in FCFF, so
            # FCFF = NOPAT minus delta NWC. Conservative and transparent.
            cx = hist.loc["capex"]
            if not cx.isna().all():
                hist.loc["dep_amort"] = cx
                flags.warn("dep_amort",
                           "D&A proxied as EQUAL TO Capex (steady-state assumption). "
                           "As a result D&A and Capex cancel out in FCFF, so "
                           "FCFF = NOPAT minus delta NWC. This is a conservative "
                           "choice, not a reported figure.")
            else:
                flags.warn("dep_amort",
                           "Neither D&A nor Capex is available. FCFF cannot be "
                           "computed reliably.")

    # -------------------------------------------------------------------
    # 2.3 DERIVED FIGURES
    # -------------------------------------------------------------------
    hist.loc["ebitda"] = hist.loc["ebit"] + hist.loc["dep_amort"].fillna(0)
    hist.loc["net_debt"] = hist.loc["total_debt"].fillna(0) - hist.loc["cash"].fillna(0)

    nwc = (hist.loc["receivable"].fillna(0)
           + hist.loc["inventory"].fillna(0)
           - hist.loc["payable"].fillna(0))
    if (hist.loc["receivable"].isna().all() and hist.loc["inventory"].isna().all()):
        flags.warn("NWC", "Receivables and inventory are unavailable. NWC assumed "
                          "zero, so delta working capital will not be modelled.")
        nwc = pd.Series(0.0, index=hist.columns)
    hist.loc["nwc"] = nwc

    hist.loc["ebit_margin"] = hist.loc["ebit"] / hist.loc["revenue"]
    hist.loc["capex_ratio"] = hist.loc["capex"] / hist.loc["revenue"]
    hist.loc["da_ratio"] = hist.loc["dep_amort"] / hist.loc["revenue"]
    hist.loc["nwc_ratio"] = hist.loc["nwc"] / hist.loc["revenue"]
    hist.loc["eff_tax"] = hist.loc["tax"] / hist.loc["pretax"]
    hist.loc["int_coverage"] = hist.loc["ebit"] / hist.loc["interest_exp"]
    hist.loc["debt_to_cap"] = hist.loc["total_debt"].fillna(0) / (
        hist.loc["total_debt"].fillna(0) + hist.loc["equity"]
    )
    hist.loc["net_debt_ebitda"] = hist.loc["net_debt"] / hist.loc["ebitda"]
    hist.loc["invested_capital"] = (hist.loc["total_debt"].fillna(0)
                                    + hist.loc["equity"]
                                    - hist.loc["cash"].fillna(0))
    hist.loc["rev_growth"] = hist.loc["revenue"].pct_change()

    # -------------------------------------------------------------------
    # 2.4 QUALITY CHECKS
    # -------------------------------------------------------------------
    # dep_amort is DELIBERATELY not checked here. That item has its own
    # fallback flow above which already logged one explanatory flag.
    # Checking it again here would produce a misleading duplicate MISSING
    # flag, as if the data were entirely absent when it has already been handled.
    for key in ["revenue", "ebit", "capex", "cash", "equity",
                "total_debt", "interest_exp", "tax", "pretax", "net_income"]:
        flags.check_series(hist.loc[key], key)

    ok = True
    for key in CRITICAL:
        if hist.loc[key].isna().all():
            ok = False

    return hist, ok


# -----------------------------------------------------------------------
# 2.5 LATEST-PERIOD SNAPSHOT
# -----------------------------------------------------------------------
def latest_snapshot(hist):
    """Take the last column as the current balance sheet position."""
    last = hist.columns[-1]
    def g(k, default=np.nan):
        v = hist.loc[k, last]
        return float(v) if pd.notna(v) else default
    return {
        "period":       str(last)[:10],
        "revenue":      g("revenue"),
        "ebit":         g("ebit"),
        "ebitda":       g("ebitda"),
        "cash":         g("cash", 0.0),
        "total_debt":   g("total_debt", 0.0),
        "net_debt":     g("net_debt", 0.0),
        "equity":       g("equity"),
        "minority":     g("minority", 0.0),
        "nwc":          g("nwc", 0.0),
        "net_income":   g("net_income"),
        "invested_capital": g("invested_capital"),
    }
