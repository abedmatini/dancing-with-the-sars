"use strict";

const state = {
  summary: null,
  grids: null,
  siteId: null,
  timeIndex: 0,
  map: null,
  siteLayer: null,
  riskLayer: null,
};

const $ = (selector) => document.querySelector(selector);
const chartConfig = { responsive: true, displayModeBar: false };
const plotFont = { family: "Inter, system-ui, sans-serif", color: "#496362" };
const riskScale = [
  [0, "#2b8b67"],
  [0.4, "#e7c65b"],
  [0.65, "#e58037"],
  [1, "#b62f3b"],
];

function meanGrid(grid) {
  let total = 0;
  let count = 0;
  grid.forEach((row) => row.forEach((value) => {
    if (Number.isFinite(value)) {
      total += value;
      count += 1;
    }
  }));
  return total / count;
}

function classifyRisk(value) {
  if (value >= 65) return { label: "High", level: "high" };
  if (value >= 40) return { label: "Medium", level: "medium" };
  return { label: "Low", level: "low" };
}

function riskColor(value) {
  const stops = [
    [0, [43, 139, 103]],
    [40, [231, 198, 91]],
    [65, [229, 128, 55]],
    [100, [182, 47, 59]],
  ];
  const clamped = Math.max(0, Math.min(100, value));
  let lower = stops[0];
  let upper = stops[stops.length - 1];
  for (let i = 1; i < stops.length; i += 1) {
    if (clamped <= stops[i][0]) {
      lower = stops[i - 1];
      upper = stops[i];
      break;
    }
  }
  const ratio = (clamped - lower[0]) / Math.max(1, upper[0] - lower[0]);
  const rgb = lower[1].map((channel, index) =>
    Math.round(channel + ratio * (upper[1][index] - channel))
  );
  return `rgb(${rgb.join(",")})`;
}

function plotLayout(yTitle, options = {}) {
  return {
    autosize: true,
    height: 325,
    margin: { l: 56, r: 20, t: 24, b: 48 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "#ffffff",
    font: plotFont,
    hovermode: options.hovermode || "x unified",
    showlegend: options.showlegend ?? true,
    legend: { orientation: "h", x: 0, y: 1.12, font: { size: 11 } },
    xaxis: {
      gridcolor: "#edf2f0",
      linecolor: "#d8e5e1",
      tickfont: { size: 10 },
      title: options.xTitle || "",
    },
    yaxis: {
      gridcolor: "#edf2f0",
      linecolor: "#d8e5e1",
      tickfont: { size: 10 },
      title: yTitle,
      ...(options.yaxis || {}),
    },
  };
}

function initMap() {
  state.map = L.map("map", {
    zoomControl: true,
    scrollWheelZoom: false,
  }).setView([-34.02, 18.48], 10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(state.map);
  state.siteLayer = L.featureGroup().addTo(state.map);
  state.riskLayer = L.featureGroup().addTo(state.map);
}

function drawSiteContext() {
  state.siteLayer.clearLayers();
  Object.entries(state.grids.sites).forEach(([siteId, site]) => {
    const [west, south, east, north] = site.bounds;
    const selected = siteId === state.siteId;
    L.rectangle([[south, west], [north, east]], {
      color: selected ? "#0d766f" : "#688783",
      weight: selected ? 3 : 1.5,
      fill: false,
    }).bindTooltip(site.name).addTo(state.siteLayer);
    L.circleMarker(site.center, {
      radius: selected ? 7 : 5,
      color: "#102f31",
      weight: 2,
      fillColor: selected ? "#f0ca7c" : "#72a69e",
      fillOpacity: 1,
    }).bindTooltip(`${site.name}${selected ? " · selected" : ""}`).addTo(state.siteLayer);
  });
}

function axisEdges(values) {
  if (values.length < 2) return [values[0] - 0.001, values[0] + 0.001];
  const edges = [values[0] + (values[0] - values[1]) / 2];
  for (let i = 0; i < values.length - 1; i += 1) {
    edges.push((values[i] + values[i + 1]) / 2);
  }
  edges.push(values.at(-1) + (values.at(-1) - values.at(-2)) / 2);
  return edges;
}

function drawRiskGrid(site, riskGrid) {
  state.riskLayer.clearLayers();
  const latEdges = axisEdges(site.latitude);
  const lonEdges = axisEdges(site.longitude);
  riskGrid.forEach((row, yIndex) => {
    row.forEach((value, xIndex) => {
      L.rectangle(
        [
          [Math.min(latEdges[yIndex], latEdges[yIndex + 1]), Math.min(lonEdges[xIndex], lonEdges[xIndex + 1])],
          [Math.max(latEdges[yIndex], latEdges[yIndex + 1]), Math.max(lonEdges[xIndex], lonEdges[xIndex + 1])],
        ],
        {
          stroke: false,
          fillColor: riskColor(value),
          fillOpacity: 0.64,
          interactive: false,
        }
      ).addTo(state.riskLayer);
    });
  });
}

function renderRainfallChart(summary) {
  const rainfall = summary.monthly_rainfall;
  Plotly.react(
    "rainfall-chart",
    [
      {
        type: "bar",
        x: rainfall.map((row) => row.month),
        y: rainfall.map((row) => row.observed_mm),
        name: "Observed (mock)",
        marker: { color: "#0d766f" },
        hovertemplate: "%{y:.1f} mm<extra>Observed</extra>",
      },
      {
        type: "scatter",
        mode: "lines+markers",
        x: rainfall.map((row) => row.month),
        y: rainfall.map((row) => row.climatology_mm),
        name: "Climatology",
        line: { color: "#d69b38", width: 3 },
        marker: { size: 6 },
        hovertemplate: "%{y:.1f} mm<extra>Climatology</extra>",
      },
    ],
    plotLayout("rainfall (mm)"),
    chartConfig
  );
}

function renderSoilChart(summary, selectedDate) {
  const soil = summary.soil_moisture_mean;
  const selected = soil.find((row) => row.date === selectedDate);
  Plotly.react(
    "soil-chart",
    [
      {
        type: "scatter",
        mode: "lines+markers",
        x: soil.map((row) => row.date),
        y: soil.map((row) => row.m3_m3),
        name: "Site mean",
        line: { color: "#0d766f", width: 3 },
        marker: { size: 6 },
        hovertemplate: "%{y:.3f} m³/m³<extra>Site mean</extra>",
      },
      {
        type: "scatter",
        mode: "markers",
        x: [selectedDate],
        y: [selected.m3_m3],
        name: "Selected scene",
        marker: { color: "#b62f3b", size: 11, line: { color: "white", width: 2 } },
        hovertemplate: "%{y:.3f} m³/m³<extra>Selected</extra>",
      },
    ],
    plotLayout("soil moisture (m³/m³)", { yaxis: { range: [0.04, 0.38] } }),
    chartConfig
  );
}

function renderHeatmap(target, values, site, type) {
  const isRisk = type === "risk";
  Plotly.react(
    target,
    [{
      type: "heatmap",
      z: values,
      x: site.longitude,
      y: site.latitude,
      colorscale: isRisk ? riskScale : "Earth",
      zmin: 0,
      zmax: isRisk ? 100 : 48,
      colorbar: {
        title: isRisk ? "index" : "degrees",
        thickness: 10,
        len: 0.8,
        tickfont: { size: 9 },
      },
      hovertemplate: `Lon %{x:.4f}<br>Lat %{y:.4f}<br>${isRisk ? "Risk" : "Slope"} %{z:.1f}<extra></extra>`,
    }],
    plotLayout("", {
      hovermode: "closest",
      showlegend: false,
      xTitle: "longitude",
      yaxis: { scaleanchor: "x", scaleratio: 1 },
    }),
    chartConfig
  );
}

function renderScene() {
  const site = state.grids.sites[state.siteId];
  const summary = state.summary.sites[state.siteId];
  const date = site.dates[state.timeIndex];
  const soilGrid = site.soil_moisture[state.timeIndex];
  const riskGrid = site.risk_index[state.timeIndex];
  const soilMean = meanGrid(soilGrid);
  const riskMean = meanGrid(riskGrid);
  const risk = classifyRisk(riskMean);
  const flattenedRisk = riskGrid.flat();
  const highCount = flattenedRisk.filter((value) => value >= 65).length;
  const highPercent = (100 * highCount) / flattenedRisk.length;
  const month = date.slice(0, 7);
  const rainfall = summary.monthly_rainfall.find((row) => row.month === month);

  $("#selected-date").textContent = new Date(`${date}T12:00:00`).toLocaleDateString(
    "en-ZA", { day: "2-digit", month: "short", year: "numeric" }
  );
  $("#soil-kpi").textContent = soilMean.toFixed(3);
  $("#risk-kpi").textContent = risk.label;
  $("#risk-detail").textContent = `Index ${riskMean.toFixed(0)} / 100`;
  $("#high-kpi").textContent = `${highPercent.toFixed(1)}%`;
  $("#terrain-detail").textContent = `${highCount} of ${flattenedRisk.length} cells`;
  $(".risk-kpi").dataset.level = risk.level;
  $("#risk-chart-date").textContent = date;

  if (rainfall) {
    $("#rain-kpi").textContent = `${rainfall.percent_normal.toFixed(0)}%`;
    $("#rain-detail").textContent = `${rainfall.anomaly_mm.toFixed(1)} mm anomaly · ${month}`;
  }

  drawRiskGrid(site, riskGrid);
  renderSoilChart(summary, date);
  renderHeatmap("risk-chart", riskGrid, site, "risk");
}

function renderSite() {
  const site = state.grids.sites[state.siteId];
  const summary = state.summary.sites[state.siteId];
  state.timeIndex = site.dates.length - 1;

  $("#site-name").textContent = site.name;
  $("#site-description").textContent = site.description;
  $("#time-slider").max = site.dates.length - 1;
  $("#time-slider").value = state.timeIndex;

  drawSiteContext();
  const [west, south, east, north] = site.bounds;
  state.map.fitBounds([[south, west], [north, east]], { padding: [18, 18] });
  renderRainfallChart(summary);
  renderHeatmap("slope-chart", site.slope_degrees, site, "slope");
  renderScene();
}

async function boot() {
  try {
    const [summaryResponse, gridsResponse] = await Promise.all([
      fetch("data/summary.json"),
      fetch("data/grids.json"),
    ]);
    if (!summaryResponse.ok || !gridsResponse.ok) throw new Error("Data response failed");
    [state.summary, state.grids] = await Promise.all([
      summaryResponse.json(),
      gridsResponse.json(),
    ]);

    const siteSelect = $("#site-select");
    Object.entries(state.grids.sites).forEach(([siteId, site]) => {
      const option = document.createElement("option");
      option.value = siteId;
      option.textContent = site.name;
      siteSelect.append(option);
    });
    state.siteId = siteSelect.value;

    initMap();
    renderSite();

    siteSelect.addEventListener("change", (event) => {
      state.siteId = event.target.value;
      renderSite();
    });
    $("#time-slider").addEventListener("input", (event) => {
      state.timeIndex = Number(event.target.value);
      renderScene();
    });

    $("#loading-state").hidden = true;
    $("#dashboard").hidden = false;
    setTimeout(() => state.map.invalidateSize(), 0);
  } catch (error) {
    console.error(error);
    $("#loading-state").hidden = true;
    $("#error-state").hidden = false;
  }
}

window.addEventListener("DOMContentLoaded", boot);
