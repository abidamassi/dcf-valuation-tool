# DCF Tool - Fase 1 (Engine)

Mesin perhitungan DCF FCFF/WACC untuk emiten IDX non-keuangan. Data dari yfinance, seluruh angka dinormalisasi ke IDR. Fase ini adalah engine murni. Slider dan tampilan web menyusul di fase berikutnya.

## Peta modul

| File | Section | Isi |
|---|---|---|
| `config.py` | - | Seluruh asumsi dan threshold. Satu-satunya tempat angka boleh diubah. |
| `utils.py` | - | Helper pencarian label yfinance, pembagian aman, pencatatan flag. |
| `s01_fetch.py` | 1 | Normalisasi ticker ke `.JK`, tarik 3 laporan keuangan, konversi USD ke IDR. |
| `s02_lineitems.py` | 2 | Ekstraksi pos, turunan (EBITDA, NWC, ROIC, coverage), penandaan NaN dan nol. |
| `s03_screening.py` | 3 | 11 gate kelayakan model. Gagal di sini berarti `CANNOT PROCEED`. |
| `s04_drivers.py` | 4 | Driver moving average dan standar deviasinya. |
| `s05_beta.py` | 5 | Regresi mingguan 3 tahun vs `^JKSE`, Blume adjusted. |
| `s06_wacc.py` | 6 | CAPM, Cost of Debt dari data internal, WACC. |
| `s07_forecast.py` | 7 | Proyeksi revenue fade, EBIT, NOPAT, capex, NWC, FCFF. |
| `s08_terminal.py` | 8 | Gordon Growth, cross-check implied exit EV/EBITDA. |
| `s09_valuation.py` | 9 | Diskonto mid-year, EV, bridge ke equity value, fair value per saham. |
| `s10_recommendation.py` | 10 | BUY / HOLD / SELL. |
| `s11_sensitivity.py` | 11 | Grid 5x5 WACC x terminal growth. |
| `s12_scenario.py` | 12 | Bull / Base / Bear dari standar deviasi historis. |
| `s13_report.py` | 13 | Perakitan laporan teks dan disclaimer. |
| `universe.py` | - | Daftar ticker batch. **Wajib diganti dengan konstituen resmi.** |
| `main.py` | - | Orkestrator. Tidak berisi rumus. |
| `test_math.py` | - | Validasi seluruh rumus dengan data sintetis, tanpa jaringan. |
| `app.py` | UI | Aplikasi Streamlit. Sidebar 4 slider, laporan urut section. |
| `theme.py` | UI | Design token, CSS kustom, layout Plotly. |
| `charts.py` | UI | Empat chart Plotly: proyeksi, waterfall, heatmap, skenario. |
| `.streamlit/config.toml` | UI | Tema dasar Streamlit. |
| `requirements.txt` | - | Dependensi untuk deploy. |

## Urutan alur

```
1 Fetch + IDR  ->  2 Line item + flag  ->  3 Screening  --gagal-->  STOP
                                              |
                                            lolos
                                              v
4 Driver MA  ->  5 Beta  ->  6 WACC  ->  7 FCFF  ->  8 Terminal Value
                                                          |
                                                          v
                    9 EV & equity value  ->  10 Rating  ->  11 Sensitivity
                                                                  |
                                                                  v
                                              12 Skenario  ->  13 Laporan
```

## Web app (Streamlit)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sidebar berisi input ticker (cukup kode IDX, `.JK` ditambahkan otomatis) dan empat slider: risk-free rate, equity risk premium, terminal growth, dan horizon proyeksi. Tekan **Run analysis** untuk menjalankan.

Driver operasional (growth, margin, capex, working capital, pajak, beta) sengaja tidak dijadikan slider. Semuanya diturunkan dari lapkeu emiten dan dikunci pembatas RR x ROIC.

### Struktur halaman

Masthead emiten, screening kelayakan (Section 3), peringatan kualitas data, verdict BUY/HOLD/SELL, driver historis beserta catatan keputusan (Section 4), beta dan cost of capital (Section 5-6), proyeksi FCFF dengan chart (Section 7), terminal value (Section 8), waterfall EV ke equity value (Section 9), heatmap sensitivity (Section 11), chart skenario (Section 12), keterbatasan model, lalu disclaimer.

### Caching

Fetch yfinance dan regresi beta di-cache per ticker selama satu jam. Menggeser slider hanya menghitung ulang aritmatikanya, tidak memanggil yfinance lagi. Praktisnya: ganti ticker terasa menunggu, geser slider terasa instan.

### Deploy gratis ke Streamlit Community Cloud

1. Push folder ini ke repositori GitHub (boleh private)
2. Buka share.streamlit.io, sign in dengan GitHub
3. New app, pilih repo, set Main file path ke `app.py`
4. Deploy. `requirements.txt` dan `.streamlit/config.toml` terbaca otomatis

Tidak perlu kartu kredit. Aplikasi tidur kalau lama tidak dipakai dan bangun sendiri saat dibuka.

### Identitas visual

Navy `#0B1F3A`, ice blue `#A9C9E8`, Poppins via Google Fonts, pill label bernomor mengikuti urutan section, chart Plotly. Semua token warna ada di `theme.py`.

## Cara pakai di Colab

```python
!pip install yfinance -q

# Upload folder dcf_tool, lalu
import sys
sys.path.insert(0, "/content/dcf_tool")

from main import analyze_ticker, print_report, batch_screen

# Satu emiten
r = analyze_ticker("mapa")          # otomatis jadi MAPA.JK
print_report(r)

# Ubah asumsi tanpa menyentuh config.py
r = analyze_ticker("TLKM", rf=0.070, erp=0.075, terminal_g=0.035, years=7)
print_report(r)

# Batch seluruh universe
df = batch_screen()
df[df["Rating"] == "BUY"]
```

Verifikasi rumus tanpa jaringan:

```bash
python test_math.py
```

## Gate screening

| # | Gate | Kriteria |
|---|---|---|
| 1 | Sektor | Bukan Financial Services (bank, asuransi, multifinance) |
| 2 | Laporan tahunan | >= 4 tahun |
| 3 | Revenue | Positif seluruh periode |
| 4 | EBIT | Positif >= 2 dari 3 tahun terakhir |
| 5 | Market cap | >= IDR 1 triliun |
| 6 | Trailing P/E | 1x sampai 60x |
| 7 | Total ekuitas | > 0 |
| 8 | D/(D+E) | <= 80% |
| 9 | Net Debt/EBITDA | <= 6.0x (net cash otomatis lolos) |
| 10 | EBIT/Interest | >= 1.0x |
| 11 | EBITDA terakhir | > 0 |
| 12 | Minority Interest / Ekuitas | Informasional saja, tidak menolak. Di atas 15% diberi flag tinjauan SOTP |

Gate 7 sampai 11 adalah syarat agar FCFF/WACC menghasilkan angka yang bermakna. Ekuitas negatif merusak bobot WACC, dan emiten dengan leverage ekstrem menghasilkan equity value residual yang meledak terhadap perubahan asumsi kecil.

## Perbaikan kalibrasi (revisi 2)

Uji pertama pada MAPA, ASII, dan INDF menghasilkan upside 137%, 134%, dan 330%. Seluruh rumus sudah benar dan lulus verifikasi manual. Yang salah adalah input yang masuk ke rumus. Tujuh perbaikan berikut menutup celahnya.

| # | Masalah | Bukti | Perbaikan |
|---|---|---|---|
| 1 | Growth tanpa reinvestasi yang membiayainya | MAPA tumbuh 25% dengan RR 20.6% dan ROIC 30.5%, padahal butuh RR 82% | `g = min(g historis, RR x ROIC)` |
| 2 | Mean menyerap rebound pascapandemi | MAPA mean 25.76% vs realisasi FY25 +12.2% | Median menggantikan mean di seluruh driver |
| 3 | Capex di bawah D&A padahal tumbuh | MAPA capex 5.81% vs D&A 6.79% | Capex dilantai minimal sebesar D&A saat growth positif |
| 4 | D&A derivasi tidak dapat dipercaya | MAPA 6.79% (realitas ~2.8%), INDF 0.22% (mustahil) | Uji silang D&A/Net PP&E harus 5-35%, kalau gagal diproksi ke capex |
| 5 | Cost of Debt di bawah risk-free rate | ASII Kd 3.75% dengan Rf 6.50% | Kd dilantai di Rf + 100bps |
| 6 | Beta tidak bermakna tetap dipakai | MAPA beta 0.694 dengan R-squared 0.059 | R-squared di bawah 0.20 ditolak, diganti 1.00 |
| 7 | Fade justru mengakselerasi growth | ASII 2.42% naik ke 4.00% menuju perpetuitas | Terminal growth dibatasi tidak melebihi growth tahun pertama |

Ditambah spread minimum WACC dikurangi terminal growth dinaikkan dari 50bps ke 400bps, karena INDF dengan spread 342bps menghasilkan kontribusi terminal value 84.5% terhadap EV.

Efek pada data sintetis: growth turun dari 10% ke 5.32%, fair value dari IDR 1,700 ke IDR 1,537.

## Perbaikan revisi 3

| # | Perubahan | Isi |
|---|---|---|
| 1 | Ekstraksi | `cfo` dibuang (tidak dipakai rumus manapun). Logging `dep_amort` digabung jadi satu baris, tidak lagi dobel MISSING dan WARN |
| 2 | Gate 12 NCI | Dari hard reject jadi flag informasional. NCI besar tidak otomatis holding company, bisa juga struktur JV yang sah. Rating tetap murni threshold BUY/HOLD/SELL |
| 3 | Beta | Regresi harian 1 tahun (~252 observasi) vs `^JKSE`, sebelumnya mingguan 3 tahun. Blume adjustment tetap. Hasil di bawah 1.0 dilantai ke 1.20. Jalur R-squared reject juga memakai 1.20 |
| 4 | ERP | Default 7.00% turun ke 4.00% |
| 5 | Margin EBIT | Tidak lagi konstan. Fade linear dari margin base (median) ke margin tertinggi historis, tercapai di tahun N. Aktivasi bersyarat korelasi revenue vs margin >= 0.50 |

### Catatan metodologis atas ERP 4.00%

ERP 4.00% mendekati level mature market (US, Eropa Barat). Referensi Damodaran untuk Indonesia umumnya 6.5% sampai 8% karena memuat country risk premium. Penurunan ini menaikkan fair value lewat kanal diskonto, bukan karena FCFF membaik. Pada data sintetis, fair value naik dari IDR 1,537 ke IDR 2,239 (+45.7%) semata dari perubahan ERP ini.

Kebetulan yang perlu dicatat: efek ERP turun sebagian ternetralkan oleh lantai beta 1.20. Untuk profil seperti MAPA, Cost of Equity lama 11.36% (beta 0.694 x ERP 7%) versus baru 11.30% (beta 1.20 x ERP 4%), nyaris identik. Untuk emiten yang beta regresinya lebih tinggi, Ke akan turun lebih terasa.

### Cara mematikan margin expansion

Set `margin_expansion_enabled` ke `False` di `config.py`, atau naikkan `margin_oplev_min_corr` agar syaratnya lebih ketat.

## Asumsi default

Risk-free 6.50%, ERP 4.00%, size premium 0%, beta lantai 1.20, horizon 5 tahun, terminal growth 4.00%, konvensi mid-year. Tarif pajak dan cost of debt diturunkan dari laporan keuangan emiten, bukan dari sumber eksternal.

## Yang belum ditangani (fase 2)

- Corporate action dan peristiwa setelah tanggal neraca
- Aset non-operasional (entitas asosiasi, properti investasi) tidak ditambahkan ke equity value, jadi emiten holding cenderung undervalued oleh model ini
- Shares outstanding basis dasar, bukan fully diluted
- Konversi USD ke IDR memakai kurs spot untuk seluruh periode historis, bukan kurs rata-rata per tahun
- Emiten keuangan (menunggu tool DDM/GGM terpisah)

## Disclaimer

Disclaimer On. Output dihasilkan model otomatis berbasis data publik dan asumsi pengguna. Angka belum diverifikasi terhadap laporan keuangan resmi dan bukan rekomendasi investasi. Untuk analisis internal.
