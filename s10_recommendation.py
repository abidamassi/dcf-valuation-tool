"""
=============================================================================
SECTION 10 - KEPUTUSAN REKOMENDASI
=============================================================================
TUJUAN  : Menerjemahkan selisih antara fair value model dan harga pasar
          menjadi satu keputusan yang bisa ditindaklanjuti.

RUMUS   : Upside = (Fair Value per Share / Harga Pasar) - 1

          Upside > +10%             -> BUY     (undervalued)
          -10% <= Upside <= +10%    -> HOLD    (fairly valued)
          Upside < -10%             -> SELL    (overvalued)

          Ambang 10% dipakai sebagai zona toleransi kesalahan model. Selisih
          di bawah 10% tidak bermakna secara statistik mengingat sensitivitas
          DCF terhadap WACC dan terminal growth. Ini bukan presisi, ini
          pengakuan atas ketidakpastian.

OUTPUT  : dict {rating, upside, label, catatan}
=============================================================================
"""

import numpy as np

from config import ASSUMPTIONS


def make_recommendation(valuation, flags=None):
    A = ASSUMPTIONS
    upside = valuation.get("upside", np.nan)
    fv = valuation.get("fair_value_per_share", np.nan)
    px = valuation.get("market_price", np.nan)

    if not np.isfinite(upside):
        return {
            "rating": "N/A",
            "upside": np.nan,
            "label": "Tidak dapat dinilai",
            "catatan": "Fair value atau harga pasar tidak tersedia.",
        }

    if upside > A["buy_threshold"]:
        rating, label = "BUY", "Undervalued"
    elif upside < A["sell_threshold"]:
        rating, label = "SELL", "Overvalued"
    else:
        rating, label = "HOLD", "Fairly valued"

    catatan = (
        f"Fair value model IDR {fv:,.0f} versus harga pasar IDR {px:,.0f}, "
        f"upside {upside*100:+.1f}%."
    )

    # Peringatan kalau selisihnya ekstrem, biasanya tanda asumsi bermasalah
    if abs(upside) > 1.0 and flags is not None:
        flags.warn("Rekomendasi",
                   f"Upside {upside*100:+.0f}% terlalu ekstrem. Pada praktiknya "
                   f"selisih sebesar ini lebih sering menandakan kesalahan asumsi "
                   f"atau data ketimbang mispricing pasar. Periksa WACC, terminal "
                   f"growth, dan margin EBIT sebelum dipakai.")

    return {
        "rating": rating,
        "upside": float(upside),
        "label": label,
        "catatan": catatan,
        "threshold_buy": A["buy_threshold"],
        "threshold_sell": A["sell_threshold"],
    }
