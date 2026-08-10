"""
=============================================================================
THEME - DESIGN TOKENS AND CUSTOM STYLING
=============================================================================
PURPOSE : Single source of truth for colours, typography, and CSS. Every
          visual decision in the app derives from the tokens defined here,
          so the palette can be changed in one place.

TOKENS  : Navy and ice blue base with an amber accent, Poppins typeface,
          pill section labels, rounded consultant-report layout discipline.

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
    "amber":       "#FF8A3D",   # accent on dark ground (sidebar sliders, focus)
}

RATING_COLOR = {
    "BUY": COLORS["buy"],
    "SELL": COLORS["sell"],
    "HOLD": COLORS["hold"],
    "N/A": COLORS["ink_muted"],
    "NONE": COLORS["ink_muted"],
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
  --amber:{COLORS['amber']};
}}

html, body, [class*="css"], .stApp, button, input, textarea, select {{
  font-family:'Poppins',sans-serif !important;
}}
.stApp {{ background:{COLORS['white']}; color:var(--ink); }}
.block-container {{ padding-top:2.0rem; padding-bottom:3rem; max-width:1180px; }}
#MainMenu, footer {{ visibility:hidden; }}
/* Hide only the Streamlit toolbar clutter (hamburger menu, Deploy button).
   The header itself must stay: it's also where stExpandSidebarButton lives,
   the control that reopens the sidebar once collapsed. Hiding the whole
   header (visibility:hidden) hides that button too and strands the user
   with no way back in. */
header[data-testid="stHeader"] {{ background:transparent; }}
header[data-testid="stHeader"] [data-testid="stMainMenuButton"],
header[data-testid="stHeader"] [data-testid="stAppDeployButton"] {{ display:none; }}

/* ---------- SIDEBAR ---------- */
section[data-testid="stSidebar"] {{ background:var(--navy); }}
section[data-testid="stSidebar"] * {{ color:{COLORS['white']} !important; }}

/* Keep the assumptions panel pinned on desktop so it never scrolls out of
   view while the report below it is long. Collapses back to normal flow on
   narrow / mobile widths, where the sidebar becomes an overlay drawer. */
@media (min-width: 992px) {{
  section[data-testid="stSidebar"] {{
    position: sticky !important; top: 0 !important; height: 100vh !important; overflow-y: auto !important;
  }}
}}

section[data-testid="stSidebar"] .stSlider label,
section[data-testid="stSidebar"] .stTextInput label {{
  font-size:.72rem !important; font-weight:600 !important;
  letter-spacing:.09em; text-transform:uppercase; color:var(--ice) !important;
}}
section[data-testid="stSidebar"] input {{
  background:var(--navy-mid) !important; border:1px solid var(--navy-soft) !important;
  color:{COLORS['white']} !important; font-weight:600 !important; letter-spacing:.06em;
  text-transform:uppercase; border-radius:8px !important;
}}

/* Run analysis button: width="stretch" makes Streamlit size the container to
   100% natively; this just carries the visual style (colour, weight, radius). */
section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
  background:var(--amber) !important; color:var(--navy) !important; border:0 !important;
  font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  font-size:.8rem; padding:.7rem 0; border-radius:8px !important;
  justify-content:center;
  transition:background .15s ease, transform .1s ease;
}}
section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p {{ text-align:center; width:100%; }}
section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{ background:{COLORS['white']} !important; }}
section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:active {{ transform:scale(.99); }}
section[data-testid="stSidebar"] hr {{ border-color:var(--navy-soft); margin:1.1rem 0; }}

/* Slider thumb + active track: amber for contrast against the navy sidebar */
section[data-testid="stSidebar"] [data-testid="stSlider"] [role="slider"] {{
  background-color:var(--amber) !important; border-color:var(--amber) !important;
}}
section[data-testid="stSidebar"] [data-testid="stSlider"] [role="group"] > div > div:not([data-testid="stSliderTickBar"]) {{
  background-color:var(--amber) !important;
}}
section[data-testid="stSidebar"] [data-testid="stSliderThumbValue"] {{
  color:var(--amber) !important; font-weight:700 !important;
}}
/* Min/max tick row: keep it plain text on the navy ground, no highlight
   box behind the numbers even while the slider is focused or dragged. */
section[data-testid="stSidebar"] [data-testid="stSliderTickBar"] {{
  background:transparent !important; background-color:transparent !important;
}}
section[data-testid="stSidebar"] [data-testid="stSliderTickBar"] * {{
  background:transparent !important; background-color:transparent !important;
  color:var(--ice) !important;
}}

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
  margin:2.1rem 0 .5rem 0;
}}
.pill .num {{
  background:var(--ice); color:var(--navy); border-radius:100px;
  padding:.02rem .46rem; font-size:.66rem; font-weight:700; letter-spacing:.04em;
}}
.pill-note {{ font-size:.8rem; color:var(--ink-muted); margin:0 0 1.05rem 0; }}

/* ---------- METRIC STRIP ---------- */
.mstrip {{ display:flex; flex-wrap:wrap; gap:0; border:1px solid var(--rule); border-radius:12px; overflow:hidden; }}
.mcell {{ flex:1 1 0; min-width:132px; padding:.72rem .9rem; border-right:1px solid var(--rule); background:var(--ice-faint); }}
.mcell:last-child {{ border-right:0; }}
.mcell .k {{ font-size:.64rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-muted); }}
.mcell .v {{ font-size:1.02rem; font-weight:600; color:var(--navy); margin-top:.18rem; }}

/* ---------- VERDICT BAND (signature element, always the first highlight) ---------- */
.verdict {{ background:var(--navy); border-radius:16px; padding:1.5rem 1.7rem; margin:.4rem 0 1.6rem 0;
           box-shadow:0 8px 24px -12px rgba(11,31,58,.45); }}
/* Each stat gets an equal flex-basis so the row fills the card edge to
   edge instead of every item shrinking to its own text width and
   bunching to the left with a single large gap trailing behind them.
   flex-wrap then folds the row onto as many lines as the width needs,
   so mobile gets one stat per line for free without a media query.
   align-items is flex-start (top), not flex-end: cells vary in height
   (a one-line rating vs. a multi-line reason paragraph), and bottom
   alignment let the shorter cells' labels drift down out of line with
   the taller cell's label instead of all labels sitting flush at top. */
.verdict .row {{ display:flex; flex-wrap:wrap; align-items:flex-start; gap:1.5rem 2.2rem; }}
.verdict .vcell {{ flex:1 1 190px; min-width:150px; }}
.verdict .vcell-wide {{ flex:2 1 320px; }}
.verdict .rating {{ font-size:2.5rem; font-weight:700; line-height:1; letter-spacing:-.02em; }}
.verdict .lab {{ font-size:.64rem; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--ice); margin-bottom:.3rem; }}
.verdict .big {{ font-size:1.5rem; font-weight:600; color:{COLORS['white']}; line-height:1; }}
.verdict .small {{ font-size:.78rem; color:var(--ice); margin-top:.35rem; }}
.verdict .reason {{ font-size:.92rem; color:{COLORS['white']}; line-height:1.55; }}

/* Scale showing where market price sits inside the bear-bull range */
.scale {{ margin-top:1.25rem; }}
.scale .track {{ position:relative; height:6px; background:var(--navy-soft); border-radius:100px; }}
.scale .fill {{ position:absolute; height:6px; background:var(--ice); border-radius:100px; }}
.scale .mark {{ position:absolute; top:-6px; width:2px; height:18px; background:{COLORS['white']}; }}
.scale .ends {{ display:flex; justify-content:space-between; font-size:.66rem; color:var(--ice); margin-top:.42rem; letter-spacing:.05em; }}

/* ---------- FLAG TABLE (data quality) ----------
   Same three fields as before (level, field, note) but laid out as a
   table sharing the .rtable look. On mobile the note column keeps a
   readable min-width rather than being squeezed into a sliver, and the
   wrapper scrolls horizontally instead of forcing the layout to fit. */
.flag-wrap {{ border-left:4px solid {COLORS['warn']}; }}
.flag-rtable td.flag-field {{ font-weight:600; color:var(--navy); white-space:nowrap; }}
.flag-rtable td.flag-note {{ white-space:normal; min-width:260px; max-width:460px; color:var(--ink-muted); }}
.flag-rtable .flag-badge {{ display:inline-block; min-width:64px; text-align:center; font-size:.6rem; font-weight:700; letter-spacing:.08em; padding:.18rem .5rem; border-radius:100px; color:{COLORS['white']}; }}
.flag-rtable thead th:first-child {{ width:1%; }}

/* ---------- CALLOUTS ---------- */
.callout {{ border-left:3px solid var(--ice); background:var(--ice-pale); padding:.75rem 1.05rem; border-radius:0 12px 12px 0; font-size:.84rem; margin:.5rem 0; }}
.callout b {{ color:var(--navy); }}
.gate-ok {{ color:{COLORS['buy']}; font-weight:600; }}
.gate-no {{ color:{COLORS['sell']}; font-weight:600; }}
.gate-review {{ color:{COLORS['ink_muted']}; font-weight:600; }}

/* ---------- STYLED TABLES (custom HTML, replaces the native grid) ---------- */
.rtable-wrap {{ border:1px solid var(--rule); border-radius:14px; overflow:hidden; margin:.3rem 0 .6rem 0; }}
.rtable {{ width:100%; border-collapse:collapse; font-size:.84rem; }}
.rtable thead th {{
  background:var(--navy); color:{COLORS['white']}; text-align:left;
  padding:.62rem .9rem; font-size:.66rem; font-weight:700;
  letter-spacing:.09em; text-transform:uppercase; white-space:nowrap;
}}
.rtable thead th.num {{ text-align:right; }}
.rtable tbody td {{ padding:.52rem .9rem; border-top:1px solid var(--rule); color:var(--ink); white-space:nowrap; }}
.rtable tbody td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.rtable tbody tr:nth-child(even) td {{ background:var(--ice-faint); }}
.rtable tbody tr:hover td {{ background:var(--ice-pale); }}
.rtable .status-pass {{ color:{COLORS['buy']}; font-weight:700; }}
.rtable .status-fail {{ color:{COLORS['sell']}; font-weight:700; }}
.rtable-scroll {{ overflow-x:auto; }}

/* ---------- LIMITATIONS + DISCLAIMER ---------- */
.limits {{ border:1px solid var(--rule); border-radius:14px; padding:1.05rem 1.3rem; background:var(--ice-faint); font-size:.83rem; }}
.limits li {{ margin-bottom:.3rem; color:var(--ink-muted); }}
.disclaimer {{ background:var(--navy); color:var(--ice); border-radius:16px; padding:1.15rem 1.4rem; margin-top:2.4rem; font-size:.78rem; line-height:1.6; }}
.disclaimer .sig {{ color:{COLORS['white']}; font-weight:600; letter-spacing:.1em; text-transform:uppercase; font-size:.74rem; margin-bottom:.5rem; }}

/* ---------- EMPTY STATE ---------- */
.empty {{ border:1px dashed var(--rule); border-radius:16px; padding:3.2rem 2rem; text-align:center; background:var(--ice-faint); }}
.empty h3 {{ color:var(--navy); font-weight:600; font-size:1.1rem; margin:0 0 .4rem 0; }}
.empty p {{ color:var(--ink-muted); font-size:.87rem; margin:0; }}

/* ---------- CHARTS + MISC ROUNDING ---------- */
[data-testid="stPlotlyChart"] {{ border:1px solid var(--rule); border-radius:14px; overflow:hidden; padding:.4rem; }}

/* Reinvestment rate / ROIC / implied growth bubbles: on desktop these three
   st.columns sit side by side and already have breathing room from the
   column gap. On mobile Streamlit stacks them full-width with almost no
   vertical gap, so add one back here, matching the spacing used elsewhere
   (e.g. terminal value share of EV -> shares outstanding) via st.write(""). */
@media (max-width: 640px) {{
  .st-key-proj-bubbles [data-testid="stColumn"] {{ margin-bottom:1.1rem; }}
  .st-key-proj-bubbles [data-testid="stColumn"]:last-child {{ margin-bottom:0; }}
}}

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


def flag_table(flag_log):
    """
    Data-quality flags as a horizontally scrollable table, sharing the
    .rtable look used everywhere else in the report. Replaces the old
    fixed three-column flex row, which on mobile crushed the note column
    against the right edge. Same three fields (level, field, note); the
    note column keeps a readable width and the table scrolls left-right
    instead.
    """
    rows = "".join(
        f'<tr><td><span class="flag-badge" style="background:{FLAG_COLOR.get(lv, COLORS["miss"])}">{lv}</span></td>'
        f'<td class="flag-field">{fd}</td>'
        f'<td class="flag-note">{nt}</td></tr>'
        for lv, fd, nt in flag_log.items)
    html = (
        '<div class="rtable-wrap flag-wrap"><div class="rtable-scroll"><table class="rtable flag-rtable">'
        '<thead><tr><th>Level</th><th>Field</th><th>Note</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def styled_table(df, hide_index=True, status_col=None, right_align_numeric=True):
    """
    Render a DataFrame as a hand-styled HTML table: rounded container, navy
    uppercase header, zebra striping, and optional colour-coded status text.
    Used instead of st.dataframe so every report table shares one look.
    """
    cols = list(df.columns)
    idx_name = df.index.name or ""

    def is_numeric(col):
        try:
            pd_series = df[col]
            return right_align_numeric and pd_series.astype(str).str.match(
                r"^-?[\d.,]+%?x?$").fillna(False).all()
        except Exception:
            return False

    numeric_flags = {c: is_numeric(c) for c in cols}

    head_cells = ""
    if not hide_index:
        head_cells += f'<th>{idx_name}</th>'
    for c in cols:
        cls = ' class="num"' if numeric_flags[c] else ""
        head_cells += f"<th{cls}>{c}</th>"

    body_rows = []
    for i, row in df.iterrows():
        cells = ""
        if not hide_index:
            cells += f"<td>{i}</td>"
        for c in cols:
            val = row[c]
            cls = ' class="num"' if numeric_flags[c] else ""
            if status_col is not None and c == status_col:
                s = str(val).strip().lower()
                badge_cls = "status-pass" if s in ("passed", "pass") else "status-fail"
                cells += f'<td{cls}><span class="{badge_cls}">{val}</span></td>'
            else:
                cells += f"<td{cls}>{val}</td>"
        body_rows.append(f"<tr>{cells}</tr>")

    html = (
        '<div class="rtable-wrap"><div class="rtable-scroll"><table class="rtable">'
        f"<thead><tr>{head_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)
