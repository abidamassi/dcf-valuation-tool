"""
=============================================================================
SECTION 3 - MODEL ELIGIBILITY SCREENING
=============================================================================
PURPOSE : Determine whether an issuer is ELIGIBLE for FCFF/WACC DCF
          valuation. This is not a "is the stock attractive" screen. It is
          an "does the model even apply" screen. Issuers that fail get a
          CANNOT PROCEED status along with the specific reason.

          Principle: financial issuers (banks, insurance, multifinance) are
          ALWAYS rejected here because debt is their raw material, not a
          funding source. Enterprise Value has no meaning for them. They
          are handled by a separate DDM/GGM tool.

FORMULA : Gate 1  Sector is not Financial Services
          Gate 2  Years of filings >= 4
          Gate 3  Revenue positive in every period
          Gate 4  EBIT positive in >= 2 of the last 3 years
          Gate 5  Market cap >= IDR 1 trillion
          Gate 6  1.0x <= Trailing P/E <= 60.0x
          Gate 7  Total Equity > 0
          Gate 8  Total Debt / (Total Debt + Equity) <= 80%
          Gate 9  Net Debt / EBITDA <= 6.0x
          Gate 10 EBIT / Interest Expense >= 1.0x
          Gate 11 Latest period EBITDA > 0

OUTPUT  : dict {passed: bool, status: str, failed_gates: list, detail: DataFrame}
=============================================================================
"""

import numpy as np
import pandas as pd

from config import SCREENING


def run_screening(data, hist):
    """
    Run every gate. Returns the full result, not just pass/fail, so the user
    knows exactly which gate failed and what the number was.
    """
    S = SCREENING
    results = []          # (no, gate_name, actual_value, criteria, passed)

    def add(no, name, actual, criteria, passed):
        results.append({
            "No": no, "Gate": name, "Value": actual,
            "Criteria": criteria, "Status": "Passed" if passed else "Failed"
        })

    # ---------------- Gate 1: sector ----------------
    sector = (data.sector or "").strip()
    industry = (data.industry or "").strip().lower()
    is_financial = sector in S["excluded_sectors"] or any(
        kw in industry for kw in S["excluded_industry_keywords"]
    )
    add(1, "Non-financial sector",
        f"{sector or 'n/a'} / {data.industry or 'n/a'}",
        "Not Financial Services", not is_financial)

    # ---------------- Gate 2: sufficient history ----------------
    n_years = hist.shape[1] if hist is not None else 0
    add(2, "Annual filing availability", f"{n_years} years",
        f">= {S['min_annual_years']} years", n_years >= S["min_annual_years"])

    if hist is None or n_years == 0:
        return _compile(results, data)

    rev = hist.loc["revenue"]
    ebit = hist.loc["ebit"]
    ebitda = hist.loc["ebitda"]

    # ---------------- Gate 3: positive revenue ----------------
    rev_ok = bool(rev.notna().all() and (rev > 0).all())
    add(3, "Revenue positive every period",
        "yes" if rev_ok else "no / contains NaN", "All periods > 0", rev_ok)

    # ---------------- Gate 4: positive EBIT ----------------
    lb = S["ebit_lookback_years"]
    recent_ebit = ebit.iloc[-lb:]
    n_pos = int((recent_ebit > 0).sum())
    add(4, "EBIT positive", f"{n_pos} of the last {len(recent_ebit)} years",
        f">= {S['min_ebit_positive_years']} of {lb} years",
        n_pos >= S["min_ebit_positive_years"])

    # ---------------- Gate 5: market cap ----------------
    mcap = data.market_cap
    add(5, "Market cap",
        f"IDR {mcap/1e12:,.2f} tn" if np.isfinite(mcap) else "n/a",
        f">= IDR {S['min_market_cap_idr']/1e12:,.0f} tn",
        bool(np.isfinite(mcap) and mcap >= S["min_market_cap_idr"]))

    # ---------------- Gate 6: trailing P/E ----------------
    pe = data.trailing_pe
    pe_ok = bool(np.isfinite(pe) and S["pe_min"] <= pe <= S["pe_max"])
    add(6, "Trailing P/E",
        f"{pe:.2f}x" if np.isfinite(pe) else "n/a (negative or unavailable)",
        f"{S['pe_min']:.0f}x - {S['pe_max']:.0f}x", pe_ok)

    # ---------------- Gate 7: positive equity ----------------
    eq = float(hist.loc["equity"].iloc[-1]) if pd.notna(hist.loc["equity"].iloc[-1]) else np.nan
    eq_ok = bool(np.isfinite(eq) and eq > 0)
    add(7, "Total equity positive",
        f"IDR {eq/1e12:,.2f} tn" if np.isfinite(eq) else "n/a",
        "> 0 (negative equity breaks the WACC weights)", eq_ok)

    # ---------------- Gate 8: capital structure ----------------
    d2c = float(hist.loc["debt_to_cap"].iloc[-1]) if pd.notna(hist.loc["debt_to_cap"].iloc[-1]) else np.nan
    d2c_ok = bool(np.isfinite(d2c) and d2c <= S["max_debt_to_capital"])
    add(8, "Debt / (Debt + Equity)",
        f"{d2c*100:.1f}%" if np.isfinite(d2c) else "n/a",
        f"<= {S['max_debt_to_capital']*100:.0f}%", d2c_ok)

    # ---------------- Gate 9: leverage against EBITDA ----------------
    nde = float(hist.loc["net_debt_ebitda"].iloc[-1]) if pd.notna(hist.loc["net_debt_ebitda"].iloc[-1]) else np.nan
    # Net cash (negative value) passes automatically.
    nde_ok = bool(np.isfinite(nde) and nde <= S["max_net_debt_ebitda"])
    add(9, "Net Debt / EBITDA",
        f"{nde:.2f}x" if np.isfinite(nde) else "n/a",
        f"<= {S['max_net_debt_ebitda']:.1f}x (negative = net cash, passes)", nde_ok)

    # ---------------- Gate 10: interest coverage ----------------
    int_exp_last = hist.loc["interest_exp"].iloc[-1]
    if pd.isna(int_exp_last) or int_exp_last == 0:
        cov_ok, cov_txt = True, "no material interest expense"
    else:
        cov = float(hist.loc["int_coverage"].iloc[-1])
        cov_ok = bool(np.isfinite(cov) and cov >= S["min_interest_coverage"])
        cov_txt = f"{cov:.2f}x"
    add(10, "EBIT / Interest Expense", cov_txt,
        f">= {S['min_interest_coverage']:.1f}x", cov_ok)

    # ---------------- Gate 11: positive EBITDA ----------------
    eb_last = float(ebitda.iloc[-1]) if pd.notna(ebitda.iloc[-1]) else np.nan
    eb_ok = bool(np.isfinite(eb_last) and eb_last > 0)
    add(11, "Latest period EBITDA",
        f"IDR {eb_last/1e9:,.0f} bn" if np.isfinite(eb_last) else "n/a",
        "> 0", eb_ok)

    # ---------------- Gate 12: holding company ----------------
    # A consolidated DCF takes 100% of a subsidiary's cash flow and then
    # deducts non-controlling interest at BOOK VALUE. For a holdco, NCI's
    # book value differs greatly from its economic value, and the holding
    # discount that historically attaches to issuers like INDF would never
    # be captured. This is an INFORMATIONAL FLAG, not a rejecting gate. A
    # large NCI doesn't automatically mean a pure holding company. It could
    # also be a legitimate mining JV structure, or one strategic subsidiary
    # deliberately not fully acquired. The issuer is still valued, and the
    # rating still follows the BUY/HOLD/SELL threshold purely. Only a
    # warning is given, so the user checks whether the book-value NCI
    # bridge is representative enough.
    mi = float(hist.loc["minority"].iloc[-1]) if pd.notna(hist.loc["minority"].iloc[-1]) else 0.0
    mi_ratio = mi / eq if (np.isfinite(eq) and eq > 0) else np.nan
    add(12, "Minority Interest / Equity (informational)",
        f"{mi_ratio*100:.1f}%" if np.isfinite(mi_ratio) else "n/a",
        "Does not reject. Above 15% warrants an SOTP review", True)

    if np.isfinite(mi_ratio) and mi_ratio > S["max_minority_to_equity"]:
        data.flags.warn(
            "NCI structure",
            f"Non-controlling interest is {mi_ratio*100:.1f}% of equity, above "
            f"the {S['max_minority_to_equity']*100:.0f}% threshold. A consolidated "
            f"DCF takes 100% of the subsidiary's cash flow and then deducts NCI "
            f"at BOOK VALUE. If the subsidiary has its own market valuation, the "
            f"gap can be material. Consider an SOTP review as a cross-check."
        )

    return _compile(results, data)


def _compile(results, data):
    detail = pd.DataFrame(results)
    failed = detail.loc[detail["Status"] == "Failed", "Gate"].tolist()
    passed = len(failed) == 0

    if passed:
        status = "ELIGIBLE - proceeding to the DCF calculation"
    else:
        # Distinguish rejection due to business type vs. fundamentals
        if "Non-financial sector" in failed:
            status = ("CANNOT PROCEED - financial sector issuer. "
                      "FCFF/WACC DCF does not apply. Use a DDM/GGM tool instead.")
        elif "Minority Interest / Equity" in failed:
            status = ("CANNOT PROCEED - holding company structure. The "
                      "non-controlling interest is too large, so a consolidated "
                      "DCF produces a misleading value. Use an SOTP approach instead.")
        else:
            status = "CANNOT PROCEED - " + "; ".join(failed)

    return {
        "ticker": data.ticker,
        "name": data.name,
        "passed": passed,
        "status": status,
        "failed_gates": failed,
        "detail": detail,
    }
