"""
=============================================================================
STREAMLIT APPLICATION
=============================================================================
PURPOSE : Web front end for the DCF engine. The report follows exactly the
          same order as the command line output, so anything verified in
          Colab appears here in the same sequence.

CACHING : Network work (statement download and beta regression) is cached per
          ticker. Moving a slider only re-runs the arithmetic, so the report
          updates without hitting yfinance again.

RUN     : streamlit run app.py
=============================================================================
"""

import copy
import warnings

import numpy as np
import pandas as pd
import streamlit as st

warnings.filterwarnings("ignore")

from config import ASSUMPTIONS, SCREENING, DISCLAIMER
from theme import (COLORS, RATING_COLOR,
                   inject_css, pill, metric_strip, callout, styled_table, flag_table)
from charts import (chart_projection, chart_waterfall,
                    chart_sensitivity, chart_scenarios)
from main import fetch_bundle, analyze_ticker
from s04_drivers import drivers_table
from s06_wacc import wacc_table
from s07_forecast import projection_table
from s09_valuation import bridge_table
from s12_scenario import scenario_table

AUTHOR = "Abida Massi Armand"

st.set_page_config(page_title="DCF Valuation Engine",
                   page_icon="chart_with_upwards_trend",
                   layout="wide",
                   initial_sidebar_state="expanded")
inject_css()


# =====================================================================
# CACHED DATA LAYER
# =====================================================================
@st.cache_data(show_spinner=False, ttl=3600)
def load_bundle(ticker):
    """Download statements, prices, and run the beta regression. Cached."""
    return fetch_bundle(ticker)


def run_analysis(ticker, rf, erp, years, g_term):
    """Fetch from cache, then recompute the valuation with current inputs."""
    bundle = copy.deepcopy(load_bundle(ticker))
    return analyze_ticker(ticker, rf=rf, erp=erp, years=years,
                          terminal_g=g_term, bundle=bundle)



# =====================================================================
# VERSION-SAFE RENDER HELPERS
# =====================================================================
# Streamlit is deprecating use_container_width in favour of width="stretch".
# These wrappers try the new argument first and fall back to the old one, so
# the app runs on both current and older Streamlit builds on Community Cloud.
def show_chart(fig):
    cfg = {"displayModeBar": False}
    try:
        return st.plotly_chart(fig, width="stretch", config=cfg)
    except TypeError:
        return st.plotly_chart(fig, use_container_width=True, config=cfg)


# =====================================================================
# FORMATTERS
# =====================================================================
def f_idr(v, dp=0):
    return f"IDR {v:,.{dp}f}" if v is not None and np.isfinite(v) else "n/a"


def f_tn(v):
    return f"IDR {v/1e12:,.2f} tn" if v is not None and np.isfinite(v) else "n/a"


def f_bn(v):
    return f"IDR {v/1e9:,.0f} bn" if v is not None and np.isfinite(v) else "n/a"


def f_pct(v, dp=2, sign=False):
    if v is None or not np.isfinite(v):
        return "n/a"
    return f"{v*100:+.{dp}f}%" if sign else f"{v*100:.{dp}f}%"


def f_x(v, dp=2):
    return f"{v:.{dp}f}x" if v is not None and np.isfinite(v) else "n/a"


# =====================================================================
# SIDEBAR
# =====================================================================
with st.sidebar:
    st.markdown(
        f'<div style="padding:.2rem 0 1rem 0;">'
        f'<div style="font-size:1.05rem;font-weight:600;color:#fff;letter-spacing:-.01em;">'
        f'DCF Valuation Engine</div>'
        f'<div style="font-size:.7rem;color:{COLORS["ice"]};letter-spacing:.1em;'
        f'text-transform:uppercase;margin-top:.15rem;">Intrinsic Valuation</div>'
        f'</div>', unsafe_allow_html=True)

    st.markdown("---")

    ticker_in = st.text_input("Ticker", value="SIDO", max_chars=4,
                              help="Enter the IDX code only. The .JK suffix is added "
                                   "automatically, so SIDO becomes SIDO.JK.")

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:.68rem;font-weight:600;letter-spacing:.14em;'
        f'text-transform:uppercase;color:{COLORS["ice"]};margin-bottom:.5rem;">'
        f'Assumptions</div>', unsafe_allow_html=True)

    rf_in = st.slider("Risk-free rate", 5.0, 9.0,
                      float(ASSUMPTIONS["risk_free_rate"] * 100), 0.05,
                      format="%.2f%%",
                      help="Proxy for the 10-year INDOGB yield. Entered manually, "
                           "not fetched.") / 100

    erp_in = st.slider("Equity risk premium", 3.0, 10.0,
                       float(ASSUMPTIONS["equity_risk_premium"] * 100), 0.10,
                       format="%.2f%%",
                       help="Damodaran places Indonesia at roughly 6.5% to 8%. "
                            "Lower values raise fair value through the discount "
                            "rate, not through cash flow.") / 100

    g_in = st.slider("Terminal growth", 0.0, 6.0,
                     float(ASSUMPTIONS["terminal_growth"] * 100), 0.10,
                     format="%.2f%%",
                     help="Capped at the year-one growth rate. WACC must exceed "
                          "this by at least 400bps.") / 100

    yrs_in = st.slider("Forecast horizon", 5, 10,
                       int(ASSUMPTIONS["forecast_years"]), 1,
                       format="%d years")

    st.markdown("---")
    try:
        run = st.button("Run analysis", width="stretch")
    except TypeError:
        run = st.button("Run analysis", use_container_width=True)

    st.markdown(
        f'<div style="font-size:.66rem;color:{COLORS["ice"]};line-height:1.55;'
        f'margin-top:1rem;opacity:.75;">Beta, growth, margin, capex, working '
        f'capital, and tax are derived from the company\'s own filings. They are '
        f'not adjustable here by design.</div>', unsafe_allow_html=True)


# =====================================================================
# STATE
# =====================================================================
if "result" not in st.session_state:
    st.session_state.result = None
    st.session_state.ticker = None

if run and ticker_in.strip():
    with st.spinner("Downloading filings and running the valuation"):
        st.session_state.result = run_analysis(
            ticker_in.strip(), rf_in, erp_in, yrs_in, g_in)
        st.session_state.ticker = ticker_in.strip().upper()
elif st.session_state.result is not None and ticker_in.strip().upper() == st.session_state.ticker:
    # Slider moved on the same ticker: recompute from cached filings.
    st.session_state.result = run_analysis(
        ticker_in.strip(), rf_in, erp_in, yrs_in, g_in)

r = st.session_state.result


# =====================================================================
# DISCLAIMER (always rendered last)
# =====================================================================
def render_disclaimer():
    st.markdown(
        f'<div class="disclaimer">'
        f'<div class="sig">Disclaimer On &nbsp;|&nbsp; {AUTHOR}</div>'
        f'{DISCLAIMER}</div>', unsafe_allow_html=True)


# =====================================================================
# EMPTY STATE
# =====================================================================
if r is None:
    st.markdown('<div class="masthead"><p class="eyebrow">Equity research tooling</p>'
                '<h1>DCF Valuation Engine</h1>'
                '<div class="sub">Free cash flow to firm, discounted at WACC. '
                'Indonesian listed non-financials.</div></div>',
                unsafe_allow_html=True)
    st.markdown('<div class="empty"><h3>No company loaded</h3>'
                '<p>Enter an IDX ticker in the sidebar and select Run analysis.</p>'
                '</div>', unsafe_allow_html=True)
    render_disclaimer()
    st.stop()


d = r["data"]
scr = r["screening"]

# =====================================================================
# MASTHEAD (straight to the company, no report eyebrow)
# =====================================================================
st.markdown(
    f'<div class="masthead"><h1>{d.ticker} &nbsp;&middot;&nbsp; {d.name or "Unnamed"}</h1>'
    f'<div class="sub">{d.sector or "Sector n/a"} &nbsp;|&nbsp; '
    f'{d.industry or "Industry n/a"}</div></div>',
    unsafe_allow_html=True)


# =====================================================================
# SECTION 10 - VERDICT (the headline highlight, shown before anything else)
# =====================================================================
pill("01", "Valuation verdict")

if scr["passed"] and r.get("ok"):
    val = r["valuation"]
    rec = r["recommendation"]
    sc_df = r["scenarios"]

    fv = val["fair_value_per_share"]
    px = val["market_price"]
    rating = rec["rating"]
    rcolor = RATING_COLOR.get(rating, COLORS["ink_muted"])

    sc_vals = [float(sc_df.loc[s, "Fair value/shr"]) for s in ["BEAR", "BULL"]
               if s in sc_df.index and np.isfinite(sc_df.loc[s, "Fair value/shr"])]
    lo = min(sc_vals) if sc_vals else fv
    hi = max(sc_vals) if sc_vals else fv
    span = max(hi - lo, 1e-9)
    pos = float(np.clip((px - lo) / span, 0, 1)) * 100
    fv_pos = float(np.clip((fv - lo) / span, 0, 1)) * 100

    # Fair value below market price is downside, not upside. The sign of
    # rec['upside'] already carries this, but the row label was hard-coded
    # to "Upside" regardless, which read backwards whenever the stock
    # screened as overvalued.
    ud_label = "Upside" if rec["upside"] >= 0 else "Downside"

    st.markdown(f"""
<div class="verdict">
  <div class="row">
    <div class="vcell">
      <div class="lab">Recommendation</div>
      <div class="rating" style="color:{rcolor}">{rating}</div>
    </div>
    <div class="vcell">
      <div class="lab">Fair value per share</div>
      <div class="big">{f_idr(fv)}</div>
      <div class="small">Base case</div>
    </div>
    <div class="vcell">
      <div class="lab">Market price</div>
      <div class="big">{f_idr(px)}</div>
      <div class="small">{rec['label']}</div>
    </div>
    <div class="vcell">
      <div class="lab">{ud_label}</div>
      <div class="big" style="color:{rcolor}">{f_pct(rec['upside'], 1, sign=True)}</div>
      <div class="small">Buy above +{ASSUMPTIONS['buy_threshold']*100:.0f}%,
      sell below {ASSUMPTIONS['sell_threshold']*100:.0f}%</div>
    </div>
  </div>
  <div class="scale">
    <div class="lab">Where the market price sits inside the bear to bull range</div>
    <div class="track">
      <div class="fill" style="left:0%;width:{fv_pos:.1f}%"></div>
      <div class="mark" style="left:{pos:.1f}%"></div>
    </div>
    <div class="ends"><span>Bear {f_idr(lo)}</span><span>Bull {f_idr(hi)}</span></div>
  </div>
</div>
""", unsafe_allow_html=True)
else:
    reason = scr.get("status", "This issuer does not meet the model's eligibility criteria.")
    if reason.startswith("CANNOT PROCEED - "):
        reason = reason[len("CANNOT PROCEED - "):]
    st.markdown(f"""
<div class="verdict">
  <div class="row">
    <div class="vcell">
      <div class="lab">Recommendation</div>
      <div class="rating" style="color:{COLORS['ink_muted']}">None</div>
    </div>
    <div class="vcell vcell-wide">
      <div class="lab">Reason</div>
      <div class="reason">{reason}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# =====================================================================
# MARKET SNAPSHOT
# =====================================================================
metric_strip([
    ("Market price", f_idr(d.price)),
    ("Market cap", f_tn(d.market_cap)),
    ("Trailing P/E", f_x(d.trailing_pe)),
    ("Reporting currency", d.original_currency),
    ("FX applied", f"{d.fx_rate:,.0f}" if d.fx_rate != 1.0 else "None"),
])

if d.fx_rate != 1.0:
    callout(f"<b>Currency conversion applied.</b> Filings are reported in "
            f"{d.original_currency} while the share price is quoted in IDR. Every "
            f"income statement, balance sheet, and cash flow line has been "
            f"multiplied by {d.fx_rate:,.0f}. A single spot rate is applied across "
            f"all historical periods, which is a simplification rather than the "
            f"average rate for each year.")


# =====================================================================
# SECTION 3 - SCREENING
# =====================================================================
pill("02", "Model eligibility screening",
     "These gates test whether FCFF and WACC can be applied to this company at "
     "all, not whether the stock is attractive.")

if isinstance(scr.get("detail"), pd.DataFrame) and not scr["detail"].empty:
    det = scr["detail"].drop(columns=["No"], errors="ignore")
    styled_table(det, hide_index=True, status_col="Status")

if scr["passed"]:
    st.markdown(f'<div class="callout"><b class="gate-ok">ELIGIBLE.</b> '
                f'All gates passed. The valuation below is calculated.</div>',
                unsafe_allow_html=True)
else:
    status_text = scr["status"]
    if status_text.startswith("CANNOT PROCEED - "):
        status_text = status_text[len("CANNOT PROCEED - "):]
    st.markdown(f'<div class="callout"><b class="gate-no">CANNOT PROCEED.</b> '
                f'{status_text}</div>', unsafe_allow_html=True)
    render_disclaimer()
    st.stop()


# =====================================================================
# DATA QUALITY
# =====================================================================
drv = r["drivers"]
w = r["wacc"]
proj = r["projection"]
fsum = r["forecast_summary"]
tv = r["terminal"]
sens = r["sensitivity"]

pill("03", "Data quality warnings",
     "Read these before relying on any figure below. They record where a value "
     "was missing, derived, proxied, or clipped.")

if d.flags.has_issue:
    flag_table(d.flags)
else:
    callout("No data quality issues detected.")


# =====================================================================
# SECTION 4 - DRIVERS
# =====================================================================
pill("04", "Historical drivers and model decisions",
     "Every driver is the median of the company's own reported history. Nothing "
     "here is entered by hand.")

c1, c2 = st.columns([1.05, 1])
with c1:
    styled_table(drivers_table(drv), hide_index=True)
with c2:
    g_hist = drv.get("rev_growth_hist", np.nan)
    if np.isfinite(g_hist) and drv["rev_growth"] < g_hist - 1e-9:
        callout(f"<b>Growth constrained by reinvestment.</b> Median historical "
                f"growth of {f_pct(g_hist)} exceeds what reinvestment can fund. "
                f"Reinvestment rate {f_pct(drv.get('rr_hist', np.nan), 1)} multiplied "
                f"by ROIC {f_pct(drv.get('roic_hist', np.nan), 1)} gives "
                f"{f_pct(drv['rev_growth'])}, which is the rate applied.")
    else:
        callout(f"<b>Growth not constrained.</b> Median historical growth of "
                f"{f_pct(g_hist)} is within what reinvestment can fund.")

    if drv.get("oplev_detected"):
        callout(f"<b>Margin expansion active.</b> Revenue and EBIT margin correlate "
                f"at {drv.get('oplev_corr', float('nan')):.2f}, which indicates "
                f"operating leverage. Margin fades linearly from "
                f"{f_pct(drv['ebit_margin'])} to the historical peak of "
                f"{f_pct(drv['ebit_margin_target'])} by the final year. The "
                f"correlation rests on only a handful of annual observations.")
    else:
        callout(f"<b>Margin held flat.</b> Revenue and EBIT margin correlate at "
                f"{drv.get('oplev_corr', float('nan')):.2f}, below the 0.50 "
                f"threshold, so there is no evidence of operating leverage. Margin "
                f"stays at {f_pct(drv['ebit_margin'])} throughout.")


# =====================================================================
# SECTIONS 5 AND 6 - COST OF CAPITAL
# =====================================================================
pill("05", "Beta and cost of capital")

c1, c2 = st.columns([1, 1])
with c1:
    styled_table(wacc_table(w), hide_index=True)
with c2:
    metric_strip([("WACC", f_pct(w["wacc"])), ("Cost of equity", f_pct(w["ke"]))])
    st.write("")
    metric_strip([("Cost of debt, post-tax", f_pct(w["kd_aftertax"])),
                  ("Equity weight", f_pct(w["weight_equity"], 1))])
    st.write("")
    callout(f"<b>Beta method.</b> {r['beta']['source']}, {r['beta']['n_obs']} "
            f"observations. Raw beta {r['beta']['beta_raw']:.3f}, R-squared "
            f"{r['beta']['r_squared']:.3f}, applied beta {w['beta_adj']:.3f}.")
    callout(f"<b>Cost of debt method.</b> {w['kd_method']}")


# =====================================================================
# SECTION 7 - PROJECTION
# =====================================================================
pill("06", "Free cash flow to firm projection",
     f"{fsum['years']} year explicit forecast. FCFF equals NOPAT plus depreciation "
     f"and amortisation, less capital expenditure and the change in working capital.")

show_chart(chart_projection(proj))
styled_table(projection_table(proj), hide_index=False)

gap = fsum["avg_implied_growth"] - fsum["g1"]
with st.container(key="proj-bubbles"):
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_strip([("Avg reinvestment rate", f_pct(fsum["avg_reinvest_rate"], 1))])
    with c2:
        metric_strip([("Avg ROIC", f_pct(fsum["avg_roic"], 1))])
    with c3:
        metric_strip([("Implied growth", f_pct(fsum["avg_implied_growth"], 1))])

if np.isfinite(gap) and abs(gap) > 0.05:
    callout(f"<b>Internal consistency check.</b> Implied growth from reinvestment "
            f"differs from the assumed growth rate by "
            f"{gap*100:+.1f} percentage points. The model is not fully consistent "
            f"with itself at this setting.")


# =====================================================================
# SECTION 8 - TERMINAL VALUE
# =====================================================================
pill("07", "Terminal value",
     "Gordon growth on the final year of free cash flow, cross-checked against the "
     "implied exit multiple.")

metric_strip([
    ("Terminal growth", f_pct(tv["terminal_growth"])),
    ("WACC", f_pct(tv["wacc"])),
    ("Spread", f_pct(tv["wacc"] - tv["terminal_growth"])),
    ("Final year FCFF", f_bn(tv["fcff_final"])),
    ("Terminal value", f_bn(tv["tv_nominal"])),
    ("Implied exit EV/EBITDA", f_x(tv["implied_exit_multiple"], 1)),
])


# =====================================================================
# SECTION 9 - BRIDGE
# =====================================================================
pill("08", "Enterprise value to equity value")

c1, c2 = st.columns([1.25, 1])
with c1:
    show_chart(chart_waterfall(val))
with c2:
    bt = bridge_table(val).copy()
    bt["IDR bn"] = bt["IDR bn"].map(lambda x: f"{x:,.0f}")
    styled_table(bt, hide_index=True)
    metric_strip([("Terminal value share of EV", f_pct(val["tv_share_of_ev"], 1))])
    st.write("")
    metric_strip([("Shares outstanding",
                   f"{val['shares_outstanding']:,.0f}"
                   if np.isfinite(val["shares_outstanding"]) else "n/a")])

if np.isfinite(val["tv_share_of_ev"]) and val["tv_share_of_ev"] > 0.80:
    callout(f"<b>Terminal value dependency.</b> "
            f"{f_pct(val['tv_share_of_ev'], 1)} of enterprise value comes from the "
            f"terminal period. The valuation rests largely on a perpetuity "
            f"assumption rather than on forecasts that can be verified.")


# =====================================================================
# SECTION 11 - SENSITIVITY
# =====================================================================
pill("09", "Sensitivity",
     "Cash flows are held constant. Only the discount rate and terminal growth move, "
     "which isolates the effect of the cost of capital.")

show_chart(chart_sensitivity(sens, px))

stt = sens["stats"]
metric_strip([
    ("Lowest fair value", f_idr(stt["min"])),
    ("Median", f_idr(stt["median"])),
    ("Highest fair value", f_idr(stt["max"])),
    ("Valid cells", f"{stt['n_valid']} of {stt['n_cells']}"),
])


# =====================================================================
# SECTION 12 - SCENARIOS
# =====================================================================
pill("10", "Scenarios",
     "Bull and bear shift revenue growth and EBIT margin by one standard deviation "
     "of the company's own history, with terminal growth moved 50bps either way.")

c1, c2 = st.columns([1.15, 1])
with c1:
    show_chart(chart_scenarios(sc_df, px))
with c2:
    styled_table(scenario_table(sc_df), hide_index=False)


# =====================================================================
# LIMITATIONS
# =====================================================================
pill("11", "Model limitations")
st.markdown("""
<div class="limits"><ul>
<li>Corporate actions and post balance sheet events are not reflected. The most
recent reported period is used as is.</li>
<li>Non-operating assets such as investments in associates and investment property
are excluded from equity value, so holding structures are understated.</li>
<li>Share count is the basic figure. Dilution from employee options is not modelled
because the data is unavailable.</li>
<li>Where filings are reported in USD, a single spot rate is applied across all
historical periods rather than the average rate for each year.</li>
<li>EBIT margin expands only where the historical record shows operating leverage.
Otherwise it is held flat.</li>
<li>No consensus estimates are used. Every forecast is derived from reported
history and the assumptions set in the sidebar.</li>
<li>Data comes from yfinance and has not been reconciled against audited
financial statements or IDX filings.</li>
</ul></div>
""", unsafe_allow_html=True)

render_disclaimer()
