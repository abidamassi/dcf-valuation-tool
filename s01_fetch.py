"""
=============================================================================
SECTION 1 - DATA FETCH AND NORMALISATION TO IDR
=============================================================================
PURPOSE : Fetch the three annual financial statements, price, and metadata
          from yfinance, then STANDARDISE EVERY FIGURE TO RUPIAH.

          This is the most critical section. A number of IDX issuers
          (mining, energy) report financial statements in USD while their
          share price is quoted in IDR. Without conversion, equity value
          per share would be wrong by orders of magnitude.

FORMULA : Ticker normalisation : "BBCA" -> "BBCA.JK"
          Currency detection   : info["financialCurrency"] vs info["currency"]
          Conversion           : IDR_value = USD_value x USDIDR rate
          FX rate               : yfinance ticker "IDR=X" (USD/IDR)

          Items converted     : EVERY line of the income statement,
                                 balance sheet, and cash flow.
          Items NOT converted : share price and market cap
                                 (already in IDR from the exchange).

OUTPUT  : A CompanyData object containing
            .ticker, .name, .sector, .industry
            .income, .balance, .cashflow   (DataFrame, already IDR, chronological)
            .price, .market_cap, .shares_outstanding, .trailing_pe
            .fx_rate, .original_currency
            .flags (FlagLog)
=============================================================================
"""

import numpy as np
import pandas as pd
import yfinance as yf

from config import FALLBACK_USDIDR
from utils import FlagLog


# -----------------------------------------------------------------------
# 1.1 TICKER NORMALISATION
# -----------------------------------------------------------------------
def normalize_ticker(raw):
    """
    Turn user input into yfinance's IDX format.
      "bbca"    -> "BBCA.JK"
      "BBCA "   -> "BBCA.JK"
      "BBCA.JK" -> "BBCA.JK"
      "BBCA.jk" -> "BBCA.JK"
    """
    t = str(raw).strip().upper().replace(" ", "")
    if not t:
        raise ValueError("Ticker is empty")
    if t.endswith(".JK"):
        return t
    if "." in t:                       # non-IDX ticker, leave it as is
        return t
    return f"{t}.JK"


# -----------------------------------------------------------------------
# 1.2 USDIDR RATE
# -----------------------------------------------------------------------
_FX_CACHE = {}

def get_usdidr(flags=None):
    """
    Fetch the latest USD/IDR rate from the yfinance ticker "IDR=X".
    On failure, use FALLBACK_USDIDR and raise a hard flag.
    """
    if "USDIDR" in _FX_CACHE:
        return _FX_CACHE["USDIDR"]
    rate = None
    try:
        hist = yf.Ticker("IDR=X").history(period="5d")
        if hist is not None and not hist.empty:
            rate = float(hist["Close"].dropna().iloc[-1])
    except Exception:
        rate = None

    if rate is None or not np.isfinite(rate) or rate < 5_000 or rate > 40_000:
        rate = FALLBACK_USDIDR
        if flags is not None:
            flags.warn(
                "FX USDIDR",
                f"Could not fetch a live rate. Using fallback {rate:,.0f}. "
                "Must be verified manually before use."
            )
    _FX_CACHE["USDIDR"] = rate
    return rate


# -----------------------------------------------------------------------
# 1.3 DATA CONTAINER
# -----------------------------------------------------------------------
class CompanyData:
    def __init__(self, ticker):
        self.ticker = ticker
        self.name = None
        self.sector = None
        self.industry = None
        self.income = None
        self.balance = None
        self.cashflow = None
        self.price = np.nan
        self.market_cap = np.nan
        self.shares_outstanding = np.nan
        self.trailing_pe = np.nan
        self.fx_rate = 1.0
        self.original_currency = "IDR"
        self.flags = FlagLog(ticker)
        self.fetch_ok = False
        self.fetch_error = None


# -----------------------------------------------------------------------
# 1.4 MAIN FUNCTION
# -----------------------------------------------------------------------
def fetch_company(raw_ticker):
    """
    Fetch all data for one issuer and return it in IDR.
    Never raises an exception to the caller. Failures are recorded in
    .fetch_ok and .fetch_error so batch screening doesn't stop.
    """
    ticker = normalize_ticker(raw_ticker)
    data = CompanyData(ticker)

    try:
        tk = yf.Ticker(ticker)

        # --- metadata ---
        try:
            info = tk.info or {}
        except Exception:
            info = {}

        data.name = info.get("longName") or info.get("shortName") or ticker
        data.sector = info.get("sector")
        data.industry = info.get("industry")
        data.market_cap = _num(info.get("marketCap"))
        data.shares_outstanding = _num(info.get("sharesOutstanding"))
        data.trailing_pe = _num(info.get("trailingPE"))

        # --- latest price ---
        data.price = _num(info.get("currentPrice"))
        if not np.isfinite(data.price):
            try:
                h = tk.history(period="5d")
                if h is not None and not h.empty:
                    data.price = float(h["Close"].dropna().iloc[-1])
            except Exception:
                pass

        # --- annual financial statements ---
        income = _clean_statement(tk.income_stmt)
        balance = _clean_statement(tk.balance_sheet)
        cashflow = _clean_statement(tk.cashflow)

        if income is None or balance is None or cashflow is None:
            data.fetch_error = "One or more annual financial statements are unavailable"
            data.flags.missing("Financial statements", data.fetch_error)
            return data

        # --- currency conversion ---
        fin_ccy = (info.get("financialCurrency") or "IDR").upper()
        mkt_ccy = (info.get("currency") or "IDR").upper()
        data.original_currency = fin_ccy

        if fin_ccy != "IDR":
            if fin_ccy != "USD":
                data.flags.warn(
                    "Reporting currency",
                    f"Filings are in {fin_ccy}; the converter only supports USD. "
                    "Figures were NOT converted, so the valuation is not valid."
                )
            else:
                fx = get_usdidr(data.flags)
                data.fx_rate = fx
                income = income * fx
                balance = balance * fx
                cashflow = cashflow * fx
                data.flags.warn(
                    "Reporting currency",
                    f"Filings are in USD, converted to IDR at {fx:,.0f}. A single "
                    "spot rate is applied across all historical periods "
                    "(a simplification, not a per-year average rate)."
                )
        if mkt_ccy != "IDR":
            data.flags.warn(
                "Price currency",
                f"Price is quoted in {mkt_ccy}, not IDR. Check the ticker."
            )

        data.income = income
        data.balance = balance
        data.cashflow = cashflow

        # --- shares outstanding fallback from the balance sheet ---
        if not np.isfinite(data.shares_outstanding):
            for lbl in ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"]:
                if lbl in balance.index:
                    v = pd.to_numeric(balance.loc[lbl], errors="coerce").dropna()
                    if len(v):
                        # divided by fx since the whole balance sheet was multiplied by fx above
                        data.shares_outstanding = float(v.iloc[-1]) / data.fx_rate
                        data.flags.warn(
                            "Shares outstanding",
                            f"Taken from the balance sheet ({lbl}), not from yfinance info."
                        )
                        break

        # --- market cap fallback ---
        if not np.isfinite(data.market_cap) and np.isfinite(data.price) \
           and np.isfinite(data.shares_outstanding):
            data.market_cap = data.price * data.shares_outstanding
            data.flags.warn("Market cap", "Computed as price x shares outstanding.")

        data.fetch_ok = True
        return data

    except Exception as exc:
        data.fetch_error = f"{type(exc).__name__}: {exc}"
        data.flags.missing("Fetch", data.fetch_error)
        return data


# -----------------------------------------------------------------------
# 1.5 INTERNAL HELPERS
# -----------------------------------------------------------------------
def _num(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _clean_statement(df):
    """
    Tidy up a yfinance financial statement DataFrame:
      - drop columns that are entirely NaN
      - sort columns from oldest to newest period
      - force numeric
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    out = df.copy()
    out = out.apply(pd.to_numeric, errors="coerce")
    out = out.dropna(axis=1, how="all")
    if out.empty:
        return None
    try:
        out = out[sorted(out.columns)]      # oldest -> newest
    except Exception:
        out = out.iloc[:, ::-1]
    return out
