"""
=============================================================================
CONFIG - CENTRAL ASSUMPTIONS AND THRESHOLDS
=============================================================================
PURPOSE : Keep every assumption number and screening threshold in one place.
          No magic numbers are allowed to be written directly in other
          modules. Everything that may later become a slider lives here.
FORMULA : None. This is a constants file.
OUTPUT  : ASSUMPTIONS and SCREENING dictionaries.
=============================================================================
"""

# -----------------------------------------------------------------------
# A. COST OF CAPITAL ASSUMPTIONS (phase-2 slider candidates)
# -----------------------------------------------------------------------
ASSUMPTIONS = {
    # Risk-free rate. Default proxy is the INDOGB 10Y. Entered manually, not fetched.
    "risk_free_rate":       0.065,   # 6.50%   slider 0.050 - 0.090
    # Equity Risk Premium. Lowered from 7.00% to 4.00% at the user's decision.
    # METHODOLOGICAL NOTE: 4.00% is close to mature-market ERP levels
    # (US, Western Europe). Damodaran's reference for Indonesia is typically
    # 6.5-8% because it embeds a country risk premium. This reduction raises
    # fair value through the discount-rate channel, NOT because FCFF
    # improved. If the upside looks large, this is the most likely source.
    "equity_risk_premium":  0.040,   # 4.00%   slider 0.030 - 0.100
    # Extra premium for small/mid caps. Default 0 (conservative = none).
    "size_premium":         0.000,   # 0.00%   slider 0.000 - 0.030

    # Reasonable bounds on computed results. If breached, the value is clipped and flagged.
    "beta_floor":           0.40,
    "beta_cap":             2.20,
    "tax_floor":            0.15,
    "tax_cap":              0.30,
    "tax_fallback":         0.22,    # Indonesian corporate income tax rate (Law 7/2021 on HPP)
    # Cost of Debt floor relative to Rf. No corporation borrows below its own
    # government. An earlier absolute floor of 3.0% let ASII come out at
    # Kd 3.75% against an Rf of 6.50%, which is clearly implausible.
    "cod_spread_floor":     0.010,   # Minimum Kd = Rf + 100bps
    "cod_floor":            0.030,
    "cod_cap":              0.200,

    # Beta with low explanatory power is not used. An R-squared below this
    # threshold means stock movement is barely explained by the market, so
    # the regression beta is not meaningful. Replaced with 1.0 and flagged.
    "beta_min_r2":          0.20,

    # Beta that falls below 1.0 after the Blume adjustment is replaced with
    # this value. Also used as the fallback when the regression is rejected
    # for low R-squared. Rationale: a daily regression against IHSG tends to
    # understate non-financial issuers' beta because the index is dominated
    # by banks, compounded by non-synchronous trading bias in thinly traded
    # stocks.
    "beta_fallback":        1.20,

    # Beta regression period and frequency.
    "beta_period":          "1y",
    "beta_interval":        "1d",    # daily, roughly 252 observations
    "wacc_floor":           0.060,
    "wacc_cap":             0.250,

    # -------------------------------------------------------------------
    # B. PROJECTION ASSUMPTIONS
    # -------------------------------------------------------------------
    "forecast_years":       5,       # slider 5 - 10
    "terminal_growth":      0.025,   # 2.50%   slider 0.000 - 0.060
    "mid_year_convention":  True,    # Cash flow is assumed to occur mid-year

    # Minimum spread of WACC minus terminal growth. Previously 50bps, which
    # was too loose: INDF came out with a 342bps spread and terminal value
    # ballooned to 84.5% of EV. Below 400bps, Gordon Growth is too sensitive to use.
    "min_wacc_g_spread":    0.040,   # 400bps

    # Terminal growth may not exceed year-one growth. Without this cap, the
    # fade actually ACCELERATES growth toward the perpetuity rate, as
    # happened with ASII (2.42% rising to 4.00%). Terminal growth is a
    # ceiling, not a target to chase.
    "cap_terminal_at_g1":   True,

    # Cross-check for derived D&A against Net PP&E. Outside this range, the
    # EBITDA-minus-EBIT derivation is considered unreliable.
    "da_over_netppe_floor": 0.05,
    "da_over_netppe_cap":   0.35,

    # ---------------- MARGIN EXPANSION ----------------
    # EBIT margin is no longer held constant. When operating leverage is
    # detected in the historical data, margin fades LINEARLY from the base
    # margin (historical median) toward the HIGHEST margin the issuer has
    # ever achieved, reached in year N.
    #
    # Activation is CONDITIONAL, not automatic for every issuer. It requires
    # a positive correlation between revenue and EBIT margin in the
    # historical data. Without that evidence, margin stays flat as before.
    # This prevents margin expansion from being forced onto issuers whose
    # margin actually shrinks as revenue grows.
    "margin_expansion_enabled":  True,
    "margin_oplev_min_corr":     0.50,   # minimum revenue vs margin correlation
    "margin_target_cap":         0.60,   # maximum target margin of 60%, a sanity brake

    # Reasonable bounds on year-one revenue growth from the historical
    # moving average. This is a conservative brake so an issuer that
    # happened to grow 80% over the last two years isn't extrapolated forever.
    "rev_growth_floor":    -0.100,   # -10%
    "rev_growth_cap":       0.250,   # +25%

    # Rescue value, applied AFTER the RR x ROIC cap above has already run,
    # unchanged. Some issuers pass every screening gate yet carry a
    # negative median historical growth (AMMN, BUMI). Left alone, that
    # negative rate compounds through the explicit forecast and can drive
    # fair value negative. Only fires when growth is actually negative --
    # a positive rate is left exactly as computed even if it sits below
    # this value. Not a general minimum, only a floor under negative growth.
    "rev_growth_min_floor": 0.040,   # 4.00%

    # Reasonable bounds on moving-average driver ratios.
    "capex_ratio_cap":      0.300,   # Capex capped at 30% of revenue
    "nwc_ratio_floor":     -0.300,
    "nwc_ratio_cap":        0.600,

    # -------------------------------------------------------------------
    # C. SCENARIO AND SENSITIVITY PARAMETERS
    # -------------------------------------------------------------------
    "scenario_sd_multiple": 1.0,     # Bull/Bear = Base +/- 1 standard deviation
    "scenario_g_shift":     0.005,   # Terminal growth shifted +/- 50bps
    # Standard-deviation floor. If historical volatility is close to zero,
    # the Bull and Bear scenarios would be identical to Base and uninformative.
    "min_growth_sd":        0.030,   # 300bps
    "min_margin_sd":        0.010,   # 100bps
    "sens_wacc_step":       0.005,   # WACC grid +/- 50bps
    "sens_g_step":          0.0025,  # Terminal growth grid +/- 25bps
    "sens_steps":           2,       # 2 steps each direction, so a 5x5 grid

    # -------------------------------------------------------------------
    # D. RECOMMENDATION THRESHOLDS
    # -------------------------------------------------------------------
    "buy_threshold":        0.10,    # Upside > +10%  -> BUY
    "sell_threshold":      -0.10,    # Upside < -10%  -> SELL
                                     # In between      -> HOLD

    # Final gate, checked AFTER the full pipeline (Sections 1-12) has
    # already run to completion -- nothing here skips or alters any
    # FCFF/WACC calculation, it only decides whether the resulting rating
    # is trustworthy enough to show. A gap this wide more often points to
    # a modelling or data problem than genuine mispricing (see
    # s10_recommendation.py, make_recommendation()).
    "review_upside_threshold":   1.00,    # Upside > +100%  -> Review Required
    "review_downside_threshold": -0.50,   # Upside < -50%   -> Review Required
}

# -----------------------------------------------------------------------
# E. SCREENING GATES
# -----------------------------------------------------------------------
SCREENING = {
    # Gate 1 - Model eligibility (FCFF/WACC does not apply to financial institutions)
    "excluded_sectors": ["Financial Services", "Financial"],
    "excluded_industry_keywords": [
        "bank", "insurance", "asuransi", "capital markets", "credit services",
        "asset management", "financial data", "mortgage", "multifinance",
        "financial conglomerates", "shell companies",
    ],

    # Gate 2 - Data sufficiency
    "min_annual_years": 4,           # At least 4 complete years of annual filings

    # Gate 3 - Operational viability
    "min_ebit_positive_years": 2,    # EBIT positive in at least 2 of the last 3 years
    "ebit_lookback_years": 3,

    # Gate 4 - Size and valuation
    "min_market_cap_idr": 1_000_000_000_000,   # IDR 1 trillion
    "pe_min": 1.0,
    "pe_max": 60.0,

    # Gate 5 - Capital structure (required for FCFF/WACC to produce a
    #          meaningful number instead of an exploding residual)
    "require_positive_equity": True,       # Negative equity breaks the WACC weights
    "max_debt_to_capital": 0.80,           # D/(D+E) capped at 80%
    "max_net_debt_ebitda": 6.0,            # Net Debt/EBITDA capped at 6.0x
    "min_interest_coverage": 1.0,          # EBIT/Interest minimum 1.0x
    "require_positive_ebitda": True,

    # Gate 12 - Holding company
    # A consolidated DCF takes 100% of a subsidiary's cash flow and then
    # deducts non-controlling interest at BOOK VALUE. For a holdco, the gap
    # between NCI's book value and its economic value can be large, and the
    # holding discount that historically attaches to issuers like INDF and
    # ASII would never be captured. Rejected, not forced through.
    "max_minority_to_equity": 0.15,
}

# -----------------------------------------------------------------------
# F. FALLBACK FX RATE
# -----------------------------------------------------------------------
# Used ONLY if fetching USDIDR from yfinance fails.
# MUST BE VERIFIED BEFORE USE. This number is not data, it is a placeholder.
FALLBACK_USDIDR = 16_000.0

# -----------------------------------------------------------------------
# G. DISCLAIMER
# -----------------------------------------------------------------------
DISCLAIMER = (
    "Automated model output based on public yfinance data and user-set "
    "assumptions. Not reconciled against audited filings, not a corporate-action "
    "adjustment, and not investment advice. For internal analysis only."
)
