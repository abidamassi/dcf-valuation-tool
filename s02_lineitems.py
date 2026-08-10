"""
=============================================================================
SECTION 2 - EKSTRAKSI LINE ITEM DAN PEMERIKSAAN KUALITAS DATA
=============================================================================
TUJUAN  : Menarik pos-pos laporan keuangan yang dibutuhkan DCF ke dalam satu
          struktur seragam, dan MENANDAI setiap pos yang kosong (NaN) atau
          bernilai nol. Penandaan ini bukan kosmetik. Interest Expense yang
          NaN akan membuat Cost of Debt salah, dan pengguna harus tahu.

RUMUS   : Turunan yang dihitung di sini
            EBITDA           = EBIT + D&A
            Net Debt         = Total Debt - Cash & Equivalents
            NWC              = Piutang + Persediaan - Utang usaha
            Effective Tax    = Tax Provision / Pretax Income
            Interest Coverage= EBIT / Interest Expense
            D/(D+E)          = Total Debt / (Total Debt + Total Equity)
            Invested Capital = Total Debt + Total Equity - Cash

OUTPUT  : DataFrame `hist` (baris = pos, kolom = tahun, satuan IDR),
          dan flag terisi di data.flags.
=============================================================================
"""

import numpy as np
import pandas as pd

from config import ASSUMPTIONS
from utils import pick_row, safe_div


# -----------------------------------------------------------------------
# 2.1 KAMUS LABEL YFINANCE
# -----------------------------------------------------------------------
# yfinance tidak konsisten menamai baris. Urutan kandidat = urutan prioritas.
LABELS = {
    # Income statement
    "revenue":      ["Total Revenue", "Operating Revenue", "Revenue"],
    "cogs":         ["Cost Of Revenue", "Cost Of Goods Sold"],
    "gross_profit": ["Gross Profit"],
    "ebit":         ["Operating Income", "EBIT", "Operating Revenue"],
    "pretax":       ["Pretax Income", "Income Before Tax"],
    "tax":          ["Tax Provision", "Income Tax Expense"],
    "net_income":   ["Net Income", "Net Income Common Stockholders",
                     "Net Income From Continuing Operation Net Minority Interest"],
    "interest_exp": ["Interest Expense", "Interest Expense Non Operating",
                     "Net Interest Income"],

    # Cash flow
    "dep_amort":    ["Depreciation And Amortization",
                     "Depreciation Amortization Depletion",
                     "Depreciation",
                     "Depreciation Depletion And Amortization",
                     "Depreciation Income Statement",
                     "Depreciation And Amortization In Income Statement",
                     "Amortization Of Intangibles"],
    "capex":        ["Capital Expenditure", "Purchase Of PPE",
                     "Net PPE Purchase And Sale", "Purchase Of Business"],

    # Baris tambahan HANYA untuk derivasi D&A fallback (EBITDA - EBIT)
    "ebitda_reported": ["EBITDA", "Normalized EBITDA"],

    # Balance sheet
    "cash":         ["Cash And Cash Equivalents",
                     "Cash Cash Equivalents And Short Term Investments",
                     "Cash Financial"],
    "total_debt":   ["Total Debt"],
    "short_debt":   ["Current Debt", "Current Debt And Capital Lease Obligation",
                     "Short Term Debt"],
    "long_debt":    ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "equity":       ["Stockholders Equity", "Common Stock Equity",
                     "Total Equity Gross Minority Interest"],
    "minority":     ["Minority Interest"],
    "receivable":   ["Accounts Receivable", "Receivables",
                     "Gross Accounts Receivable"],
    "inventory":    ["Inventory"],
    "payable":      ["Accounts Payable", "Payables",
                     "Payables And Accrued Expenses"],
    "net_ppe":      ["Net PPE", "Net Property Plant And Equipment"],
    "total_assets": ["Total Assets"],
}

# Pos yang kalau hilang membuat DCF tidak bisa jalan sama sekali.
# dep_amort SENGAJA tidak dimasukkan di sini. Kalau hilang, ada dua jaring
# pengaman: (1) derivasi dari EBITDA - EBIT kalau EBITDA dilaporkan, dan
# (2) fallback ke 0% dari revenue di Section 4 dengan flag eksplisit.
# Sebelumnya dep_amort ada di CRITICAL dan menghentikan seluruh pipeline
# hanya karena satu baris cashflow tidak ketemu labelnya, walau ada
# fallback yang aman di bawahnya. Ini bug yang sudah diperbaiki.
CRITICAL = ["revenue", "ebit", "capex", "equity", "cash"]


# -----------------------------------------------------------------------
# 2.2 EKSTRAKSI
# -----------------------------------------------------------------------
def build_history(data):
    """
    Bangun DataFrame historis dari objek CompanyData hasil Section 1.
    Mengembalikan (hist, ok). `ok` False kalau pos kritikal tidak ada.
    """
    flags = data.flags
    src = {
        "income":   data.income,
        "balance":  data.balance,
        "cashflow": data.cashflow,
    }
    where = {
        "revenue": "income", "cogs": "income", "gross_profit": "income",
        "ebit": "income", "pretax": "income", "tax": "income",
        "net_income": "income", "interest_exp": "income",
        "dep_amort": "cashflow", "capex": "cashflow",
        "cash": "balance", "total_debt": "balance", "short_debt": "balance",
        "long_debt": "balance", "equity": "balance", "minority": "balance",
        "receivable": "balance", "inventory": "balance", "payable": "balance",
        "net_ppe": "balance", "total_assets": "balance",
        "ebitda_reported": "income",
    }

    # Sumbu tahun diambil dari income statement
    if data.income is None or data.income.empty:
        flags.missing("Income statement")
        return None, False
    years = list(data.income.columns)

    rows = {}
    for key, candidates in LABELS.items():
        series = pick_row(src[where[key]], candidates)
        if series is None:
            rows[key] = pd.Series([np.nan] * len(years), index=years)
            if key in CRITICAL:
                flags.missing(key, "Pos kritikal tidak ditemukan di yfinance")
            elif key in ("dep_amort", "ebitda_reported"):
                pass    # ditangani alur fallback D&A, flag dicatat di sana
            else:
                flags.missing(key)
        else:
            rows[key] = series.reindex(years)

    hist = pd.DataFrame(rows).T
    hist = hist[sorted(hist.columns)]           # kronologis

    # ---- buang periode yang revenue-nya kosong ----
    # yfinance kadang mengembalikan satu kolom tahun tambahan yang datanya
    # nyaris seluruhnya NaN (periode tertua di luar cakupan, atau kolom TTM
    # parsial). Kolom seperti ini merusak moving average kalau dibiarkan.
    empty_years = hist.columns[hist.loc["revenue"].isna()]
    if len(empty_years) > 0:
        flags.warn("Periode kosong",
                   f"{len(empty_years)} periode dibuang karena revenue kosong: "
                   f"{[str(c)[:10] for c in empty_years]}")
        hist = hist.drop(columns=empty_years)

    # ---- normalisasi tanda ----
    # Capex di yfinance bertanda negatif (arus keluar). Kita simpan positif.
    hist.loc["capex"] = hist.loc["capex"].abs()
    # Interest expense kadang negatif kadang positif. Simpan positif.
    hist.loc["interest_exp"] = hist.loc["interest_exp"].abs()
    hist.loc["dep_amort"] = hist.loc["dep_amort"].abs()

    # ---- fallback total debt ----
    td = hist.loc["total_debt"]
    if td.isna().all():
        sd = hist.loc["short_debt"].fillna(0)
        ld = hist.loc["long_debt"].fillna(0)
        combined = sd + ld
        if combined.abs().sum() > 0:
            hist.loc["total_debt"] = combined
            flags.warn("total_debt", "Dijumlahkan dari Current Debt + Long Term Debt.")
        else:
            hist.loc["total_debt"] = 0.0
            flags.zero("total_debt", "Tidak ada data utang. Diasumsikan nol, verifikasi.")

    hist.loc["minority"] = hist.loc["minority"].fillna(0.0)

    # ---- fallback D&A berlapis ----
    # Baris "EBITDA" di yfinance BUKAN selalu EBIT + D&A murni. Sering itu
    # versi normalized yang sudah menyerap pos non-operasional. Derivasi
    # EBITDA dikurangi EBIT karena itu WAJIB divalidasi silang.
    #
    # Uji: D&A / Net PP&E harus berada di rentang wajar. Terlalu tinggi
    # berarti derivasi menyerap beban non-penyusutan. Terlalu rendah berarti
    # baris EBITDA-nya kosong atau salah.
    #
    # Bukti empiris yang memicu perbaikan ini:
    #   MAPA  derivasi menghasilkan D&A/Revenue 6.79%, realitas sekitar 2.8%
    #   INDF  derivasi menghasilkan D&A/Revenue 0.22%, mustahil untuk
    #         manufaktur seukuran itu
    if hist.loc["dep_amort"].isna().all():
        eb_rep = hist.loc["ebitda_reported"]
        derived_ok = False

        if not eb_rep.isna().all():
            derived = (eb_rep - hist.loc["ebit"]).clip(lower=0)
            ppe = hist.loc["net_ppe"]
            ratio = (derived / ppe).replace([np.inf, -np.inf], np.nan).dropna()

            if len(ratio) > 0:
                med = float(ratio.median())
                lo = ASSUMPTIONS["da_over_netppe_floor"]
                hi = ASSUMPTIONS["da_over_netppe_cap"]
                if lo <= med <= hi:
                    hist.loc["dep_amort"] = derived
                    derived_ok = True
                    flags.warn("dep_amort",
                               f"Tidak ada baris D&A di cashflow. Diderivasi dari "
                               f"EBITDA dikurangi EBIT. Lulus uji silang: "
                               f"D&A/Net PP&E = {med*100:.1f}% (wajar).")
                else:
                    flags.warn("dep_amort",
                               f"Derivasi EBITDA dikurangi EBIT DITOLAK. "
                               f"D&A/Net PP&E hasil derivasi = {med*100:.1f}%, "
                               f"di luar rentang wajar {lo*100:.0f}-{hi*100:.0f}%. "
                               f"Baris EBITDA yfinance kemungkinan versi normalized "
                               f"yang menyerap pos non-operasional.")

        if not derived_ok:
            # Asumsi steady state: maintenance capex kira-kira sebesar D&A.
            # Konsekuensinya D&A dan Capex saling meniadakan di FCFF, sehingga
            # FCFF = NOPAT dikurangi delta NWC. Konservatif dan transparan.
            cx = hist.loc["capex"]
            if not cx.isna().all():
                hist.loc["dep_amort"] = cx
                flags.warn("dep_amort",
                           "D&A diproksi SAMA DENGAN Capex (asumsi steady state). "
                           "Akibatnya D&A dan Capex saling meniadakan di FCFF, "
                           "sehingga FCFF = NOPAT dikurangi delta NWC. Ini pilihan "
                           "konservatif, bukan angka laporan.")
            else:
                flags.warn("dep_amort",
                           "D&A dan Capex sama-sama tidak tersedia. FCFF tidak "
                           "dapat dihitung dengan andal.")

    # -------------------------------------------------------------------
    # 2.3 TURUNAN
    # -------------------------------------------------------------------
    hist.loc["ebitda"] = hist.loc["ebit"] + hist.loc["dep_amort"].fillna(0)
    hist.loc["net_debt"] = hist.loc["total_debt"].fillna(0) - hist.loc["cash"].fillna(0)

    nwc = (hist.loc["receivable"].fillna(0)
           + hist.loc["inventory"].fillna(0)
           - hist.loc["payable"].fillna(0))
    if (hist.loc["receivable"].isna().all() and hist.loc["inventory"].isna().all()):
        flags.warn("NWC", "Piutang dan persediaan tidak tersedia. NWC dianggap nol, "
                          "delta working capital tidak akan dimodelkan.")
        nwc = pd.Series(0.0, index=hist.columns)
    hist.loc["nwc"] = nwc

    hist.loc["ebit_margin"] = hist.loc["ebit"] / hist.loc["revenue"]
    hist.loc["capex_ratio"] = hist.loc["capex"] / hist.loc["revenue"]
    hist.loc["da_ratio"] = hist.loc["dep_amort"] / hist.loc["revenue"]
    hist.loc["nwc_ratio"] = hist.loc["nwc"] / hist.loc["revenue"]
    hist.loc["eff_tax"] = hist.loc["tax"] / hist.loc["pretax"]
    hist.loc["int_coverage"] = hist.loc["ebit"] / hist.loc["interest_exp"]
    hist.loc["debt_to_cap"] = hist.loc["total_debt"].fillna(0) / (
        hist.loc["total_debt"].fillna(0) + hist.loc["equity"]
    )
    hist.loc["net_debt_ebitda"] = hist.loc["net_debt"] / hist.loc["ebitda"]
    hist.loc["invested_capital"] = (hist.loc["total_debt"].fillna(0)
                                    + hist.loc["equity"]
                                    - hist.loc["cash"].fillna(0))
    hist.loc["rev_growth"] = hist.loc["revenue"].pct_change()

    # -------------------------------------------------------------------
    # 2.4 PEMERIKSAAN KUALITAS
    # -------------------------------------------------------------------
    # dep_amort SENGAJA tidak diperiksa di sini. Pos itu punya alur fallback
    # sendiri di atas yang sudah mencatat satu flag penjelas. Memeriksanya
    # lagi di sini menghasilkan flag MISSING dobel yang menyesatkan, seolah
    # datanya hilang total padahal sudah ditangani.
    for key in ["revenue", "ebit", "capex", "cash", "equity",
                "total_debt", "interest_exp", "tax", "pretax", "net_income"]:
        flags.check_series(hist.loc[key], key)

    ok = True
    for key in CRITICAL:
        if hist.loc[key].isna().all():
            ok = False

    return hist, ok


# -----------------------------------------------------------------------
# 2.5 SNAPSHOT PERIODE TERAKHIR
# -----------------------------------------------------------------------
def latest_snapshot(hist):
    """Ambil kolom terakhir sebagai posisi neraca terkini."""
    last = hist.columns[-1]
    def g(k, default=np.nan):
        v = hist.loc[k, last]
        return float(v) if pd.notna(v) else default
    return {
        "period":       str(last)[:10],
        "revenue":      g("revenue"),
        "ebit":         g("ebit"),
        "ebitda":       g("ebitda"),
        "cash":         g("cash", 0.0),
        "total_debt":   g("total_debt", 0.0),
        "net_debt":     g("net_debt", 0.0),
        "equity":       g("equity"),
        "minority":     g("minority", 0.0),
        "nwc":          g("nwc", 0.0),
        "net_income":   g("net_income"),
        "invested_capital": g("invested_capital"),
    }
