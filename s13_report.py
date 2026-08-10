"""
=============================================================================
SECTION 13 - REPORT ASSEMBLY
=============================================================================
PURPOSE : Assemble the output of every preceding section into one report
          that reads top to bottom, with data flags placed where the reader
          cannot skip past them.

FORMULA : None. This is the presentation layer.

OUTPUT  : Complete report string, ending with the disclaimer.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import DISCLAIMER, ASSUMPTIONS
from s04_drivers import drivers_table
from s06_wacc import wacc_table
from s07_forecast import projection_table
from s09_valuation import bridge_table
from s12_scenario import scenario_table

LINE = "=" * 78
THIN = "-" * 78


def _h(title):
    return f"\n{LINE}\n{title}\n{LINE}"


def render_report(result):
    """
    result is the dict returned by main.analyze_ticker().
    """
    p = []
    d = result["data"]

    # ---------------- header ----------------
    p.append(_h(f"DCF VALUATION - {d.ticker} - {d.name}"))
    p.append(f"Sector          : {d.sector or 'n/a'} / {d.industry or 'n/a'}")
    p.append(f"Market price    : IDR {d.price:,.0f}" if np.isfinite(d.price) else "Market price    : n/a")
    p.append(f"Market cap      : IDR {d.market_cap/1e12:,.2f} tn" if np.isfinite(d.market_cap) else "Market cap      : n/a")
    p.append(f"Trailing P/E    : {d.trailing_pe:.2f}x" if np.isfinite(d.trailing_pe) else "Trailing P/E    : n/a")
    p.append(f"Reporting ccy   : {d.original_currency}"
             + (f" (converted to IDR @ {d.fx_rate:,.0f})" if d.fx_rate != 1.0 else ""))

    # ---------------- screening ----------------
    scr = result["screening"]
    p.append(_h("SECTION 3 - MODEL ELIGIBILITY SCREENING"))
    p.append(scr["detail"].to_string(index=False))
    p.append("")
    p.append(f"STATUS: {scr['status']}")

    if not scr["passed"]:
        p.append(_h("DATA FLAGS"))
        p.append(d.flags.render())
        p.append(_h("DISCLAIMER"))
        p.append(DISCLAIMER)
        return "\n".join(p)

    # ---------------- data flags (placed ahead of the results) ----------------
    p.append(_h("DATA QUALITY WARNINGS - READ BEFORE USING THE FIGURES BELOW"))
    p.append(d.flags.render())

    # ---------------- drivers ----------------
    p.append(_h("SECTION 4 - HISTORICAL DRIVERS (MOVING AVERAGE)"))
    p.append(f"Basis: {result['drivers']['n_periods']} annual periods")
    p.append(drivers_table(result["drivers"]).to_string(index=False))

    # ---------------- wacc ----------------
    p.append(_h("SECTION 5-6 - BETA AND COST OF CAPITAL"))
    p.append(f"Beta method: {result['beta']['source']}, {result['beta']['n_obs']} observations")
    p.append(THIN)
    p.append(wacc_table(result["wacc"]).to_string(index=False))
    p.append(THIN)
    p.append(f"Cost of Debt method: {result['wacc']['kd_method']}")

    # ---------------- projection ----------------
    p.append(_h("SECTION 7 - FCFF PROJECTION (IDR bn)"))
    p.append(projection_table(result["projection"]).to_string())
    fs = result["forecast_summary"]
    p.append(THIN)
    p.append(f"Avg reinvestment rate       : {fs['avg_reinvest_rate']*100:,.1f}%")
    p.append(f"Avg ROIC                    : {fs['avg_roic']*100:,.1f}%")
    p.append(f"Implied growth (RR x ROIC)  : {fs['avg_implied_growth']*100:,.1f}%")
    p.append(f"Assumed revenue growth Y1   : {fs['g1']*100:,.1f}%")
    gap = fs["avg_implied_growth"] - fs["g1"]
    if np.isfinite(gap) and abs(gap) > 0.05:
        p.append(f"NOTE: {gap*100:+.1f}pp gap between implied growth and the assumed "
                 f"growth rate. The model is not fully internally consistent at this setting.")

    # ---------------- terminal value ----------------
    tv = result["terminal"]
    p.append(_h("SECTION 8 - TERMINAL VALUE"))
    p.append(f"Terminal growth             : {tv['terminal_growth']*100:.2f}%")
    p.append(f"WACC                        : {tv['wacc']*100:.2f}%")
    p.append(f"Spread (WACC - g)           : {(tv['wacc']-tv['terminal_growth'])*100:.2f}%")
    p.append(f"Final year FCFF             : IDR {tv['fcff_final']/1e9:,.0f} bn")
    p.append(f"Nominal terminal value      : IDR {tv['tv_nominal']/1e9:,.0f} bn")
    p.append(f"Implied exit EV/EBITDA      : {tv['implied_exit_multiple']:.1f}x"
             if np.isfinite(tv["implied_exit_multiple"]) else "Implied exit EV/EBITDA      : n/a")

    # ---------------- valuation ----------------
    v = result["valuation"]
    p.append(_h("SECTION 9 - ENTERPRISE VALUE TO EQUITY VALUE (IDR bn)"))
    p.append(bridge_table(v).to_string(index=False))
    p.append(THIN)
    p.append(f"Terminal value share of EV      : {v['tv_share_of_ev']*100:.1f}%"
             if np.isfinite(v["tv_share_of_ev"]) else "Terminal value share of EV      : n/a")
    p.append(f"Implied EV/EBITDA, current      : {v['implied_ev_ebitda_current']:.1f}x"
             if np.isfinite(v["implied_ev_ebitda_current"]) else "Implied EV/EBITDA, current      : n/a")
    p.append(f"Shares outstanding              : {v['shares_outstanding']:,.0f}"
             if np.isfinite(v["shares_outstanding"]) else "Shares outstanding              : n/a")

    # ---------------- recommendation ----------------
    rec = result["recommendation"]
    A = ASSUMPTIONS
    p.append(_h("SECTION 10 - DECISION"))
    p.append(f"Market price       : IDR {v['market_price']:,.0f}")
    p.append(f"Fair value (base)  : IDR {v['fair_value_per_share']:,.0f}"
             if np.isfinite(v["fair_value_per_share"]) else "Fair value (base)  : n/a")
    p.append(f"Upside / downside  : {rec['upside']*100:+.1f}%"
             if np.isfinite(rec["upside"]) else "Upside / downside  : n/a")
    p.append(f"Status             : {rec['label']}")
    p.append(f"RECOMMENDATION     : {rec['rating']}")
    p.append(f"Thresholds: BUY if upside > {A['buy_threshold']*100:.0f}%, "
             f"SELL if < {A['sell_threshold']*100:.0f}%, HOLD in between.")

    # ---------------- sensitivity ----------------
    sens = result["sensitivity"]
    p.append(_h("SECTION 11 - SENSITIVITY: FAIR VALUE PER SHARE (IDR)"))
    p.append("Rows = WACC, Columns = Terminal growth")
    p.append(sens["fair_value"].to_string())
    p.append("")
    p.append("Upside against market price (%)")
    p.append(sens["upside"].to_string())
    st = sens["stats"]
    p.append(THIN)
    p.append(f"Fair value range: IDR {st['min']:,.0f} to IDR {st['max']:,.0f}, "
             f"median IDR {st['median']:,.0f} ({st['n_valid']}/{st['n_cells']} valid cells)")

    # ---------------- scenarios ----------------
    p.append(_h("SECTION 12 - SCENARIOS (deviation from historical standard deviation)"))
    p.append(scenario_table(result["scenarios"]).to_string())

    # ---------------- limitations ----------------
    p.append(_h("MODEL LIMITATIONS AT THIS STAGE"))
    p.append("- Corporate actions and post balance sheet events are not accounted for")
    p.append("- Non-operating assets (associates, investment property) are not added to equity value")
    p.append("- Shares outstanding uses the basic figure, not fully diluted")
    p.append("- USD to IDR conversion uses the spot rate across the entire historical period")
    p.append("- EBIT margin only expands where historical operating leverage is detected")
    p.append("- No consensus estimates are used; every projection is derived from historical data")

    p.append(_h("DISCLAIMER"))
    p.append(DISCLAIMER)
    return "\n".join(p)
