/**
 * SIGeCAD - Frontend Application Logic
 * Communicates with FastAPI backend, manages tabs, renders controls and evaluates telemetry windows.
 */

let appConfig = null;
let currentReport = null;

// DOM Elements
const elements = {
  statusBadge: document.getElementById("system-status-badge"),
  statusBanner: document.getElementById("status-banner"),
  modelVersionTag: document.getElementById("model-version-tag"),
  scenariosList: document.getElementById("scenarios-list"),
  featureFields: document.getElementById("feature-fields"),
  telemetryForm: document.getElementById("telemetry-form"),
  btnSubmit: document.getElementById("btn-submit"),
  btnReset: document.getElementById("btn-reset"),
  resourceSelect: document.getElementById("resource-select"),
  resultEmpty: document.getElementById("result-empty"),
  resultContent: document.getElementById("result-content"),
  diagnosisBadge: document.getElementById("diagnosis-badge"),
  diagnosisResource: document.getElementById("diagnosis-resource"),
  diagnosisText: document.getElementById("diagnosis-text"),
  modelAlertBadge: document.getElementById("model-alert-badge"),
  modelScoreVal: document.getElementById("model-score-val"),
  modelThresholdVal: document.getElementById("model-threshold-val"),
  modelScoreBar: document.getElementById("model-score-bar"),
  baselineAlertBadge: document.getElementById("baseline-alert-badge"),
  baselineScoreVal: document.getElementById("baseline-score-val"),
  baselineThresholdVal: document.getElementById("baseline-threshold-val"),
  baselineScoreBar: document.getElementById("baseline-score-bar"),
  baselineViolationsText: document.getElementById("baseline-violations-text"),
  indicatorsList: document.getElementById("indicators-list"),
  metricsTableBody: document.getElementById("metrics-table-body"),
  incidentsList: document.getElementById("incidents-list")
};

// Initialize Application
async function initApp() {
  setupTabs();
  try {
    // 1. Fetch Health
    const healthRes = await fetch("/api/health");
    const healthData = await healthRes.json();
    
    if (healthData.status === "ok") {
      elements.statusBadge.textContent = "Servicio Activo";
      elements.statusBadge.classList.add("badge-status");
      elements.modelVersionTag.textContent = healthData.version || "v1.0";
    } else {
      elements.statusBadge.textContent = "Modelo no entrenado";
      elements.statusBadge.classList.add("badge-status", "error");
      showBanner("El modelo de detección aún no está listo. Ejecute 'python -m app.train'.", "error");
      return;
    }

    // 2. Fetch Config & Features
    const configRes = await fetch("/api/config");
    appConfig = await configRes.json();
    
    renderFeatureFields(appConfig.features, appConfig.feature_order);
    renderScenarios(appConfig.scenarios);

    // 3. Fetch Evaluation Metrics
    const metricsRes = await fetch("/api/metrics");
    if (metricsRes.ok) {
      currentReport = await metricsRes.json();
      renderEvaluationMetrics(currentReport);
    }

    // Enable submit
    elements.btnSubmit.disabled = false;

    // Load first default scenario (Usual)
    if (appConfig.scenarios && appConfig.scenarios.length > 0) {
      loadScenario(appConfig.scenarios[0].id);
    }

  } catch (err) {
    console.error("Initialization error:", err);
    elements.statusBadge.textContent = "Error de Conexión";
    elements.statusBadge.classList.add("badge-status", "error");
    showBanner(`No se pudo conectar con la API de SIGeCAD: ${err.message}`, "error");
  }
}

// Navigation Tabs Setup
function setupTabs() {
  const navBtns = document.querySelectorAll(".nav-btn");
  const views = document.querySelectorAll(".view");

  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetView = btn.dataset.view;
      
      navBtns.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-pressed", "false");
      });
      views.forEach((v) => v.classList.add("hidden"));

      btn.classList.add("active");
      btn.setAttribute("aria-pressed", "true");
      document.getElementById(targetView).classList.remove("hidden");
    });
  });
}

// Render Input Sliders and Numbers
function renderFeatureFields(features, featureOrder) {
  elements.featureFields.innerHTML = "";

  featureOrder.forEach((key) => {
    const meta = features[key];
    const group = document.createElement("div");
    group.className = "field-group";

    group.innerHTML = `
      <div class="field-header">
        <label class="field-label" for="slider-${key}">${meta.label}</label>
        <span class="field-unit">${meta.unit}</span>
      </div>
      <div class="field-controls">
        <input 
          type="range" 
          id="slider-${key}" 
          name="${key}" 
          class="field-slider"
          min="${meta.min}" 
          max="${meta.max}" 
          step="${meta.step}" 
          value="${meta.default}"
          aria-label="${meta.label}"
        />
        <input 
          type="number" 
          id="num-${key}" 
          class="field-number"
          min="${meta.min}" 
          max="${meta.max}" 
          step="${meta.step}" 
          value="${meta.default}"
          aria-label="${meta.label} valor numérico"
        />
      </div>
    `;

    const slider = group.querySelector(`#slider-${key}`);
    const numInput = group.querySelector(`#num-${key}`);

    slider.addEventListener("input", (e) => {
      numInput.value = e.target.value;
      clearActiveScenario();
    });

    numInput.addEventListener("input", (e) => {
      slider.value = e.target.value;
      clearActiveScenario();
    });

    elements.featureFields.appendChild(group);
  });
}

// Render Scenario Quick-load Buttons
function renderScenarios(scenarios) {
  elements.scenariosList.innerHTML = "";

  scenarios.forEach((scn, idx) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `chip-btn ${idx === 0 ? "active" : ""}`;
    btn.dataset.scenarioId = scn.id;
    btn.textContent = scn.name;
    btn.title = scn.description;

    btn.addEventListener("click", () => {
      loadScenario(scn.id);
    });

    elements.scenariosList.appendChild(btn);
  });
}

function clearActiveScenario() {
  document.querySelectorAll(".chip-btn").forEach((b) => b.classList.remove("active"));
}

// Load Scenario Values into Form
function loadScenario(scenarioId) {
  if (!appConfig) return;
  const scenario = appConfig.scenarios.find((s) => s.id === scenarioId);
  if (!scenario) return;

  clearActiveScenario();
  const activeBtn = document.querySelector(`.chip-btn[data-scenario-id="${scenarioId}"]`);
  if (activeBtn) activeBtn.classList.add("active");

  // Populate values
  Object.entries(scenario.values || {}).forEach(([key, val]) => {
    const slider = document.getElementById(`slider-${key}`);
    const num = document.getElementById(`num-${key}`);
    if (slider) slider.value = val;
    if (num) num.value = val;
  });

  // Assign appropriate resource based on scenario
  if (scenarioId === "cpu_overheat") {
    elements.resourceSelect.value = "node:dl360-04";
  } else if (scenarioId === "storage_stall") {
    elements.resourceSelect.value = "node:srvzy";
  } else if (scenarioId === "vm_crash" || scenarioId === "memory_leak") {
    elements.resourceSelect.value = "guest:100_AD-Zentyal";
  } else {
    elements.resourceSelect.value = "node:dl380-01";
  }

  // Auto-submit analysis for seamless user experience
  submitAnalysis();
}

// Submit Telemetry Form
elements.telemetryForm.addEventListener("submit", (e) => {
  e.preventDefault();
  submitAnalysis();
});

elements.btnReset.addEventListener("click", () => {
  if (appConfig && appConfig.scenarios.length > 0) {
    loadScenario(appConfig.scenarios[0].id);
  }
});

async function submitAnalysis() {
  if (!appConfig) return;
  hideBanner();

  const payload = {
    resource_id: elements.resourceSelect.value
  };

  appConfig.feature_order.forEach((key) => {
    const numInput = document.getElementById(`num-${key}`);
    payload[key] = parseFloat(numInput.value);
  });

  try {
    elements.btnSubmit.disabled = true;

    const res = await fetch("/api/inspect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.status === 422) {
      const errData = await res.json();
      const details = (errData.detalles || []).map((d) => `• ${d.field}: ${d.message}`).join("<br>");
      showBanner(`<strong>Entrada rechazada (Error 422):</strong><br>${details}`, "error");
      elements.btnSubmit.disabled = false;
      return;
    }

    if (!res.ok) {
      throw new Error(`Error en servidor HTTP ${res.status}`);
    }

    const data = await res.json();
    renderAnalysisResult(data);

  } catch (err) {
    console.error("Inspection error:", err);
    showBanner(`Error al procesar la ventana: ${err.message}`, "error");
  } finally {
    elements.btnSubmit.disabled = false;
  }
}

// Render Results on Screen
function renderAnalysisResult(data) {
  elements.resultEmpty.classList.add("hidden");
  elements.resultContent.classList.remove("hidden");

  // Diagnosis Card
  elements.diagnosisResource.textContent = data.resource_id;
  elements.diagnosisText.textContent = data.diagnosis;

  const isAlert = data.alert || data.baseline.alert;
  const diagCard = document.getElementById("diagnosis-card");
  diagCard.className = "diagnosis-card";

  if (data.alert) {
    diagCard.classList.add("alert");
    elements.diagnosisBadge.className = "badge badge-alert";
    elements.diagnosisBadge.textContent = "ALERTA CRÍTICA";
  } else if (data.baseline.alert) {
    diagCard.classList.add("warning");
    elements.diagnosisBadge.className = "badge badge-warning";
    elements.diagnosisBadge.textContent = "ALERTA UMBRAL";
  } else {
    elements.diagnosisBadge.className = "badge badge-normal";
    elements.diagnosisBadge.textContent = "NORMAL";
  }

  // Model Card
  elements.modelAlertBadge.className = `badge ${data.alert ? "badge-alert" : "badge-normal"}`;
  elements.modelAlertBadge.textContent = data.alert ? "ANOMALÍA" : "NORMAL";
  elements.modelScoreVal.textContent = data.score.toFixed(4);
  elements.modelThresholdVal.textContent = data.threshold.toFixed(4);

  // Score Bar (% normalized roughly around threshold)
  const modelPct = Math.min(Math.max(((data.score - 0.3) / 0.4) * 100, 5), 100);
  elements.modelScoreBar.style.width = `${modelPct}%`;
  elements.modelScoreBar.className = `progress-bar-fill ${data.alert ? "alert" : ""}`;

  // Baseline Card
  elements.baselineAlertBadge.className = `badge ${data.baseline.alert ? "badge-alert" : "badge-normal"}`;
  elements.baselineAlertBadge.textContent = data.baseline.alert ? "ALERTA" : "NORMAL";
  elements.baselineScoreVal.textContent = data.baseline.score.toFixed(4);
  elements.baselineThresholdVal.textContent = data.baseline.threshold.toFixed(4);

  const basePct = Math.min(Math.max((data.baseline.score / 1.2) * 100, 5), 100);
  elements.baselineScoreBar.style.width = `${basePct}%`;
  elements.baselineScoreBar.className = `progress-bar-fill ${data.baseline.alert ? "alert" : ""}`;

  // Baseline Violations Description
  const decision = data?.baseline?.decision;
  if (decision && decision.alert) {
    const list = [...(decision.critical_violations || []), ...(decision.warning_violations || [])];
    const text = list.map((v) => `${v.feature} (${v.value} ≥ ${v.threshold})`).join(", ");
    elements.baselineViolationsText.textContent = `Infracción detectada: ${text}`;
  } else {
    elements.baselineViolationsText.textContent = "Todas las variables respetan los umbrales fijos operacionales.";
  }

  // Indicators List
  renderIndicators(data?.indicators || []);
}

// Render Indicators and Robust MAD Distances
function renderIndicators(indicators = []) {
  elements.indicatorsList.innerHTML = "";

  (indicators || []).forEach((item) => {
    const row = document.createElement("div");
    row.className = "indicator-item";

    const madDist = item.robust_distance;
    const isHigh = madDist >= 3.0;
    const barWidth = Math.min((madDist / 6.0) * 100, 100);

    row.innerHTML = `
      <span class="indicator-name" title="${item.label}">${item.label}</span>
      <span class="indicator-val">${item.value} ${item.unit}</span>
      <div class="indicator-bar-wrap">
        <div class="indicator-bar-fill ${isHigh ? "high" : ""}" style="width: ${barWidth}%"></div>
      </div>
      <span class="indicator-mad" title="Distancia MAD">${madDist.toFixed(1)}σ</span>
    `;

    elements.indicatorsList.appendChild(row);
  });
}

// Render Evaluation Metrics Tab
function renderEvaluationMetrics(report) {
  const modelEv = report.test.model.event_based;
  const baseEv = report.test.baseline.event_based;

  // Key cards
  document.getElementById("m-event-f1-model").textContent = modelEv.event_f1.toFixed(4);
  document.getElementById("m-event-f1-base").textContent = baseEv.event_f1.toFixed(4);

  document.getElementById("m-event-rec-model").textContent = `${(modelEv.event_recall * 100).toFixed(0)}%`;
  document.getElementById("m-event-rec-base").textContent = `${(baseEv.event_recall * 100).toFixed(0)}%`;

  document.getElementById("m-lead-model").textContent = `${modelEv.avg_lead_time_minutes}m`;
  document.getElementById("m-lead-base").textContent = `${baseEv.avg_lead_time_minutes}m`;

  document.getElementById("m-fpr-model").textContent = `${(report.test.model.false_positive_rate * 100).toFixed(2)}%`;
  document.getElementById("m-fpr-base").textContent = `${(report.test.baseline.false_positive_rate * 100).toFixed(2)}%`;

  // Full table
  const rows = [
    { label: "F1 por Evento de Incidente (Métrica Principal)", m: modelEv.event_f1.toFixed(4), b: baseEv.event_f1.toFixed(4), desc: "Calidad global ponderada de detección de incidentes completos" },
    { label: "Recall por Evento (Incidentes Detectados)", m: `${modelEv.tp_events} / ${modelEv.total_incidents} (${(modelEv.event_recall * 100).toFixed(1)}%)`, b: `${baseEv.tp_events} / ${baseEv.total_incidents} (${(baseEv.event_recall * 100).toFixed(1)}%)`, desc: "Porcentaje de incidentes reales alertados a tiempo" },
    { label: "Precision por Evento", m: modelEv.event_precision.toFixed(4), b: baseEv.event_precision.toFixed(4), desc: "Porcentaje de alertas que corresponden a incidentes reales" },
    { label: "Eventos Falsos Positivos (FP)", m: modelEv.fp_events, b: baseEv.fp_events, desc: "Ráfagas de alertas falsas en periodos normales" },
    { label: "Lead Time Medio de Alerta Temprana", m: `${modelEv.avg_lead_time_minutes} minutos`, b: `${baseEv.avg_lead_time_minutes} minutos`, desc: "Anticipación promedio de la primera alerta antes de la falla total" },
    { label: "Average Precision (PR-AUC)", m: report.test.model.average_precision.toFixed(4), b: report.test.baseline.average_precision.toFixed(4), desc: "Capacidad de discriminación continua del puntaje" },
    { label: "Precision Puntual (a nivel de ventana)", m: report.test.model.precision.toFixed(4), b: report.test.baseline.precision.toFixed(4), desc: "Exactitud de cada ventana de 10 min individual" },
    { label: "Recall Puntual", m: report.test.model.recall.toFixed(4), b: report.test.baseline.recall.toFixed(4), desc: "Cobertura de todas las ventanas marcadas como anómalas" },
    { label: "Tasa de Falsos Positivos (FPR)", m: `${(report.test.model.false_positive_rate * 100).toFixed(2)}%`, b: `${(report.test.baseline.false_positive_rate * 100).toFixed(2)}%`, desc: "Respeto del presupuesto de falsas alarmas (≤ 5%)" },
    { label: "Ventanas Alertadas en Prueba", m: `${report.test.model.alerts} / ${report.data_counts.test_windows}`, b: `${report.test.baseline.alerts} / ${report.data_counts.test_windows}`, desc: "Volumen total de ventanas marcadas para revisión humana" }
  ];

  elements.metricsTableBody.innerHTML = rows.map((r) => `
    <tr>
      <td><strong>${r.label}</strong></td>
      <td style="font-family: var(--font-mono); color: var(--accent-cyan);">${r.m}</td>
      <td style="font-family: var(--font-mono);">${r.b}</td>
      <td style="color: var(--text-muted); font-size: 0.8rem;">${r.desc}</td>
    </tr>
  `).join("");

  // Incidents Catalog
  elements.incidentsList.innerHTML = (modelEv.incident_details || []).map((inc) => `
    <div class="incident-card">
      <div class="incident-card-header">
        <span class="incident-id">${inc.incident_id}</span>
        <span class="badge ${inc.detected ? "badge-normal" : "badge-alert"}">
          ${inc.detected ? "DETECTADO" : "OMITIDO"}
        </span>
      </div>
      <p><strong>Recurso:</strong> ${inc.resource_id}</p>
      <div class="incident-timing">
        <div>Inicio: ${inc.start_time.replace("T", " ")}</div>
        ${inc.first_alert ? `<div>1ra Alerta: ${inc.first_alert.replace("T", " ")}</div>` : ""}
        <div>Anticipación: ${inc.lead_time_minutes} min</div>
      </div>
    </div>
  `).join("");
}

// Banner Utility
function showBanner(message, type = "info") {
  elements.statusBanner.innerHTML = message;
  elements.statusBanner.className = `banner ${type}`;
  elements.statusBanner.classList.remove("hidden");
}

function hideBanner() {
  elements.statusBanner.classList.add("hidden");
}

// Start
document.addEventListener("DOMContentLoaded", initApp);
