const numberFormatter = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});

const percentFormatter = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

let historyRecords = [];

function formatTableValue(value) {
  const truncatedThousands = Math.trunc(value / 1000);
  return `${truncatedThousands}k`;
}

function updateEffectiveStats() {
  const mu = Number(document.getElementById("mu").value);
  const sigma = Number(document.getElementById("sigma").value);
  const yearlyMu = 4 * mu;
  const yearlySigma = 2 * sigma;
  const growthMean = Math.exp(yearlyMu + (yearlySigma ** 2) / 2);
  const growthVariance = (Math.exp(yearlySigma ** 2) - 1) * Math.exp(2 * yearlyMu + yearlySigma ** 2);
  const returnMean = growthMean - 1;
  const returnStd = Math.sqrt(growthVariance);

  document.getElementById("effectiveStats").textContent =
    `Implied yearly return distribution from the selected quarterly log parameters: ` +
    `mean ${percentFormatter.format(returnMean * 100)}%, std ${percentFormatter.format(returnStd * 100)}%.`;
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

function renderHistoryChart(records, selectedQuarter, endQuarter) {
  const quarters = records.map((record) => record.quarter);
  const values = records.map((record) => record.annualized_return * 100);
  const selectedRecord = records.find((record) => record.quarter === selectedQuarter);

  Plotly.newPlot(
    "historyChart",
    [
      {
        type: "scatter",
        mode: "lines",
        x: quarters,
        y: values,
        line: { color: "#0f4c5c", width: 2.5 },
        hovertemplate: `Start %{x}<br>Annualized total return to ${endQuarter}: %{y:.2f}%<extra></extra>`,
      },
      {
        type: "scatter",
        mode: "markers",
        x: selectedRecord ? [selectedRecord.quarter] : [],
        y: selectedRecord ? [selectedRecord.annualized_return * 100] : [],
        marker: { color: "#d95f02", size: 11 },
        hovertemplate: `Selected %{x}<br>Annualized total return to ${endQuarter}: %{y:.2f}%<extra></extra>`,
      },
    ],
    {
      margin: { t: 12, r: 12, b: 72, l: 56 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: { tickangle: -45 },
      yaxis: { title: "Annualized total return (% per year)" },
      showlegend: false,
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

  thead.innerHTML = "";
  tbody.innerHTML = "";

  const headRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.textContent = "Percentile";
  headRow.appendChild(corner);
  for (const quarter of quarters) {
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
  ).textContent =
    `From ${stats.start_quarter} through ${stats.end_quarter} inclusive: ` +
    `annualized total return ${percentFormatter.format(stats.annualized_return * 100)}% per year. ` +
    `Quarterly log mu ${numberFormatter.format(stats.mu)}, quarterly log sigma ${numberFormatter.format(stats.sigma)}, ` +
    `${stats.observations} quarterly observations.`;
  updateEffectiveStats();
  renderHistoryChart(historyRecords, startQuarter, stats.end_quarter);
}

async function runSimulation() {
  const payload = {
    initial_balance: Number(document.getElementById("initialBalance").value),
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
  renderHistoryChart(history.records, history.default_stats.start_quarter, history.end_quarter);
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
