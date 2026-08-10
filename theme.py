"""
=============================================================================
THEME - DESIGN TOKENS AND CUSTOM STYLING
=============================================================================
PURPOSE : Single source of truth for colours, typography, and CSS. Every
          visual decision in the app derives from the tokens defined here,
          so the palette can be changed in one place.

TOKENS  : Navy and ice blue base, Poppins typeface, pill section labels,
          consultant-report layout discipline.

OUTPUT  : COLORS dict, PLOTLY_LAYOUT dict, and inject_css().
=============================================================================
"""

import streamlit as st

# ---------------------------------------------------------------------
# COLOUR TOKENS
# ---------------------------------------------------------------------
COLORS = {
    "navy":        "#0B1F3A",   # primary, headers and verdict band
    "navy_mid":    "#14304F",   # secondary surfaces
    "navy_soft":   "#2C4A6B",   # borders and muted text on light ground
    "ice":         "#A9C9E8",   # accent, chart primary
    "ice_pale":    "#E4EEF7",   # card background
    "ice_faint":   "#F4F8FC",   # page alternate ground
    "white":       "#FFFFFF",
    "ink":         "#1A2733",   # body text
    "ink_muted":   "#63748A",   # captions and secondary labels
    "rule":        "#D6E2EE",   # hairline dividers
    "buy":         "#1E8F5F",
    "sell":        "#C0392B",
    "hold":        "#B08D57",
    "warn":        "#D98B2B",
    "miss":        "#8A94A6",
}

RATING_COLOR = {
    "BUY": COLORS["buy"],
    "SELL": COLORS["sell"],
    "HOLD": COLORS["hold"],
    "N/A": COLORS["ink_muted"],
}

FLAG_COLOR = {
    "MISSING": COLORS["miss"],
    "ZERO":    COLORS["warn"],
    "WARN":    COLORS["warn"],
}

# ---------------------------------------------------------------------
# PLOTLY BASE LAYOUT
# ---------------------------------------------------------------------
PLOTLY_LAYOUT = dict(
    font=dict(family="Poppins, sans-serif", size=12, color=COLORS["ink"]),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=48, b=10),
    hoverlabel=dict(font=dict(family="Poppins, sans-serif", size=12)),
    title=dict(font=dict(size=14, color=COLORS["navy"]), x=0, xanchor="left"),
    xaxis=dict(gridcolor=COLORS["rule"], zerolinecolor=COLORS["rule"],
               linecolor=COLORS["rule"], tickfont=dict(size=11)),
    yaxis=dict(gridcolor=COLORS["rule"], zerolinecolor=COLORS["rule"],
               linecolor=COLORS["rule"], tickfont=dict(size=11)),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
)


def inject_css():
    """Load Poppins and apply the full stylesheet."""
    st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<style>
:root {{
  --navy:{COLORS['navy']}; --navy-mid:{COLORS['navy_mid']}; --navy-soft:{COLORS['navy_soft']};
  --ice:{COLORS['ice']}; --ice-pale:{COLORS['ice_pale']}; --ice-faint:{COLORS['ice_faint']};
  --ink:{COLORS['ink']}; --ink-muted:{COLORS['ink_muted']}; --rule:{COLORS['rule']};
}}

html, body, [class*="css"], .stApp, button, input, textarea, select {{
  font-family:'Poppins',sans-serif !important;
}}
.stApp {{ background:{COLORS['white']}; color:var(--ink); }}
.block-container {{ padding-top:2.0rem; padding-bottom:3rem; max-width:1180px; }}
#MainMenu, footer, header {{ visibility:hidden; }}

/* ---------- SIDEBAR ---------- */
section[data-testid="stSidebar"] {{ background:var(--navy); }}
section[data-testid="stSidebar"] * {{ color:{COLORS['white']} !important; }}
section[data-testid="stSidebar"] .stSlider label,
section[data-testid="stSidebar"] .stTextInput label {{
  font-size:.72rem !important; font-weight:600 !important;
  letter-spacing:.09em; text-transform:uppercase; color:var(--ice) !important;
}}
section[data-testid="stSidebar"] input {{
  background:var(--navy-mid) !important; border:1px solid var(--navy-soft) !important;
  color:{COLORS['white']} !important; font-weight:600 !important; letter-spacing:.06em;
}}
section[data-testid="stSidebar"] .stButton button {{
  background:var(--ice); color:var(--navy) !important; border:0; width:100%;
  font-weight:600; letter-spacing:.08em; text-transform:uppercase;
  font-size:.78rem; padding:.62rem 0; border-radius:2px;
}}
section[data-testid="stSidebar"] .stButton button:hover {{ background:{COLORS['white']}; }}
section[data-testid="stSidebar"] hr {{ border-color:var(--navy-soft); margin:1.1rem 0; }}

/* ---------- TYPOGRAPHY ---------- */
.eyebrow {{
  font-size:.68rem; font-weight:600; letter-spacing:.16em; text-transform:uppercase;
  color:var(--ink-muted); margin:0 0 .25rem 0;
}}
.masthead {{
  border-bottom:2px solid var(--navy); padding-bottom:.7rem; margin-bottom:1.4rem;
}}
.masthead h1 {{
  font-size:1.85rem; font-weight:600; color:var(--navy); margin:0; letter-spacing:-.015em;
}}
.masthead .sub {{ font-size:.9rem; color:var(--ink-muted); margin-top:.15rem; }}

/* Pill section label: the structural device carrying section number + name */
.pill {{
  display:inline-flex; align-items:center; gap:.55rem;
  background:var(--navy); color:{COLORS['white']};
  padding:.34rem .95rem; border-radius:100px;
  font-size:.74rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
  margin:1.9rem 0 .3rem 0;
}}
.pill .num {{
  background:var(--ice); color:var(--navy); border-radius:100px;
  padding:.02rem .46rem; font-size:.66rem; font-weight:700; letter-spacing:.04em;
}}
.pill-note {{ font-size:.8rem; color:var(--ink-muted); margin:0 0 .7rem 0; }}

/* ---------- METRIC STRIP ---------- */
.mstrip {{ display:flex; flex-wrap:wrap; gap:0; border:1px solid var(--rule); border-radius:3px; overflow:hidden; }}
.mcell {{ flex:1 1 0; min-width:132px; padding:.72rem .9rem; border-right:1px solid var(--rule); background:var(--ice-faint); }}
.mcell:last-child {{ border-right:0; }}
.mcell .k {{ font-size:.64rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-muted); }}
.mcell .v {{ font-size:1.02rem; font-weight:600; color:var(--navy); margin-top:.18rem; }}

/* ---------- VERDICT BAND (signature element) ---------- */
.verdict {{ background:var(--navy); border-radius:4px; padding:1.35rem 1.6rem; margin:.4rem 0 .3rem 0; }}
.verdict .row {{ display:flex; flex-wrap:wrap; align-items:flex-end; gap:2.4rem; }}
.verdict .rating {{ font-size:2.5rem; font-weight:700; line-height:1; letter-spacing:-.02em; }}
.verdict .lab {{ font-size:.64rem; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--ice); margin-bottom:.3rem; }}
.verdict .big {{ font-size:1.5rem; font-weight:600; color:{COLORS['white']}; line-height:1; }}
.verdict .small {{ font-size:.78rem; color:var(--ice); margin-top:.35rem; }}

/* Scale showing where market price sits inside the bear-bull range */
.scale {{ margin-top:1.25rem; }}
.scale .track {{ position:relative; height:6px; background:var(--navy-soft); border-radius:100px; }}
.scale .fill {{ position:absolute; height:6px; background:var(--ice); border-radius:100px; }}
.scale .mark {{ position:absolute; top:-6px; width:2px; height:18px; background:{COLORS['white']}; }}
.scale .ends {{ display:flex; justify-content:space-between; font-size:.66rem; color:var(--ice); margin-top:.42rem; letter-spacing:.05em; }}

/* ---------- FLAG PANEL ---------- */
.flagbox {{ border:1px solid var(--rule); border-left:3px solid {COLORS['warn']}; border-radius:3px; background:var(--ice-faint); padding:.85rem 1rem; }}
.flagrow {{ display:flex; gap:.7rem; padding:.32rem 0; border-bottom:1px solid var(--rule); font-size:.82rem; }}
.flagrow:last-child {{ border-bottom:0; }}
.flagtag {{ flex:0 0 66px; font-size:.6rem; font-weight:700; letter-spacing:.08em; text-align:center; padding:.16rem 0; border-radius:100px; height:fit-content; color:{COLORS['white']}; }}
.flagfield {{ flex:0 0 168px; font-weight:600; color:var(--navy); }}
.flagnote {{ flex:1 1 auto; color:var(--ink-muted); }}

/* ---------- CALLOUTS ---------- */
.callout {{ border-left:3px solid var(--ice); background:var(--ice-pale); padding:.72rem 1rem; border-radius:0 3px 3px 0; font-size:.84rem; margin:.5rem 0; }}
.callout b {{ color:var(--navy); }}
.gate-ok {{ color:{COLORS['buy']}; font-weight:600; }}
.gate-no {{ color:{COLORS['sell']}; font-weight:600; }}

/* ---------- TABLES ---------- */
[data-testid="stDataFrame"] {{ border:1px solid var(--rule); border-radius:3px; }}

/* ---------- LIMITATIONS + DISCLAIMER ---------- */
.limits {{ border:1px solid var(--rule); border-radius:3px; padding:1rem 1.2rem; background:var(--ice-faint); font-size:.83rem; }}
.limits li {{ margin-bottom:.3rem; color:var(--ink-muted); }}
.disclaimer {{ background:var(--navy); color:var(--ice); border-radius:4px; padding:1.15rem 1.4rem; margin-top:2.4rem; font-size:.78rem; line-height:1.6; }}
.disclaimer .sig {{ color:{COLORS['white']}; font-weight:600; letter-spacing:.1em; text-transform:uppercase; font-size:.74rem; margin-bottom:.5rem; }}

/* ---------- EMPTY STATE ---------- */
.empty {{ border:1px dashed var(--rule); border-radius:4px; padding:3.2rem 2rem; text-align:center; background:var(--ice-faint); }}
.empty h3 {{ color:var(--navy); font-weight:600; font-size:1.1rem; margin:0 0 .4rem 0; }}
.empty p {{ color:var(--ink-muted); font-size:.87rem; margin:0; }}

@media (prefers-reduced-motion: reduce) {{ * {{ animation:none !important; transition:none !important; }} }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# SMALL RENDER HELPERS
# ---------------------------------------------------------------------
def pill(number, label, note=""):
    """Section label: numbered pill. The number encodes the pipeline order."""
    st.markdown(
        f'<div class="pill"><span class="num">{number}</span>{label}</div>',
        unsafe_allow_html=True)
    if note:
        st.markdown(f'<p class="pill-note">{note}</p>', unsafe_allow_html=True)


def metric_strip(pairs):
    """Horizontal strip of key/value cells."""
    cells = "".join(
        f'<div class="mcell"><div class="k">{k}</div><div class="v">{v}</div></div>'
        for k, v in pairs)
    st.markdown(f'<div class="mstrip">{cells}</div>', unsafe_allow_html=True)


def callout(html):
    st.markdown(f'<div class="callout">{html}</div>', unsafe_allow_html=True)
