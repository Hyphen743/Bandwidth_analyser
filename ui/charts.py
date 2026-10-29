"""
Plotly Chart Builders for Bandwidth Usage Monitor.
Enforces zero blue across all traces, layout backgrounds, fonts, and scales.
Palette:
- Primary Terracotta: #C8553D
- Amber: #E0A458
- Sage: #7A9E7E
- Muted Stone: #B8B2A7
- Alert Red: #A63D40
"""

from __future__ import annotations

from typing import List, Optional, Union
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from ui.theme import COLORWAY, WARM_PALETTE


def apply_custom_layout(
    fig: go.Figure,
    title: Optional[str] = None,
    height: int = 380,
    dark_mode: bool = False,
    show_legend: bool = True
) -> go.Figure:
    """Apply minimal styling, calm colors, clean typography, and subtle grid lines."""
    bg = WARM_PALETTE["bg_dark"] if dark_mode else WARM_PALETTE["bg_light"]
    surface = WARM_PALETTE["surface_dark"] if dark_mode else WARM_PALETTE["surface_light"]
    text = WARM_PALETTE["text_dark"] if dark_mode else WARM_PALETTE["text_light"]
    grid = "#3A3835" if dark_mode else "#ECE6DC"

    fig.update_layout(
        title={
            "text": title or "",
            "font": {"family": "Newsreader, Georgia, serif", "size": 17, "color": text},
            "x": 0.01,
            "xanchor": "left"
        },
        paper_bgcolor=bg,
        plot_bgcolor=surface,
        font={"family": "Inter, sans-serif", "color": text, "size": 11},
        height=height,
        margin={"l": 40, "r": 30, "t": 45 if title else 20, "b": 35},
        showlegend=show_legend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 10, "color": text}
        },
        colorway=COLORWAY,
        hoverlabel={
            "bgcolor": surface,
            "font": {"family": "Inter, sans-serif", "size": 11, "color": text},
            "bordercolor": WARM_PALETTE["terracotta"]
        }
    )

    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=grid,
        zeroline=False,
        linecolor=grid,
        tickfont={"size": 10, "color": text}
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=grid,
        zeroline=False,
        linecolor=grid,
        tickfont={"size": 10, "color": text}
    )
    return fig


def build_line_chart(
    df: pd.DataFrame,
    x: str,
    y: Union[str, List[str]],
    title: Optional[str] = None,
    y_label: str = "Mbps",
    height: int = 380,
    dark_mode: bool = False
) -> go.Figure:
    """Build multi-series or single line chart with calm palette."""
    fig = go.Figure()
    y_cols = [y] if isinstance(y, str) else y

    for i, col in enumerate(y_cols):
        color = COLORWAY[i % len(COLORWAY)]
        fig.add_trace(go.Scatter(
            x=df[x],
            y=df[col],
            mode="lines",
            name=col.replace("_", " ").title(),
            line={"width": 2, "color": color}
        ))

    fig = apply_custom_layout(fig, title=title, height=height, dark_mode=dark_mode)
    fig.update_yaxes(title_text=y_label)
    return fig


def build_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: Optional[str] = None,
    color_col: Optional[str] = None,
    horizontal: bool = False,
    height: int = 380,
    dark_mode: bool = False
) -> go.Figure:
    """Render clean bar chart."""
    if horizontal:
        fig = px.bar(
            df,
            x=x,
            y=y,
            orientation="h",
            color=color_col,
            color_discrete_sequence=COLORWAY
        )
    else:
        fig = px.bar(
            df,
            x=x,
            y=y,
            color=color_col,
            color_discrete_sequence=COLORWAY
        )

    fig = apply_custom_layout(fig, title=title, height=height, dark_mode=dark_mode)
    return fig


def build_donut_chart(
    df: pd.DataFrame,
    names: str,
    values: str,
    title: Optional[str] = None,
    height: int = 350,
    dark_mode: bool = False
) -> go.Figure:
    """Render minimalist donut chart."""
    fig = go.Figure(data=[go.Pie(
        labels=df[names],
        values=df[values],
        hole=0.55,
        marker={"colors": COLORWAY},
        textinfo="percent+label",
        hoverinfo="label+value+percent"
    )])
    fig = apply_custom_layout(fig, title=title, height=height, dark_mode=dark_mode)
    return fig


def build_area_updown_chart(
    df: pd.DataFrame,
    x: str,
    y_up: str = "mbps_up",
    y_down: str = "mbps_down",
    title: Optional[str] = None,
    height: int = 380,
    dark_mode: bool = False
) -> go.Figure:
    """Bidirectional stacked or dual area chart comparing upload and download."""
    fig = go.Figure()

    # Upload trace (Terracotta)
    fig.add_trace(go.Scatter(
        x=df[x],
        y=df[y_up],
        name="Upload (Mbps)",
        fill="tozeroy",
        mode="lines",
        line={"width": 1.5, "color": WARM_PALETTE["terracotta"]},
        fillcolor="rgba(200, 85, 61, 0.25)"
    ))

    # Download trace (Sage)
    fig.add_trace(go.Scatter(
        x=df[x],
        y=df[y_down],
        name="Download (Mbps)",
        fill="tozeroy",
        mode="lines",
        line={"width": 1.5, "color": WARM_PALETTE["sage"]},
        fillcolor="rgba(122, 158, 126, 0.25)"
    ))

    fig = apply_custom_layout(fig, title=title, height=height, dark_mode=dark_mode)
    fig.update_yaxes(title_text="Throughput (Mbps)")
    return fig


def build_heatmap_chart(
    matrix_df: pd.DataFrame,
    title: Optional[str] = None,
    height: int = 320,
    dark_mode: bool = False
) -> go.Figure:
    """
    Hour-by-weekday heatmap using a custom warm gradient:
    Cream/Sand -> Amber -> Terracotta -> Dark Clay. NO blue.
    """
    custom_colorscale = [
        [0.0, "#FAF7F2"],
        [0.2, "#EFE7DA"],
        [0.45, "#E0A458"],
        [0.75, "#C8553D"],
        [1.0, "#7A2E1D"]
    ]

    fig = go.Figure(data=go.Heatmap(
        z=matrix_df.values,
        x=[f"{h:02d}:00" for h in matrix_df.columns],
        y=matrix_df.index,
        colorscale=custom_colorscale,
        showscale=True,
        colorbar={
            "title": {"text": "Avg Mbps", "side": "right"},
            "len": 0.85,
            "thickness": 12,
            "tickfont": {"size": 9}
        }
    ))

    fig = apply_custom_layout(fig, title=title, height=height, dark_mode=dark_mode, show_legend=False)
    fig.update_xaxes(title_text="Hour of Day", dtick=2)
    return fig


def build_anomaly_timeline(
    df: pd.DataFrame,
    x: str = "hour_ts",
    y: str = "mbps",
    anomaly_col: str = "is_anomaly",
    title: Optional[str] = None,
    height: int = 380,
    dark_mode: bool = False
) -> go.Figure:
    """Renders continuous traffic line with highlighted red anomaly markers."""
    fig = go.Figure()

    # Normal traffic line
    fig.add_trace(go.Scatter(
        x=df[x],
        y=df[y],
        mode="lines",
        name="Traffic (Mbps)",
        line={"width": 1.5, "color": WARM_PALETTE["stone"]}
    ))

    # Baseline line if available
    if "baseline_mean" in df.columns:
        fig.add_trace(go.Scatter(
            x=df[x],
            y=df["baseline_mean"],
            mode="lines",
            name="Baseline Mean",
            line={"width": 1.2, "dash": "dot", "color": WARM_PALETTE["amber"]}
        ))

    # Anomaly markers
    anomalies = df[df[anomaly_col] == 1]
    if not anomalies.empty:
        fig.add_trace(go.Scatter(
            x=anomalies[x],
            y=anomalies[y],
            mode="markers",
            name="Detected Anomaly",
            marker={
                "size": 9,
                "color": WARM_PALETTE["alert_red"],
                "symbol": "diamond",
                "line": {"width": 1.5, "color": "#FFFFFF"}
            },
            text=anomalies.get("severity", ""),
            hovertemplate="<b>Anomaly</b><br>Time: %{x}<br>Value: %{y:.1f} Mbps<br>Severity: %{text}<extra></extra>"
        ))

    fig = apply_custom_layout(fig, title=title, height=height, dark_mode=dark_mode)
    fig.update_yaxes(title_text="Traffic (Mbps)")
    return fig


def build_forecast_chart(
    historical_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    capacity_mbps: float = 100.0,
    title: Optional[str] = None,
    height: int = 400,
    dark_mode: bool = False
) -> go.Figure:
    """Renders recent history, forecast curve, confidence band, and capacity ceiling."""
    fig = go.Figure()

    # History (last 72 hours)
    hist_tail = historical_df.tail(72)
    fig.add_trace(go.Scatter(
        x=hist_tail["hour_ts"],
        y=hist_tail["mbps"],
        mode="lines",
        name="Actual Traffic",
        line={"width": 2, "color": WARM_PALETTE["stone"]}
    ))

    # Confidence interval band (shaded amber)
    fig.add_trace(go.Scatter(
        x=forecast_df["target_ts"],
        y=forecast_df["upper_bound"],
        mode="lines",
        line={"width": 0},
        showlegend=False,
        hoverinfo="skip",
        connectgaps=False
    ))
    fig.add_trace(go.Scatter(
        x=forecast_df["target_ts"],
        y=forecast_df["lower_bound"],
        mode="lines",
        line={"width": 0},
        fill="tonexty",
        fillcolor="rgba(224, 164, 88, 0.20)",
        name="Recent Variation",
        connectgaps=False
    ))

    # Start the projection at the latest observed point, then draw a clean
    # forecast line without a marker at every hourly prediction.
    observed = historical_df.dropna(subset=["mbps"])
    forecast_x = forecast_df["target_ts"].tolist()
    forecast_y = forecast_df["predicted_mbps"].tolist()
    if not observed.empty:
        forecast_x.insert(0, observed.iloc[-1]["hour_ts"])
        forecast_y.insert(0, float(observed.iloc[-1]["mbps"]))

    fig.add_trace(go.Scatter(
        x=forecast_x,
        y=forecast_y,
        mode="lines",
        name="Predicted Demand",
        line={"width": 2.8, "color": WARM_PALETTE["terracotta"]},
        connectgaps=False,
        hovertemplate="%{x|%a, %d %b %H:%M}<br>Forecast: %{y:.2f} Mbps<extra></extra>"
    ))

    # Capacity threshold line (dark red solid)
    fig.add_hline(
        y=capacity_mbps,
        line_dash="dot",
        line_color=WARM_PALETTE["alert_red"],
        line_width=2,
        annotation_text=f"Link Capacity ({capacity_mbps:.0f} Mbps)",
        annotation_position="top right",
        annotation_font_color=WARM_PALETTE["alert_red"],
        annotation_font_size=10
    )

    fig = apply_custom_layout(fig, title=title, height=height, dark_mode=dark_mode)
    fig.update_yaxes(title_text="Mbps")
    fig.update_xaxes(tickformat="%d %b %H:%M", nticks=8, tickangle=0)
    return fig


def build_congestion_chart(
    metrics_df: pd.DataFrame,
    threshold_util: float = 80.0,
    title: Optional[str] = None,
    height: int = 380,
    dark_mode: bool = False
) -> go.Figure:
    """Renders utilization curve with highlighted congestion threshold."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=metrics_df["ts"],
        y=metrics_df["utilization_pct"],
        mode="lines",
        name="Utilization %",
        line={"width": 1.8, "color": WARM_PALETTE["amber"]}
    ))

    # Congestion points
    # The page slider is a utilization threshold, so only utilization
    # crossings should move these markers as the slider changes.
    congested = metrics_df[
        metrics_df["utilization_pct"] >= threshold_util
    ]
    if not congested.empty:
        fig.add_trace(go.Scatter(
            x=congested["ts"],
            y=congested["utilization_pct"],
            mode="markers",
            name="Congestion Incident",
            marker={"size": 7, "color": WARM_PALETTE["alert_red"]}
        ))

    # Threshold horizontal line
    fig.add_hline(
        y=threshold_util,
        line_dash="dash",
        line_color=WARM_PALETTE["alert_red"],
        line_width=1.5,
        annotation_text=f"Saturation Threshold ({threshold_util:.0f}%)",
        annotation_position="bottom right",
        annotation_font_color=WARM_PALETTE["alert_red"],
        annotation_font_size=10
    )

    fig = apply_custom_layout(fig, title=title, height=height, dark_mode=dark_mode)
    fig.update_yaxes(title_text="Utilization %", range=[0, 105])
    return fig
