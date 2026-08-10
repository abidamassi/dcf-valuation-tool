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

          A final gate runs after the rating above: Upside > +100% or
          < -50% overrides rating to "Review Required" and adds a
          reason_override string. This runs after the full pipeline has
          completed (not a screening-style early skip) and does not alter
          fair_value_per_share, upside, or any FCFF/WACC figure -- see
          config.py review_upside_threshold / review_downside_threshold.

OUTPUT  : dict {rating, upside, label, note[, reason_override]}
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

    result = {
        "rating": rating,
        "upside": float(upside),
        "label": label,
        "note": note,
        "threshold_buy": A["buy_threshold"],
        "threshold_sell": A["sell_threshold"],
    }

    # -------------------------------------------------------------------
    # FINAL GATE - REVIEW REQUIRED
    # -------------------------------------------------------------------
    # Runs here, AFTER upside above is fully computed from a completed
    # valuation -- unlike the Section 3 screening gate, which runs before
    # any DCF math and can skip the calculation entirely, this gate never
    # skips anything. fair_value_per_share, upside, and every FCFF/WACC
    # number computed upstream are untouched; this only overrides which
    # rating is considered trustworthy enough to surface. The UI is
    # responsible for hiding fair_value_per_share/upside and Sections
    # 7-12 when it sees this rating -- they stay in this dict either way
    # for internal debugging.
    if upside > A["review_upside_threshold"] or upside < A["review_downside_threshold"]:
        result["rating"] = "Review Required"
        result["reason_override"] = (
            "This result falls outside a defensible range for FCFF-based DCF. "
            "The gap between fair value and market price is wide enough that "
            "it more often signals a modelling or data issue than genuine "
            "mispricing. Consider cross-checking with SOTP, Net Asset Value, "
            "or relative valuation (EV/EBITDA, P/E against peers) before "
            "drawing a conclusion."
        )

    return result
