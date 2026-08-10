"""
=============================================================================
SECTION 4 - HISTORICAL DRIVERS (MOVING AVERAGE)
=============================================================================
PURPOSE : Derive projection assumptions from the issuer's own historical
          data, not from guesswork. Every driver uses a simple moving
          average over all available periods. This is a deliberate
          conservative choice: an issuer that happened to grow 60% over the
          last two years should not be extrapolated forever.

FORMULA : Revenue growth   g_hist = mean(pct_change(Revenue))
          EBIT margin      m_hist = mean(EBIT_t / Revenue_t)
          D&A ratio        d_hist = mean(D&A_t / Revenue_t)
          Capex ratio      c_hist = mean(Capex_t / Revenue_t)
          NWC ratio        w_hist = mean(NWC_t / Revenue_t)
          Effective tax    t_hist = mean(Tax Provision_t / Pretax Income_t)

          Every result is clipped to a reasonable range in config.py. Each
          clip is logged as a flag so it's visible that the value in use
          isn't the raw result.

          Each driver's standard deviation is also computed here, since it
          will be used by Section 12 to build the Bull and Bear scenarios.

OUTPUT  : a driver dict containing base values and their standard deviations.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from utils import nanmean, nanstd, clip_flag


def build_drivers(hist, flags):
    """
    Compute base drivers and their standard deviations from the entire
    historical period.
    """
    A = ASSUMPTIONS

    def series(key):
        return pd.to_numeric(hist.loc[key], errors="coerce").dropna().tolist()

    # ---------------- 4.1 Revenue growth ----------------
    # MEDIAN, not mean. The 4-year window (2022-2025) still absorbs the
    # post-pandemic rebound, and one extreme year pulls the mean up sharply.
    # MAPA came out at 25.76% with the mean, far above the FY25 actual (+12.2%).
    g_list = series("rev_growth")
    g_raw = float(np.median(g_list)) if len(g_list) else np.nan
    g_sd = nanstd(g_list)
    if not np.isfinite(g_raw):
        g_raw = 0.0
        flags.warn("Revenue growth", "Could not be computed, used 0% instead.")
    g_hist = clip_flag(g_raw, A["rev_growth_floor"], A["rev_growth_cap"],
                       "Revenue growth (median)", flags)
    if not np.isfinite(g_sd):
        g_sd = 0.03
        flags.warn("Revenue growth SD", "Could not be computed, used 3% instead.")
    elif g_sd < A["min_growth_sd"]:
        flags.warn("Revenue growth SD",
                   f"Historical volatility is only {g_sd*100:.2f}%, too low to "
                   f"form a meaningful scenario spread. Floor of "
                   f"{A['min_growth_sd']*100:.1f}% used instead.")
        g_sd = A["min_growth_sd"]

    # ---------------- 4.2 EBIT margin ----------------
    m_list = series("ebit_margin")
    m_base = float(np.median(m_list)) if len(m_list) else np.nan
    m_sd = nanstd(m_list)
    if not np.isfinite(m_base) or m_base <= 0:
        flags.warn("EBIT margin", "Historical average is not positive. "
                                  "The model will not produce a meaningful fair value.")
        m_base = max(m_base if np.isfinite(m_base) else 0.01, 0.01)
    if not np.isfinite(m_sd):
        m_sd = 0.02
        flags.warn("EBIT margin SD", "Could not be computed, used 200bps instead.")
    elif m_sd < A["min_margin_sd"]:
        flags.warn("EBIT margin SD",
                   f"Historical volatility is only {m_sd*100:.2f}%, too low to "
                   f"form a meaningful scenario spread. Floor of "
                   f"{A['min_margin_sd']*100:.1f}% used instead.")
        m_sd = A["min_margin_sd"]

    # ---------------- 4.3 Depreciation and amortisation ----------------
    d_list = series("da_ratio")
    d_base = float(np.median(d_list)) if len(d_list) else np.nan
    if not np.isfinite(d_base) or d_base < 0:
        d_base = 0.0
        flags.warn("D&A ratio", "Not available, used 0% of revenue instead. "
                                "FCFF will be understated.")

    # ---------------- 4.4 Capex ----------------
    c_list = series("capex_ratio")
    c_raw = float(np.median(c_list)) if len(c_list) else np.nan
    if not np.isfinite(c_raw) or c_raw < 0:
        c_raw = d_base
        flags.warn("Capex ratio", "Not available. Proxied as equal to the D&A ratio "
                                  "(maintenance capex assumption).")
    c_base = clip_flag(c_raw, 0.0, A["capex_ratio_cap"], "Capex ratio (MA)", flags)

    # ---------------- 4.5 Working capital ----------------
    w_list = series("nwc_ratio")
    w_raw = float(np.median(w_list)) if len(w_list) else np.nan
    if not np.isfinite(w_raw):
        w_raw = 0.0
        flags.warn("NWC ratio", "Not available, used 0% instead. "
                                "Delta working capital will not be modelled.")
    w_base = clip_flag(w_raw, A["nwc_ratio_floor"], A["nwc_ratio_cap"],
                       "NWC ratio (MA)", flags)

    # ---------------- 4.6 Effective tax rate ----------------
    t_list = [t for t in series("eff_tax") if 0 < t < 1]
    t_raw = float(np.median(t_list)) if len(t_list) else np.nan
    if not np.isfinite(t_raw):
        t_base = A["tax_fallback"]
        flags.warn("Effective tax rate",
                   f"Could not be computed from Tax Provision / Pretax Income. "
                   f"Used the statutory rate of {t_base*100:.0f}% instead.")
    else:
        t_base = clip_flag(t_raw, A["tax_floor"], A["tax_cap"],
                           "Effective tax rate", flags)

    # -------------------------------------------------------------------
    # 4.7 FUNDAMENTAL REINVESTMENT-BASED GROWTH CAP
    # -------------------------------------------------------------------
    # Fundamental growth identity:
    #     g_sustainable = Reinvestment Rate x ROIC
    #
    # A company cannot grow beyond what its reinvestment can fund. Before
    # this fix, the model forced MAPA to grow at 25% while only setting
    # aside 20.6% of NOPAT for reinvestment. To grow 25% with a 30.5% ROIC,
    # the reinvestment rate would need to be 82%. The gap fell into FCFF as
    # cash that never existed, and that was the main source of the 137% upside.
    #
    # Historical components:
    #     NOPAT_t        = EBIT_t x (1 - effective tax rate)
    #     Reinvestment_t = Capex_t - D&A_t + delta NWC_t
    #     RR_t           = Reinvestment_t / NOPAT_t
    #     ROIC_t         = NOPAT_t / Invested Capital_t-1
    #
    # g used = min(median historical g, sustainable g)
    ebit_h = pd.to_numeric(hist.loc["ebit"], errors="coerce")
    capex_h = pd.to_numeric(hist.loc["capex"], errors="coerce")
    da_h = pd.to_numeric(hist.loc["dep_amort"], errors="coerce")
    nwc_h = pd.to_numeric(hist.loc["nwc"], errors="coerce")
    ic_h = pd.to_numeric(hist.loc["invested_capital"], errors="coerce")

    nopat_h = ebit_h * (1 - t_base)
    rr_vals, roic_vals = [], []
    for i in range(1, len(ebit_h)):
        nop = nopat_h.iloc[i]
        if pd.isna(nop) or nop <= 0:
            continue
        reinv = ((capex_h.iloc[i] if pd.notna(capex_h.iloc[i]) else 0)
                 - (da_h.iloc[i] if pd.notna(da_h.iloc[i]) else 0)
                 + ((nwc_h.iloc[i] - nwc_h.iloc[i - 1])
                    if pd.notna(nwc_h.iloc[i]) and pd.notna(nwc_h.iloc[i - 1]) else 0))
        rr_vals.append(reinv / nop)
        ic_prev = ic_h.iloc[i - 1]
        if pd.notna(ic_prev) and ic_prev > 0:
            roic_vals.append(nop / ic_prev)

    rr_hist = float(np.median(rr_vals)) if rr_vals else np.nan
    roic_hist = float(np.median(roic_vals)) if roic_vals else np.nan

    if np.isfinite(rr_hist) and np.isfinite(roic_hist):
        g_sust = max(rr_hist * roic_hist, 0.0)
        if g_sust < g_hist:
            flags.warn(
                "Growth capped by reinvestment",
                f"Median historical growth of {g_hist*100:.2f}% EXCEEDS what "
                f"reinvestment can fund. Historical RR {rr_hist*100:.1f}% x "
                f"ROIC {roic_hist*100:.1f}% = {g_sust*100:.2f}%. Growth lowered "
                f"to {g_sust*100:.2f}% to stay economically consistent."
            )
            g_base = g_sust
        else:
            g_base = g_hist
    else:
        g_base = g_hist
        rr_hist = np.nan
        roic_hist = np.nan
        flags.warn("Growth capped by reinvestment",
                   "Historical RR or ROIC could not be computed. Growth uses the "
                   "historical median with no fundamental cap applied.")

    # -------------------------------------------------------------------
    # 4.7b GROWTH FLOOR (lower-bound safety net, not a new basis)
    # -------------------------------------------------------------------
    # Applied only AFTER g_base above is fully settled by the RR x ROIC cap,
    # which does not change. Some issuers pass every screening gate with a
    # negative median historical growth (a post-boom pullback, for example),
    # and a negative g_base compounds year over year through the explicit
    # forecast, occasionally driving fair value negative. If the final
    # g_base is below the floor -- including negative -- the floor is used
    # instead. If it already clears the floor, it is left untouched.
    g_floor = A["rev_growth_min_floor"]
    if g_base < g_floor:
        flags.warn(
            "Growth floor applied",
            f"Growth after the reinvestment cap is {g_base*100:.2f}%, below the "
            f"{g_floor*100:.1f}% floor. {g_floor*100:.1f}% is used instead so the "
            f"forecast does not compound a declining or negative growth path. "
            f"This is a lower bound only, not a recalculation of the rate."
        )
        g_base = g_floor

    # -------------------------------------------------------------------
    # 4.8 MARGIN TARGET AND OPERATING LEVERAGE DETECTION
    # -------------------------------------------------------------------
    # EBIT margin is no longer constant across the projection. If there's
    # evidence of operating leverage, margin fades linearly from the base
    # toward the HIGHEST margin the issuer has ever achieved, reached in
    # the final year.
    #
    # Evidence of operating leverage is tested via the Pearson correlation
    # between historical revenue and EBIT margin. The logic: if the fixed
    # cost base stays relatively stable while revenue rises, fixed costs get
    # diluted and margin expands. That pattern shows up as a positive correlation.
    #
    # Activation is CONDITIONAL. Without evidence of positive correlation,
    # margin stays flat. This prevents margin expansion from being forced
    # onto an issuer whose margin actually shrinks as revenue rises, for
    # example because of a price war or input cost increases that can't be
    # passed on to consumers.
    #
    # STATISTICAL CAVEAT: with only 4 annual periods, this correlation is
    # computed from 4 data points. That is a very small sample and the
    # result is fragile. The 0.50 threshold is used as a rough filter, not
    # a significance test.
    m_target = m_base
    oplev_corr = np.nan
    oplev_detected = False

    if A["margin_expansion_enabled"]:
        rev_s = pd.to_numeric(hist.loc["revenue"], errors="coerce")
        mgn_s = pd.to_numeric(hist.loc["ebit_margin"], errors="coerce")
        pair = pd.concat([rev_s, mgn_s], axis=1).dropna()

        if len(pair) >= 3 and pair.iloc[:, 0].std() > 0 and pair.iloc[:, 1].std() > 0:
            oplev_corr = float(np.corrcoef(pair.iloc[:, 0], pair.iloc[:, 1])[0, 1])

            if np.isfinite(oplev_corr) and oplev_corr >= A["margin_oplev_min_corr"]:
                m_max = float(np.nanmax(m_list)) if len(m_list) else m_base
                m_target = min(max(m_max, m_base), A["margin_target_cap"])
                oplev_detected = True
                flags.warn(
                    "Margin expansion ACTIVE",
                    f"Revenue vs EBIT margin correlation = {oplev_corr:.2f} "
                    f"(threshold {A['margin_oplev_min_corr']:.2f}), operating "
                    f"leverage detected. Margin fades linearly from "
                    f"{m_base*100:.2f}% to the historical high of "
                    f"{m_target*100:.2f}% by the final projection year. "
                    f"The correlation rests on only {len(pair)} data points, "
                    f"which is statistically fragile."
                )
            else:
                flags.warn(
                    "Margin expansion NOT ACTIVE",
                    f"Revenue vs EBIT margin correlation = {oplev_corr:.2f}, below "
                    f"the {A['margin_oplev_min_corr']:.2f} threshold. No evidence "
                    f"of operating leverage. Margin held flat at "
                    f"{m_base*100:.2f}%."
                )

    return {
        "rev_growth":       float(g_base),
        "rev_growth_hist":  float(g_hist),
        "rr_hist":          float(rr_hist) if np.isfinite(rr_hist) else np.nan,
        "roic_hist":        float(roic_hist) if np.isfinite(roic_hist) else np.nan,
        "rev_growth_sd":    float(g_sd),
        "rev_growth_raw":   float(g_raw),
        "ebit_margin":      float(m_base),
        "ebit_margin_target": float(m_target),
        "oplev_corr":       float(oplev_corr) if np.isfinite(oplev_corr) else np.nan,
        "oplev_detected":   bool(oplev_detected),
        "ebit_margin_sd":   float(m_sd),
        "da_ratio":         float(d_base),
        "capex_ratio":      float(c_base),
        "nwc_ratio":        float(w_base),
        "tax_rate":         float(t_base),
        "n_periods":        int(hist.shape[1]),
    }


def drivers_table(drv):
    """Driver table for display to the user."""
    rows = [
        ("Historical revenue growth (median)", f"{drv.get('rev_growth_hist', np.nan)*100:.2f}%"),
        ("Historical reinvestment rate", f"{drv.get('rr_hist', np.nan)*100:.1f}%"),
        ("Historical ROIC", f"{drv.get('roic_hist', np.nan)*100:.1f}%"),
        ("Revenue growth used", f"{drv['rev_growth']*100:.2f}%"),
        ("EBIT margin base (median)", f"{drv['ebit_margin']*100:.2f}%"),
        ("EBIT margin target (year N)", f"{drv.get('ebit_margin_target', np.nan)*100:.2f}%"),
        ("Revenue vs margin correlation", f"{drv.get('oplev_corr', np.nan):.2f}"),
        ("D&A / Revenue (MA)", f"{drv['da_ratio']*100:.2f}%"),
        ("Capex / Revenue (MA)", f"{drv['capex_ratio']*100:.2f}%"),
        ("NWC / Revenue (MA)", f"{drv['nwc_ratio']*100:.2f}%"),
        ("Effective tax rate", f"{drv['tax_rate']*100:.2f}%"),
    ]
    return pd.DataFrame(rows, columns=["Driver", "Value"])
