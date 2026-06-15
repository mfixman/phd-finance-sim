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

const STORAGE_KEY = "unemployment-withdrawal-simulator-values";

const DEFAULT_CONFIG = {
  initial_balance: 100000,
  start_year: 2025,
  start_quarter: 4,
  end_year: 2029,
  end_quarter: 4,
  primary_withdrawal: {
    name: "Primary quarterly withdrawal",
    amount: 0,
    start_year: 2025,
    start_quarter: 4,
    end_year: 2029,
    end_quarter: 4,
    cadence: "quarterly",
    special: "primary_quarterly",
  },
  withdrawal_rules: [],
  goal_year: 2029,
  goal_quarter: 4,
  goal_balance: 100000,
  goal_percentile: 5,
  mu: 0.02,
  sigma: 0.08,
  simulations: 40000,
  seed: 42,
  history_start_quarter: "",
};

let historyRecords = [];
let currentConfig = structuredClone(DEFAULT_CONFIG);

function quarterLabel(year, quarter) {
  return `Q${quarter} ${year}`;
}

function formatTableValue(value) {
  return `${Math.trunc(value / 1000)}k`;
}

function setStatus(message) {
  document.getElementById("statusText").textContent = message;
}

function updatePrimaryWithdrawalLabel(amount = Number(document.getElementById("primaryWithdrawalAmount").value)) {
  const label = document.getElementById("primaryWithdrawalAmountLabel");
  label.textContent = amount > 0 ? `Amount (${currencyFormatter.format(amount)})` : "Amount";
}

function quarterValue(id) {
  return Number(document.getElementById(id).dataset.quarter);
}

function setQuarterValue(id, quarter) {
  const control = document.getElementById(id);
  control.dataset.quarter = String(quarter);
  for (const button of control.querySelectorAll("button")) {
    button.classList.toggle("active", Number(button.dataset.quarter) === quarter);
  }
}

function buildQuarterControl(id, onChange) {
  const control = document.getElementById(id);
  control.innerHTML = "";
  for (const quarter of [1, 2, 3, 4]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quarter-button";
    button.dataset.quarter = String(quarter);
    button.textContent = `Q${quarter}`;
    button.addEventListener("click", () => {
      setQuarterValue(id, quarter);
      onChange();
    });
    control.appendChild(button);
  }
  setQuarterValue(id, Number(control.dataset.quarter || 1));
}

function normalizeRule(rule = {}, fallbackIndex = 0) {
  const startYear = Number(rule.start_year ?? currentConfig.start_year);
  const startQuarter = Number(rule.start_quarter ?? currentConfig.start_quarter);
  return {
    name: String(rule.name || `Withdrawal ${fallbackIndex + 1}`),
    amount: Math.max(0, Number(rule.amount || 0)),
    cadence: ["once", "quarterly", "annual"].includes(rule.cadence) ? rule.cadence : "once",
    start_year: startYear,
    start_quarter: Number(rule.start_quarter ?? startQuarter),
    end_year: Number(rule.end_year ?? startYear),
    end_quarter: Number(rule.end_quarter ?? startQuarter),
    ...(rule.special ? { special: String(rule.special) } : {}),
  };
}

function normalizePrimaryWithdrawal(rule = {}) {
  const fallback = DEFAULT_CONFIG.primary_withdrawal;
  return {
    ...fallback,
    ...normalizeRule(
      {
        ...fallback,
        ...rule,
        name: "Primary quarterly withdrawal",
        cadence: "quarterly",
        special: "primary_quarterly",
      },
      0
    ),
  };
}

function normalizeConfig(config = {}) {
  const incomingRules = Array.isArray(config.withdrawal_rules)
    ? config.withdrawal_rules.map((rule, index) => normalizeRule(rule, index))
    : [];
  const primaryRule =
    config.primary_withdrawal || incomingRules.find((rule) => rule.special === "primary_quarterly");

  return {
    ...DEFAULT_CONFIG,
    ...config,
    initial_balance: Math.max(0, Number(config.initial_balance ?? DEFAULT_CONFIG.initial_balance)),
    start_year: Number(config.start_year ?? DEFAULT_CONFIG.start_year),
    start_quarter: Number(config.start_quarter ?? DEFAULT_CONFIG.start_quarter),
    end_year: Number(config.end_year ?? DEFAULT_CONFIG.end_year),
    end_quarter: Number(config.end_quarter ?? DEFAULT_CONFIG.end_quarter),
    goal_year: Number(config.goal_year ?? DEFAULT_CONFIG.goal_year),
    goal_quarter: Number(config.goal_quarter ?? DEFAULT_CONFIG.goal_quarter),
    goal_balance: Math.max(0, Number(config.goal_balance ?? DEFAULT_CONFIG.goal_balance)),
    goal_percentile: Math.min(99, Math.max(1, Number(config.goal_percentile ?? DEFAULT_CONFIG.goal_percentile))),
    mu: Number(config.mu ?? DEFAULT_CONFIG.mu),
    sigma: Math.max(0, Number(config.sigma ?? DEFAULT_CONFIG.sigma)),
    simulations: Math.min(250000, Math.max(1000, Number(config.simulations ?? DEFAULT_CONFIG.simulations))),
    seed: Math.max(0, Number(config.seed ?? DEFAULT_CONFIG.seed)),
    primary_withdrawal: normalizePrimaryWithdrawal(primaryRule),
    withdrawal_rules: incomingRules.filter((rule) => rule.special !== "primary_quarterly"),
  };
}

function combinedWithdrawalRules(config, options = {}) {
  const primary = normalizePrimaryWithdrawal(config.primary_withdrawal);
  const primaryRule =
    primary.amount > 0 || options.includeZeroPrimary
      ? [
          {
            ...primary,
            name: "Primary quarterly withdrawal",
            cadence: "quarterly",
            special: "primary_quarterly",
          },
        ]
      : [];
  return [...primaryRule, ...config.withdrawal_rules.map((rule, index) => normalizeRule(rule, index))];
}

function exportConfig(config = collectConfig(), options = {}) {
  return {
    ...config,
    withdrawal_rules: combinedWithdrawalRules(config, options),
  };
}

function collectConfig() {
  return normalizeConfig({
    initial_balance: Number(document.getElementById("initialBalance").value),
    start_year: Number(document.getElementById("projectionStartYear").value),
    start_quarter: quarterValue("projectionStartQuarter"),
    end_year: Number(document.getElementById("projectionEndYear").value),
    end_quarter: quarterValue("projectionEndQuarter"),
    goal_year: Number(document.getElementById("goalYear").value),
    goal_quarter: quarterValue("goalQuarter"),
    goal_balance: Number(document.getElementById("goalBalance").value),
    goal_percentile: Number(document.getElementById("goalPercentile").value),
    mu: Number(document.getElementById("mu").value),
    sigma: Number(document.getElementById("sigma").value),
    simulations: currentConfig.simulations,
    seed: currentConfig.seed,
    history_start_quarter: document.getElementById("startQuarter").value,
    primary_withdrawal: {
      name: "Primary quarterly withdrawal",
      amount: Number(document.getElementById("primaryWithdrawalAmount").value),
      cadence: "quarterly",
      special: "primary_quarterly",
      start_year: Number(document.getElementById("primaryWithdrawalStartYear").value),
      start_quarter: Number(document.getElementById("primaryWithdrawalStartQuarter").value),
      end_year: Number(document.getElementById("primaryWithdrawalEndYear").value),
      end_quarter: Number(document.getElementById("primaryWithdrawalEndQuarter").value),
    },
    withdrawal_rules: Array.from(document.querySelectorAll(".rule-card")).map((card) => ({
      name: card.querySelector("[data-field='name']").value,
      amount: Number(card.querySelector("[data-field='amount']").value),
      cadence: card.querySelector("[data-field='cadence']").value,
      start_year: Number(card.querySelector("[data-field='start_year']").value),
      start_quarter: Number(card.querySelector("[data-field='start_quarter']").value),
      end_year: Number(card.querySelector("[data-field='end_year']").value),
      end_quarter: Number(card.querySelector("[data-field='end_quarter']").value),
    })),
  });
}

function applyConfig(config) {
  currentConfig = normalizeConfig(config);
  document.getElementById("initialBalance").value = currentConfig.initial_balance;
  document.getElementById("projectionStartYear").value = currentConfig.start_year;
  setQuarterValue("projectionStartQuarter", currentConfig.start_quarter);
  document.getElementById("projectionEndYear").value = currentConfig.end_year;
  setQuarterValue("projectionEndQuarter", currentConfig.end_quarter);
  document.getElementById("goalYear").value = currentConfig.goal_year;
  setQuarterValue("goalQuarter", currentConfig.goal_quarter);
  document.getElementById("goalBalance").value = currentConfig.goal_balance;
  document.getElementById("goalPercentile").value = currentConfig.goal_percentile;
  document.getElementById("mu").value = currentConfig.mu;
  document.getElementById("sigma").value = currentConfig.sigma;
  document.getElementById("primaryWithdrawalAmount").value = currentConfig.primary_withdrawal.amount;
  updatePrimaryWithdrawalLabel(currentConfig.primary_withdrawal.amount);
  document.getElementById("primaryWithdrawalStartYear").value = currentConfig.primary_withdrawal.start_year;
  document.getElementById("primaryWithdrawalStartQuarter").value = currentConfig.primary_withdrawal.start_quarter;
  document.getElementById("primaryWithdrawalEndYear").value = currentConfig.primary_withdrawal.end_year;
  document.getElementById("primaryWithdrawalEndQuarter").value = currentConfig.primary_withdrawal.end_quarter;
  renderRules(currentConfig.withdrawal_rules);
  if (currentConfig.history_start_quarter) {
    document.getElementById("startQuarter").value = currentConfig.history_start_quarter;
  }
}

function saveLocalConfig() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(exportConfig()));
}

function downloadConfig() {
  const blob = new Blob([JSON.stringify(exportConfig(), null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "values.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

function renderRules(rules) {
  const list = document.getElementById("rulesList");
  list.innerHTML = "";
  rules.forEach((rule, index) => list.appendChild(buildRuleCard(rule, index)));
}

function buildRuleCard(rule, index) {
  const normalized = normalizeRule(rule, index);
  const card = document.createElement("div");
  card.className = "rule-card";
  card.innerHTML = `
    <div class="rule-grid">
      <label><span>Name</span><input data-field="name" value="${escapeHtml(normalized.name)}" /></label>
      <label><span>Amount</span><input data-field="amount" type="number" min="0" step="100" value="${normalized.amount}" /></label>
      <label>
        <span>Cadence</span>
        <select data-field="cadence">
          <option value="once">Once</option>
          <option value="quarterly">Quarterly</option>
          <option value="annual">Annual</option>
        </select>
      </label>
      <label><span>Start year</span><input data-field="start_year" type="number" min="1900" max="2200" value="${normalized.start_year}" /></label>
      <label><span>Start Q</span><select data-field="start_quarter">${quarterOptions(normalized.start_quarter)}</select></label>
      <label><span>End year</span><input data-field="end_year" type="number" min="1900" max="2200" value="${normalized.end_year}" /></label>
      <label><span>End Q</span><select data-field="end_quarter">${quarterOptions(normalized.end_quarter)}</select></label>
      <button class="rule-remove" type="button">Remove</button>
    </div>
  `;
  card.querySelector("[data-field='cadence']").value = normalized.cadence;
  card.querySelector(".rule-remove").addEventListener("click", () => {
    card.remove();
    saveLocalConfig();
    runSimulation();
  });
  card.querySelectorAll("input, select").forEach((input) => {
    input.addEventListener("change", () => {
      saveLocalConfig();
      runSimulation();
    });
  });
  return card;
}

function quarterOptions(selectedQuarter) {
  return [1, 2, 3, 4]
    .map((quarter) => `<option value="${quarter}"${quarter === selectedQuarter ? " selected" : ""}>Q${quarter}</option>`)
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed: ${response.status}`);
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
  const q1Quarters = quarters.filter((quarter) => quarter.endsWith("Q1"));
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
        line: { color: "#176b87", width: 2.5 },
        hovertemplate: `Start %{x}<br>Annualized total return to ${endQuarter}: %{y:.2f}%<extra></extra>`,
      },
      {
        type: "scatter",
        mode: "markers",
        x: selectedRecord ? [selectedRecord.quarter] : [],
        y: selectedRecord ? [selectedRecord.annualized_return * 100] : [],
        marker: { color: "#b45309", size: 11 },
        hovertemplate: `Selected %{x}<br>Annualized total return to ${endQuarter}: %{y:.2f}%<extra></extra>`,
      },
    ],
    {
      margin: { t: 12, r: 12, b: 72, l: 56 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: { tickangle: -45, tickmode: "array", tickvals: q1Quarters, ticktext: q1Quarters },
      yaxis: { title: "Annualized total return (% per year)" },
      showlegend: false,
    },
    { responsive: true }
  );
}

function renderProjectionChart(series, goal) {
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
  traces.push({
    type: "scatter",
    mode: "markers",
    name: "Goal",
    x: [goal.quarter],
    y: [goal.balance],
    marker: { color: "#b45309", size: 12, symbol: "diamond" },
    hovertemplate: `Goal<br>${goal.quarter}: %{y:,.0f}<extra></extra>`,
  });

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

async function loadHistoryData() {
  const history = await fetchJson("/api/history");
  historyRecords = history.records;
  buildHistoryOptions(history.quarters);
  const requestedQuarter = currentConfig.history_start_quarter;
  document.getElementById("startQuarter").value =
    requestedQuarter && history.quarters.includes(requestedQuarter) ? requestedQuarter : history.default_stats.start_quarter;
  return history;
}

async function applyHistoryStats(applyToInputs = true) {
  const startQuarter = document.getElementById("startQuarter").value;
  const stats = await fetchJson(`/api/history/stats?start_quarter=${encodeURIComponent(startQuarter)}`);
  if (applyToInputs) {
    document.getElementById("mu").value = stats.mu.toFixed(4);
    document.getElementById("sigma").value = stats.sigma.toFixed(4);
  }
  document.getElementById("returnStats").textContent =
    `Annualized return from ${stats.start_quarter} to ${stats.end_quarter}: ` +
    `${percentFormatter.format(stats.annualized_return * 100)}%. ` +
    `Quarterly mu ${numberFormatter.format(stats.mu)}, sigma ${numberFormatter.format(stats.sigma)}.`;
  renderHistoryChart(historyRecords, startQuarter, stats.end_quarter);
}

function simulationPayload() {
  return exportConfig();
}

async function runSimulation() {
  const payload = simulationPayload();
  const result = await fetchJson("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  renderProjectionChart(result.chart_percentiles, result.goal);
  renderTwentileTable(result.twentiles, result.quarters);
  document.getElementById("goalStats").textContent =
    `P${result.goal.percentile} at ${result.goal.quarter}: ${currencyFormatter.format(result.goal.actual_balance)} ` +
    `${result.goal.met ? "meets" : "is below"} the ${currencyFormatter.format(result.goal.balance)} goal by ` +
    `${currencyFormatter.format(Math.abs(result.goal.gap))}.`;
  saveLocalConfig();
  setStatus(`Projection range: ${result.quarters[0]} to ${result.quarters.at(-1)}.`);
}

async function findIdealWithdrawal() {
  const config = collectConfig();
  const result = await fetchJson("/api/ideal-withdrawal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(exportConfig(config, { includeZeroPrimary: true })),
  });
  document.getElementById("primaryWithdrawalAmount").value = result.recommended_withdrawal.toFixed(0);
  updatePrimaryWithdrawalLabel(result.recommended_withdrawal);
  await runSimulation();
  document.getElementById("idealWithdrawalResult").textContent =
    `Primary quarterly withdrawal set to target P${result.percentile} ${currencyFormatter.format(result.target_balance)} ` +
    `at ${result.target_quarter}: ${currencyFormatter.format(result.recommended_withdrawal)}. ` +
    `Achieved: ${currencyFormatter.format(result.achieved_balance)}.`;
}

function bindInputs() {
  document.querySelectorAll("input, select").forEach((input) => {
    if (input.id === "configFile") {
      return;
    }
    input.addEventListener("change", () => {
      document.getElementById("idealWithdrawalResult").textContent = "";
      if (input.id === "primaryWithdrawalAmount") {
        updatePrimaryWithdrawalLabel(Number(input.value));
      }
      runSimulation().catch((error) => setStatus(`Error: ${error.message}`));
    });
  });
}

function addRuleFromCurrentRange() {
  const config = collectConfig();
  const rule = normalizeRule(
    {
      name: "Withdrawal",
      amount: 0,
      cadence: "once",
      start_year: config.start_year,
      start_quarter: config.start_quarter,
      end_year: config.start_year,
      end_quarter: config.start_quarter,
    },
    config.withdrawal_rules.length
  );
  document.getElementById("rulesList").appendChild(buildRuleCard(rule, config.withdrawal_rules.length));
  saveLocalConfig();
}

async function importConfig(file) {
  const text = await file.text();
  const config = normalizeConfig(JSON.parse(text));
  applyConfig(config);
  saveLocalConfig();
  await runSimulation();
  setStatus(`Loaded ${file.name}.`);
}

async function init() {
  buildQuarterControl("projectionStartQuarter", () => runSimulation().catch((error) => setStatus(`Error: ${error.message}`)));
  buildQuarterControl("projectionEndQuarter", () => runSimulation().catch((error) => setStatus(`Error: ${error.message}`)));
  buildQuarterControl("goalQuarter", () => runSimulation().catch((error) => setStatus(`Error: ${error.message}`)));

  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    currentConfig = normalizeConfig(JSON.parse(saved));
    setStatus("Loaded saved browser values.");
  }

  applyConfig(currentConfig);
  await loadHistoryData();
  await applyHistoryStats();
  bindInputs();
  await runSimulation();

  document.getElementById("useHistory").addEventListener("click", () => {
    applyHistoryStats().then(runSimulation).catch((error) => setStatus(`Error: ${error.message}`));
  });
  document.getElementById("runSimulation").addEventListener("click", () => {
    runSimulation().catch((error) => setStatus(`Error: ${error.message}`));
  });
  document.getElementById("idealWithdrawal").addEventListener("click", () => {
    findIdealWithdrawal().catch((error) => setStatus(`Error: ${error.message}`));
  });
  document.getElementById("addRule").addEventListener("click", addRuleFromCurrentRange);
  document.getElementById("resetConfig").addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEY);
    applyConfig(DEFAULT_CONFIG);
    runSimulation().catch((error) => setStatus(`Error: ${error.message}`));
  });
  document.getElementById("saveConfig").addEventListener("click", () => {
    saveLocalConfig();
    downloadConfig();
  });
  document.getElementById("loadConfig").addEventListener("click", () => {
    document.getElementById("configFile").click();
  });
  document.getElementById("configFile").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      importConfig(file).catch((error) => setStatus(`Error: ${error.message}`));
    }
    event.target.value = "";
  });
}

window.addEventListener("DOMContentLoaded", () => {
  init().catch((error) => setStatus(`Error: ${error.message}`));
});
