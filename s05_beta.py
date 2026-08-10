"""
=============================================================================
SECTION 5 - BETA
=============================================================================
PURPOSE : Measure the stock's return sensitivity to the market's return.
          This beta becomes the Cost of Equity input in Section 6.

          We do NOT use yfinance's info["beta"]. For .JK tickers that
          figure is often empty, or computed against the wrong index. Beta
          is computed here directly against the IHSG (^JKSE).

FORMULA : Weekly return    R_t = ln(P_t / P_t-1)
          Raw beta         beta_raw = Cov(R_stock, R_IHSG) / Var(R_IHSG)
          Blume adjustment beta_adj = 0.67 x beta_raw + 0.33 x 1.00

          The Blume adjustment pulls beta toward 1.0 because historical
          beta empirically tends to be mean-reverting. This is a standard
          convention (used by Bloomberg's Adjusted Beta).

          Period: 3 years, weekly frequency (roughly 156 observations).
                  Weekly was chosen to reduce noise from non-synchronous
                  trading in thinly traded stocks.

OUTPUT  : dict {beta_raw, beta_adj, r_squared, n_obs, source}
=============================================================================
"""

import numpy as np
import pandas as pd
import yfinance as yf

from config import ASSUMPTIONS
from utils import clip_flag

MARKET_INDEX = "^JKSE"
_MKT_CACHE = {}


def _market_returns(period=None, interval=None):
    """Fetch weekly IHSG returns. Cached so a batch run doesn't fetch repeatedly."""
    period = period or ASSUMPTIONS["beta_period"]
    interval = interval or ASSUMPTIONS["beta_interval"]
    key = f"mkt_{period}_{interval}"
    if key in _MKT_CACHE:
        return _MKT_CACHE[key]
    try:
        h = yf.Ticker(MARKET_INDEX).history(period=period, interval=interval)
        if h is None or h.empty:
            return None
        px = h["Close"].dropna()
        ret = np.log(px / px.shift(1)).dropna()
        _MKT_CACHE[key] = ret
        return ret
    except Exception:
        return None


def compute_beta(ticker, flags, period=None, interval=None):
    """
    Compute the stock's beta against the IHSG. On failure, return a
    fallback beta with an explicit flag, never silently.
    """
    A = ASSUMPTIONS
    period = period or A["beta_period"]
    interval = interval or A["beta_interval"]
    fb = A["beta_fallback"]
    out = {"beta_raw": np.nan, "beta_adj": fb, "r_squared": np.nan,
           "n_obs": 0, "source": f"fallback beta of {fb:.2f}"}

    mkt = _market_returns(period, interval)
    if mkt is None:
        flags.warn("Beta", f"Could not fetch IHSG data. Beta of {fb:.2f} used instead.")
        return out

    try:
        h = yf.Ticker(ticker).history(period=period, interval=interval)
        if h is None or h.empty:
            flags.warn("Beta", f"Could not fetch price history. Beta of {fb:.2f} used instead.")
            return out
        px = h["Close"].dropna()
        stk = np.log(px / px.shift(1)).dropna()
    except Exception as exc:
        flags.warn("Beta", f"Error fetching price ({type(exc).__name__}). Beta of {fb:.2f} used instead.")
        return out

    # Align dates. Timezone is normalised so the join doesn't fail.
    df = pd.DataFrame({"stk": stk, "mkt": mkt})
    df.index = pd.to_datetime(df.index).tz_localize(None) if df.index.tz is not None else df.index
    try:
        s = stk.copy(); m = mkt.copy()
        s.index = pd.to_datetime(s.index).tz_localize(None) if getattr(s.index, "tz", None) else s.index
        m.index = pd.to_datetime(m.index).tz_localize(None) if getattr(m.index, "tz", None) else m.index
        df = pd.concat([s.rename("stk"), m.rename("mkt")], axis=1).dropna()
    except Exception:
        df = df.dropna()

    n = len(df)
    min_obs = 120 if interval == "1d" else 52
    if n < min_obs:
        flags.warn("Beta", f"Only {n} observations (minimum {min_obs} for "
                           f"interval {interval}). Beta of {fb:.2f} used instead.")
        return out

    x = df["mkt"].values
    y = df["stk"].values
    var_m = np.var(x, ddof=1)
    if var_m == 0 or not np.isfinite(var_m):
        flags.warn("Beta", f"Market variance is zero. Beta of {fb:.2f} used instead.")
        return out

    cov = np.cov(y, x, ddof=1)[0, 1]
    beta_raw = cov / var_m

    corr = np.corrcoef(y, x)[0, 1]
    r2 = corr ** 2 if np.isfinite(corr) else np.nan

    beta_adj = 0.67 * beta_raw + 0.33 * 1.0

    # BETA FLOOR. If the Blume result falls below 1.0, beta_fallback is used
    # instead. The basis isn't statistical but structural: IHSG is
    # dominated by large banks, so non-financial issuer regressions tend to
    # understate beta. Compounded by non-synchronous trading bias in
    # thinly traded stocks, which artificially pushes beta down.
    beta_before_floor = beta_adj
    floored = False
    if beta_adj < 1.0:
        beta_adj = fb
        floored = True
        flags.warn("Beta",
                   f"Regression beta {beta_before_floor:.3f} fell below 1.00, "
                   f"raised to the floor of {fb:.2f}. This is a structural "
                   f"adjustment, not a regression result.")

    beta_adj = clip_flag(beta_adj, A["beta_floor"], A["beta_cap"], "Beta", flags)

    # Beta with low explanatory power is NOT USED, not just flagged. MAPA came
    # out at beta 0.694 with R-squared 0.059, meaning 94% of its movement is
    # unexplained by the market. A beta of 0.69 for a mid-cap discretionary
    # retailer is not credible: this sector is structurally more volatile than
    # the market, not calmer.
    if not np.isfinite(r2) or r2 < A["beta_min_r2"]:
        flags.warn("Beta",
                   f"Regression R-squared is only {r2:.3f}, below the "
                   f"{A['beta_min_r2']:.2f} threshold. The regression beta "
                   f"({beta_before_floor:.3f}) was REJECTED and replaced with {fb:.2f}. "
                   f"Stock movement is not sufficiently explained by the market "
                   f"for beta to be meaningful.")
        return {
            "beta_raw": float(beta_raw),
            "beta_adj": float(fb),
            "r_squared": float(r2) if np.isfinite(r2) else np.nan,
            "n_obs": int(n),
            "source": f"regression rejected (low R2), beta of {fb:.2f} used instead",
        }

    return {
        "beta_raw": float(beta_raw),
        "beta_adj": float(beta_adj),
        "r_squared": float(r2) if np.isfinite(r2) else np.nan,
        "n_obs": int(n),
        "source": (f"{interval} regression over {period} vs {MARKET_INDEX}, "
                   f"Blume adjusted" + (", floored to fallback" if floored else "")),
    }
