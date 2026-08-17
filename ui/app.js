/**
 * AERO-HEALTH AI - Frontend Application Logic
 * NASA C-MAPSS Predictive Maintenance UI Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    currentDataset: 'FD001',
    fleetEngines: [],
    selectedEngineId: 1,
    historyChart: null,
  };

  // DOM Elements
  const datasetSelect = document.getElementById('dataset-select');
  const apiStatusText = document.getElementById('api-status-text');

  // KPI Elements
  const valTotalEngines = document.getElementById('val-total-engines');
  const valHealthyCount = document.getElementById('val-healthy-count');
  const valHealthyPct = document.getElementById('val-healthy-pct');
  const valMonitorCount = document.getElementById('val-monitor-count');
  const valMonitorPct = document.getElementById('val-monitor-pct');
  const valMaintCount = document.getElementById('val-maint-count');
  const valMaintPct = document.getElementById('val-maint-pct');
  const valCriticalCount = document.getElementById('val-critical-count');
  const valCriticalPct = document.getElementById('val-critical-pct');
  const subFleetDataset = document.getElementById('sub-fleet-dataset');

  // Table Elements
  const fleetTableBody = document.getElementById('fleet-table-body');
  const searchInput = document.getElementById('engine-search-input');
  const statusFilter = document.getElementById('status-filter');

  // Inspector Elements
  const inspTitle = document.getElementById('inspector-engine-title');
  const inspBadge = document.getElementById('inspector-health-badge');
  const inspRul = document.getElementById('insp-rul');
  const inspActualRul = document.getElementById('insp-actual-rul');
  const inspAnomScore = document.getElementById('insp-anom-score');
  const inspAnomStatus = document.getElementById('insp-anom-status');
  const inspComposite = document.getElementById('insp-composite');
  const inspRisk = document.getElementById('insp-risk');
  const inspUrgency = document.getElementById('insp-urgency');
  const inspRec = document.getElementById('insp-recommendation');
  const inspReason = document.getElementById('insp-reason');
  const inspComponentsTags = document.getElementById('insp-components-tags');
  const inspTasks = document.getElementById('insp-tasks');
  const inspSensorsList = document.getElementById('insp-sensors-list');
  const chartCanvas = document.getElementById('engine-history-chart');

  // Simulator Elements
  const simEngineId = document.getElementById('sim-engine-id');
  const simCycle = document.getElementById('sim-cycle');
  const simRul = document.getElementById('sim-rul');
  const simRulVal = document.getElementById('sim-rul-val');
  const simAnom = document.getElementById('sim-anom');
  const simAnomVal = document.getElementById('sim-anom-val');
  const simSensors = document.getElementById('sim-sensors');
  const btnRunSim = document.getElementById('btn-run-sim');

  const simResStatus = document.getElementById('sim-res-status');
  const simResRisk = document.getElementById('sim-res-risk');
  const simResComposite = document.getElementById('sim-res-composite');
  const simResUrgency = document.getElementById('sim-res-urgency');
  const simResReason = document.getElementById('sim-res-reason');
  const simResRec = document.getElementById('sim-res-rec');
  const simResActions = document.getElementById('sim-res-actions');
  const simResComponents = document.getElementById('sim-res-components');

  // Initialize Tabs
  initTabs();

  // Initialize Event Listeners
  datasetSelect.addEventListener('change', (e) => {
    state.currentDataset = e.target.value;
    loadFleetData();
  });

  searchInput.addEventListener('input', renderFleetTable);
  statusFilter.addEventListener('change', renderFleetTable);

  // Simulator Events
  simRul.addEventListener('input', (e) => {
    simRulVal.textContent = `${e.target.value} cycles`;
  });
  simAnom.addEventListener('input', (e) => {
    simAnomVal.textContent = `${parseFloat(e.target.value).toFixed(1)}`;
  });
  btnRunSim.addEventListener('click', runSimulatorInference);

  // Preset Buttons
  document.getElementById('preset-healthy').addEventListener('click', () => {
    simRul.value = 115;
    simRulVal.textContent = '115 cycles';
    simAnom.value = 15;
    simAnomVal.textContent = '15.0';
    simSensors.value = 'Nominal Telemetry';
    runSimulatorInference();
  });

  document.getElementById('preset-monitor').addEventListener('click', () => {
    simRul.value = 60;
    simRulVal.textContent = '60 cycles';
    simAnom.value = 52;
    simAnomVal.textContent = '52.0';
    simSensors.value = 'sensor_11 (+1.85σ, Moderate deviation) | sensor_4 (+1.65σ, Moderate deviation)';
    runSimulatorInference();
  });

  document.getElementById('preset-maint').addEventListener('click', () => {
    simRul.value = 32;
    simRulVal.textContent = '32 cycles';
    simAnom.value = 72;
    simAnomVal.textContent = '72.0';
    simSensors.value = 'sensor_11 (+3.42σ, High deviation) | sensor_3 (+2.85σ, High deviation)';
    runSimulatorInference();
  });

  document.getElementById('preset-critical').addEventListener('click', () => {
    simRul.value = 8;
    simRulVal.textContent = '8 cycles';
    simAnom.value = 88;
    simAnomVal.textContent = '88.0';
    simSensors.value = 'sensor_12 (-4.75σ, Critical) | sensor_11 (+4.50σ, Critical) | sensor_8 (+4.12σ, Critical)';
    runSimulatorInference();
  });

  // Initial Load
  loadFleetData();

  // --- Functions ---

  function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        tabBtns.forEach(b => b.classList.remove('active'));
        tabPanes.forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(targetTab).classList.add('active');
      });
    });
  }

  async function loadFleetData() {
    subFleetDataset.textContent = `C-MAPSS ${state.currentDataset}`;
    fleetTableBody.innerHTML = `<tr><td colspan="7" class="loading-cell"><i class="fa-solid fa-spinner fa-spin"></i> Loading ${state.currentDataset} fleet telemetry...</td></tr>`;

    try {
      const resp = await fetch(`/api/fleet/summary?dataset=${state.currentDataset}`);
      if (!resp.ok) throw new Error('API request failed');
      const data = await resp.json();

      apiStatusText.textContent = 'Backend Online';

      // Update KPIs
      const total = data.total_engines;
      const hd = data.health_distribution;
      valTotalEngines.textContent = total;

      valHealthyCount.textContent = hd.HEALTHY;
      valHealthyPct.textContent = `(${((hd.HEALTHY / total) * 100).toFixed(1)}%)`;

      valMonitorCount.textContent = hd.MONITOR;
      valMonitorPct.textContent = `(${((hd.MONITOR / total) * 100).toFixed(1)}%)`;

      valMaintCount.textContent = hd.MAINTENANCE_REQUIRED;
      valMaintPct.textContent = `(${((hd.MAINTENANCE_REQUIRED / total) * 100).toFixed(1)}%)`;

      valCriticalCount.textContent = hd.CRITICAL;
      valCriticalPct.textContent = `(${((hd.CRITICAL / total) * 100).toFixed(1)}%)`;

      state.fleetEngines = data.engines || [];
      renderFleetTable();

      // Select first engine by default
      if (state.fleetEngines.length > 0) {
        selectEngine(state.fleetEngines[0].engine_id);
      }
    } catch (err) {
      console.error('Error fetching fleet summary:', err);
      apiStatusText.textContent = 'API Offline';
      fleetTableBody.innerHTML = `<tr><td colspan="7" class="loading-cell" style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Could not connect to backend API. Please run <code>python run_maintenance_advisor.py --serve</code></td></tr>`;
    }
  }

  function renderFleetTable() {
    const query = searchInput.value.trim().toLowerCase();
    const filter = statusFilter.value;

    const filtered = state.fleetEngines.filter(eng => {
      const matchSearch = String(eng.engine_id).includes(query);
      const matchFilter = filter === 'ALL' || eng.engine_health_status === filter;
      return matchSearch && matchFilter;
    });

    if (filtered.length === 0) {
      fleetTableBody.innerHTML = `<tr><td colspan="7" class="loading-cell">No engines matching query.</td></tr>`;
      return;
    }

    fleetTableBody.innerHTML = '';
    filtered.forEach(eng => {
      const tr = document.createElement('tr');
      if (eng.engine_id === state.selectedEngineId) {
        tr.classList.add('selected-row');
      }

      const statusBadge = getStatusBadgeHTML(eng.engine_health_status);
      const anomColor = eng.latest_anomaly_score >= 80 ? 'color-critical' : eng.latest_anomaly_score >= 65 ? 'color-maintenance' : eng.latest_anomaly_score >= 45 ? 'color-monitor' : 'color-healthy';

      tr.innerHTML = `
        <td><strong>#${eng.engine_id}</strong></td>
        <td>${eng.latest_observed_cycle}</td>
        <td><span class="color-blue font-bold">${eng.predicted_RUL.toFixed(1)}</span> cycles</td>
        <td><span class="${anomColor} font-bold">${eng.latest_anomaly_score.toFixed(1)}</span>/100</td>
        <td>${statusBadge}</td>
        <td><span class="font-bold">${eng.risk_level}</span></td>
        <td><button class="btn-inspect" data-id="${eng.engine_id}"><i class="fa-solid fa-magnifying-glass"></i> Inspect</button></td>
      `;

      tr.addEventListener('click', () => selectEngine(eng.engine_id));
      const btn = tr.querySelector('.btn-inspect');
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectEngine(eng.engine_id);
      });

      fleetTableBody.appendChild(tr);
    });
  }

  async function selectEngine(engineId) {
    state.selectedEngineId = engineId;

    // Highlight row in table
    const rows = fleetTableBody.querySelectorAll('tr');
    rows.forEach(r => r.classList.remove('selected-row'));
    const matchingRow = Array.from(rows).find(r => r.querySelector('strong')?.textContent === `#${engineId}`);
    if (matchingRow) matchingRow.classList.add('selected-row');

    inspTitle.textContent = `Engine #${engineId}`;

    try {
      // 1. Fetch Engine Detailed Advisory
      const resp = await fetch(`/api/engine/${engineId}?dataset=${state.currentDataset}`);
      if (!resp.ok) throw new Error('Failed to fetch engine detail');
      const det = await resp.json();

      // Update Inspector UI
      inspBadge.className = `badge badge-${getStatusSlug(det.engine_health_status)}`;
      inspBadge.textContent = det.engine_health_status;

      inspRul.textContent = parseFloat(det.predicted_RUL).toFixed(1);
      inspActualRul.textContent = det.true_RUL !== undefined ? `True RUL: ${det.true_RUL} cycles (Err: ${det.absolute_error})` : 'C-MAPSS Simulation';

      inspAnomScore.textContent = parseFloat(det.latest_anomaly_score).toFixed(1);
      inspAnomStatus.textContent = `Status: ${det.latest_anomaly_status} (${det.latest_anomaly_severity})`;

      inspComposite.textContent = parseFloat(det.composite_health_score).toFixed(1);
      inspRisk.textContent = `Risk Level: ${det.risk_level}`;

      inspUrgency.textContent = det.urgency_window_cycles !== -1 ? det.urgency_window_cycles : 'None (Healthy)';

      inspRec.textContent = det.maintenance_recommendation;
      inspReason.textContent = det.decision_reason;

      // Implicated Components Tags
      inspComponentsTags.innerHTML = '';
      const comps = (det.impacted_components || 'General Subsystems').split(',');
      comps.forEach(c => {
        const tag = document.createElement('span');
        tag.className = 'component-tag';
        tag.textContent = c.trim();
        inspComponentsTags.appendChild(tag);
      });

      inspTasks.textContent = det.targeted_action_items || 'Routine flight line monitoring.';

      // Sensors List
      inspSensorsList.innerHTML = '';
      const sensTokens = (det.top_abnormal_sensors || 'All sensors nominal').split('|');
      sensTokens.forEach(st => {
        const chip = document.createElement('span');
        chip.className = 'sensor-chip';
        chip.textContent = st.trim();
        inspSensorsList.appendChild(chip);
      });

      // 2. Fetch and render cycle history chart
      loadEngineHistoryChart(engineId);

    } catch (err) {
      console.error('Error loading engine diagnostics:', err);
    }
  }

  async function loadEngineHistoryChart(engineId) {
    try {
      const resp = await fetch(`/api/engine/${engineId}/history?dataset=${state.currentDataset}`);
      if (!resp.ok) return;
      const data = await resp.json();
      const trajectory = data.trajectory || [];

      const cycles = trajectory.map(t => t.cycle);
      const ruls = trajectory.map(t => t.predicted_RUL);
      const anoms = trajectory.map(t => t.anomaly_score);

      if (state.historyChart) {
        state.historyChart.destroy();
      }

      const ctx = chartCanvas.getContext('2d');
      state.historyChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: cycles,
          datasets: [
            {
              label: 'Predicted RUL (cycles)',
              data: ruls,
              borderColor: '#0ea5e9',
              backgroundColor: 'rgba(14, 165, 233, 0.1)',
              borderWidth: 2.5,
              pointRadius: 0,
              pointHoverRadius: 4,
              yAxisID: 'yRul',
              tension: 0.2,
            },
            {
              label: 'Anomaly Score (0-100)',
              data: anoms,
              borderColor: '#ef4444',
              backgroundColor: 'rgba(239, 68, 68, 0.08)',
              borderWidth: 2,
              borderDash: [4, 4],
              pointRadius: 0,
              pointHoverRadius: 4,
              yAxisID: 'yAnom',
              tension: 0.2,
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false,
          },
          plugins: {
            legend: {
              labels: {
                color: '#9ca3af',
                font: { size: 11, family: 'Inter' }
              }
            },
            tooltip: {
              backgroundColor: '#1f2937',
              titleColor: '#f9fafb',
              bodyColor: '#e5e7eb',
              borderColor: '#374151',
              borderWidth: 1,
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(75, 85, 99, 0.2)' },
              ticks: { color: '#9ca3af', maxTicksLimit: 10 }
            },
            yRul: {
              type: 'linear',
              position: 'left',
              grid: { color: 'rgba(75, 85, 99, 0.2)' },
              ticks: { color: '#0ea5e9' },
              title: { display: true, text: 'RUL (cycles)', color: '#0ea5e9', font: { size: 10 } }
            },
            yAnom: {
              type: 'linear',
              position: 'right',
              grid: { drawOnChartArea: false },
              ticks: { color: '#ef4444' },
              min: 0,
              max: 100,
              title: { display: true, text: 'Anomaly Score (0–100)', color: '#ef4444', font: { size: 10 } }
            }
          }
        }
      });
    } catch (err) {
      console.error('Error building history chart:', err);
    }
  }

  async function runSimulatorInference() {
    const payload = {
      engine_id: parseInt(simEngineId.value) || 42,
      cycle: parseInt(simCycle.value) || 150,
      predicted_rul: parseFloat(simRul.value),
      anomaly_score: parseFloat(simAnom.value),
      anomaly_status: parseFloat(simAnom.value) >= 65 ? 'Anomalous' : 'Normal',
      top_abnormal_sensors: simSensors.value,
    };

    btnRunSim.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Evaluating...';

    try {
      const resp = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) throw new Error('Simulator request failed');
      const res = await resp.json();

      simResStatus.textContent = res.engine_health_status;
      simResStatus.className = `status-pill-large badge-${getStatusSlug(res.engine_health_status)}`;
      simResRisk.textContent = `Risk: ${res.risk_level}`;
      simResComposite.textContent = `${parseFloat(res.composite_health_score).toFixed(1)}%`;
      simResUrgency.textContent = res.urgency_window_cycles !== null && res.urgency_window_cycles !== -1 ? `${res.urgency_window_cycles} Cycles` : 'Routine Line Monitoring';
      simResReason.textContent = res.decision_reason;
      simResRec.textContent = res.maintenance_recommendation;
      simResActions.textContent = res.targeted_action_items;
      simResComponents.textContent = res.impacted_components;

    } catch (err) {
      console.error('Simulator error:', err);
    } finally {
      btnRunSim.innerHTML = '<i class="fa-solid fa-bolt"></i> Evaluate Engine Health & Advisory';
    }
  }

  function getStatusSlug(status) {
    const s = String(status).toUpperCase();
    if (s.includes('CRITICAL')) return 'critical';
    if (s.includes('MAINTENANCE')) return 'maint';
    if (s.includes('MONITOR')) return 'monitor';
    return 'healthy';
  }

  function getStatusBadgeHTML(status) {
    const slug = getStatusSlug(status);
    return `<span class="badge badge-${slug}">${status}</span>`;
  }

});
