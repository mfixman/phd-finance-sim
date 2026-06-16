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
  initial_balance: 500000,
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
  withdrawal_rules: [
    {
      name: "Withdrawal",
      amount: 0,
      start_year: 2025,
      start_quarter: 4,
      end_year: 2025,
      end_quarter: 4,
      cadence: "quarterly",
    },
  ],
  goal_year: 2029,
  goal_quarter: 4,
  goal_balance: 500000,
  goal_percentile: 5,
  money_values: {},
  mu: 0.02,
  sigma: 0.08,
  simulations: 40000,
  seed: 42,
  history_start_quarter: "",
};

let historyRecords = [];
let currentConfig = structuredClone(DEFAULT_CONFIG);
let lastTwentileRows = [];
let lastTwentileQuarters = [];
let goalAdjustmentToken = 0;

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
  if (label) {
    label.textContent = amount > 0 ? currencyFormatter.format(amount) : "";
  }
}

function updateGoalQuarterText(config = collectConfig()) {
  const target = document.getElementById("goalQuarterText");
  if (target) {
    target.textContent = quarterLabel(config.end_year, config.end_quarter);
  }
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
  const endYear = Number(rule.end_year ?? startYear);
  const endQuarter = Number(rule.end_quarter ?? startQuarter);
  return {
    name: String(rule.name || `Withdrawal ${fallbackIndex + 1}`),
    amount: Number(rule.amount ?? 0),
    cadence: "quarterly",
    start_year: startYear,
    start_quarter: Number(rule.start_quarter ?? startQuarter),
    end_year: endYear,
    end_quarter: endQuarter,
    ...(rule.special ? { special: String(rule.special) } : {}),
  };
}

function normalizePrimaryWithdrawal(rule = {}, timeline = currentConfig) {
  const fallback = DEFAULT_CONFIG.primary_withdrawal;
  const projectionRule = {
    start_year: timeline.start_year,
    start_quarter: timeline.start_quarter,
    end_year: timeline.end_year,
    end_quarter: timeline.end_quarter,
  };
  return {
    ...fallback,
    ...normalizeRule(
      {
        ...fallback,
        ...rule,
        ...projectionRule,
        name: "Primary quarterly withdrawal",
        cadence: "quarterly",
        special: "primary_quarterly",
      },
      0
    ),
  };
}

function expandWithdrawalRule(rule = {}, index = 0) {
  if (rule.special === "primary_quarterly") {
    return [normalizeRule(rule, index)];
  }

  const cadence = ["once", "quarterly", "annual"].includes(rule.cadence) ? rule.cadence : "quarterly";
  if (cadence === "annual") {
    const startIndex = quarterIndex(Number(rule.start_year ?? currentConfig.start_year), Number(rule.start_quarter ?? currentConfig.start_quarter));
    const endIndex = quarterIndex(Number(rule.end_year ?? currentConfig.end_year), Number(rule.end_quarter ?? currentConfig.end_quarter));
    const rules = [];
    for (let targetIndex = startIndex; targetIndex <= endIndex; targetIndex += 4) {
      const [year, quarter] = quarterFromIndex(targetIndex);
      rules.push(
        normalizeRule(
          {
            ...rule,
            name: `${rule.name || "Withdrawal"} ${year}`,
            start_year: year,
            start_quarter: quarter,
            end_year: year,
            end_quarter: quarter,
          },
          index + rules.length
        )
      );
    }
    return rules;
  }

  if (cadence === "once") {
    return [
      normalizeRule(
        {
          ...rule,
          end_year: rule.start_year,
          end_quarter: rule.start_quarter,
        },
        index
      ),
    ];
  }

  return [normalizeRule(rule, index)];
}

function quarterIndex(year, quarter) {
  return year * 4 + quarter - 1;
}

function quarterFromIndex(index) {
  const year = Math.floor(index / 4);
  return [year, index % 4 + 1];
}

function normalizeMoneyValues(values = {}) {
  return Object.fromEntries(
    Object.entries(values)
      .map(([quarter, amounts]) => {
        const normalizedAmounts = (Array.isArray(amounts) ? amounts : [amounts])
          .map((amount) => Number(amount))
          .filter(Number.isFinite)
          .slice(0, 2);
        return [String(quarter), normalizedAmounts];
      })
      .filter(([, amounts]) => amounts.length > 0)
  );
}

function normalizeConfig(config = {}) {
  const startYear = Number(config.start_year ?? DEFAULT_CONFIG.start_year);
  const startQuarter = Number(config.start_quarter ?? DEFAULT_CONFIG.start_quarter);
  const endYear = Number(config.end_year ?? DEFAULT_CONFIG.end_year);
  const endQuarter = Number(config.end_quarter ?? DEFAULT_CONFIG.end_quarter);
  const rawRules = Array.isArray(config.withdrawal_rules) ? config.withdrawal_rules : DEFAULT_CONFIG.withdrawal_rules;
  const incomingRules = rawRules.flatMap((rule, index) => expandWithdrawalRule(rule, index));
  const primaryRule =
    config.primary_withdrawal || incomingRules.find((rule) => rule.special === "primary_quarterly");

  return {
    ...DEFAULT_CONFIG,
    ...config,
    initial_balance: Math.max(0, Number(config.initial_balance ?? DEFAULT_CONFIG.initial_balance)),
    start_year: startYear,
    start_quarter: startQuarter,
    end_year: endYear,
    end_quarter: endQuarter,
    goal_year: endYear,
    goal_quarter: endQuarter,
    goal_balance: Math.max(0, Number(config.goal_balance ?? DEFAULT_CONFIG.goal_balance)),
    goal_percentile: Math.min(99, Math.max(1, Number(config.goal_percentile ?? DEFAULT_CONFIG.goal_percentile))),
    money_values: normalizeMoneyValues(config.money_values),
    mu: Number(config.mu ?? DEFAULT_CONFIG.mu),
    sigma: Math.max(0, Number(config.sigma ?? DEFAULT_CONFIG.sigma)),
    simulations: Math.min(250000, Math.max(1000, Number(config.simulations ?? DEFAULT_CONFIG.simulations))),
    seed: Math.max(0, Number(config.seed ?? DEFAULT_CONFIG.seed)),
    primary_withdrawal: normalizePrimaryWithdrawal(primaryRule, {
      start_year: startYear,
      start_quarter: startQuarter,
      end_year: endYear,
      end_quarter: endQuarter,
    }),
    withdrawal_rules: incomingRules.filter((rule) => rule.special !== "primary_quarterly"),
  };
}

function combinedWithdrawalRules(config, options = {}) {
  const primary = normalizePrimaryWithdrawal(config.primary_withdrawal, config);
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
  const endYear = Number(document.getElementById("projectionEndYear").value);
  const endQuarter = quarterValue("projectionEndQuarter");
  return normalizeConfig({
    initial_balance: Number(document.getElementById("initialBalance").value),
    start_year: Number(document.getElementById("projectionStartYear").value),
    start_quarter: quarterValue("projectionStartQuarter"),
    end_year: endYear,
    end_quarter: endQuarter,
    goal_year: endYear,
    goal_quarter: endQuarter,
    goal_balance: Number(document.getElementById("goalBalance").value),
    goal_percentile: Number(document.getElementById("goalPercentile").value),
    money_values: currentConfig.money_values,
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
      start_year: Number(document.getElementById("projectionStartYear").value),
      start_quarter: quarterValue("projectionStartQuarter"),
      end_year: endYear,
      end_quarter: endQuarter,
    },
    withdrawal_rules: Array.from(document.querySelectorAll(".rule-card")).map((card) => ({
      name: card.querySelector("[data-field='name']").value,
      amount: Number(card.querySelector("[data-field='amount']").value),
      cadence: "quarterly",
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
  document.getElementById("goalBalance").value = currentConfig.goal_balance;
  document.getElementById("goalPercentile").value = currentConfig.goal_percentile;
  updateGoalQuarterText(currentConfig);
  document.getElementById("mu").value = currentConfig.mu;
  document.getElementById("sigma").value = currentConfig.sigma;
  document.getElementById("primaryWithdrawalAmount").value = currentConfig.primary_withdrawal.amount;
  updatePrimaryWithdrawalLabel(currentConfig.primary_withdrawal.amount);
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
      <label><span>Amount</span><input data-field="amount" type="number" step="100" value="${normalized.amount}" /></label>
      <label><span>Start year</span><input data-field="start_year" type="number" min="1900" max="2200" value="${normalized.start_year}" /></label>
      <label><span>Start Q</span><select data-field="start_quarter">${quarterOptions(normalized.start_quarter)}</select></label>
      <label><span>End year</span><input data-field="end_year" type="number" min="1900" max="2200" value="${normalized.end_year}" /></label>
      <label><span>End Q</span><select data-field="end_quarter">${quarterOptions(normalized.end_quarter)}</select></label>
      <button class="rule-remove" type="button">Remove</button>
    </div>
  `;
  card.querySelector(".rule-remove").addEventListener("click", () => {
    card.remove();
    saveLocalConfig();
    adjustWithdrawalToGoal().catch((error) => setStatus(`Error: ${error.message}`));
  });
  card.querySelectorAll("input, select").forEach((input) => {
    input.addEventListener("change", () => {
      saveLocalConfig();
      adjustWithdrawalToGoal().catch((error) => setStatus(`Error: ${error.message}`));
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
  lastTwentileRows = rows;
  lastTwentileQuarters = quarters;
  const thead = document.querySelector("#twentileTable thead");
  const tbody = document.querySelector("#twentileTable tbody");
  const highlights = highlightedTwentileRows(rows, quarters);
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
      const quarter = quarters[quarterIndex];
      td.textContent = formatTableValue(value);
      td.dataset.quarter = quarter;
      td.dataset.rowIndex = String(rowIndex);
      td.dataset.quarterIndex = String(quarterIndex);
      td.dataset.value = String(value);
      td.title = `${quarter} P${row.percentile}: ${currencyFormatter.format(value)}`;
      if (highlights.get(quarter)?.has(rowIndex)) {
        td.classList.add("table-highlight");
      }
      td.addEventListener("click", handleTwentileCellClick);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

function highlightedTwentileRows(rows, quarters) {
  const highlights = new Map();
  const moneyValues = normalizeMoneyValues(currentConfig.money_values);

  for (const [quarter, values] of Object.entries(moneyValues)) {
    const quarterIndex = quarters.indexOf(quarter);
    if (quarterIndex === -1) {
      continue;
    }
    const selectedRows = new Set();
    for (const value of values) {
      let bestRow = 0;
      let bestDistance = Number.POSITIVE_INFINITY;
      rows.forEach((row, rowIndex) => {
        const distance = Math.abs(row.values[quarterIndex] - value);
        if (distance < bestDistance) {
          bestDistance = distance;
          bestRow = rowIndex;
        }
      });
      selectedRows.add(bestRow);
    }
    const orderedRows = [...selectedRows].sort((left, right) => left - right);
    if (orderedRows.length === 1 || (orderedRows.length === 2 && Math.abs(orderedRows[0] - orderedRows[1]) === 1)) {
      highlights.set(quarter, new Set(orderedRows.slice(0, 2)));
    } else if (orderedRows.length > 0) {
      highlights.set(quarter, new Set([orderedRows[0]]));
    }
  }

  return highlights;
}

function selectedRowsForQuarter(quarter) {
  return Array.from(document.querySelectorAll("#twentileTable td.table-highlight"))
    .filter((cell) => cell.dataset.quarter === quarter)
    .map((cell) => Number(cell.dataset.rowIndex))
    .sort((left, right) => left - right);
}

function saveMoneyValuesForQuarter(quarter, rowIndexes) {
  const quarterIndex = lastTwentileQuarters.indexOf(quarter);
  const nextValues = { ...normalizeMoneyValues(currentConfig.money_values) };
  if (quarterIndex === -1 || rowIndexes.length === 0) {
    delete nextValues[quarter];
  } else {
    nextValues[quarter] = rowIndexes
      .slice(0, 2)
      .map((rowIndex) => lastTwentileRows[rowIndex]?.values[quarterIndex])
      .filter(Number.isFinite);
  }
  currentConfig = normalizeConfig({ ...collectConfig(), money_values: nextValues });
  saveLocalConfig();
  renderTwentileTable(lastTwentileRows, lastTwentileQuarters);
}

function handleTwentileCellClick(event) {
  const cell = event.currentTarget;
  const quarter = cell.dataset.quarter;
  const rowIndex = Number(cell.dataset.rowIndex);
  const selectedRows = selectedRowsForQuarter(quarter);
  let nextRows;

  if (selectedRows.includes(rowIndex)) {
    nextRows = selectedRows.filter((selectedRow) => selectedRow !== rowIndex);
  } else if (selectedRows.length === 1 && Math.abs(selectedRows[0] - rowIndex) === 1) {
    nextRows = [...selectedRows, rowIndex].sort((left, right) => left - right);
  } else if (selectedRows.length === 2) {
    const [lowerRow, upperRow] = selectedRows;
    if (rowIndex === lowerRow - 1) {
      nextRows = [rowIndex, lowerRow];
    } else if (rowIndex === upperRow + 1) {
      nextRows = [upperRow, rowIndex];
    } else {
      nextRows = [rowIndex];
    }
  } else {
    nextRows = [rowIndex];
  }

  saveMoneyValuesForQuarter(quarter, nextRows);
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
    `Quarterly lognormal mu ${numberFormatter.format(stats.mu)}, sigma ${numberFormatter.format(stats.sigma)}.`;
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

async function findIdealWithdrawal(options = {}) {
  const token = ++goalAdjustmentToken;
  const config = collectConfig();
  const result = await fetchJson("/api/ideal-withdrawal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(exportConfig(config, { includeZeroPrimary: true })),
  });
  if (token !== goalAdjustmentToken) {
    return result;
  }
  document.getElementById("primaryWithdrawalAmount").value = result.recommended_withdrawal.toFixed(0);
  updatePrimaryWithdrawalLabel(result.recommended_withdrawal);
  await runSimulation();
  if (options.showResult !== false) {
    document.getElementById("idealWithdrawalResult").textContent =
      `Primary quarterly withdrawal set to target P${result.percentile} ${currencyFormatter.format(result.target_balance)} ` +
      `at ${result.target_quarter}: ${currencyFormatter.format(result.recommended_withdrawal)}. ` +
      `Achieved: ${currencyFormatter.format(result.achieved_balance)}.`;
  }
  return result;
}

async function adjustWithdrawalToGoal() {
  document.getElementById("idealWithdrawalResult").textContent = "";
  await findIdealWithdrawal({ showResult: false });
}

function bindInputs() {
  document.querySelectorAll("input, select").forEach((input) => {
    if (input.id === "configFile") {
      return;
    }
    input.addEventListener("change", async () => {
      try {
        document.getElementById("idealWithdrawalResult").textContent = "";
        if (input.id === "primaryWithdrawalAmount") {
          updatePrimaryWithdrawalLabel(Number(input.value));
          await runSimulation();
          return;
        }
        if (input.id === "startQuarter") {
          await applyHistoryStats();
          await adjustWithdrawalToGoal();
          return;
        }
        if (input.id === "projectionEndYear") {
          updateGoalQuarterText();
        }
        await adjustWithdrawalToGoal();
      } catch (error) {
        setStatus(`Error: ${error.message}`);
      }
    });
  });
}

function addRuleFromCurrentRange() {
  const config = collectConfig();
  const rule = normalizeRule(
    {
      name: "Withdrawal",
      amount: 0,
      cadence: "quarterly",
      start_year: config.start_year,
      start_quarter: config.start_quarter,
      end_year: config.start_year,
      end_quarter: config.start_quarter,
    },
    config.withdrawal_rules.length
  );
  document.getElementById("rulesList").appendChild(buildRuleCard(rule, config.withdrawal_rules.length));
  saveLocalConfig();
  adjustWithdrawalToGoal().catch((error) => setStatus(`Error: ${error.message}`));
}

async function importConfig(file) {
  const text = await file.text();
  const config = normalizeConfig(JSON.parse(text));
  applyConfig(config);
  saveLocalConfig();
  await adjustWithdrawalToGoal();
  setStatus(`Loaded ${file.name}.`);
}

async function init() {
  buildQuarterControl("projectionStartQuarter", () => {
    adjustWithdrawalToGoal().catch((error) => setStatus(`Error: ${error.message}`));
  });
  buildQuarterControl("projectionEndQuarter", () => {
    updateGoalQuarterText();
    adjustWithdrawalToGoal().catch((error) => setStatus(`Error: ${error.message}`));
  });

  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    currentConfig = normalizeConfig(JSON.parse(saved));
    setStatus("Loaded saved browser values.");
  }

  applyConfig(currentConfig);
  await loadHistoryData();
  await applyHistoryStats();
  bindInputs();
  await adjustWithdrawalToGoal();

  document.getElementById("useHistory").addEventListener("click", () => {
    applyHistoryStats().then(adjustWithdrawalToGoal).catch((error) => setStatus(`Error: ${error.message}`));
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
    adjustWithdrawalToGoal().catch((error) => setStatus(`Error: ${error.message}`));
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
