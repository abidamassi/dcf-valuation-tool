"""
=============================================================================
CHARTS - PLOTLY VISUALS
=============================================================================
PURPOSE : Build every chart in the app. All colours and fonts come from
          theme.py, so charts stay consistent with the rest of the report.

CHARTS  : 1. Projection    revenue bars, FCFF bars, EBIT margin line
          2. Waterfall     enterprise value to equity value bridge
          3. Sensitivity   WACC by terminal growth heatmap
          4. Scenario      bull, base, and bear fair value against price

OUTPUT  : Plotly Figure objects.
=============================================================================
"""

import copy
import numpy as np
import plotly.graph_objects as go

from theme import COLORS, PLOTLY_LAYOUT


def _base(title=None, height=340):
    layout = copy.deepcopy(PLOTLY_LAYOUT)
    if title:
        layout["title"]["text"] = title
    layout["height"] = height
    return layout


# ---------------------------------------------------------------------
# 1. PROJECTION
# ---------------------------------------------------------------------
def chart_projection(proj):
    """Revenue and FCFF in IDR bn, with the EBIT margin path on the right axis."""
    yrs = [f"Y{int(t)}" for t in proj.index]
    rev = (proj["Revenue"] / 1e9).round(0)
    fcff = (proj["FCFF"] / 1e9).round(0)
    margin = (proj["EBIT margin"] * 100).round(2)

    fig = go.Figure()
    fig.add_bar(x=yrs, y=rev, name="Revenue",
                marker_color=COLORS["ice_pale"],
                marker_line=dict(color=COLORS["ice"], width=1),
                hovertemplate="Revenue: %{y:,.0f} bn<extra></extra>")
    fig.add_bar(x=yrs, y=fcff, name="FCFF",
                marker_color=COLORS["navy"],
                hovertemplate="FCFF: %{y:,.0f} bn<extra></extra>")
    fig.add_scatter(x=yrs, y=margin, name="EBIT margin", yaxis="y2",
                    mode="lines+markers",
                    line=dict(color=COLORS["hold"], width=2.5),
                    marker=dict(size=7, color=COLORS["hold"]),
                    hovertemplate="Margin: %{y:.2f}%<extra></extra>")

    layout = _base("Projected revenue, FCFF, and EBIT margin", 400)
    layout["barmode"] = "group"
    layout["yaxis"]["title"] = dict(text="IDR bn", font=dict(size=11))
    layout["yaxis2"] = dict(title=dict(text="EBIT margin %", font=dict(size=11)),
                            overlaying="y", side="right", showgrid=False,
                            tickfont=dict(size=11), linecolor=COLORS["rule"])
    # The shared default legend sits above the plot, flush right. That works
    # at full desktop width, but as the chart narrows on mobile the three
    # entries wrap onto a second line and collide with the title above them.
    # Anchoring it below the plot instead keeps it clear of the title at
    # every width, so only the bottom margin needs to grow to make room.
    layout["legend"] = dict(orientation="h", yanchor="top", y=-0.22,
                            xanchor="center", x=0.5, font=dict(size=11),
                            bgcolor="rgba(0,0,0,0)")
    layout["margin"] = dict(l=10, r=10, t=48, b=70)
    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------
# 2. WATERFALL
# ---------------------------------------------------------------------
def chart_waterfall(v):
    """Bridge from discounted cash flows to equity value."""
    labels = ["PV explicit FCFF", "PV terminal value", "Enterprise value",
              "Cash", "Total debt", "Minority interest", "Equity value"]
    values = [v["pv_explicit"] / 1e9, v["pv_terminal"] / 1e9, 0,
              v["cash"] / 1e9, -v["total_debt"] / 1e9, -v["minority"] / 1e9, 0]
    measures = ["relative", "relative", "total",
                "relative", "relative", "relative", "total"]

    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measures, x=labels, y=values,
        text=[f"{x:,.0f}" if m == "relative" else "" for x, m in zip(values, measures)],
        textposition="outside", textfont=dict(size=10),
        connector=dict(line=dict(color=COLORS["rule"], width=1)),
        increasing=dict(marker=dict(color=COLORS["ice"])),
        decreasing=dict(marker=dict(color=COLORS["sell"])),
        totals=dict(marker=dict(color=COLORS["navy"])),
        hovertemplate="%{x}: %{y:,.0f} bn<extra></extra>",
    ))
    layout = _base("Enterprise value to equity value (IDR bn)", 380)
    layout["xaxis"]["tickangle"] = -18
    layout["xaxis"]["tickfont"] = dict(size=10)
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------
# 3. SENSITIVITY HEATMAP
# ---------------------------------------------------------------------
def chart_sensitivity(sens, price):
    """WACC by terminal growth. Colour encodes upside against market price."""
    fv = sens["fair_value"].astype(float)
    z = fv.values
    up = (z / price - 1) * 100 if (price and np.isfinite(price) and price > 0) else z

    fig = go.Figure(go.Heatmap(
        z=up, x=list(fv.columns), y=list(fv.index),
        text=[[f"{val:,.0f}" if np.isfinite(val) else "n/a" for val in row] for row in z],
        texttemplate="%{text}", textfont=dict(size=11, family="Poppins"),
        colorscale=[[0.0, COLORS["sell"]], [0.45, "#F2E9DC"],
                    [0.55, COLORS["ice_pale"]], [1.0, COLORS["navy"]]],
        zmid=0,
        colorbar=dict(title=dict(text="Upside %", font=dict(size=10)),
                      thickness=12, tickfont=dict(size=10), outlinewidth=0),
        hovertemplate="WACC %{y} | g %{x}<br>Fair value IDR %{text}<extra></extra>",
    ))
    layout = _base("Fair value per share by WACC and terminal growth (IDR)", 360)
    layout["xaxis"]["title"] = dict(text="Terminal growth", font=dict(size=11))
    layout["yaxis"]["title"] = dict(text="WACC", font=dict(size=11))
    layout["xaxis"]["gridcolor"] = "rgba(0,0,0,0)"
    layout["yaxis"]["gridcolor"] = "rgba(0,0,0,0)"
    layout["yaxis"]["autorange"] = "reversed"
    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------
# 4. SCENARIOS
# ---------------------------------------------------------------------
def chart_scenarios(sc_df, price):
    """Bull, base, and bear fair value with the market price as reference."""
    order = [s for s in ["BEAR", "BASE", "BULL"] if s in sc_df.index]
    vals = [float(sc_df.loc[s, "Fair value/shr"]) for s in order]
    ratings = [str(sc_df.loc[s, "Rating"]) for s in order]

    bar_colors = {"BEAR": COLORS["ice_pale"], "BASE": COLORS["navy"],
                  "BULL": COLORS["ice"]}
    fig = go.Figure()
    fig.add_bar(x=order, y=vals,
                marker_color=[bar_colors[s] for s in order],
                marker_line=dict(color=COLORS["navy_soft"], width=1),
                text=[f"IDR {v:,.0f}<br>{r}" if np.isfinite(v) else "n/a"
                      for v, r in zip(vals, ratings)],
                textposition="outside", textfont=dict(size=11),
                hovertemplate="%{x}: IDR %{y:,.0f}<extra></extra>",
                name="Fair value")

    if price and np.isfinite(price) and price > 0:
        fig.add_hline(y=price, line=dict(color=COLORS["sell"], width=2, dash="dash"),
                      annotation_text=f"Market price IDR {price:,.0f}",
                      annotation_position="top left",
                      annotation_font=dict(size=11, color=COLORS["sell"]))

    finite = [v for v in vals if np.isfinite(v)]
    top = max(finite + ([price] if price and np.isfinite(price) else [0]))
    layout = _base("Scenario fair value against market price (IDR per share)", 360)
    layout["yaxis"]["range"] = [0, top * 1.28]
    layout["yaxis"]["title"] = dict(text="IDR per share", font=dict(size=11))
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig
