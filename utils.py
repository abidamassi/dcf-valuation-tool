"""
=============================================================================
UTILS - SHARED HELPERS
=============================================================================
PURPOSE : Provide helper functions used across sections, mainly lookup of
          yfinance financial statement labels (which are inconsistently
          named across issuers), and logging of problematic data flags.
FORMULA : No financial formulas here.
OUTPUT  : pick_row, safe_div, clip_flag functions, and the FlagLog class.
=============================================================================
"""

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------
# 1. FINANCIAL STATEMENT ROW LOOKUP
# -----------------------------------------------------------------------
def pick_row(df, candidates):
    """
    Find the first row whose label matches one of the candidates.

    yfinance uses different row names across issuers, e.g.
    'Depreciation And Amortization' vs 'Depreciation Amortization Depletion'.
    This function tries the candidates in order.

    Returns: a pandas Series (index = period date) or None if not found.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for label in candidates:
        if label in df.index:
            row = df.loc[label]
            if isinstance(row, pd.DataFrame):     # duplicate label
                row = row.iloc[0]
            return pd.to_numeric(row, errors="coerce")
    return None


def to_ascending(series):
    """yfinance orders columns newest to oldest. Flip to chronological order."""
    if series is None:
        return None
    return series.sort_index()


def safe_div(numerator, denominator, default=np.nan):
    """Division that doesn't blow up when the denominator is zero, NaN, or None."""
    try:
        if denominator is None or numerator is None:
            return default
        if isinstance(denominator, (int, float)):
            if denominator == 0 or not np.isfinite(denominator):
                return default
        return numerator / denominator
    except Exception:
        return default


def nanmean(values):
    """Mean that ignores NaN. Returns NaN if every value is NaN."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if arr.size == 0 or np.all(np.isnan(arr)):
        return np.nan
    return float(np.nanmean(arr))


def nanstd(values, ddof=1):
    """Sample standard deviation that ignores NaN."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size <= ddof:
        return np.nan
    return float(np.std(arr, ddof=ddof))


def clip_flag(value, low, high, name, flags, unit="x"):
    """
    Clip a value into a reasonable range. If clipped, log a flag so the
    user knows the number in use isn't the raw computed result.
    """
    if value is None or not np.isfinite(value):
        flags.warn(name, f"Invalid value, floor {low}{unit} used instead")
        return low
    if value < low:
        flags.warn(name, f"Computed {value:.4f} below the floor, clipped to {low}")
        return low
    if value > high:
        flags.warn(name, f"Computed {value:.4f} above the cap, clipped to {high}")
        return high
    return value


# -----------------------------------------------------------------------
# 2. DATA FLAG LOGGING
# -----------------------------------------------------------------------
class FlagLog:
    """
    Holds every data warning raised during one run.

    Three levels:
      MISSING - data is entirely absent from yfinance
      ZERO    - data exists but is zero, often meaning it wasn't reported
      WARN    - data exists but the computed result is out of a reasonable
                range, or was proxied
    """

    def __init__(self, ticker=""):
        self.ticker = ticker
        self.items = []

    def missing(self, field, note=""):
        self.items.append(("MISSING", field, note or "Not available from yfinance"))

    def zero(self, field, note=""):
        self.items.append(("ZERO", field, note or "Value is zero, verify whether this is genuine"))

    def warn(self, field, note=""):
        self.items.append(("WARN", field, note))

    def check_series(self, series, field):
        """Check one historical series, logging a flag if it's empty or has zeros/NaN."""
        if series is None or len(series) == 0:
            self.missing(field)
            return False
        arr = pd.to_numeric(series, errors="coerce")
        n_nan = int(arr.isna().sum())
        n_zero = int((arr.fillna(1) == 0).sum())
        if n_nan == len(arr):
            self.missing(field)
            return False
        if n_nan > 0:
            self.warn(field, f"{n_nan} of {len(arr)} periods are NaN")
        if n_zero > 0:
            self.zero(field, f"{n_zero} of {len(arr)} periods are 0")
        return True

    @property
    def has_issue(self):
        return len(self.items) > 0

    def to_frame(self):
        if not self.items:
            return pd.DataFrame(columns=["Level", "Field", "Note"])
        return pd.DataFrame(self.items, columns=["Level", "Field", "Note"])

    def render(self):
        """Print the flag table as text."""
        if not self.items:
            return "No data quality issues detected."
        lines = []
        order = {"MISSING": 0, "ZERO": 1, "WARN": 2}
        for level, field, note in sorted(self.items, key=lambda x: order.get(x[0], 9)):
            lines.append(f"  [{level:<7}] {field:<28} {note}")
        return "\n".join(lines)


# -----------------------------------------------------------------------
# 3. NUMBER FORMATTING
# -----------------------------------------------------------------------
def fmt_idr(value, unit="bn"):
    """Format an IDR number in billions or trillions."""
    if value is None or not np.isfinite(value):
        return "n/a"
    if unit == "tn":
        return f"IDR {value/1e12:,.2f} tn"
    return f"IDR {value/1e9:,.1f} bn"


def fmt_pct(value, dp=2):
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{value*100:.{dp}f}%"


def fmt_x(value, dp=2):
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{value:.{dp}f}x"
