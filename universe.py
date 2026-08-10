"""
=============================================================================
UNIVERSE - ISSUER LIST FOR BATCH SCREENING
=============================================================================
PURPOSE : Provide the list of tickers to run as a batch.

DATA WARNING:
    Kompas100 constituents are revised twice a year (February and August)
    by IDX together with Harian Kompas. The list below is NOT the official
    list and is NOT current. It exists only to exercise the pipeline.

    BEFORE SERIOUS USE: replace KOMPAS100_SAMPLE with the official
    constituents. Source: idx.co.id, index announcements, or a Bloomberg
    terminal. A plain 4-letter code is enough; .JK is appended automatically
    by Section 1.

OUTPUT  : list of tickers.
=============================================================================
"""

# -----------------------------------------------------------------------
# SAMPLE ONLY - MUST BE REPLACED WITH OFFICIAL CONSTITUENTS
# -----------------------------------------------------------------------
KOMPAS100_SAMPLE = [
    # Consumer
    "ICBP", "INDF", "MYOR", "UNVR", "AMRT", "MAPI", "MAPA", "ACES", "MIDI",
    # Telco and towers
    "TLKM", "ISAT", "EXCL", "TBIG", "TOWR", "MTEL",
    # Mining and energy
    "ADRO", "ITMG", "PTBA", "INCO", "ANTM", "TINS", "MDKA", "AMMN", "INDY",
    "PGAS", "MEDC", "ESSA",
    # Property
    "BSDE", "CTRA", "SMRA", "PWON",
    # Industrials and others
    "ASII", "UNTR", "SMGR", "INTP", "INKP", "TKIM", "JPFA", "CPIN",
    "AKRA", "JSMR", "KLBF", "SIDO", "MIKA",
]

# The user's own custom universe. Fill in manually.
CUSTOM = []


def get_universe(name="sample"):
    """
    name = "sample"  -> the sample list above
           "custom"  -> the CUSTOM list
           list      -> used as is
    """
    if isinstance(name, (list, tuple)):
        return list(name)
    if name == "custom":
        if not CUSTOM:
            raise ValueError("CUSTOM is empty. Fill it in inside universe.py first.")
        return list(CUSTOM)
    return list(KOMPAS100_SAMPLE)


UNIVERSE_WARNING = (
    "The universe in use is a sample, not the official Kompas100 "
    "constituents. Replace KOMPAS100_SAMPLE in universe.py with the official "
    "IDX list before using batch results for decision-making."
)
