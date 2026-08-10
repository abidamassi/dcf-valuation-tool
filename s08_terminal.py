"""
=============================================================================
SECTION 8 - TERMINAL VALUE
=============================================================================
TUJUAN  : Menilai arus kas setelah periode proyeksi eksplisit berakhir. Pada
          sebagian besar emiten, komponen ini menyumbang 60 sampai 80 persen
          dari total Enterprise Value, jadi asumsinya harus terlihat jelas.

RUMUS   :
  8.1 GORDON GROWTH (metode utama)
      FCFF_N+1 = FCFF_N x (1 + g)
      TV_N     = FCFF_N+1 / (WACC - g)

      Syarat mutlak: WACC harus lebih besar dari g. Kalau tidak, penyebutnya
      nol atau negatif dan nilai perusahaan menjadi tak hingga atau negatif.
      Model akan menolak melanjutkan kalau syarat ini tidak terpenuhi.

  8.2 CROSS-CHECK: IMPLIED EXIT EV/EBITDA
      Implied multiple = TV_N / EBITDA_N

      Ini bukan metode valuasi terpisah, melainkan uji kewajaran. Kalau
      Gordon Growth menghasilkan implied exit multiple 25x untuk emiten yang
      historisnya diperdagangkan di 6x, asumsi g atau WACC terlalu longgar.

  8.3 UJI KETERGANTUNGAN
      Kontribusi TV = PV(TV) / Enterprise Value

      Di atas 80% berarti valuasi hampir seluruhnya bertumpu pada asumsi
      perpetuitas, bukan pada proyeksi yang bisa diverifikasi. Diberi flag.

OUTPUT  : dict {tv_nominal, implied_exit_multiple, valid, reason}
=============================================================================
"""

import numpy as np

from config import ASSUMPTIONS


def terminal_value(fcff_final, ebitda_final, wacc, terminal_g=None, flags=None):
    """
    Hitung terminal value dengan Gordon Growth dan uji kewajarannya.
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

    # --- syarat WACC > g ---
    spread = wacc - g
    min_spread = A["min_wacc_g_spread"]
    if spread < min_spread:
        result["reason"] = (
            f"WACC ({wacc*100:.2f}%) hanya {spread*100:.2f}% di atas terminal "
            f"growth ({g*100:.2f}%). Selisih minimal {min_spread*10000:.0f}bps "
            f"diperlukan agar Gordon Growth stabil. Di bawah itu, terminal value "
            f"mendominasi valuasi dan hasilnya sangat sensitif terhadap "
            f"perubahan asumsi kecil. Turunkan terminal growth."
        )
        if flags:
            flags.warn("Terminal Value", result["reason"])
        return result

    # --- FCFF tahun terakhir harus positif ---
    if not np.isfinite(fcff_final) or fcff_final <= 0:
        result["reason"] = (
            f"FCFF tahun terakhir tidak positif ({fcff_final/1e9:,.1f} bn). "
            f"Terminal value Gordon Growth tidak bermakna. Emiten masih dalam "
            f"fase investasi berat atau margin terlalu tipis."
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
                       f"{mult:.1f}x. Terlalu tinggi untuk emiten IDX pada umumnya. "
                       f"Periksa asumsi terminal growth dan WACC.")
        elif flags and mult < 2:
            flags.warn("Implied exit EV/EBITDA",
                       f"{mult:.1f}x. Sangat rendah, periksa apakah FCFF "
                       f"tahun terakhir tertekan capex yang tidak normal.")

    return result


def check_tv_dependency(pv_tv, enterprise_value, flags=None):
    """Uji seberapa besar valuasi bergantung pada terminal value."""
    if not np.isfinite(enterprise_value) or enterprise_value == 0:
        return np.nan
    share = pv_tv / enterprise_value
    if flags and share > 0.80:
        flags.warn("Ketergantungan Terminal Value",
                   f"{share*100:.1f}% dari Enterprise Value berasal dari terminal "
                   f"value. Valuasi hampir seluruhnya bertumpu pada asumsi "
                   f"perpetuitas, bukan proyeksi yang bisa diverifikasi.")
    return share
