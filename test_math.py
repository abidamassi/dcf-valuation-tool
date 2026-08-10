"""
=============================================================================
TEST - MATH VALIDATION WITH SYNTHETIC DATA
=============================================================================
PURPOSE : Exercise Section 2 through 12 without calling yfinance. Financial
          statement data is built by hand with numbers whose results can be
          checked by hand, then compared against the model's output.

          Run with: python test_math.py
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS as A
from s01_fetch import CompanyData
from s02_lineitems import build_history, latest_snapshot
from s03_screening import run_screening
from s04_drivers import build_drivers
from s06_wacc import compute_wacc
from s07_forecast import project_fcff
from s08_terminal import terminal_value
from s09_valuation import discount_and_value
from s10_recommendation import make_recommendation
from s11_sensitivity import sensitivity_grid
from s12_scenario import run_scenarios


# -----------------------------------------------------------------------
# SYNTHETIC ISSUER
# Revenue grows 10% per year, EBIT margin a constant 15%, tax rate 22%,
# D&A 4% of revenue, capex 6% of revenue, NWC 10% of revenue.
# -----------------------------------------------------------------------
def make_fake_company():
    years = pd.to_datetime(["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"])
    rev = np.array([10_000, 11_000, 12_100, 13_310], dtype=float) * 1e9   # IDR bn -> IDR

    income = pd.DataFrame(index=[
        "Total Revenue", "Cost Of Revenue", "Operating Income",
        "Pretax Income", "Tax Provision", "Net Income", "Interest Expense",
    ], columns=years, dtype=float)

    income.loc["Total Revenue"] = rev
    income.loc["Cost Of Revenue"] = rev * 0.60
    income.loc["Operating Income"] = rev * 0.15
    income.loc["Interest Expense"] = 150e9
    income.loc["Pretax Income"] = rev * 0.15 - 150e9
    income.loc["Tax Provision"] = (rev * 0.15 - 150e9) * 0.22
    income.loc["Net Income"] = (rev * 0.15 - 150e9) * 0.78

    balance = pd.DataFrame(index=[
        "Cash And Cash Equivalents", "Total Debt", "Stockholders Equity",
        "Minority Interest", "Accounts Receivable", "Inventory",
        "Accounts Payable", "Net PPE", "Total Assets",
    ], columns=years, dtype=float)

    balance.loc["Cash And Cash Equivalents"] = rev * 0.08
    balance.loc["Total Debt"] = 2_000e9
    balance.loc["Stockholders Equity"] = rev * 0.50
    balance.loc["Minority Interest"] = 100e9
    balance.loc["Accounts Receivable"] = rev * 0.08
    balance.loc["Inventory"] = rev * 0.10
    balance.loc["Accounts Payable"] = rev * 0.08
    balance.loc["Net PPE"] = rev * 0.35
    balance.loc["Total Assets"] = rev * 0.90

    cashflow = pd.DataFrame(index=[
        "Operating Cash Flow", "Capital Expenditure",
        "Depreciation And Amortization",
    ], columns=years, dtype=float)

    cashflow.loc["Depreciation And Amortization"] = rev * 0.04
    cashflow.loc["Capital Expenditure"] = -rev * 0.06        # yfinance: negative
    cashflow.loc["Operating Cash Flow"] = rev * 0.13

    d = CompanyData("TEST.JK")
    d.name = "PT Uji Coba Tbk"
    d.sector = "Consumer Cyclical"
    d.industry = "Specialty Retail"
    d.income = income
    d.balance = balance
    d.cashflow = cashflow
    d.price = 1_000.0
    d.shares_outstanding = 10_000_000_000.0            # 10 billion shares
    d.market_cap = d.price * d.shares_outstanding      # IDR 10 tn
    d.trailing_pe = d.market_cap / float(income.loc["Net Income"].iloc[-1])
    d.fetch_ok = True
    return d


def main():
    print("=" * 70)
    print("DCF MATH VALIDATION - SYNTHETIC DATA")
    print("=" * 70)

    d = make_fake_company()
    hist, ok = build_history(d)
    assert ok, "Section 2 failed"
    snap = latest_snapshot(hist)

    # ---- Section 2 ----
    print("\n[Section 2] Line items")
    print(f"  Latest revenue    : {snap['revenue']/1e9:>12,.0f} bn (expect 13,310)")
    print(f"  Latest EBIT       : {snap['ebit']/1e9:>12,.0f} bn (expect 1,997)")
    print(f"  Latest EBITDA     : {snap['ebitda']/1e9:>12,.0f} bn (expect 2,529)")
    print(f"  Net debt          : {snap['net_debt']/1e9:>12,.0f} bn (expect 935)")
    assert abs(snap["revenue"] - 13_310e9) < 1e6
    assert abs(snap["ebit"] - 13_310e9 * 0.15) < 1e6
    assert abs(snap["ebitda"] - 13_310e9 * 0.19) < 1e6

    # ---- Section 3 ----
    scr = run_screening(d, hist)
    print(f"\n[Section 3] Screening : {scr['status']}")
    print(scr["detail"].to_string(index=False))
    assert scr["passed"], "The synthetic issuer should pass"

    # ---- Section 4 ----
    drv = build_drivers(hist, d.flags)
    print("\n[Section 4] Drivers")
    print(f"  Historical revenue growth (median) : {drv['rev_growth_hist']*100:>7.2f}%  (expect 10.00)")
    print(f"  Historical reinvestment rate       : {drv['rr_hist']*100:>7.2f}%  (informational only)")
    print(f"  Historical ROIC                    : {drv['roic_hist']*100:>7.2f}%  (informational only)")
    print(f"  g sustainable = RR x ROIC          : {drv['rr_hist']*drv['roic_hist']*100:>7.2f}%  (not applied)")
    print(f"  Revenue growth USED                : {drv['rev_growth']*100:>7.2f}%  (= historical median)")
    print(f"  EBIT margin base  : {drv['ebit_margin']*100:>7.2f}%  (expect 15.00)")
    print(f"  EBIT margin target: {drv['ebit_margin_target']*100:>7.2f}%")
    print(f"  Operating leverage: {drv['oplev_detected']} (correlation {drv['oplev_corr']:.2f})")
    print(f"  D&A ratio         : {drv['da_ratio']*100:>7.2f}%  (expect 4.00)")
    print(f"  Capex ratio       : {drv['capex_ratio']*100:>7.2f}%  (expect 6.00)")
    print(f"  NWC ratio         : {drv['nwc_ratio']*100:>7.2f}%  (expect 10.00)")
    print(f"  Tax rate          : {drv['tax_rate']*100:>7.2f}%  (expect 22.00)")
    # Growth used is the historical median, unadjusted by RR x ROIC (that
    # ratio is informational only now, see s04_drivers.py section 4.7).
    assert abs(drv["rev_growth_hist"] - 0.10) < 1e-6, "historical growth must be 10%"
    assert abs(drv["rev_growth"] - drv["rev_growth_hist"]) < 1e-9, \
        "growth used must equal the historical median, unconstrained"
    assert abs(drv["ebit_margin"] - 0.15) < 1e-6
    assert abs(drv["capex_ratio"] - 0.06) < 1e-6
    assert abs(drv["tax_rate"] - 0.22) < 1e-6

    # ---- Section 6 (beta forced to 1.0, no network) ----
    beta = {"beta_raw": 1.0, "beta_adj": 1.0, "r_squared": 0.5,
            "n_obs": 156, "source": "forced for testing"}
    w = compute_wacc(d, hist, drv, beta, d.flags)
    ke_exp = A["risk_free_rate"] + 1.0 * A["equity_risk_premium"] + A["size_premium"]
    print("\n[Section 6] WACC")
    print(f"  Ke   = {A['risk_free_rate']*100:.2f}% + 1.00 x {A['equity_risk_premium']*100:.2f}% "
          f"= {w['ke']*100:.2f}%  (expect {ke_exp*100:.2f})")
    print(f"  Kd   = 150 / avg debt 2000 = {w['kd_pretax']*100:.2f}%  (expect 7.50)")
    print(f"  Kd after tax = {w['kd_aftertax']*100:.2f}%  (expect 5.85)")
    print(f"  Weight E = {w['weight_equity']*100:.2f}%  (expect 83.33)")
    print(f"  WACC = {w['wacc']*100:.2f}%")
    assert abs(w["ke"] - ke_exp) < 1e-9
    assert abs(w["kd_pretax"] - 0.075) < 1e-9
    manual_wacc = (10/12) * ke_exp + (2/12) * 0.075 * 0.78
    print(f"  Manual WACC check = {manual_wacc*100:.4f}%")
    assert abs(w["wacc"] - manual_wacc) < 1e-9, "WACC doesn't match the manual calculation"

    # ---- Section 7 ----
    proj, fsum = project_fcff(hist, drv, snap, years=5, terminal_g=0.04)
    print("\n[Section 7] FCFF projection (IDR bn)")
    print((proj[["Growth", "Revenue", "EBIT", "NOPAT", "D&A", "Capex",
                 "Delta NWC", "FCFF"]] / 1e9).round(1).to_string())

    # Manually verify year 1
    g1 = drv["rev_growth"]      # already capped by RR x ROIC
    rev1 = 13_310e9 * (1 + g1)
    ebit1 = rev1 * drv["ebit_margin"]   # year 1 always uses the base margin
    nopat1 = ebit1 * 0.78
    da1 = rev1 * 0.04
    cx1 = rev1 * max(0.06, 0.04)   # capex floor >= D&A, not binding here
    nwc0 = 13_310e9 * 0.10
    nwc1 = rev1 * 0.10
    fcff1 = nopat1 + da1 - cx1 - (nwc1 - nwc0)
    print(f"\n  Manual year-1 FCFF check = {fcff1/1e9:,.2f} bn")
    print(f"  Model year-1 FCFF        = {proj.loc[1,'FCFF']/1e9:,.2f} bn")
    assert abs(proj.loc[1, "FCFF"] - fcff1) < 1e3

    # ---- Section 8 ----
    tv = terminal_value(fsum["fcff_final"], fsum["ebitda_final"], w["wacc"],
                        terminal_g=0.04, flags=d.flags)
    manual_tv = fsum["fcff_final"] * 1.04 / (w["wacc"] - 0.04)
    print("\n[Section 8] Terminal Value")
    print(f"  TV model  = {tv['tv_nominal']/1e9:,.0f} bn")
    print(f"  TV manual = {manual_tv/1e9:,.0f} bn")
    print(f"  Implied exit EV/EBITDA = {tv['implied_exit_multiple']:.2f}x")
    assert abs(tv["tv_nominal"] - manual_tv) < 1e3

    # ---- Section 9 ----
    v = discount_and_value(proj, tv, w["wacc"], snap, d, d.flags)
    print("\n[Section 9] Valuation")
    print(f"  PV explicit   = {v['pv_explicit']/1e9:,.0f} bn")
    print(f"  PV terminal   = {v['pv_terminal']/1e9:,.0f} bn")
    print(f"  EV            = {v['enterprise_value']/1e9:,.0f} bn")
    print(f"  Equity value  = {v['equity_value']/1e9:,.0f} bn")
    print(f"  Fair value/sh = IDR {v['fair_value_per_share']:,.2f}")
    print(f"  TV contribution = {v['tv_share_of_ev']*100:.1f}%")

    # Check manual mid-year discounting
    manual_pv = sum(
        float(proj.loc[t, "FCFF"]) / (1 + w["wacc"]) ** (t - 0.5)
        for t in range(1, 6)
    )
    print(f"  Manual PV explicit check = {manual_pv/1e9:,.0f} bn")
    assert abs(v["pv_explicit"] - manual_pv) < 1e3

    manual_eq = v["enterprise_value"] + snap["cash"] - snap["total_debt"] - snap["minority"]
    assert abs(v["equity_value"] - manual_eq) < 1e3
    assert abs(v["fair_value_per_share"] - manual_eq / 10e9) < 1e-6

    # ---- Section 10 ----
    rec = make_recommendation(v, d.flags)
    print("\n[Section 10] Recommendation")
    print(f"  Price IDR {v['market_price']:,.0f} vs fair value IDR "
          f"{v['fair_value_per_share']:,.0f}")
    print(f"  Upside {rec['upside']*100:+.1f}% -> {rec['rating']} ({rec['label']})")

    # ---- Section 11 ----
    sens = sensitivity_grid(proj, w["wacc"], 0.04, snap, d, d.flags)
    print("\n[Section 11] Sensitivity of fair value per share (IDR)")
    print(sens["fair_value"].to_string())
    st = sens["stats"]
    print(f"  Valid cells {st['n_valid']}/{st['n_cells']}, "
          f"range {st['min']:,.0f} - {st['max']:,.0f}")
    # Value must fall as WACC rises, and rise as g rises
    fv = sens["fair_value"].astype(float)
    assert fv.iloc[0, 0] > fv.iloc[-1, 0], "Fair value must fall as WACC rises"
    assert fv.iloc[0, -1] > fv.iloc[0, 0], "Fair value must rise as g rises"

    # ---- Section 12 ----
    sc, _ = run_scenarios(hist, drv, snap, d, w["wacc"], years=5, g_base=0.04)
    print("\n[Section 12] Scenarios")
    print(sc.to_string())

    # ---- Flags ----
    print("\n[Flag data]")
    print(d.flags.render())

    print("\n" + "=" * 70)
    print("ALL ASSERTIONS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
