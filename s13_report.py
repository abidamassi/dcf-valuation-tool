"""
=============================================================================
SECTION 13 - PERAKITAN LAPORAN
=============================================================================
TUJUAN  : Menyusun seluruh keluaran section sebelumnya menjadi satu laporan
          yang bisa dibaca berurutan, dengan flag data ditempatkan di posisi
          yang tidak bisa dilewati pembaca.

RUMUS   : Tidak ada. Ini lapisan penyajian.

OUTPUT  : String laporan lengkap, diakhiri disclaimer.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import DISCLAIMER, ASSUMPTIONS
from s04_drivers import drivers_table
from s06_wacc import wacc_table
from s07_forecast import projection_table
from s09_valuation import bridge_table
from s12_scenario import scenario_table

LINE = "=" * 78
THIN = "-" * 78


def _h(title):
    return f"\n{LINE}\n{title}\n{LINE}"


def render_report(result):
    """
    result adalah dict hasil main.analyze_ticker().
    """
    p = []
    d = result["data"]

    # ---------------- header ----------------
    p.append(_h(f"DCF VALUATION - {d.ticker} - {d.name}"))
    p.append(f"Sektor          : {d.sector or 'n/a'} / {d.industry or 'n/a'}")
    p.append(f"Harga pasar     : IDR {d.price:,.0f}" if np.isfinite(d.price) else "Harga pasar     : n/a")
    p.append(f"Market cap      : IDR {d.market_cap/1e12:,.2f} tn" if np.isfinite(d.market_cap) else "Market cap      : n/a")
    p.append(f"Trailing P/E    : {d.trailing_pe:.2f}x" if np.isfinite(d.trailing_pe) else "Trailing P/E    : n/a")
    p.append(f"Mata uang lapkeu: {d.original_currency}"
             + (f" (dikonversi ke IDR @ {d.fx_rate:,.0f})" if d.fx_rate != 1.0 else ""))

    # ---------------- screening ----------------
    scr = result["screening"]
    p.append(_h("SECTION 3 - SCREENING KELAYAKAN MODEL"))
    p.append(scr["detail"].to_string(index=False))
    p.append("")
    p.append(f"STATUS: {scr['status']}")

    if not scr["passed"]:
        p.append(_h("FLAG DATA"))
        p.append(d.flags.render())
        p.append(_h("DISCLAIMER"))
        p.append(DISCLAIMER)
        return "\n".join(p)

    # ---------------- flag data (ditaruh di depan hasil) ----------------
    p.append(_h("PERINGATAN KUALITAS DATA - BACA SEBELUM MEMAKAI ANGKA DI BAWAH"))
    p.append(d.flags.render())

    # ---------------- driver ----------------
    p.append(_h("SECTION 4 - DRIVER HISTORIS (MOVING AVERAGE)"))
    p.append(f"Basis: {result['drivers']['n_periods']} periode tahunan")
    p.append(drivers_table(result["drivers"]).to_string(index=False))

    # ---------------- wacc ----------------
    p.append(_h("SECTION 5-6 - BETA DAN COST OF CAPITAL"))
    p.append(f"Metode beta: {result['beta']['source']}, {result['beta']['n_obs']} observasi")
    p.append(THIN)
    p.append(wacc_table(result["wacc"]).to_string(index=False))
    p.append(THIN)
    p.append(f"Metode Cost of Debt: {result['wacc']['kd_method']}")

    # ---------------- proyeksi ----------------
    p.append(_h("SECTION 7 - PROYEKSI FCFF (IDR miliar)"))
    p.append(projection_table(result["projection"]).to_string())
    fs = result["forecast_summary"]
    p.append(THIN)
    p.append(f"Rata-rata reinvestment rate : {fs['avg_reinvest_rate']*100:,.1f}%")
    p.append(f"Rata-rata ROIC              : {fs['avg_roic']*100:,.1f}%")
    p.append(f"Implied growth (RR x ROIC)  : {fs['avg_implied_growth']*100:,.1f}%")
    p.append(f"Asumsi revenue growth th-1  : {fs['g1']*100:,.1f}%")
    gap = fs["avg_implied_growth"] - fs["g1"]
    if np.isfinite(gap) and abs(gap) > 0.05:
        p.append(f"CATATAN: selisih {gap*100:+.1f}pp antara implied growth dan asumsi "
                 f"growth. Model tidak sepenuhnya konsisten secara internal.")

    # ---------------- terminal value ----------------
    tv = result["terminal"]
    p.append(_h("SECTION 8 - TERMINAL VALUE"))
    p.append(f"Terminal growth             : {tv['terminal_growth']*100:.2f}%")
    p.append(f"WACC                        : {tv['wacc']*100:.2f}%")
    p.append(f"Spread (WACC - g)           : {(tv['wacc']-tv['terminal_growth'])*100:.2f}%")
    p.append(f"FCFF tahun terakhir         : IDR {tv['fcff_final']/1e9:,.0f} bn")
    p.append(f"Terminal Value nominal      : IDR {tv['tv_nominal']/1e9:,.0f} bn")
    p.append(f"Implied exit EV/EBITDA      : {tv['implied_exit_multiple']:.1f}x"
             if np.isfinite(tv["implied_exit_multiple"]) else "Implied exit EV/EBITDA      : n/a")

    # ---------------- valuasi ----------------
    v = result["valuation"]
    p.append(_h("SECTION 9 - ENTERPRISE VALUE KE EQUITY VALUE (IDR miliar)"))
    p.append(bridge_table(v).to_string(index=False))
    p.append(THIN)
    p.append(f"Kontribusi Terminal Value ke EV : {v['tv_share_of_ev']*100:.1f}%"
             if np.isfinite(v["tv_share_of_ev"]) else "Kontribusi Terminal Value ke EV : n/a")
    p.append(f"Implied EV/EBITDA saat ini      : {v['implied_ev_ebitda_current']:.1f}x"
             if np.isfinite(v["implied_ev_ebitda_current"]) else "Implied EV/EBITDA saat ini      : n/a")
    p.append(f"Shares outstanding              : {v['shares_outstanding']:,.0f}"
             if np.isfinite(v["shares_outstanding"]) else "Shares outstanding              : n/a")

    # ---------------- rekomendasi ----------------
    rec = result["recommendation"]
    A = ASSUMPTIONS
    p.append(_h("SECTION 10 - KEPUTUSAN"))
    p.append(f"Harga pasar        : IDR {v['market_price']:,.0f}")
    p.append(f"Fair value (base)  : IDR {v['fair_value_per_share']:,.0f}"
             if np.isfinite(v["fair_value_per_share"]) else "Fair value (base)  : n/a")
    p.append(f"Upside / downside  : {rec['upside']*100:+.1f}%"
             if np.isfinite(rec["upside"]) else "Upside / downside  : n/a")
    p.append(f"Status             : {rec['label']}")
    p.append(f"REKOMENDASI        : {rec['rating']}")
    p.append(f"Ambang: BUY jika upside > {A['buy_threshold']*100:.0f}%, "
             f"SELL jika < {A['sell_threshold']*100:.0f}%, di antaranya HOLD.")

    # ---------------- sensitivity ----------------
    sens = result["sensitivity"]
    p.append(_h("SECTION 11 - SENSITIVITY: FAIR VALUE PER SAHAM (IDR)"))
    p.append("Baris = WACC, Kolom = Terminal growth")
    p.append(sens["fair_value"].to_string())
    p.append("")
    p.append("Upside terhadap harga pasar (%)")
    p.append(sens["upside"].to_string())
    st = sens["stats"]
    p.append(THIN)
    p.append(f"Rentang fair value: IDR {st['min']:,.0f} sampai IDR {st['max']:,.0f}, "
             f"median IDR {st['median']:,.0f} ({st['n_valid']}/{st['n_cells']} sel valid)")

    # ---------------- skenario ----------------
    p.append(_h("SECTION 12 - SKENARIO (deviasi dari standar deviasi historis)"))
    p.append(scenario_table(result["scenarios"]).to_string())

    # ---------------- keterbatasan ----------------
    p.append(_h("KETERBATASAN MODEL FASE INI"))
    p.append("- Corporate action dan peristiwa setelah tanggal neraca tidak diperhitungkan")
    p.append("- Aset non-operasional (asosiasi, properti investasi) tidak ditambahkan ke equity value")
    p.append("- Shares outstanding memakai basis dasar, bukan fully diluted")
    p.append("- Konversi USD ke IDR memakai kurs spot untuk seluruh periode historis")
    p.append("- Margin EBIT hanya mengembang bila terdeteksi operating leverage historis")
    p.append("- Consensus estimate tidak dipakai, seluruh proyeksi berasal dari data historis")

    p.append(_h("DISCLAIMER"))
    p.append(DISCLAIMER)
    return "\n".join(p)
