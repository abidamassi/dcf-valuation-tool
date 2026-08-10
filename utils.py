"""
=============================================================================
UTILS - HELPER BERSAMA
=============================================================================
TUJUAN  : Menyediakan fungsi pembantu yang dipakai lintas section, terutama
          pencarian label laporan keuangan yfinance yang penamaannya tidak
          konsisten antar emiten, dan pencatatan flag data bermasalah.
RUMUS   : Tidak ada rumus keuangan di sini.
OUTPUT  : Fungsi pick_row, safe_div, clip_flag, dan class FlagLog.
=============================================================================
"""

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------
# 1. PENCARIAN BARIS LAPORAN KEUANGAN
# -----------------------------------------------------------------------
def pick_row(df, candidates):
    """
    Cari baris pertama yang labelnya cocok dari daftar kandidat.

    yfinance memakai nama baris yang berbeda-beda antar emiten, misalnya
    'Depreciation And Amortization' vs 'Depreciation Amortization Depletion'.
    Fungsi ini mencoba kandidat secara berurutan.

    Return: pandas Series (index = tanggal periode) atau None kalau tidak ada.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for label in candidates:
        if label in df.index:
            row = df.loc[label]
            if isinstance(row, pd.DataFrame):     # duplikat label
                row = row.iloc[0]
            return pd.to_numeric(row, errors="coerce")
    return None


def to_ascending(series):
    """yfinance mengurutkan kolom dari terbaru ke terlama. Balik jadi kronologis."""
    if series is None:
        return None
    return series.sort_index()


def safe_div(numerator, denominator, default=np.nan):
    """Pembagian yang tidak meledak kalau penyebutnya nol, NaN, atau None."""
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
    """Rata-rata yang mengabaikan NaN. Return NaN kalau semua NaN."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if arr.size == 0 or np.all(np.isnan(arr)):
        return np.nan
    return float(np.nanmean(arr))


def nanstd(values, ddof=1):
    """Standar deviasi sampel yang mengabaikan NaN."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size <= ddof:
        return np.nan
    return float(np.std(arr, ddof=ddof))


def clip_flag(value, low, high, name, flags, unit="x"):
    """
    Batasi nilai ke rentang wajar. Kalau kena clip, catat flag supaya
    pengguna tahu angka yang dipakai bukan hasil perhitungan mentah.
    """
    if value is None or not np.isfinite(value):
        flags.warn(name, f"Nilai tidak valid, dipakai batas bawah {low}{unit}")
        return low
    if value < low:
        flags.warn(name, f"Hasil hitung {value:.4f} di bawah batas, di-clip ke {low}")
        return low
    if value > high:
        flags.warn(name, f"Hasil hitung {value:.4f} di atas batas, di-clip ke {high}")
        return high
    return value


# -----------------------------------------------------------------------
# 2. PENCATATAN FLAG DATA
# -----------------------------------------------------------------------
class FlagLog:
    """
    Menampung seluruh peringatan data selama satu run.

    Tiga level:
      MISSING - data tidak ada sama sekali dari yfinance
      ZERO    - data ada tapi nilainya nol, sering berarti tidak dilaporkan
      WARN    - data ada tapi hasil hitung di luar rentang wajar atau di-proxy
    """

    def __init__(self, ticker=""):
        self.ticker = ticker
        self.items = []

    def missing(self, field, note=""):
        self.items.append(("MISSING", field, note or "Tidak tersedia di yfinance"))

    def zero(self, field, note=""):
        self.items.append(("ZERO", field, note or "Nilai nol, cek apakah benar-benar nol"))

    def warn(self, field, note=""):
        self.items.append(("WARN", field, note))

    def check_series(self, series, field):
        """Periksa satu deret historis, catat kalau kosong atau ada nol/NaN."""
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
            self.warn(field, f"{n_nan} dari {len(arr)} periode bernilai NaN")
        if n_zero > 0:
            self.zero(field, f"{n_zero} dari {len(arr)} periode bernilai 0")
        return True

    @property
    def has_issue(self):
        return len(self.items) > 0

    def to_frame(self):
        if not self.items:
            return pd.DataFrame(columns=["Level", "Field", "Catatan"])
        return pd.DataFrame(self.items, columns=["Level", "Field", "Catatan"])

    def render(self):
        """Cetak tabel flag dalam format teks."""
        if not self.items:
            return "Tidak ada isu data yang terdeteksi."
        lines = []
        order = {"MISSING": 0, "ZERO": 1, "WARN": 2}
        for level, field, note in sorted(self.items, key=lambda x: order.get(x[0], 9)):
            lines.append(f"  [{level:<7}] {field:<28} {note}")
        return "\n".join(lines)


# -----------------------------------------------------------------------
# 3. FORMAT ANGKA
# -----------------------------------------------------------------------
def fmt_idr(value, unit="bn"):
    """Format angka IDR ke miliar atau triliun."""
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
