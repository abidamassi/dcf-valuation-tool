"""
=============================================================================
SECTION 3 - SCREENING KELAYAKAN MODEL
=============================================================================
TUJUAN  : Menentukan apakah satu emiten LAYAK dinilai dengan FCFF/WACC DCF.
          Ini bukan screening "saham menarik atau tidak". Ini screening
          "modelnya berlaku atau tidak". Emiten yang gagal akan mendapat
          status CANNOT PROCEED beserta alasan spesifiknya.

          Prinsip: emiten keuangan (bank, asuransi, multifinance) SELALU
          ditolak di sini karena utang bagi mereka adalah bahan baku, bukan
          sumber pendanaan. Enterprise Value tidak punya arti. Mereka akan
          ditangani tool DDM/GGM terpisah.

RUMUS   : Gate 1  Sektor bukan Financial Services
          Gate 2  Jumlah tahun laporan >= 4
          Gate 3  Revenue positif di seluruh periode
          Gate 4  EBIT positif >= 2 dari 3 tahun terakhir
          Gate 5  Market cap >= IDR 1 triliun
          Gate 6  1.0x <= Trailing P/E <= 60.0x
          Gate 7  Total Equity > 0
          Gate 8  Total Debt / (Total Debt + Equity) <= 80%
          Gate 9  Net Debt / EBITDA <= 6.0x
          Gate 10 EBIT / Interest Expense >= 1.0x
          Gate 11 EBITDA periode terakhir > 0

OUTPUT  : dict {passed: bool, status: str, failed_gates: list, detail: DataFrame}
=============================================================================
"""

import numpy as np
import pandas as pd

from config import SCREENING


def run_screening(data, hist):
    """
    Jalankan seluruh gate. Mengembalikan hasil lengkap, bukan hanya lolos
    atau tidak, supaya pengguna tahu gate mana yang gagal dan angkanya berapa.
    """
    S = SCREENING
    results = []          # (no, nama_gate, nilai_aktual, kriteria, lolos)

    def add(no, name, actual, criteria, passed):
        results.append({
            "No": no, "Gate": name, "Nilai": actual,
            "Kriteria": criteria, "Status": "PASS" if passed else "FAIL"
        })

    # ---------------- Gate 1: sektor ----------------
    sector = (data.sector or "").strip()
    industry = (data.industry or "").strip().lower()
    is_financial = sector in S["excluded_sectors"] or any(
        kw in industry for kw in S["excluded_industry_keywords"]
    )
    add(1, "Sektor non-keuangan",
        f"{sector or 'n/a'} / {data.industry or 'n/a'}",
        "Bukan Financial Services", not is_financial)

    # ---------------- Gate 2: kecukupan tahun ----------------
    n_years = hist.shape[1] if hist is not None else 0
    add(2, "Ketersediaan laporan tahunan", f"{n_years} tahun",
        f">= {S['min_annual_years']} tahun", n_years >= S["min_annual_years"])

    if hist is None or n_years == 0:
        return _compile(results, data)

    rev = hist.loc["revenue"]
    ebit = hist.loc["ebit"]
    ebitda = hist.loc["ebitda"]

    # ---------------- Gate 3: revenue positif ----------------
    rev_ok = bool(rev.notna().all() and (rev > 0).all())
    add(3, "Revenue positif seluruh periode",
        "ya" if rev_ok else "tidak / ada NaN", "Semua periode > 0", rev_ok)

    # ---------------- Gate 4: EBIT positif ----------------
    lb = S["ebit_lookback_years"]
    recent_ebit = ebit.iloc[-lb:]
    n_pos = int((recent_ebit > 0).sum())
    add(4, "EBIT positif", f"{n_pos} dari {len(recent_ebit)} tahun terakhir",
        f">= {S['min_ebit_positive_years']} dari {lb} tahun",
        n_pos >= S["min_ebit_positive_years"])

    # ---------------- Gate 5: market cap ----------------
    mcap = data.market_cap
    add(5, "Market cap",
        f"IDR {mcap/1e12:,.2f} tn" if np.isfinite(mcap) else "n/a",
        f">= IDR {S['min_market_cap_idr']/1e12:,.0f} tn",
        bool(np.isfinite(mcap) and mcap >= S["min_market_cap_idr"]))

    # ---------------- Gate 6: P/E berjalan ----------------
    pe = data.trailing_pe
    pe_ok = bool(np.isfinite(pe) and S["pe_min"] <= pe <= S["pe_max"])
    add(6, "Trailing P/E",
        f"{pe:.2f}x" if np.isfinite(pe) else "n/a (negatif atau tidak tersedia)",
        f"{S['pe_min']:.0f}x - {S['pe_max']:.0f}x", pe_ok)

    # ---------------- Gate 7: ekuitas positif ----------------
    eq = float(hist.loc["equity"].iloc[-1]) if pd.notna(hist.loc["equity"].iloc[-1]) else np.nan
    eq_ok = bool(np.isfinite(eq) and eq > 0)
    add(7, "Total ekuitas positif",
        f"IDR {eq/1e12:,.2f} tn" if np.isfinite(eq) else "n/a",
        "> 0 (ekuitas negatif merusak bobot WACC)", eq_ok)

    # ---------------- Gate 8: struktur modal ----------------
    d2c = float(hist.loc["debt_to_cap"].iloc[-1]) if pd.notna(hist.loc["debt_to_cap"].iloc[-1]) else np.nan
    d2c_ok = bool(np.isfinite(d2c) and d2c <= S["max_debt_to_capital"])
    add(8, "Debt / (Debt + Equity)",
        f"{d2c*100:.1f}%" if np.isfinite(d2c) else "n/a",
        f"<= {S['max_debt_to_capital']*100:.0f}%", d2c_ok)

    # ---------------- Gate 9: leverage terhadap EBITDA ----------------
    nde = float(hist.loc["net_debt_ebitda"].iloc[-1]) if pd.notna(hist.loc["net_debt_ebitda"].iloc[-1]) else np.nan
    # Net cash (nilai negatif) otomatis lolos.
    nde_ok = bool(np.isfinite(nde) and nde <= S["max_net_debt_ebitda"])
    add(9, "Net Debt / EBITDA",
        f"{nde:.2f}x" if np.isfinite(nde) else "n/a",
        f"<= {S['max_net_debt_ebitda']:.1f}x (negatif = net cash, lolos)", nde_ok)

    # ---------------- Gate 10: interest coverage ----------------
    int_exp_last = hist.loc["interest_exp"].iloc[-1]
    if pd.isna(int_exp_last) or int_exp_last == 0:
        cov_ok, cov_txt = True, "tidak ada beban bunga material"
    else:
        cov = float(hist.loc["int_coverage"].iloc[-1])
        cov_ok = bool(np.isfinite(cov) and cov >= S["min_interest_coverage"])
        cov_txt = f"{cov:.2f}x"
    add(10, "EBIT / Interest Expense", cov_txt,
        f">= {S['min_interest_coverage']:.1f}x", cov_ok)

    # ---------------- Gate 11: EBITDA positif ----------------
    eb_last = float(ebitda.iloc[-1]) if pd.notna(ebitda.iloc[-1]) else np.nan
    eb_ok = bool(np.isfinite(eb_last) and eb_last > 0)
    add(11, "EBITDA periode terakhir",
        f"IDR {eb_last/1e9:,.0f} bn" if np.isfinite(eb_last) else "n/a",
        "> 0", eb_ok)

    # ---------------- Gate 12: holding company ----------------
    # DCF konsolidasi mengambil 100% arus kas anak usaha lalu mengurangi
    # kepentingan non-pengendali pada NILAI BUKU. Untuk holdco, nilai buku MI
    # jauh berbeda dari nilai ekonomisnya, dan holding discount yang secara
    # historis melekat pada emiten seperti INDF tidak akan pernah tertangkap.
    # Ini FLAG INFORMASIONAL, bukan gate penolak. NCI besar tidak otomatis
    # berarti holding company murni. Bisa juga struktur JV pertambangan yang
    # sah, atau satu anak usaha strategis yang sengaja tidak diakuisisi penuh.
    # Emiten tetap dihitung, rating tetap murni mengikuti threshold
    # BUY/HOLD/SELL. Yang diberikan hanya peringatan agar pengguna memeriksa
    # apakah bridge NCI di nilai buku cukup representatif.
    mi = float(hist.loc["minority"].iloc[-1]) if pd.notna(hist.loc["minority"].iloc[-1]) else 0.0
    mi_ratio = mi / eq if (np.isfinite(eq) and eq > 0) else np.nan
    add(12, "Minority Interest / Ekuitas (informasional)",
        f"{mi_ratio*100:.1f}%" if np.isfinite(mi_ratio) else "n/a",
        "Tidak menolak. Di atas 15% perlu tinjauan SOTP", True)

    if np.isfinite(mi_ratio) and mi_ratio > S["max_minority_to_equity"]:
        data.flags.warn(
            "Struktur NCI",
            f"Kepentingan non-pengendali {mi_ratio*100:.1f}% dari ekuitas, di atas "
            f"ambang {S['max_minority_to_equity']*100:.0f}%. DCF konsolidasi "
            f"mengambil 100% arus kas anak usaha lalu mengurangi NCI pada NILAI "
            f"BUKU. Kalau anak usaha punya valuasi pasar sendiri, selisihnya bisa "
            f"material. Pertimbangkan tinjauan SOTP sebagai pembanding."
        )

    return _compile(results, data)


def _compile(results, data):
    detail = pd.DataFrame(results)
    failed = detail.loc[detail["Status"] == "FAIL", "Gate"].tolist()
    passed = len(failed) == 0

    if passed:
        status = "ELIGIBLE - lanjut ke perhitungan DCF"
    else:
        # Bedakan penolakan karena jenis usaha vs karena fundamental
        if "Sektor non-keuangan" in failed:
            status = ("CANNOT PROCEED - emiten sektor keuangan. "
                      "FCFF/WACC DCF tidak berlaku. Gunakan tool DDM/GGM.")
        elif "Minority Interest / Ekuitas" in failed:
            status = ("CANNOT PROCEED - struktur holding company. Porsi "
                      "kepentingan non-pengendali terlalu besar sehingga DCF "
                      "konsolidasi menghasilkan nilai yang menyesatkan. "
                      "Gunakan pendekatan SOTP.")
        else:
            status = "CANNOT PROCEED - " + "; ".join(failed)

    return {
        "ticker": data.ticker,
        "name": data.name,
        "passed": passed,
        "status": status,
        "failed_gates": failed,
        "detail": detail,
    }
