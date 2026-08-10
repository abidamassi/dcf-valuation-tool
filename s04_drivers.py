"""
=============================================================================
SECTION 4 - DRIVER HISTORIS (MOVING AVERAGE)
=============================================================================
TUJUAN  : Menurunkan asumsi proyeksi dari data historis emiten itu sendiri,
          bukan dari tebakan. Semua driver memakai rata-rata bergerak
          sederhana atas seluruh periode yang tersedia. Ini pilihan sadar
          untuk konservatif: emiten yang kebetulan tumbuh 60% dua tahun
          terakhir tidak boleh langsung diekstrapolasi selamanya.

RUMUS   : Revenue growth   g_hist = mean(pct_change(Revenue))
          EBIT margin      m_hist = mean(EBIT_t / Revenue_t)
          D&A ratio        d_hist = mean(D&A_t / Revenue_t)
          Capex ratio      c_hist = mean(Capex_t / Revenue_t)
          NWC ratio        w_hist = mean(NWC_t / Revenue_t)
          Effective tax    t_hist = mean(Tax Provision_t / Pretax Income_t)

          Seluruh hasil di-clip ke rentang wajar di config.py. Setiap
          clipping dicatat sebagai flag supaya terlihat bahwa angka yang
          dipakai bukan hasil mentah.

          Standar deviasi tiap driver juga dihitung di sini karena akan
          dipakai Section 12 untuk membentuk skenario Bull dan Bear.

OUTPUT  : dict driver berisi nilai base dan standar deviasinya.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from utils import nanmean, nanstd, clip_flag


def build_drivers(hist, flags):
    """
    Hitung driver base dan standar deviasinya dari seluruh periode historis.
    """
    A = ASSUMPTIONS

    def series(key):
        return pd.to_numeric(hist.loc[key], errors="coerce").dropna().tolist()

    # ---------------- 4.1 Pertumbuhan revenue ----------------
    # MEDIAN, bukan mean. Jendela 4 tahun (2022-2025) masih menyerap rebound
    # pasca pandemi, dan satu tahun ekstrem menarik mean naik tajam. MAPA
    # keluar 25.76% dengan mean, jauh di atas realisasi FY25 (+12.2%).
    g_list = series("rev_growth")
    g_raw = float(np.median(g_list)) if len(g_list) else np.nan
    g_sd = nanstd(g_list)
    if not np.isfinite(g_raw):
        g_raw = 0.0
        flags.warn("Revenue growth", "Tidak bisa dihitung, dipakai 0%.")
    g_hist = clip_flag(g_raw, A["rev_growth_floor"], A["rev_growth_cap"],
                       "Revenue growth (median)", flags)
    if not np.isfinite(g_sd):
        g_sd = 0.03
        flags.warn("Revenue growth SD", "Tidak bisa dihitung, dipakai 3%.")
    elif g_sd < A["min_growth_sd"]:
        flags.warn("Revenue growth SD",
                   f"Volatilitas historis hanya {g_sd*100:.2f}%, terlalu rendah "
                   f"untuk membentuk skenario yang bermakna. Dipakai lantai "
                   f"{A['min_growth_sd']*100:.1f}%.")
        g_sd = A["min_growth_sd"]

    # ---------------- 4.2 Margin EBIT ----------------
    m_list = series("ebit_margin")
    m_base = float(np.median(m_list)) if len(m_list) else np.nan
    m_sd = nanstd(m_list)
    if not np.isfinite(m_base) or m_base <= 0:
        flags.warn("EBIT margin", "Rata-rata historis tidak positif. "
                                  "Model tidak akan menghasilkan nilai wajar.")
        m_base = max(m_base if np.isfinite(m_base) else 0.01, 0.01)
    if not np.isfinite(m_sd):
        m_sd = 0.02
        flags.warn("EBIT margin SD", "Tidak bisa dihitung, dipakai 200bps.")
    elif m_sd < A["min_margin_sd"]:
        flags.warn("EBIT margin SD",
                   f"Volatilitas historis hanya {m_sd*100:.2f}%, terlalu rendah "
                   f"untuk membentuk skenario yang bermakna. Dipakai lantai "
                   f"{A['min_margin_sd']*100:.1f}%.")
        m_sd = A["min_margin_sd"]

    # ---------------- 4.3 Depresiasi dan amortisasi ----------------
    d_list = series("da_ratio")
    d_base = float(np.median(d_list)) if len(d_list) else np.nan
    if not np.isfinite(d_base) or d_base < 0:
        d_base = 0.0
        flags.warn("D&A ratio", "Tidak tersedia, dipakai 0% dari revenue. "
                                "FCFF akan understate.")

    # ---------------- 4.4 Capex ----------------
    c_list = series("capex_ratio")
    c_raw = float(np.median(c_list)) if len(c_list) else np.nan
    if not np.isfinite(c_raw) or c_raw < 0:
        c_raw = d_base
        flags.warn("Capex ratio", "Tidak tersedia. Diproksi sama dengan D&A ratio "
                                  "(asumsi maintenance capex).")
    c_base = clip_flag(c_raw, 0.0, A["capex_ratio_cap"], "Capex ratio (MA)", flags)

    # ---------------- 4.5 Modal kerja ----------------
    w_list = series("nwc_ratio")
    w_raw = float(np.median(w_list)) if len(w_list) else np.nan
    if not np.isfinite(w_raw):
        w_raw = 0.0
        flags.warn("NWC ratio", "Tidak tersedia, dipakai 0%. "
                                "Delta working capital tidak dimodelkan.")
    w_base = clip_flag(w_raw, A["nwc_ratio_floor"], A["nwc_ratio_cap"],
                       "NWC ratio (MA)", flags)

    # ---------------- 4.6 Tarif pajak efektif ----------------
    t_list = [t for t in series("eff_tax") if 0 < t < 1]
    t_raw = float(np.median(t_list)) if len(t_list) else np.nan
    if not np.isfinite(t_raw):
        t_base = A["tax_fallback"]
        flags.warn("Effective tax rate",
                   f"Tidak bisa dihitung dari Tax Provision / Pretax Income. "
                   f"Dipakai tarif statutori {t_base*100:.0f}%.")
    else:
        t_base = clip_flag(t_raw, A["tax_floor"], A["tax_cap"],
                           "Effective tax rate", flags)

    # -------------------------------------------------------------------
    # 4.7 PEMBATAS GROWTH BERBASIS REINVESTASI FUNDAMENTAL
    # -------------------------------------------------------------------
    # Persamaan pertumbuhan fundamental:
    #     g_sustainable = Reinvestment Rate x ROIC
    #
    # Perusahaan tidak bisa tumbuh melebihi apa yang dibiayai reinvestasinya.
    # Sebelum perbaikan ini, model memaksa MAPA tumbuh 25% sambil hanya
    # menyisihkan 20.6% NOPAT untuk reinvestasi. Untuk tumbuh 25% dengan ROIC
    # 30.5%, reinvestment rate harus 82%. Selisihnya jatuh ke FCFF sebagai kas
    # yang tidak pernah ada, dan itulah sumber utama upside 137%.
    #
    # Komponen historis:
    #     NOPAT_t        = EBIT_t x (1 - tarif pajak efektif)
    #     Reinvestment_t = Capex_t - D&A_t + delta NWC_t
    #     RR_t           = Reinvestment_t / NOPAT_t
    #     ROIC_t         = NOPAT_t / Invested Capital_t-1
    #
    # g yang dipakai = min(g historis median, g sustainable)
    ebit_h = pd.to_numeric(hist.loc["ebit"], errors="coerce")
    capex_h = pd.to_numeric(hist.loc["capex"], errors="coerce")
    da_h = pd.to_numeric(hist.loc["dep_amort"], errors="coerce")
    nwc_h = pd.to_numeric(hist.loc["nwc"], errors="coerce")
    ic_h = pd.to_numeric(hist.loc["invested_capital"], errors="coerce")

    nopat_h = ebit_h * (1 - t_base)
    rr_vals, roic_vals = [], []
    for i in range(1, len(ebit_h)):
        nop = nopat_h.iloc[i]
        if pd.isna(nop) or nop <= 0:
            continue
        reinv = ((capex_h.iloc[i] if pd.notna(capex_h.iloc[i]) else 0)
                 - (da_h.iloc[i] if pd.notna(da_h.iloc[i]) else 0)
                 + ((nwc_h.iloc[i] - nwc_h.iloc[i - 1])
                    if pd.notna(nwc_h.iloc[i]) and pd.notna(nwc_h.iloc[i - 1]) else 0))
        rr_vals.append(reinv / nop)
        ic_prev = ic_h.iloc[i - 1]
        if pd.notna(ic_prev) and ic_prev > 0:
            roic_vals.append(nop / ic_prev)

    rr_hist = float(np.median(rr_vals)) if rr_vals else np.nan
    roic_hist = float(np.median(roic_vals)) if roic_vals else np.nan

    if np.isfinite(rr_hist) and np.isfinite(roic_hist):
        g_sust = max(rr_hist * roic_hist, 0.0)
        if g_sust < g_hist:
            flags.warn(
                "Growth dibatasi reinvestasi",
                f"Growth historis median {g_hist*100:.2f}% MELEBIHI growth yang "
                f"bisa dibiayai reinvestasi. RR historis {rr_hist*100:.1f}% x "
                f"ROIC {roic_hist*100:.1f}% = {g_sust*100:.2f}%. Growth diturunkan "
                f"ke {g_sust*100:.2f}% agar konsisten secara ekonomi."
            )
            g_base = g_sust
        else:
            g_base = g_hist
    else:
        g_base = g_hist
        rr_hist = np.nan
        roic_hist = np.nan
        flags.warn("Growth dibatasi reinvestasi",
                   "RR atau ROIC historis tidak dapat dihitung. Growth memakai "
                   "median historis tanpa pembatas fundamental.")

    # -------------------------------------------------------------------
    # 4.8 MARGIN TARGET DAN DETEKSI OPERATING LEVERAGE
    # -------------------------------------------------------------------
    # Margin EBIT tidak lagi konstan sepanjang proyeksi. Kalau ada bukti
    # operating leverage, margin di-fade linear dari base menuju margin
    # TERTINGGI yang pernah dicapai emiten, tercapai di tahun terakhir.
    #
    # Bukti operating leverage diuji lewat korelasi Pearson antara revenue
    # dan EBIT margin historis. Logikanya: kalau basis biaya tetap relatif
    # stabil sementara revenue naik, biaya tetap ter-dilusi dan margin
    # mengembang. Pola itu akan muncul sebagai korelasi positif.
    #
    # Aktivasi BERSYARAT. Tanpa bukti korelasi positif, margin tetap flat.
    # Ini mencegah margin expansion dipaksakan pada emiten yang justru
    # marginnya menyusut saat revenue naik, misalnya karena perang harga
    # atau kenaikan biaya bahan baku yang tidak bisa diteruskan ke konsumen.
    #
    # PERINGATAN STATISTIK: dengan hanya 4 periode tahunan, korelasi ini
    # dihitung dari 4 titik data. Itu jumlah yang sangat sedikit dan hasilnya
    # rapuh. Ambang 0.50 dipakai sebagai penyaring kasar, bukan uji signifikan.
    m_target = m_base
    oplev_corr = np.nan
    oplev_detected = False

    if A["margin_expansion_enabled"]:
        rev_s = pd.to_numeric(hist.loc["revenue"], errors="coerce")
        mgn_s = pd.to_numeric(hist.loc["ebit_margin"], errors="coerce")
        pair = pd.concat([rev_s, mgn_s], axis=1).dropna()

        if len(pair) >= 3 and pair.iloc[:, 0].std() > 0 and pair.iloc[:, 1].std() > 0:
            oplev_corr = float(np.corrcoef(pair.iloc[:, 0], pair.iloc[:, 1])[0, 1])

            if np.isfinite(oplev_corr) and oplev_corr >= A["margin_oplev_min_corr"]:
                m_max = float(np.nanmax(m_list)) if len(m_list) else m_base
                m_target = min(max(m_max, m_base), A["margin_target_cap"])
                oplev_detected = True
                flags.warn(
                    "Margin expansion AKTIF",
                    f"Korelasi revenue vs EBIT margin = {oplev_corr:.2f} "
                    f"(ambang {A['margin_oplev_min_corr']:.2f}), terdeteksi "
                    f"operating leverage. Margin di-fade linear dari "
                    f"{m_base*100:.2f}% menuju margin tertinggi historis "
                    f"{m_target*100:.2f}% pada tahun terakhir proyeksi. "
                    f"Basis korelasi hanya {len(pair)} titik data, rapuh secara "
                    f"statistik."
                )
            else:
                flags.warn(
                    "Margin expansion TIDAK AKTIF",
                    f"Korelasi revenue vs EBIT margin = {oplev_corr:.2f}, di bawah "
                    f"ambang {A['margin_oplev_min_corr']:.2f}. Tidak ada bukti "
                    f"operating leverage. Margin ditahan konstan di "
                    f"{m_base*100:.2f}%."
                )

    return {
        "rev_growth":       float(g_base),
        "rev_growth_hist":  float(g_hist),
        "rr_hist":          float(rr_hist) if np.isfinite(rr_hist) else np.nan,
        "roic_hist":        float(roic_hist) if np.isfinite(roic_hist) else np.nan,
        "rev_growth_sd":    float(g_sd),
        "rev_growth_raw":   float(g_raw),
        "ebit_margin":      float(m_base),
        "ebit_margin_target": float(m_target),
        "oplev_corr":       float(oplev_corr) if np.isfinite(oplev_corr) else np.nan,
        "oplev_detected":   bool(oplev_detected),
        "ebit_margin_sd":   float(m_sd),
        "da_ratio":         float(d_base),
        "capex_ratio":      float(c_base),
        "nwc_ratio":        float(w_base),
        "tax_rate":         float(t_base),
        "n_periods":        int(hist.shape[1]),
    }


def drivers_table(drv):
    """Tabel driver untuk ditampilkan ke pengguna."""
    rows = [
        ("Revenue growth historis (median)", f"{drv.get('rev_growth_hist', np.nan)*100:.2f}%",
         f"SD {drv['rev_growth_sd']*100:.2f}%"),
        ("Reinvestment rate historis", f"{drv.get('rr_hist', np.nan)*100:.1f}%", ""),
        ("ROIC historis", f"{drv.get('roic_hist', np.nan)*100:.1f}%", ""),
        ("Revenue growth DIPAKAI", f"{drv['rev_growth']*100:.2f}%",
         "min(historis, RR x ROIC)"),
        ("EBIT margin base (median)", f"{drv['ebit_margin']*100:.2f}%",
         f"SD {drv['ebit_margin_sd']*100:.2f}%"),
        ("EBIT margin target (tahun N)", f"{drv.get('ebit_margin_target', np.nan)*100:.2f}%",
         "aktif" if drv.get("oplev_detected") else "tidak aktif, margin flat"),
        ("Korelasi revenue vs margin", f"{drv.get('oplev_corr', np.nan):.2f}",
         "uji operating leverage"),
        ("D&A / Revenue (MA)", f"{drv['da_ratio']*100:.2f}%", ""),
        ("Capex / Revenue (MA)", f"{drv['capex_ratio']*100:.2f}%", ""),
        ("NWC / Revenue (MA)", f"{drv['nwc_ratio']*100:.2f}%", ""),
        ("Effective tax rate", f"{drv['tax_rate']*100:.2f}%", ""),
    ]
    return pd.DataFrame(rows, columns=["Driver", "Base", "Dispersi"])
