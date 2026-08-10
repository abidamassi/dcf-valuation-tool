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

    note = (
        f"Model fair value IDR {fv:,.0f} versus market price IDR {px:,.0f}, "
        f"upside {upside*100:+.1f}%."
    )

    # Flag when the gap is extreme, usually a sign of a problematic assumption
    if abs(upside) > 1.0 and flags is not None:
        flags.warn("Recommendation",
                   f"Upside of {upside*100:+.0f}% is too extreme. In practice a "
                   f"gap this large more often signals a flawed assumption or "
                   f"data issue than genuine market mispricing. Check WACC, "
                   f"terminal growth, and EBIT margin before relying on it.")

    return {
        "rating": rating,
        "upside": float(upside),
        "label": label,
        "note": note,
        "threshold_buy": A["buy_threshold"],
        "threshold_sell": A["sell_threshold"],
    }
