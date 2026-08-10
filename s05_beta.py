"""
=============================================================================
SECTION 5 - BETA
=============================================================================
TUJUAN  : Mengukur sensitivitas return saham terhadap return pasar. Beta ini
          menjadi input Cost of Equity di Section 6.

          Kami TIDAK memakai info["beta"] dari yfinance. Untuk ticker .JK
          angka itu sering kosong, atau dihitung terhadap indeks yang salah.
          Beta dihitung sendiri terhadap IHSG (^JKSE).

RUMUS   : Return mingguan  R_t = ln(P_t / P_t-1)
          Raw beta         beta_raw = Cov(R_saham, R_IHSG) / Var(R_IHSG)
          Blume adjustment beta_adj = 0.67 x beta_raw + 0.33 x 1.00

          Blume adjustment menarik beta ke arah 1.0 karena beta historis
          secara empiris cenderung mean-reverting. Ini konvensi standar
          (dipakai Bloomberg pada Adjusted Beta).

          Periode : 3 tahun, frekuensi mingguan (sekitar 156 observasi).
                    Mingguan dipilih untuk mengurangi noise dari
                    non-synchronous trading pada saham berlikuiditas tipis.

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
    """Ambil return mingguan IHSG. Di-cache supaya batch tidak fetch berulang."""
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
    Hitung beta saham terhadap IHSG. Kalau gagal, kembalikan beta 1.0
    dengan flag eksplisit, bukan diam-diam.
    """
    A = ASSUMPTIONS
    period = period or A["beta_period"]
    interval = interval or A["beta_interval"]
    fb = A["beta_fallback"]
    out = {"beta_raw": np.nan, "beta_adj": fb, "r_squared": np.nan,
           "n_obs": 0, "source": f"fallback beta {fb:.2f}"}

    mkt = _market_returns(period, interval)
    if mkt is None:
        flags.warn("Beta", f"Gagal ambil data IHSG. Beta dipakai {fb:.2f}.")
        return out

    try:
        h = yf.Ticker(ticker).history(period=period, interval=interval)
        if h is None or h.empty:
            flags.warn("Beta", f"Gagal ambil harga historis. Beta dipakai {fb:.2f}.")
            return out
        px = h["Close"].dropna()
        stk = np.log(px / px.shift(1)).dropna()
    except Exception as exc:
        flags.warn("Beta", f"Error ambil harga ({type(exc).__name__}). Beta dipakai {fb:.2f}.")
        return out

    # Samakan tanggal. Timezone dinormalisasi supaya join tidak gagal.
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
        flags.warn("Beta", f"Hanya {n} observasi (minimum {min_obs} untuk "
                           f"interval {interval}). Beta dipakai {fb:.2f}.")
        return out

    x = df["mkt"].values
    y = df["stk"].values
    var_m = np.var(x, ddof=1)
    if var_m == 0 or not np.isfinite(var_m):
        flags.warn("Beta", f"Varians pasar nol. Beta dipakai {fb:.2f}.")
        return out

    cov = np.cov(y, x, ddof=1)[0, 1]
    beta_raw = cov / var_m

    corr = np.corrcoef(y, x)[0, 1]
    r2 = corr ** 2 if np.isfinite(corr) else np.nan

    beta_adj = 0.67 * beta_raw + 0.33 * 1.0

    # LANTAI BETA. Kalau hasil Blume jatuh di bawah 1.0, dipakai beta_fallback.
    # Dasarnya bukan statistik melainkan pertimbangan struktural: IHSG
    # didominasi bank besar, sehingga regresi emiten non-keuangan cenderung
    # meng-understate beta. Ditambah bias non-synchronous trading pada saham
    # berlikuiditas tipis yang menekan beta ke bawah secara artifisial.
    beta_before_floor = beta_adj
    floored = False
    if beta_adj < 1.0:
        beta_adj = fb
        floored = True
        flags.warn("Beta",
                   f"Beta hasil regresi {beta_before_floor:.3f} berada di bawah "
                   f"1.00, dinaikkan ke lantai {fb:.2f}. Ini penyesuaian "
                   f"struktural atas keputusan pengguna, bukan hasil regresi.")

    beta_adj = clip_flag(beta_adj, A["beta_floor"], A["beta_cap"], "Beta", flags)

    # Beta dengan daya jelas rendah TIDAK DIPAKAI, bukan sekadar diberi
    # peringatan. MAPA keluar beta 0.694 dengan R-squared 0.059, artinya 94%
    # pergerakannya tidak dijelaskan pasar sama sekali. Beta 0.69 untuk
    # peritel diskresioner mid-cap tidak kredibel: sektor ini secara
    # struktural lebih volatil dari pasar, bukan lebih tenang.
    if not np.isfinite(r2) or r2 < A["beta_min_r2"]:
        flags.warn("Beta",
                   f"R-squared regresi hanya {r2:.3f}, di bawah ambang "
                   f"{A['beta_min_r2']:.2f}. Beta hasil regresi "
                   f"({beta_before_floor:.3f}) DITOLAK dan diganti {fb:.2f}. "
                   f"Pergerakan saham tidak cukup dijelaskan pasar untuk "
                   f"membuat beta bermakna.")
        return {
            "beta_raw": float(beta_raw),
            "beta_adj": float(fb),
            "r_squared": float(r2) if np.isfinite(r2) else np.nan,
            "n_obs": int(n),
            "source": f"regresi ditolak (R2 rendah), dipakai beta {fb:.2f}",
        }

    return {
        "beta_raw": float(beta_raw),
        "beta_adj": float(beta_adj),
        "r_squared": float(r2) if np.isfinite(r2) else np.nan,
        "n_obs": int(n),
        "source": (f"regresi {interval} periode {period} vs {MARKET_INDEX}, "
                   f"Blume adjusted" + (", dilantai ke fallback" if floored else "")),
    }
