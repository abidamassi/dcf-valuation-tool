"""
=============================================================================
SECTION 1 - PENGAMBILAN DATA DAN NORMALISASI KE IDR
=============================================================================
TUJUAN  : Mengambil tiga laporan keuangan tahunan, harga, dan metadata dari
          yfinance, lalu MENYERAGAMKAN SELURUH ANGKA KE RUPIAH.

          Ini section paling kritikal. Sejumlah emiten IDX (tambang, energi)
          melaporkan laporan keuangan dalam USD sementara harga sahamnya
          dalam IDR. Kalau tidak dikonversi, equity value per share akan
          salah ribuan kali lipat.

RUMUS   : Normalisasi ticker : "BBCA" -> "BBCA.JK"
          Deteksi mata uang  : info["financialCurrency"] vs info["currency"]
          Konversi           : Nilai_IDR = Nilai_USD x Kurs USDIDR
          Kurs               : yfinance ticker "IDR=X" (USD/IDR)

          Item yang dikonversi : SELURUH baris income statement,
                                 balance sheet, dan cash flow.
          Item yang TIDAK dikonversi : harga saham dan market cap
                                       (sudah dalam IDR dari bursa).

OUTPUT  : Object CompanyData berisi
            .ticker, .name, .sector, .industry
            .income, .balance, .cashflow   (DataFrame, sudah IDR, urut kronologis)
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
# 1.1 NORMALISASI TICKER
# -----------------------------------------------------------------------
def normalize_ticker(raw):
    """
    Ubah input pengguna jadi format yfinance IDX.
      "bbca"    -> "BBCA.JK"
      "BBCA "   -> "BBCA.JK"
      "BBCA.JK" -> "BBCA.JK"
      "BBCA.jk" -> "BBCA.JK"
    """
    t = str(raw).strip().upper().replace(" ", "")
    if not t:
        raise ValueError("Ticker kosong")
    if t.endswith(".JK"):
        return t
    if "." in t:                       # ticker non-IDX, biarkan apa adanya
        return t
    return f"{t}.JK"


# -----------------------------------------------------------------------
# 1.2 KURS USDIDR
# -----------------------------------------------------------------------
_FX_CACHE = {}

def get_usdidr(flags=None):
    """
    Ambil kurs USD/IDR terakhir dari yfinance ticker "IDR=X".
    Kalau gagal, pakai FALLBACK_USDIDR dan beri flag keras.
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
                f"Gagal ambil kurs live. Memakai fallback {rate:,.0f}. "
                "WAJIB diverifikasi manual sebelum angka dipakai."
            )
    _FX_CACHE["USDIDR"] = rate
    return rate


# -----------------------------------------------------------------------
# 1.3 WADAH DATA
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
# 1.4 FUNGSI UTAMA
# -----------------------------------------------------------------------
def fetch_company(raw_ticker):
    """
    Ambil seluruh data satu emiten dan kembalikan dalam IDR.
    Tidak pernah melempar exception ke pemanggil. Kegagalan dicatat di
    .fetch_ok dan .fetch_error supaya batch screening tidak berhenti.
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

        # --- harga terakhir ---
        data.price = _num(info.get("currentPrice"))
        if not np.isfinite(data.price):
            try:
                h = tk.history(period="5d")
                if h is not None and not h.empty:
                    data.price = float(h["Close"].dropna().iloc[-1])
            except Exception:
                pass

        # --- laporan keuangan tahunan ---
        income = _clean_statement(tk.income_stmt)
        balance = _clean_statement(tk.balance_sheet)
        cashflow = _clean_statement(tk.cashflow)

        if income is None or balance is None or cashflow is None:
            data.fetch_error = "Salah satu laporan keuangan tahunan tidak tersedia"
            data.flags.missing("Laporan keuangan", data.fetch_error)
            return data

        # --- konversi mata uang ---
        fin_ccy = (info.get("financialCurrency") or "IDR").upper()
        mkt_ccy = (info.get("currency") or "IDR").upper()
        data.original_currency = fin_ccy

        if fin_ccy != "IDR":
            if fin_ccy != "USD":
                data.flags.warn(
                    "Mata uang laporan",
                    f"Laporan dalam {fin_ccy}, konverter hanya mendukung USD. "
                    "Angka TIDAK dikonversi, hasil valuasi tidak valid."
                )
            else:
                fx = get_usdidr(data.flags)
                data.fx_rate = fx
                income = income * fx
                balance = balance * fx
                cashflow = cashflow * fx
                data.flags.warn(
                    "Mata uang laporan",
                    f"Laporan asli USD, dikonversi ke IDR dengan kurs {fx:,.0f}. "
                    "Kurs spot dipakai untuk seluruh periode historis "
                    "(penyederhanaan, bukan kurs rata-rata per tahun)."
                )
        if mkt_ccy != "IDR":
            data.flags.warn(
                "Mata uang harga",
                f"Harga dalam {mkt_ccy}, bukan IDR. Periksa ticker."
            )

        data.income = income
        data.balance = balance
        data.cashflow = cashflow

        # --- fallback shares outstanding dari neraca ---
        if not np.isfinite(data.shares_outstanding):
            for lbl in ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"]:
                if lbl in balance.index:
                    v = pd.to_numeric(balance.loc[lbl], errors="coerce").dropna()
                    if len(v):
                        # dibagi fx karena tadi seluruh neraca dikali fx
                        data.shares_outstanding = float(v.iloc[-1]) / data.fx_rate
                        data.flags.warn(
                            "Shares outstanding",
                            f"Diambil dari neraca ({lbl}), bukan dari info yfinance."
                        )
                        break

        # --- fallback market cap ---
        if not np.isfinite(data.market_cap) and np.isfinite(data.price) \
           and np.isfinite(data.shares_outstanding):
            data.market_cap = data.price * data.shares_outstanding
            data.flags.warn("Market cap", "Dihitung dari harga x shares outstanding.")

        data.fetch_ok = True
        return data

    except Exception as exc:
        data.fetch_error = f"{type(exc).__name__}: {exc}"
        data.flags.missing("Fetch", data.fetch_error)
        return data


# -----------------------------------------------------------------------
# 1.5 HELPER INTERNAL
# -----------------------------------------------------------------------
def _num(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _clean_statement(df):
    """
    Rapikan DataFrame laporan keuangan yfinance:
      - buang kolom yang seluruhnya NaN
      - urutkan kolom dari periode terlama ke terbaru
      - paksa numerik
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    out = df.copy()
    out = out.apply(pd.to_numeric, errors="coerce")
    out = out.dropna(axis=1, how="all")
    if out.empty:
        return None
    try:
        out = out[sorted(out.columns)]      # terlama -> terbaru
    except Exception:
        out = out.iloc[:, ::-1]
    return out
