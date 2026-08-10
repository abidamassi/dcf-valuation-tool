"""
=============================================================================
SECTION 8 - TERMINAL VALUE
=============================================================================
PURPOSE : Value the cash flows after the explicit projection period ends.
          For most issuers, this component contributes 60 to 80 percent of
          total Enterprise Value, so its assumptions must be clearly visible.

FORMULA :
  8.1 GORDON GROWTH (primary method)
      FCFF_N+1 = FCFF_N x (1 + g)
      TV_N     = FCFF_N+1 / (WACC - g)

      Absolute requirement: WACC must exceed g. Otherwise the denominator
      is zero or negative and firm value becomes infinite or negative. The
      model will refuse to proceed if this requirement isn't met.

  8.2 CROSS-CHECK: IMPLIED EXIT EV/EBITDA
      Implied multiple = TV_N / EBITDA_N

      This isn't a separate valuation method, but a reasonableness test. If
      Gordon Growth produces an implied exit multiple of 25x for an issuer
      that has historically traded at 6x, the g or WACC assumption is too loose.

  8.3 DEPENDENCY TEST
      TV contribution = PV(TV) / Enterprise Value

      Above 80% means the valuation rests almost entirely on the perpetuity
      assumption rather than on verifiable projections. Flagged.

OUTPUT  : dict {tv_nominal, implied_exit_multiple, valid, reason}
=============================================================================
"""

import numpy as np

from config import ASSUMPTIONS


def terminal_value(fcff_final, ebitda_final, wacc, terminal_g=None, flags=None):
    """
    Compute terminal value with Gordon Growth and test its reasonableness.
    """
    A = ASSUMPTIONS
    g = A["terminal_growth"] if terminal_g is None else terminal_g

    result = {
        "terminal_growth": g,
        "wacc": wacc,
        "fcff_final": fcff_final,
        "fcff_terminal": np.nan,
        "tv_nominal": np.nan,
        "implied_exit_multiple": np.nan,
        "valid": False,
        "reason": "",
    }

    # --- requirement: WACC > g ---
    spread = wacc - g
    min_spread = A["min_wacc_g_spread"]
    if spread < min_spread:
        result["reason"] = (
            f"WACC ({wacc*100:.2f}%) is only {spread*100:.2f}% above terminal "
            f"growth ({g*100:.2f}%). A minimum spread of {min_spread*10000:.0f}bps "
            f"is needed for Gordon Growth to stay stable. Below that, terminal "
            f"value dominates the valuation and the result becomes highly "
            f"sensitive to small assumption changes. Lower the terminal growth."
        )
        if flags:
            flags.warn("Terminal Value", result["reason"])
        return result

    # --- final year FCFF must be positive ---
    if not np.isfinite(fcff_final) or fcff_final <= 0:
        result["reason"] = (
            f"Final year FCFF is not positive ({fcff_final/1e9:,.1f} bn). "
            f"The Gordon Growth terminal value is not meaningful. The company "
            f"is likely still in a heavy investment phase or margins are too thin."
        )
        if flags:
            flags.warn("Terminal Value", result["reason"])
        return result

    fcff_next = fcff_final * (1 + g)
    tv = fcff_next / spread

    result["fcff_terminal"] = fcff_next
    result["tv_nominal"] = tv
    result["valid"] = True

    # --- cross-check multiple ---
    if np.isfinite(ebitda_final) and ebitda_final > 0:
        mult = tv / ebitda_final
        result["implied_exit_multiple"] = mult
        if flags and mult > 20:
            flags.warn("Implied exit EV/EBITDA",
                       f"{mult:.1f}x. Too high for a typical IDX issuer. "
                       f"Check the terminal growth and WACC assumptions.")
        elif flags and mult < 2:
            flags.warn("Implied exit EV/EBITDA",
                       f"{mult:.1f}x. Very low, check whether final-year FCFF "
                       f"is depressed by abnormal capex.")

    return result


def check_tv_dependency(pv_tv, enterprise_value, flags=None):
    """Test how much the valuation depends on terminal value."""
    if not np.isfinite(enterprise_value) or enterprise_value == 0:
        return np.nan
    share = pv_tv / enterprise_value
    if flags and share > 0.80:
        flags.warn("Terminal value dependency",
                   f"{share*100:.1f}% of Enterprise Value comes from the terminal "
                   f"value. The valuation rests almost entirely on the perpetuity "
                   f"assumption rather than on verifiable projections.")
    return share
