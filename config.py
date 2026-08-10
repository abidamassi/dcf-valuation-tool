"""
=============================================================================
CONFIG - PUSAT ASUMSI DAN THRESHOLD
=============================================================================
TUJUAN  : Menyimpan seluruh angka asumsi dan batas screening di satu tempat.
          Tidak ada angka ajaib (magic number) yang boleh ditulis langsung di
          modul lain. Semua yang bisa digeser nanti di slider, ada di sini.
RUMUS   : Tidak ada. Ini file konstanta.
OUTPUT  : Dictionary ASSUMPTIONS dan SCREENING.
=============================================================================
"""

# -----------------------------------------------------------------------
# A. ASUMSI COST OF CAPITAL (kandidat slider fase 2)
# -----------------------------------------------------------------------
ASSUMPTIONS = {
    # Risk-free rate. Default proxy INDOGB 10Y. Diisi manual, tidak di-fetch.
    "risk_free_rate":       0.065,   # 6.50%   slider 0.050 - 0.090
    # Equity Risk Premium. Diturunkan dari 7.00% ke 4.00% atas keputusan
    # pengguna. CATATAN METODOLOGIS: 4.00% mendekati level ERP mature market
    # (US, Eropa Barat). Referensi Damodaran untuk Indonesia umumnya 6.5-8%
    # karena memuat country risk premium. Penurunan ini menaikkan fair value
    # lewat kanal diskonto, BUKAN karena FCFF membaik. Kalau upside terlihat
    # besar, sumbernya kemungkinan besar dari sini.
    "equity_risk_premium":  0.040,   # 4.00%   slider 0.030 - 0.100
    # Premi tambahan untuk small/mid cap. Default 0 (konservatif = tidak ada).
    "size_premium":         0.000,   # 0.00%   slider 0.000 - 0.030

    # Batas wajar hasil perhitungan. Kalau tembus, di-clip dan diberi flag.
    "beta_floor":           0.40,
    "beta_cap":             2.20,
    "tax_floor":            0.15,
    "tax_cap":              0.30,
    "tax_fallback":         0.22,    # Tarif PPh Badan Indonesia (UU HPP 7/2021)
    # Lantai Cost of Debt relatif terhadap Rf. Tidak ada korporasi yang
    # meminjam di bawah pemerintahnya sendiri. Sebelumnya lantai absolut 3.0%
    # membuat ASII keluar Kd 3.75% padahal Rf 6.50%, jelas mustahil.
    "cod_spread_floor":     0.010,   # Kd minimum = Rf + 100bps
    "cod_floor":            0.030,
    "cod_cap":              0.200,

    # Beta dengan daya jelas rendah tidak dipakai. R-squared di bawah ambang
    # ini berarti pergerakan saham nyaris tidak dijelaskan pasar, sehingga
    # beta hasil regresi tidak bermakna. Diganti 1.0 dengan flag.
    "beta_min_r2":          0.20,

    # Beta yang jatuh di bawah 1.0 setelah Blume adjustment diganti dengan
    # nilai ini. Dipakai juga sebagai fallback ketika regresi ditolak karena
    # R-squared rendah. Alasan: regresi harian terhadap IHSG cenderung
    # meng-understate beta emiten non-keuangan karena indeks didominasi bank,
    # ditambah bias non-synchronous trading pada saham berlikuiditas tipis.
    "beta_fallback":        1.20,

    # Periode dan frekuensi regresi beta.
    "beta_period":          "1y",
    "beta_interval":        "1d",    # harian, sekitar 252 observasi
    "wacc_floor":           0.060,
    "wacc_cap":             0.250,

    # -------------------------------------------------------------------
    # B. ASUMSI PROYEKSI
    # -------------------------------------------------------------------
    "forecast_years":       5,       # slider 5 - 10
    "terminal_growth":      0.040,   # 4.00%   slider 0.000 - 0.060
    "mid_year_convention":  True,    # Cash flow dianggap terjadi di tengah tahun

    # Spread minimum WACC dikurangi terminal growth. Sebelumnya 50bps, terlalu
    # longgar: INDF keluar spread 342bps dan terminal value melonjak jadi 84.5%
    # dari EV. Di bawah 400bps, Gordon Growth terlalu sensitif untuk dipakai.
    "min_wacc_g_spread":    0.040,   # 400bps

    # Terminal growth tidak boleh melampaui growth tahun pertama. Tanpa batas
    # ini, fade justru MENGAKSELERASI pertumbuhan menuju perpetuitas, seperti
    # yang terjadi pada ASII (2.42% naik ke 4.00%). Terminal growth adalah
    # batas atas, bukan target yang dikejar.
    "cap_terminal_at_g1":   True,

    # Validasi silang D&A hasil derivasi terhadap Net PP&E. Di luar rentang
    # ini, derivasi EBITDA dikurangi EBIT dianggap tidak dapat dipercaya.
    "da_over_netppe_floor": 0.05,
    "da_over_netppe_cap":   0.35,

    # ---------------- MARGIN EXPANSION ----------------
    # Margin EBIT tidak lagi konstan. Kalau terdeteksi operating leverage di
    # data historis, margin di-fade LINEAR dari margin base (median historis)
    # menuju margin TERTINGGI yang pernah dicapai emiten, tercapai di tahun N.
    #
    # Aktivasi BERSYARAT, bukan otomatis untuk semua emiten. Syaratnya ada
    # korelasi positif antara revenue dan EBIT margin di data historis. Tanpa
    # bukti itu, margin tetap flat seperti sebelumnya. Ini mencegah margin
    # expansion dipaksakan pada emiten yang justru marginnya menyusut saat
    # revenue naik.
    "margin_expansion_enabled":  True,
    "margin_oplev_min_corr":     0.50,   # korelasi revenue vs margin minimum
    "margin_target_cap":         0.60,   # margin target maksimum 60%, rem waras

    # Batas wajar growth revenue tahun-1 hasil moving average historis.
    # Ini rem konservatif supaya emiten yang kebetulan tumbuh 80% dua tahun
    # terakhir tidak diekstrapolasi jadi selamanya.
    "rev_growth_floor":    -0.100,   # -10%
    "rev_growth_cap":       0.250,   # +25%

    # Batas wajar rasio driver hasil moving average.
    "capex_ratio_cap":      0.300,   # Capex maksimum 30% dari revenue
    "nwc_ratio_floor":     -0.300,
    "nwc_ratio_cap":        0.600,

    # -------------------------------------------------------------------
    # C. PARAMETER SKENARIO DAN SENSITIVITY
    # -------------------------------------------------------------------
    "scenario_sd_multiple": 1.0,     # Bull/Bear = Base +/- 1 standar deviasi
    "scenario_g_shift":     0.005,   # Terminal growth digeser +/- 50bps
    # Lantai standar deviasi. Kalau volatilitas historis mendekati nol,
    # skenario Bull dan Bear akan identik dengan Base dan tidak informatif.
    "min_growth_sd":        0.030,   # 300bps
    "min_margin_sd":        0.010,   # 100bps
    "sens_wacc_step":       0.005,   # Grid WACC +/- 50bps
    "sens_g_step":          0.0025,  # Grid terminal growth +/- 25bps
    "sens_steps":           2,       # 2 langkah tiap arah, jadi grid 5x5

    # -------------------------------------------------------------------
    # D. AMBANG REKOMENDASI
    # -------------------------------------------------------------------
    "buy_threshold":        0.10,    # Upside > +10%  -> BUY
    "sell_threshold":      -0.10,    # Upside < -10%  -> SELL
                                     # Di antaranya   -> HOLD
}

# -----------------------------------------------------------------------
# E. GATE SCREENING
# -----------------------------------------------------------------------
SCREENING = {
    # Gate 1 - Kelayakan model (FCFF/WACC tidak berlaku untuk lembaga keuangan)
    "excluded_sectors": ["Financial Services", "Financial"],
    "excluded_industry_keywords": [
        "bank", "insurance", "asuransi", "capital markets", "credit services",
        "asset management", "financial data", "mortgage", "multifinance",
        "financial conglomerates", "shell companies",
    ],

    # Gate 2 - Kecukupan data
    "min_annual_years": 4,           # Minimal 4 tahun laporan tahunan lengkap

    # Gate 3 - Kelayakan operasional
    "min_ebit_positive_years": 2,    # EBIT positif minimal 2 dari 3 tahun terakhir
    "ebit_lookback_years": 3,

    # Gate 4 - Ukuran dan valuasi
    "min_market_cap_idr": 1_000_000_000_000,   # IDR 1 triliun
    "pe_min": 1.0,
    "pe_max": 60.0,

    # Gate 5 - Struktur modal (syarat agar FCFF/WACC menghasilkan angka
    #          yang bermakna, bukan residual yang meledak)
    "require_positive_equity": True,       # Ekuitas negatif merusak bobot WACC
    "max_debt_to_capital": 0.80,           # D/(D+E) maksimum 80%
    "max_net_debt_ebitda": 6.0,            # Net Debt/EBITDA maksimum 6.0x
    "min_interest_coverage": 1.0,          # EBIT/Interest minimum 1.0x
    "require_positive_ebitda": True,

    # Gate 12 - Holding company
    # DCF konsolidasi mengambil 100% arus kas anak usaha lalu mengurangi
    # kepentingan non-pengendali pada NILAI BUKU. Untuk holdco, selisih antara
    # nilai buku MI dan nilai ekonomisnya besar, dan holding discount yang
    # secara historis melekat pada emiten seperti INDF dan ASII tidak akan
    # pernah tertangkap. Ditolak, bukan dipaksakan.
    "max_minority_to_equity": 0.15,
}

# -----------------------------------------------------------------------
# F. KURS FALLBACK
# -----------------------------------------------------------------------
# Dipakai HANYA kalau fetch USDIDR dari yfinance gagal.
# WAJIB DIVERIFIKASI SEBELUM DIPAKAI. Angka ini bukan data, ini placeholder.
FALLBACK_USDIDR = 16_000.0

# -----------------------------------------------------------------------
# G. DISCLAIMER
# -----------------------------------------------------------------------
DISCLAIMER = (
    "Disclaimer On. Output ini dihasilkan oleh model otomatis berbasis data "
    "publik yfinance dan asumsi yang diinput pengguna. Angka belum diverifikasi "
    "terhadap laporan keuangan resmi, belum memperhitungkan corporate action "
    "maupun peristiwa setelah tanggal neraca, dan bukan merupakan rekomendasi "
    "investasi. Untuk keperluan analisis internal."
)
