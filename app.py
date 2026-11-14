"""Streamlit dashboard for the Dancing with the SARs hackathon project."""

from __future__ import annotations

from datetime import datetime
import json

import folium
from branca.colormap import LinearColormap
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from drought_monitor.assistant import (
    NO_KEY_NOTICE,
    answer_question,
    build_context,
    earthdata_credentials_present,
    earthdata_token_notice,
    llm_provider,
    summarize_view,
)
from drought_monitor.data import (
    build_summary,
    list_sites,
    load_site_data,
    slope_geotiff_bytes,
)


st.set_page_config(
    page_title="Dancing with the SARs",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root { --ink: #000000; --teal: #0d7d75; --sand: #e8c98e; }
      .stApp {
        background: #ffffff;
        color: #000000;
      }
      [data-testid="stMain"],
      [data-testid="stMain"] p,
      [data-testid="stMain"] span,
      [data-testid="stMain"] label,
      [data-testid="stMain"] li,
      [data-testid="stMain"] small,
      [data-testid="stMain"] h1,
      [data-testid="stMain"] h2,
      [data-testid="stMain"] h3,
      [data-testid="stMarkdownContainer"],
      [data-testid="stCaptionContainer"],
      [data-testid="stMetricLabel"],
      [data-testid="stMetricValue"],
      [data-testid="stMetricDelta"] {
        color: #000000;
      }
      [data-testid="stSidebar"] { background: #102f31; }
      [data-testid="stSidebar"] * { color: #f7fffc !important; }
      [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
      [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
        color: #f7fffc !important;
        font-size: 0.95rem !important;
        line-height: 1.45 !important;
        opacity: 1 !important;
      }
      [data-testid="stSidebar"] [data-testid="stAlert"] {
        background: #e7f5f2 !important;
      }
      [data-testid="stSidebar"] [data-testid="stAlert"] * {
        color: #10231f !important;
        background: transparent !important;
        font-size: 0.95rem !important;
      }
      [data-testid="stMain"] .hero,
      [data-testid="stMain"] .hero h1,
      [data-testid="stMain"] .hero p {
        color: #ffffff !important;
      }
      .hero {
        border-radius: 18px; padding: 1.35rem 1.6rem; margin-bottom: 1rem;
        color: #ffffff !important; background:
          radial-gradient(circle at 87% 20%, rgba(232,201,142,.32), transparent 24%),
          linear-gradient(120deg, #102f31 0%, #0d6c66 100%);
        box-shadow: 0 12px 30px rgba(20,43,44,.12);
      }
      .hero h1 { margin: 0; font-size: 2rem; letter-spacing: -.03em; }
      .hero p { margin: .45rem 0 0; max-width: 760px; }
      .mock-chip {
        display: inline-block; font-size: .72rem; font-weight: 700;
        letter-spacing: .09em; padding: .25rem .5rem; border-radius: 999px;
        background: #f1d59f !important; color: #1a1208 !important; margin-bottom: .65rem;
      }
      [data-testid="stMetric"] {
        background: white; border: 1px solid #dceae6; padding: .85rem 1rem;
        border-radius: 14px; box-shadow: 0 6px 18px rgba(20,43,44,.05);
      }
      div[data-testid="stPlotlyChart"], iframe {
        border-radius: 14px; overflow: hidden;
      }
      h2, h3 { color: var(--ink); letter-spacing: -.02em; }
      .source-note {
        padding: .7rem .85rem; border-radius: 10px; background: #ffffff;
        border: 1px solid #dceae6; border-left: 4px solid #0d7d75;
        color: #000000; font-size: .87rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def get_site_data(site_id: str, source: str = "mock"):
    return load_site_data(site_id, source=source)


RISK_LEGEND = "Low 0–39.9 · Medium 40–64.9 · High 65–100"
CHART_TEXT = {"family": "Inter, sans-serif", "color": "#000000", "size": 13}


def risk_label(value: float) -> tuple[str, str]:
    if value >= 65:
        return "High", "#c43d3d"
    if value >= 40:
        return "Medium", "#d5962e"
    return "Low", "#2b8b67"


def base_chart_layout(title: str, y_title: str) -> dict:
    return {
        "title": {"text": title, "x": 0.02, "font": {"size": 17, "color": "#000000"}},
        "height": 340,
        "margin": {"l": 52, "r": 18, "t": 56, "b": 42},
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "font": CHART_TEXT,
        "yaxis": {
            "title": {"text": y_title, "font": CHART_TEXT},
            "tickfont": CHART_TEXT,
            "gridcolor": "#e7efed",
            "zerolinecolor": "#bbcfc9",
        },
        "xaxis": {"tickfont": CHART_TEXT, "title": {"font": CHART_TEXT}, "gridcolor": "#eef3f2"},
        "hovermode": "x unified",
        "legend": {"orientation": "h", "y": 1.16, "x": 0, "font": CHART_TEXT},
    }


def rainfall_chart(frame: pd.DataFrame, climatology_name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        x=frame["time"],
        y=frame["observed_mm"],
        name="Observed",
        marker_color="#0d7d75",
        hovertemplate="%{y:.1f} mm<extra>Observed</extra>",
    )
    fig.add_scatter(
        x=frame["time"],
        y=frame["climatology_mm"],
        name=climatology_name,
        mode="lines+markers",
        line={"color": "#d5962e", "width": 3},
        hovertemplate="%{y:.1f} mm<extra>Climatology</extra>",
    )
    fig.update_layout(**base_chart_layout("Rainfall against climatology", "Monthly rainfall (mm)"))
    return fig


def soil_chart(site, selected_time: pd.Timestamp) -> go.Figure:
    data = site.soil_moisture["soil_moisture"]
    mean = data.mean(("y", "x"))
    p10 = data.quantile(0.1, dim=("y", "x"))
    p90 = data.quantile(0.9, dim=("y", "x"))
    fig = go.Figure()
    fig.add_scatter(
        x=mean.time.values,
        y=p90.values,
        mode="lines",
        line={"width": 0},
        showlegend=False,
        hoverinfo="skip",
    )
    fig.add_scatter(
        x=mean.time.values,
        y=p10.values,
        mode="lines",
        fill="tonexty",
        fillcolor="rgba(13,125,117,.15)",
        line={"width": 0},
        name="10th–90th percentile",
        hoverinfo="skip",
    )
    fig.add_scatter(
        x=mean.time.values,
        y=mean.values,
        name="Site mean",
        mode="lines+markers",
        line={"color": "#0d7d75", "width": 3},
        hovertemplate="%{y:.3f}<extra>Site mean</extra>",
    )
    fig.add_scatter(
        x=[selected_time, selected_time],
        y=[float(np.nanmin(mean.values)) - 0.02, float(np.nanmax(mean.values)) + 0.02],
        mode="lines",
        name="Selected slider date",
        line={"color": "#c43d3d", "width": 2, "dash": "dot"},
        hovertemplate=f"{selected_time:%d %b %Y}<extra>Selected slider date</extra>",
    )
    units = site.soil_moisture["soil_moisture"].attrs.get("units", "m3 m-3")
    y_title = "Soil moisture (m³/m³)" if units == "m3 m-3" else "Surface wetness (fraction)"
    fig.update_layout(**base_chart_layout(site.soil_moisture.attrs.get("title", "Soil moisture"), y_title))
    low = float(np.nanmin(mean.values)) - 0.03
    high = float(np.nanmax(mean.values)) + 0.03
    fig.update_yaxes(range=[low, high])
    return fig


def raster_figure(values: np.ndarray, x: np.ndarray, y: np.ndarray, title: str, kind: str) -> go.Figure:
    if kind == "slope":
        colorscale, zmin, label = "Earth", 0, "degrees"
        zmax = max(48.0, float(np.nanpercentile(values, 99)))
    else:
        colorscale = [[0, "#2b8b67"], [0.4, "#e7c65b"], [0.65, "#e58037"], [1, "#b62f3b"]]
        zmin, zmax, label = 0, 100, "risk index"
    fig = go.Figure(
        go.Heatmap(
            z=values,
            x=x,
            y=y,
            colorscale=colorscale,
            zmin=zmin,
            zmax=zmax,
            colorbar={
                "title": {"text": label, "font": CHART_TEXT},
                "tickfont": CHART_TEXT,
                "thickness": 14,
            },
            hovertemplate="Lon %{x:.4f}<br>Lat %{y:.4f}<br>Value %{z:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": title, "x": 0.02, "font": {"size": 17}},
        height=360,
        margin={"l": 45, "r": 20, "t": 55, "b": 40},
        paper_bgcolor="white",
        font=CHART_TEXT,
        legend={"font": CHART_TEXT},
        xaxis={
            "title": {"text": "Longitude", "font": CHART_TEXT},
            "tickfont": CHART_TEXT,
        },
        yaxis={
            "title": {"text": "Latitude", "font": CHART_TEXT},
            "tickfont": CHART_TEXT,
            "scaleanchor": "x",
            "scaleratio": 1,
        },
    )
    return fig


def site_map(site, risk_values: np.ndarray) -> folium.Map:
    fmap = folium.Map(
        location=site.center,
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    for site_id in list_sites():
        map_site = get_site_data(site_id)
        selected = site_id == site.site_id
        west, south, east, north = map_site.boundary.total_bounds
        folium.Rectangle(
            bounds=[[south, west], [north, east]],
            color="#0d7d75" if selected else "#708b86",
            weight=3 if selected else 1.5,
            fill=False,
            tooltip=map_site.name,
        ).add_to(fmap)
        folium.CircleMarker(
            map_site.center,
            radius=7 if selected else 5,
            color="#102f31",
            fill=True,
            fill_color="#f1c972" if selected else "#6da79d",
            fill_opacity=1,
            tooltip=f"{map_site.name} · {'selected' if selected else 'study site'}",
        ).add_to(fmap)

    west, south, east, north = site.boundary.total_bounds
    palette = LinearColormap(
        ["#2b8b67", "#e7c65b", "#e58037", "#b62f3b"], vmin=0, vmax=100
    )
    folium.raster_layers.ImageOverlay(
        image=risk_values,
        bounds=[[south, west], [north, east]],
        opacity=0.66,
        colormap=lambda value: palette.rgba_floats_tuple(value),
        name="Runoff / erosion risk",
        origin="upper",
        zindex=2,
    ).add_to(fmap)
    palette.caption = f"Runoff / erosion risk · {RISK_LEGEND}"
    palette.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap


with st.sidebar:
    st.markdown("### 🛰️ Dancing with the SARs")
    st.caption("NISAR drought + runoff intelligence")
    names = list_sites()
    site_id = st.selectbox(
        "Study site",
        options=list(names),
        format_func=names.get,
    )
    source_label = st.radio("Data source", ["Mock", "NASA Earthdata"], horizontal=True)
    source = "earthdata" if source_label == "NASA Earthdata" else "mock"

site = get_site_data(site_id, source)
available_times = [pd.Timestamp(value) for value in site.soil_moisture.time.values]
if site.metadata.get("fallback") or source == "mock":
    hero_chip = "MOCK DATA PROTOTYPE"
elif site.metadata.get("partial_mock"):
    hero_chip = "NASA DATA · SOME LAYERS MOCK"
else:
    hero_chip = "NASA EARTHDATA"

with st.sidebar:
    st.markdown("**What is loaded**")
    if site.metadata.get("fallback"):
        st.info("MOCK FALLBACK\n\nThe NASA request failed, so this page is synthetic.")
    elif source == "earthdata":
        layer_text = "\n".join(
            f"{name}: {value}" for name, value in site.metadata.get("layers", {}).items()
        )
        st.info(f"NASA EARTHDATA\n\n{layer_text}")
    else:
        st.info("MOCK / SYNTHETIC\n\nEarthdata-compatible shapes; no operational decisions.")
    if not earthdata_credentials_present():
        st.caption(
            "No EARTHDATA_TOKEN is set, so NISAR files stay on NASA's servers. "
            "Add EARTHDATA_TOKEN in Streamlit Cloud > App settings > Secrets. "
            "Free signup: https://urs.earthdata.nasa.gov"
        )
    st.markdown("**Mission concept**")
    st.caption(
        "A NASA Space Apps 2026 prototype combining L-band soil moisture, "
        "winter rainfall deficits, terrain and fire history."
    )

st.markdown(
    f"""
    <div class="hero">
      <span class="mock-chip">{hero_chip}</span>
      <h1>Dancing with the SARs</h1>
      <p>Drought stress and runoff-risk signals for Cape Town's fynbos catchments,
      shaped like the NASA Earthdata products that will replace them.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
using_mock = source == "mock" or bool(site.metadata.get("fallback"))
if not earthdata_credentials_present() and not st.session_state.get("hide_earthdata_notice"):
    notice_parts = [earthdata_token_notice(using_mock)]
    if site.metadata.get("notice"):
        notice_parts.append(site.metadata["notice"])
    notice_col, dismiss_col = st.columns([6, 1])
    with notice_col:
        st.warning("\n\n".join(notice_parts))
    with dismiss_col:
        if st.button("Dismiss", key="dismiss_earthdata_notice"):
            st.session_state.hide_earthdata_notice = True
            st.rerun()
elif site.metadata.get("fallback"):
    st.warning(site.metadata["notice"])
elif site.metadata.get("notice"):
    st.info(site.metadata["notice"])

control_col, note_col = st.columns([1.25, 1])
with control_col:
    selected_time = st.select_slider(
        "NISAR 12-day observation",
        options=available_times,
        value=available_times[-1],
        format_func=lambda value: value.strftime("%d %b %Y"),
        help=(
            "Moving this slider updates the risk map, soil-moisture and runoff "
            "metrics, scene interpretation, risk heatmap, and the red dotted "
            "line on the soil-moisture chart."
        ),
    )
    st.caption(
        "Moving the slider updates the map, the soil-moisture, runoff-risk and "
        "high-risk metrics, the scene interpretation, the risk heatmap, and the "
        "red dotted marker on the soil-moisture chart."
    )
with note_col:
    st.markdown(
        f"""<div class="source-note"><strong>{site.name}</strong><br>{site.description}</div>""",
        unsafe_allow_html=True,
    )

time_index = available_times.index(selected_time)
soil_slice = site.soil_moisture["soil_moisture"].isel(time=time_index)
risk_slice = site.runoff_risk["risk_index"].isel(time=time_index)
class_slice = site.runoff_risk["risk_class"].isel(time=time_index)
mean_soil = float(soil_slice.mean())
mean_risk = float(risk_slice.mean())
risk_name, risk_color = risk_label(mean_risk)
latest_rain = site.rainfall.iloc[-1]
high_area = float((class_slice == 2).mean()) * 100

rain_month = latest_rain.time.strftime("%B %Y")
uses_power = source == "earthdata" and not site.metadata.get("fallback")
climatology_name = "POWER climatology" if uses_power else "1991–2020 climatology"
rain_help = (
    f"{latest_rain.percent_normal:.0f}% is {rain_month} observed rainfall as a "
    f"percent of that month's {climatology_name} "
    f"({latest_rain.observed_mm:.1f} mm ÷ {latest_rain.climatology_mm:.1f} mm). "
    f"The {latest_rain.anomaly_mm:.0f} mm figure is the anomaly for the same month: "
    "observed millimetres minus the climatology, rounded to the nearest millimetre. "
    "A negative anomaly is a rainfall deficit. This card uses the latest rainfall "
    "month and does not follow the observation slider."
)
k1, k2, k3, k4 = st.columns(4)
k1.metric(
    "Rainfall vs normal",
    f"{latest_rain.percent_normal:.0f}%",
    f"{latest_rain.anomaly_mm:.0f} mm vs climatology",
    help=rain_help,
)
k1.caption(f"{rain_month} percent of the {climatology_name}. Delta: observed minus climatology.")
soil_units = site.soil_moisture["soil_moisture"].attrs.get("units", "m3 m-3")
soil_unit_label = "m³/m³" if soil_units == "m3 m-3" else "wetness fraction"
k2.metric("Mean soil moisture", f"{mean_soil:.3f} {soil_unit_label}", "Selected scene")
k3.metric(
    "Runoff risk",
    risk_name,
    f"Index {mean_risk:.0f}/100",
    help=f"Scene-average risk index. Classes: {RISK_LEGEND}.",
)
k3.caption(RISK_LEGEND)
k4.metric("High-risk pixels", f"{high_area:.1f}%", f"{int((class_slice == 2).sum())} cells")

view_context = build_context(
    site_name=site.name,
    slider_date=selected_time.strftime("%d %B %Y"),
    rain_month=rain_month,
    percent_normal=float(latest_rain.percent_normal),
    anomaly_mm=float(latest_rain.anomaly_mm),
    climatology_name=climatology_name,
    soil_value=mean_soil,
    soil_unit=soil_unit_label,
    soil_first=float(site.soil_moisture["soil_moisture"].isel(time=0).mean()),
    risk_score=mean_risk,
    risk_class=risk_name,
    burned_percent=float(site.burn_mask.mean()) * 100,
    mean_slope=float(site.slope.mean()),
    source_mode=source,
    using_mock=using_mock,
)
st.session_state["view_context"] = view_context


def _close_chat() -> None:
    st.session_state.open_chat = False


@st.dialog("Ask about this data", width="large", on_dismiss=_close_chat)
def ask_about_data() -> None:
    context = st.session_state["view_context"]
    if llm_provider() is None:
        st.info(NO_KEY_NOTICE)
    messages = st.session_state.setdefault("qa_messages", [])
    for message in messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    question = st.chat_input("Ask about the numbers on this page")
    if question:
        reply, provider = answer_question(question, context)
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": reply})
        st.session_state["qa_provider"] = provider
        st.rerun()


ask_col, summary_col = st.columns(2)
if ask_col.button("Ask about this data", width="stretch"):
    st.session_state.open_chat = True
if st.session_state.get("open_chat"):
    ask_about_data()
if summary_col.button("Summarize this view", width="stretch"):
    summary_text, summary_provider = summarize_view(view_context)
    st.session_state["view_summary"] = summary_text
    st.session_state["summary_provider"] = summary_provider
if st.session_state.get("view_summary"):
    st.markdown(st.session_state["view_summary"])
    if st.session_state.get("summary_provider") == "page":
        st.caption("On-page summary. Add GEMINI_API_KEY or LLM_API_KEY to use a language model.")
    else:
        st.caption(f"Summary from {st.session_state['summary_provider']}.")

st.subheader("Study area & current risk surface")
map_col, context_col = st.columns([1.7, 1])
with map_col:
    st.caption(f"Map classes follow the risk index. {RISK_LEGEND}.")
    st_folium(
        site_map(site, risk_slice.values),
        height=475,
        use_container_width=True,
        returned_objects=[],
        key=f"map-{site_id}-{time_index}",
    )
with context_col:
    st.markdown("#### Scene interpretation")
    st.markdown(
        f"""
        **Acquisition:** {selected_time.strftime('%d %B %Y')}  
        **Repeat interval:** {site.metadata['orbit_repeat_days']} days  
        **Burned pixels:** {float(site.burn_mask.mean()) * 100:.1f}%  
        **Terrain:** {float(site.slope.mean()):.1f}° mean slope
        """
    )
    if risk_name == "High":
        st.error("Elevated runoff/erosion signal: steep or burned terrain overlaps wetter cells.")
    elif risk_name == "Medium":
        st.warning("Watch signal: local steep and burned cells may mobilise sediment after rain.")
    else:
        st.success("Lower scene-average runoff signal; continue monitoring local hotspots.")
    st.caption(
        f"Classes: {RISK_LEGEND}. Prototype index = 50% slope + 32% soil wetness "
        "+ 18% burn flag. It is an explainable hackathon indicator, not a calibrated hazard model."
    )
    st.download_button(
        "Download mock slope GeoTIFF",
        data=slope_geotiff_bytes(site),
        file_name=f"{site_id}_mock_slope.tif",
        mime="image/tiff",
        width="stretch",
    )

st.subheader("Drought signals")
rain_col, soil_col = st.columns(2)
with rain_col:
    st.plotly_chart(
        rainfall_chart(site.rainfall, climatology_name),
        width="stretch",
        theme=None,
    )
with soil_col:
    st.plotly_chart(soil_chart(site, selected_time), width="stretch", theme=None)
    st.caption(
        "The red dotted line, labelled Selected slider date, marks the date "
        "chosen on the NISAR 12-day observation slider."
    )

st.subheader("Terrain controls & derived hazard")
slope_col, risk_col = st.columns(2)
with slope_col:
    st.plotly_chart(
        raster_figure(
            site.slope.values,
            site.slope.x.values,
            site.slope.y.values,
            "DEM-derived slope",
            "slope",
        ),
        width="stretch",
        theme=None,
    )
with risk_col:
    st.plotly_chart(
        raster_figure(
            risk_slice.values,
            risk_slice.x.values,
            risk_slice.y.values,
            f"Runoff / erosion risk · {selected_time:%d %b}",
            "risk",
        ),
        width="stretch",
        theme=None,
    )
    st.caption(f"Heatmap classes: {RISK_LEGEND}.")

with st.expander("Data contract & Earthdata hand-off"):
    st.code(
        "load_site_data(site_id, source='mock')  # today\n"
        "load_site_data(site_id, source='earthdata')  # future",
        language="python",
    )
    st.markdown(
        "The loader returns a GeoDataFrame boundary, CHIRPS-like rainfall table, "
        "NISAR SME2-like xarray Dataset, raster-compatible slope layer, burn mask, "
        "and derived risk Dataset. The app never reads source files directly."
    )
    st.download_button(
        "Download all-site mock summary (JSON)",
        data=json.dumps(build_summary(), indent=2),
        file_name="summary.json",
        mime="application/json",
    )

st.caption(
    f"MOCK DATA · Generated deterministically · Dashboard rendered {datetime.now():%Y-%m-%d} · "
    "NASA Space Apps 2026 concept"
)
