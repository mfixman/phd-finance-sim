const numberFormatter = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});

const percentFormatter = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const currencyFormatter = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

const DEFAULT_INITIAL_BALANCE = 303200;

let historyRecords = [];
let historyEndQuarter = "";

function taxesEnabled() {
  return document.getElementById("applyTaxes").checked;
}

function formatTableValue(value) {
  const truncatedThousands = Math.trunc(value / 1000);
  return `${truncatedThousands}k`;
}

function tableHighlightTargets(applyTaxes) {
  return {
    "Q1 2026": applyTaxes ? 296000 : 308000,
    "Q2 2026": applyTaxes ? 279000 : 288000,
  };
}

function highlightedTwentileRows(rows, quarters, applyTaxes) {
  const quarterTargets = tableHighlightTargets(applyTaxes);
  const highlights = new Map();

  for (const [quarterLabel, target] of Object.entries(quarterTargets)) {
    const quarterIndex = quarters.indexOf(quarterLabel);
    if (quarterIndex === -1) {
      continue;
    }

    const targetShown = Math.trunc(target / 1000);
    const rankedRows = rows
      .map((row, rowIndex) => ({
        rowIndex,
        shownValue: Math.trunc(row.values[quarterIndex] / 1000),
        distance: Math.abs(Math.trunc(row.values[quarterIndex] / 1000) - targetShown),
      }))
      .sort((left, right) => left.distance - right.distance || left.rowIndex - right.rowIndex);

    const selectedRows = new Set([rankedRows[0].rowIndex]);
    if (rankedRows.length > 1) {
      const firstValue = rankedRows[0].shownValue;
      const secondValue = rankedRows[1].shownValue;
      const lowerValue = Math.min(firstValue, secondValue);
      const upperValue = Math.max(firstValue, secondValue);
      const q25 = lowerValue + 0.25 * (upperValue - lowerValue);
      const q75 = lowerValue + 0.75 * (upperValue - lowerValue);

      if (targetShown >= q25 && targetShown <= q75) {
        selectedRows.add(rankedRows[1].rowIndex);
      }
    }
    highlights.set(quarterLabel, selectedRows);
  }

  return highlights;
}

function clearIdealWithdrawalResult() {
  document.getElementById("idealWithdrawalResult").textContent = "";
}

function updateInitialBalanceDisplay(effectiveInitialBalance, applyTaxes) {
  const input = document.getElementById("initialBalanceDisplay");
  input.value = currencyFormatter.format(effectiveInitialBalance);
  input.title = applyTaxes
    ? `Base £303,200 minus £14,290 tax adjustment on unrealised gains`
    : `Base ${currencyFormatter.format(DEFAULT_INITIAL_BALANCE)}`;
}

function updateEffectiveStats() {
  const payload = {
    initial_balance: DEFAULT_INITIAL_BALANCE,
    apply_taxes: taxesEnabled(),
    mu: Number(document.getElementById("mu").value),
    sigma: Number(document.getElementById("sigma").value),
  };

  return fetchJson("/api/effective-stats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((result) => {
    updateInitialBalanceDisplay(result.effective_initial_balance, result.apply_taxes);
    document.getElementById("effectiveStats").textContent =
      `${result.apply_taxes ? "With taxes" : "Without taxes"} the effective starting balance is ${currencyFormatter.format(
        result.effective_initial_balance
      )}. ` +
      `Implied yearly return distribution from the selected quarterly log parameters: ` +
      `mean ${percentFormatter.format(result.yearly_mean * 100)}%, std ${percentFormatter.format(
        result.yearly_std * 100
      )}%.`;
  });
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

async function loadHistoryData() {
  const history = await fetchJson("/api/history?apply_taxes=false");
  historyRecords = history.records;
  historyEndQuarter = history.end_quarter;
  const currentSelection = document.getElementById("startQuarter").value;
  buildHistoryOptions(history.quarters);
  document.getElementById("startQuarter").value =
    history.quarters.includes(currentSelection) && currentSelection ? currentSelection : history.default_stats.start_quarter;
  return history;
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

function renderTwentileTable(rows, quarters, applyTaxes) {
  const thead = document.querySelector("#twentileTable thead");
  const tbody = document.querySelector("#twentileTable tbody");
  const highlights = highlightedTwentileRows(rows, quarters, applyTaxes);

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

  for (const [rowIndex, row] of rows.entries()) {
    const tr = document.createElement("tr");
    const label = document.createElement("th");
    label.textContent = `P${row.percentile}`;
    tr.appendChild(label);
    for (const [quarterIndex, value] of row.values.entries()) {
      const td = document.createElement("td");
      const displayValue = formatTableValue(value);
      const quarterLabel = quarters[quarterIndex];
      if (highlights.get(quarterLabel)?.has(rowIndex)) {
        td.classList.add("table-highlight");
        const strong = document.createElement("strong");
        strong.textContent = displayValue;
        td.appendChild(strong);
      } else {
        td.textContent = displayValue;
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

async function applyHistoryStats(applyToInputs = true) {
  const startQuarter = document.getElementById("startQuarter").value;
  const untaxedStats = await fetchJson(
    `/api/history/stats?start_quarter=${encodeURIComponent(startQuarter)}&apply_taxes=false`
  );
  const taxedStats = await fetchJson(
    `/api/history/stats?start_quarter=${encodeURIComponent(startQuarter)}&apply_taxes=true`
  );
  const stats = untaxedStats;
  if (applyToInputs) {
    document.getElementById("mu").value = stats.mu.toFixed(4);
    document.getElementById("sigma").value = stats.sigma.toFixed(4);
  }
  document.getElementById(
    "historyStats"
  ).textContent =
    `From ${stats.start_quarter} through ${stats.end_quarter} inclusive: ` +
    `pre-tax annualized total return ${percentFormatter.format(stats.annualized_return * 100)}% per year. ` +
    `Quarterly log mu ${numberFormatter.format(stats.mu)}, quarterly log sigma ${numberFormatter.format(stats.sigma)}, ` +
    `${stats.observations} quarterly observations. These are the parameters used for simulation.`;
  document.getElementById("verificationStats").textContent =
    `Verification for ${startQuarter} to ${stats.end_quarter}: ` +
    `without taxes annualized growth ${percentFormatter.format(untaxedStats.annualized_return * 100)}% per year, ` +
    `quarterly log mu ${numberFormatter.format(untaxedStats.mu)}, quarterly log sigma ${numberFormatter.format(
      untaxedStats.sigma
    )}; with taxes annualized growth ${percentFormatter.format(taxedStats.annualized_return * 100)}% per year, ` +
    `quarterly log mu ${numberFormatter.format(taxedStats.mu)}, quarterly log sigma ${numberFormatter.format(
      taxedStats.sigma
    )}. Sigma here is a standard deviation of log returns, so it is not a percent figure. Tax mode is applied in the simulation, not fitted twice.`;
  await updateEffectiveStats();
  renderHistoryChart(historyRecords, startQuarter, stats.end_quarter);
}

async function runSimulation() {
  const payload = {
    initial_balance: DEFAULT_INITIAL_BALANCE,
    apply_taxes: taxesEnabled(),
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
  renderTwentileTable(result.twentiles, result.quarters, taxesEnabled());
}

async function findIdealWithdrawal() {
  const payload = {
    initial_balance: DEFAULT_INITIAL_BALANCE,
    apply_taxes: taxesEnabled(),
    mu: Number(document.getElementById("mu").value),
    sigma: Number(document.getElementById("sigma").value),
    simulations: Number(document.getElementById("simulations").value),
    seed: Number(document.getElementById("seed").value),
  };

  const result = await fetchJson("/api/ideal-withdrawal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  document.getElementById("withdrawal").value = result.recommended_withdrawal.toFixed(0);
  document.getElementById("idealWithdrawalResult").textContent =
    `Ideal X for a 5th percentile of £100k at the start of ${result.target_quarter}: ` +
    `${currencyFormatter.format(result.recommended_withdrawal)}. ` +
    `Achieved 5th percentile: ${currencyFormatter.format(result.achieved_balance)}.`;
  await runSimulation();
}

async function refreshTaxMode() {
  clearIdealWithdrawalResult();
  await applyHistoryStats(false);
  await runSimulation();
}

async function init() {
  const history = await loadHistoryData();
  updateInitialBalanceDisplay(DEFAULT_INITIAL_BALANCE, false);
  await applyHistoryStats();
  await runSimulation();

  document.getElementById("useHistory").addEventListener("click", () => {
    clearIdealWithdrawalResult();
    applyHistoryStats();
  });
  document.getElementById("idealWithdrawal").addEventListener("click", findIdealWithdrawal);
  document.getElementById("runSimulation").addEventListener("click", runSimulation);
  document.getElementById("startQuarter").addEventListener("change", () => {
    clearIdealWithdrawalResult();
    applyHistoryStats();
  });
  document.getElementById("applyTaxes").addEventListener("change", refreshTaxMode);
  document.getElementById("mu").addEventListener("change", () => {
    clearIdealWithdrawalResult();
    updateEffectiveStats();
  });
  document.getElementById("sigma").addEventListener("change", () => {
    clearIdealWithdrawalResult();
    updateEffectiveStats();
  });
  document.getElementById("withdrawal").addEventListener("change", clearIdealWithdrawalResult);
  document.getElementById("simulations").addEventListener("change", clearIdealWithdrawalResult);
  document.getElementById("seed").addEventListener("change", clearIdealWithdrawalResult);
}

window.addEventListener("DOMContentLoaded", () => {
  init().catch((error) => {
    document.getElementById("historyStats").textContent = `Error: ${error.message}`;
  });
});
