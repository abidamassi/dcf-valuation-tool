"""
=============================================================================
UNIVERSE - DAFTAR EMITEN UNTUK BATCH SCREENING
=============================================================================
TUJUAN  : Menyediakan daftar ticker yang akan dijalankan secara batch.

PERINGATAN DATA:
    Konstituen Kompas100 direvisi dua kali setahun (Februari dan Agustus)
    oleh BEI bersama Harian Kompas. Daftar di bawah BUKAN daftar resmi dan
    BUKAN daftar terkini. Ini hanya contoh untuk menguji pipeline.

    SEBELUM DIPAKAI SERIUS: ganti KOMPAS100 dengan konstituen resmi.
    Sumber: idx.co.id, pengumuman indeks, atau terminal Bloomberg.
    Format cukup kode 4 huruf, .JK ditambahkan otomatis oleh Section 1.

OUTPUT  : list ticker.
=============================================================================
"""

# -----------------------------------------------------------------------
# CONTOH SAJA - WAJIB DIGANTI DENGAN KONSTITUEN RESMI
# -----------------------------------------------------------------------
KOMPAS100_SAMPLE = [
    # Consumer
    "ICBP", "INDF", "MYOR", "UNVR", "AMRT", "MAPI", "MAPA", "ACES", "MIDI",
    # Telco dan tower
    "TLKM", "ISAT", "EXCL", "TBIG", "TOWR", "MTEL",
    # Tambang dan energi
    "ADRO", "ITMG", "PTBA", "INCO", "ANTM", "TINS", "MDKA", "AMMN", "INDY",
    "PGAS", "MEDC", "ESSA",
    # Properti
    "BSDE", "CTRA", "SMRA", "PWON",
    # Industri dan lain-lain
    "ASII", "UNTR", "SMGR", "INTP", "INKP", "TKIM", "JPFA", "CPIN",
    "AKRA", "JSMR", "KLBF", "SIDO", "MIKA",
]

# Universe kustom milik pengguna. Isi manual.
CUSTOM = []


def get_universe(name="sample"):
    """
    name = "sample"  -> daftar contoh di atas
           "custom"  -> daftar CUSTOM
           list      -> dipakai langsung
    """
    if isinstance(name, (list, tuple)):
        return list(name)
    if name == "custom":
        if not CUSTOM:
            raise ValueError("CUSTOM kosong. Isi dulu di universe.py.")
        return list(CUSTOM)
    return list(KOMPAS100_SAMPLE)


UNIVERSE_WARNING = (
    "Daftar universe yang dipakai adalah contoh, bukan konstituen Kompas100 "
    "resmi. Ganti isi KOMPAS100_SAMPLE di universe.py dengan daftar resmi dari "
    "BEI sebelum hasil batch dipakai untuk pengambilan keputusan."
)
