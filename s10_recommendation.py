"""
=============================================================================
SECTION 10 - RECOMMENDATION DECISION
=============================================================================
PURPOSE : Translate the gap between the model's fair value and the market
          price into one actionable decision.

FORMULA : Upside = (Fair Value per Share / Market Price) - 1

          Upside > +10%             -> BUY     (undervalued)
          -10% <= Upside <= +10%    -> HOLD    (fairly valued)
          Upside < -10%             -> SELL    (overvalued)

          The 10% threshold acts as a tolerance zone for model error. A gap
          below 10% isn't statistically meaningful given the DCF's
          sensitivity to WACC and terminal growth. This is not precision,
          it's an acknowledgement of uncertainty.

OUTPUT  : dict {rating, upside, label, note}
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
            "label": "Cannot be rated",
            "note": "Fair value or market price is unavailable.",
        }

    if upside > A["buy_threshold"]:
        rating, label = "BUY", "Undervalued"
    elif upside < A["sell_threshold"]:
        rating, label = "SELL", "Overvalued"
    else:
        rating, label = "HOLD", "Fairly valued"

    # "Upside" reads backwards once fair value falls below market price, so
    # the word itself flips with the sign rather than staying fixed.
    ud_word = "upside" if upside >= 0 else "downside"

    note = (
        f"Model fair value IDR {fv:,.0f} versus market price IDR {px:,.0f}, "
        f"{ud_word} {upside*100:+.1f}%."
    )

    # Flag when the gap is extreme, usually a sign of a problematic assumption
    if abs(upside) > 1.0 and flags is not None:
        flags.warn("Recommendation",
                   f"{ud_word.capitalize()} of {upside*100:+.0f}% is too extreme. In "
                   f"practice a gap this large more often signals a flawed "
                   f"assumption or data issue than genuine market mispricing. "
                   f"Check WACC, terminal growth, and EBIT margin before relying "
                   f"on it.")

    return {
        "rating": rating,
        "upside": float(upside),
        "label": label,
        "note": note,
        "threshold_buy": A["buy_threshold"],
        "threshold_sell": A["sell_threshold"],
    }
