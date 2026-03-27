const numberFormatter = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});

const percentFormatter = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const TABLE_START_YEAR = 2026;
const TABLE_START_QUARTER = 4;

let historyRecords = [];

function buildDisplayQuarterLabels(length) {
  const labels = [];
  let year = TABLE_START_YEAR;
  let quarter = TABLE_START_QUARTER;

  for (let index = 0; index < length; index += 1) {
    labels.push(`Q${quarter} ${year}`);
    quarter += 1;
    if (quarter === 5) {
      quarter = 1;
      year += 1;
    }
  }

  return labels;
}

function formatTableValue(value) {
  const truncatedThousands = Math.trunc(value / 1000);
  return `${truncatedThousands}k`;
}

function updateEffectiveStats() {
  const mu = Number(document.getElementById("mu").value);
  const sigma = Number(document.getElementById("sigma").value);
  const growthMean = Math.exp(mu + (sigma ** 2) / 2);
  const growthVariance = (Math.exp(sigma ** 2) - 1) * Math.exp(2 * mu + sigma ** 2);
  const returnMean = growthMean - 1;
  const returnStd = Math.sqrt(growthVariance);

  document.getElementById("effectiveStats").textContent =
    `Implied quarterly return distribution: mean ${percentFormatter.format(returnMean * 100)}%, ` +
    `std ${percentFormatter.format(returnStd * 100)}%.`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function buildHistoryOptions(quarters) {
  const select = document.getElementById("startQuarter");
  select.innerHTML = "";
  for (const quarter of quarters) {
    const option = document.createElement("option");
    option.value = quarter;
    option.textContent = quarter;
    select.appendChild(option);
  }
}

function renderHistoryChart(records, selectedQuarter) {
  const quarters = records.map((record) => record.quarter);
  const values = records.map((record) => record.quarter_return * 100);
  const colors = records.map((record) => (record.quarter === selectedQuarter ? "#d95f02" : "#0f4c5c"));

  Plotly.newPlot(
    "historyChart",
    [
      {
        type: "bar",
        x: quarters,
        y: values,
        marker: { color: colors },
        hovertemplate: "%{x}<br>%{y:.2f}%<extra></extra>",
      },
    ],
    {
      margin: { t: 12, r: 12, b: 72, l: 56 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: { tickangle: -45 },
      yaxis: { title: "Quarter return (%)" },
    },
    { responsive: true }
  );
}

function renderProjectionChart(series) {
  const traces = series.map((entry) => ({
    type: "scatter",
    mode: "lines",
    name: `P${entry.percentile}`,
    x: entry.quarter_labels,
    y: entry.values,
    line: {
      width: entry.percentile === 50 ? 4 : 2,
    },
    hovertemplate: `${entry.percentile}th percentile<br>%{x}: %{y:,.0f}<extra></extra>`,
  }));

  Plotly.newPlot(
    "projectionChart",
    traces,
    {
      showlegend: false,
      margin: { t: 12, r: 12, b: 48, l: 72 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      yaxis: {
        title: "Balance (£)",
        tickprefix: "£",
      },
    },
    { responsive: true }
  );
}

function renderTwentileTable(rows, quarters) {
  const thead = document.querySelector("#twentileTable thead");
  const tbody = document.querySelector("#twentileTable tbody");
  const displayQuarters = buildDisplayQuarterLabels(quarters.length);

  thead.innerHTML = "";
  tbody.innerHTML = "";

  const headRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.textContent = "Percentile";
  headRow.appendChild(corner);
  for (const quarter of displayQuarters) {
    const cell = document.createElement("th");
    cell.textContent = quarter;
    headRow.appendChild(cell);
  }
  thead.appendChild(headRow);

  for (const row of rows) {
    const tr = document.createElement("tr");
    const label = document.createElement("th");
    label.textContent = `P${row.percentile}`;
    tr.appendChild(label);
    for (const value of row.values) {
      const td = document.createElement("td");
      td.textContent = formatTableValue(value);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

async function applyHistoryStats() {
  const startQuarter = document.getElementById("startQuarter").value;
  const stats = await fetchJson(`/api/history/stats?start_quarter=${encodeURIComponent(startQuarter)}`);
  document.getElementById("mu").value = stats.mu.toFixed(4);
  document.getElementById("sigma").value = stats.sigma.toFixed(4);
  document.getElementById(
    "historyStats"
  ).textContent = `From ${stats.start_quarter} onward: mu ${numberFormatter.format(stats.mu)}, sigma ${numberFormatter.format(
    stats.sigma
  )}, observations ${stats.observations}.`;
  updateEffectiveStats();
  renderHistoryChart(historyRecords, startQuarter);
}

async function runSimulation() {
  const payload = {
    withdrawal: Number(document.getElementById("withdrawal").value),
    mu: Number(document.getElementById("mu").value),
    sigma: Number(document.getElementById("sigma").value),
    simulations: Number(document.getElementById("simulations").value),
    seed: Number(document.getElementById("seed").value),
  };

  const result = await fetchJson("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  renderProjectionChart(result.chart_percentiles);
  renderTwentileTable(result.twentiles, result.quarters);
}

async function init() {
  const history = await fetchJson("/api/history");
  historyRecords = history.records;
  buildHistoryOptions(history.quarters);
  document.getElementById("startQuarter").value = history.default_stats.start_quarter;
  renderHistoryChart(history.records, history.default_stats.start_quarter);
  await applyHistoryStats();
  await runSimulation();

  document.getElementById("useHistory").addEventListener("click", applyHistoryStats);
  document.getElementById("runSimulation").addEventListener("click", runSimulation);
  document.getElementById("startQuarter").addEventListener("change", applyHistoryStats);
  document.getElementById("mu").addEventListener("input", updateEffectiveStats);
  document.getElementById("sigma").addEventListener("input", updateEffectiveStats);
}

window.addEventListener("DOMContentLoaded", () => {
  init().catch((error) => {
    document.getElementById("historyStats").textContent = `Error: ${error.message}`;
  });
});
