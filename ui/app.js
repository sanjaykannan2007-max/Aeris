/**
 * AERIS Frontend Controller
 * Aircraft Engine Reliability & Intelligence System
 */

document.addEventListener('DOMContentLoaded', () => {
  const state = {
    currentDataset: 'FD001',
    fleetEngines: [],
    aircraftList: [],
    selectedEngineId: 1,
    historyChart: null,
    replayInterval: null,
    replayCycle: 1,
    replayMaxCycles: 192,
  };

  // 1. Navigation & Screen Router
  const navLinks = document.querySelectorAll('.nav-link[data-view]');
  const viewPanes = document.querySelectorAll('.view-pane');

  function navigateTo(viewId) {
    viewPanes.forEach(pane => pane.classList.remove('active'));
    navLinks.forEach(link => link.classList.remove('active'));

    const targetPane = document.getElementById(viewId);
    if (targetPane) {
      targetPane.classList.add('active');
    }

    const activeLink = document.querySelector(`.nav-link[data-view="${viewId}"]`);
    if (activeLink) {
      activeLink.classList.add('active');
    }

    closeCommandPalette();

    // Trigger sub-view loads
    if (viewId === 'view-aircraft') loadAircraftData();
    if (viewId === 'view-maintenance') loadWorkOrders();
    if (viewId === 'view-alerts') loadAlerts();
    if (viewId === 'view-engines') loadEngineInspector(state.selectedEngineId);
  }

  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const viewId = link.getAttribute('data-view');
      navigateTo(viewId);
    });
  });

  // 2. Global Command Palette (Ctrl + K)
  const cmdPalette = document.getElementById('cmd-palette');
  const cmdInput = document.getElementById('cmd-input');

  window.toggleCommandPalette = () => {
    if (cmdPalette.style.display === 'flex') {
      closeCommandPalette();
    } else {
      cmdPalette.style.display = 'flex';
      cmdPalette.classList.add('active');
      cmdInput.focus();
    }
  };

  function closeCommandPalette() {
    cmdPalette.style.display = 'none';
    cmdPalette.classList.remove('active');
  }

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      window.toggleCommandPalette();
    }
    if (e.key === 'Escape') {
      closeCommandPalette();
    }
  });

  // 3. Dataset Selector Switcher
  const datasetSelect = document.getElementById('dataset-select');
  datasetSelect.addEventListener('change', (e) => {
    state.currentDataset = e.target.value;
    loadFleetData();
  });

  // 4. Auth & Quick Login
  window.quickLogin = (email, pwd) => {
    document.getElementById('auth-email').value = email;
    document.getElementById('auth-password').value = pwd;
    login();
  };

  const authForm = document.getElementById('auth-form');
  authForm.addEventListener('submit', (e) => {
    e.preventDefault();
    login();
  });

  async function login() {
    const email = document.getElementById('auth-email').value;
    const pwd = document.getElementById('auth-password').value;

    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: pwd })
      });
      const data = await resp.json();

      if (data.success) {
        document.getElementById('screen-auth').style.display = 'none';
        document.getElementById('app-platform').style.display = 'flex';
        document.getElementById('user-display-name').textContent = data.user.full_name;
        document.getElementById('user-display-role').textContent = data.user.role;
        loadFleetData();
      } else {
        alert(data.error || 'Login failed.');
      }
    } catch (err) {
      // Offline / Hackathon direct login fallback
      document.getElementById('screen-auth').style.display = 'none';
      document.getElementById('app-platform').style.display = 'flex';
      loadFleetData();
    }
  }

  window.logout = () => {
    document.getElementById('app-platform').style.display = 'none';
    document.getElementById('screen-auth').style.display = 'flex';
  };

  // 5. Load Monitored Fleet Data
  async function loadFleetData() {
    try {
      const resp = await fetch(`/api/fleet/summary?dataset=${state.currentDataset}`);
      const data = await resp.json();

      document.getElementById('sub-fleet-dataset').textContent = `C-MAPSS ${state.currentDataset}`;
      document.getElementById('val-total-engines').textContent = data.total_engines;

      const hd = data.health_distribution;
      const total = data.total_engines;
      document.getElementById('val-healthy-count').textContent = hd.HEALTHY;
      document.getElementById('val-healthy-pct').textContent = `(${((hd.HEALTHY / total) * 100).toFixed(1)}%)`;

      document.getElementById('val-monitor-count').textContent = hd.MONITOR;
      document.getElementById('val-monitor-pct').textContent = `(${((hd.MONITOR / total) * 100).toFixed(1)}%)`;

      document.getElementById('val-maint-count').textContent = hd.MAINTENANCE_REQUIRED;
      document.getElementById('val-maint-pct').textContent = `(${((hd.MAINTENANCE_REQUIRED / total) * 100).toFixed(1)}%)`;

      document.getElementById('val-critical-count').textContent = hd.CRITICAL;
      document.getElementById('val-critical-pct').textContent = `(${((hd.CRITICAL / total) * 100).toFixed(1)}%)`;

      state.fleetEngines = data.engines || [];
      renderFleetTable();
    } catch (err) {
      console.error('Error loading fleet:', err);
    }
  }

  function renderFleetTable() {
    const tbody = document.getElementById('fleet-table-body');
    const filter = document.getElementById('engine-search-input').value.toLowerCase();

    const filtered = state.fleetEngines.filter(e => 
      String(e.engine_id).includes(filter) || e.engine_id_code.toLowerCase().includes(filter)
    );

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="mono">No engine matching query.</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map(eng => {
      const badgeClass = eng.engine_health_status.toLowerCase().replace(' ', '');
      return `
        <tr onclick="inspectEngine(${eng.engine_id})">
          <td class="mono" style="font-weight: 700;">${eng.engine_id_code}</td>
          <td class="mono">${eng.aircraft_id_code} <span class="demo-tag">DEMO</span></td>
          <td class="mono">${eng.latest_observed_cycle}</td>
          <td class="mono" style="font-weight: 700; color: var(--color-sky);">${eng.predicted_RUL} cycles</td>
          <td class="mono">${eng.latest_anomaly_score}</td>
          <td><span class="badge-pill ${badgeClass}">${eng.engine_health_status}</span></td>
          <td class="mono" style="font-weight: 700;">${eng.priority_score}</td>
          <td><button class="replay-btn" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">Inspect</button></td>
        </tr>
      `;
    }).join('');
  }

  window.inspectEngine = (engId) => {
    state.selectedEngineId = engId;
    navigateTo('view-engines');
  };

  // 6. Load Engine Inspector & History Chart
  async function loadEngineInspector(engId) {
    try {
      const detailResp = await fetch(`/api/engine/${engId}?dataset=${state.currentDataset}`);
      const eng = await detailResp.json();

      document.getElementById('insp-title').textContent = `Engine AE-${engId.toString().padStart(4, '0')}-L`;
      document.getElementById('insp-rul').textContent = `${eng.predicted_RUL} cycles`;
      document.getElementById('insp-anom').textContent = `${eng.latest_anomaly_score}`;
      document.getElementById('insp-comp').textContent = `${eng.composite_health_score}%`;
      document.getElementById('insp-conf').textContent = `${eng.confidence_pct}%`;
      document.getElementById('insp-ai-reason').textContent = eng.decision_reason || "Engine telemetry demonstrates nominal operational baseline across all compressor and turbine stages.";

      const badge = document.getElementById('insp-badge');
      badge.textContent = eng.engine_health_status;
      badge.className = `badge-pill ${eng.engine_health_status.toLowerCase().replace(' ', '')}`;

      // Render Subsystem Bars
      const subs = eng.subsystems || { Compressor: 54, Turbine: 72, Thermal: 61, Pressure: 49, Mechanical: 83 };
      const subContainer = document.getElementById('subsystems-bars');
      subContainer.innerHTML = Object.entries(subs).map(([name, val]) => `
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 0.2rem;">
            <span>${name}</span>
            <span class="mono">${val}%</span>
          </div>
          <div style="height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
            <div style="width: ${val}%; height: 100%; background: ${val < 50 ? 'var(--color-critical)' : val < 70 ? 'var(--color-warning)' : 'var(--color-healthy)'};"></div>
          </div>
        </div>
      `).join('');

      // Load History Chart
      const histResp = await fetch(`/api/engine/${engId}/history?dataset=${state.currentDataset}`);
      const histData = await histResp.json();
      renderHistoryChart(histData.trajectory || []);
    } catch (err) {
      console.error('Error loading engine detail:', err);
    }
  }

  function renderHistoryChart(trajectory) {
    const ctx = document.getElementById('engine-history-chart').getContext('2d');
    if (state.historyChart) state.historyChart.destroy();

    const labels = trajectory.map(t => t.cycle);
    const ruls = trajectory.map(t => t.predicted_RUL);
    const anoms = trajectory.map(t => t.anomaly_score);

    state.historyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          { label: 'Predicted RUL (Cycles)', data: ruls, borderColor: '#0284c7', borderWidth: 2, yAxisID: 'y' },
          { label: 'Anomaly Score (0-100)', data: anoms, borderColor: '#ef4444', borderWidth: 2, yAxisID: 'y1' }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
          y: { position: 'left', grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
          y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#ef4444' } }
        }
      }
    });
  }

  // 7. Load Aircraft Registry
  async function loadAircraftData() {
    try {
      const resp = await fetch('/api/aircraft');
      const data = await resp.json();
      const tbody = document.getElementById('aircraft-table-body');
      tbody.innerHTML = (data.aircraft || []).map(ac => `
        <tr>
          <td class="mono" style="font-weight: 700;">${ac.aircraft_id}</td>
          <td class="mono">${ac.registration}</td>
          <td>${ac.manufacturer} ${ac.aircraft_model}</td>
          <td>${ac.operator}</td>
          <td class="mono">${ac.base_airport}</td>
          <td class="mono">${ac.total_flight_hours} hrs</td>
          <td class="mono">${ac.total_flight_cycles} cycles</td>
          <td><span class="badge-pill healthy">${ac.status}</span></td>
        </tr>
      `).join('');
    } catch (err) {
      console.error(err);
    }
  }

  // 8. Load Maintenance Work Orders
  async function loadWorkOrders() {
    try {
      const resp = await fetch('/api/maintenance/workorders');
      const data = await resp.json();
      const tbody = document.getElementById('maintenance-table-body');
      tbody.innerHTML = (data.work_orders || []).map(wo => `
        <tr>
          <td class="mono" style="font-weight: 700;">${wo.work_order_id}</td>
          <td class="mono">${wo.aircraft_id_code}</td>
          <td class="mono">${wo.engine_id_code}</td>
          <td>${wo.issue_summary}</td>
          <td><span class="badge-pill ${wo.priority === 'HIGH' ? 'critical' : 'warning'}">${wo.priority}</span></td>
          <td>${wo.recommended_action}</td>
          <td class="mono">${wo.urgency_window_cycles} cycles</td>
          <td>${wo.assigned_engineer}</td>
          <td><span class="badge-pill ${wo.status === 'OPEN' ? 'warning' : 'healthy'}">${wo.status}</span></td>
        </tr>
      `).join('');
    } catch (err) {
      console.error(err);
    }
  }

  // 9. Load Alerts
  async function loadAlerts() {
    try {
      const resp = await fetch('/api/alerts');
      const data = await resp.json();
      const container = document.getElementById('alerts-container');
      container.innerHTML = (data.alerts || []).map(alt => `
        <div class="panel" style="margin-bottom: 1rem; border-left: 4px solid ${alt.severity === 'CRITICAL' ? 'var(--color-critical)' : 'var(--color-warning)'}">
          <div class="panel-header" style="margin-bottom: 0.5rem;">
            <div class="panel-title" style="font-size: 0.95rem;">
              <span class="badge-pill ${alt.severity.toLowerCase()}">${alt.severity}</span>
              <span class="mono">${alt.engine_id_code} (${alt.aircraft_id_code})</span>
            </div>
            <span class="mono" style="font-size: 0.75rem; color: var(--text-secondary);">${alt.created_at}</span>
          </div>
          <p style="font-size: 0.85rem; color: var(--text-primary);">${alt.message}</p>
        </div>
      `).join('');
    } catch (err) {
      console.error(err);
    }
  }

  // 10. What-If Simulator
  window.runSimulator = async () => {
    const rul = parseFloat(document.getElementById('sim-rul').value);
    const anom = parseFloat(document.getElementById('sim-anom').value);

    try {
      const resp = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_rul: 72, current_anom: 45, simulated_rul: rul, simulated_anom: anom })
      });
      const data = await resp.json();
      const out = document.getElementById('sim-outcome-content');
      out.innerHTML = `
        <strong>[BEFORE]</strong> Health: ${data.before.health_status} (Score: ${data.before.composite_health}%)<br>
        <strong>[AFTER]</strong> Health: <span style="color: var(--color-cyan);">${data.after.health_status}</span> (Score: ${data.after.composite_health}%)<br>
        <strong>Confidence:</strong> ${data.after.confidence_pct}%<br>
        <strong>Rationale:</strong> ${data.after.decision_reason}<br>
        <strong>Recommendation:</strong> ${data.after.recommendation} (Window: ${data.after.urgency_window} cycles)
      `;
    } catch (err) {
      console.error(err);
    }
  };

  // C-MAPSS Replay Controls
  document.getElementById('btn-replay-play').addEventListener('click', () => {
    if (state.replayInterval) clearInterval(state.replayInterval);
    state.replayInterval = setInterval(() => {
      if (state.replayCycle < state.replayMaxCycles) {
        state.replayCycle++;
        document.getElementById('replay-cycle-num').textContent = state.replayCycle;
        document.getElementById('replay-slider').value = state.replayCycle;
        const rul = Math.max(0, 125 - state.replayCycle);
        document.getElementById('replay-rul-val').textContent = `${rul} cycles`;
        const badge = document.getElementById('replay-status-badge');
        if (rul < 20) { badge.textContent = 'CRITICAL'; badge.className = 'badge-pill critical'; }
        else if (rul < 45) { badge.textContent = 'WARNING'; badge.className = 'badge-pill warning'; }
        else if (rul < 75) { badge.textContent = 'MONITOR'; badge.className = 'badge-pill monitor'; }
        else { badge.textContent = 'HEALTHY'; badge.className = 'badge-pill healthy'; }
      } else {
        clearInterval(state.replayInterval);
      }
    }, 500);
  });

  document.getElementById('btn-replay-pause').addEventListener('click', () => {
    if (state.replayInterval) clearInterval(state.replayInterval);
  });

  document.getElementById('btn-replay-reset').addEventListener('click', () => {
    if (state.replayInterval) clearInterval(state.replayInterval);
    state.replayCycle = 1;
    document.getElementById('replay-cycle-num').textContent = 1;
    document.getElementById('replay-slider').value = 1;
    document.getElementById('replay-rul-val').textContent = '125 cycles';
    const badge = document.getElementById('replay-status-badge');
    badge.textContent = 'HEALTHY'; badge.className = 'badge-pill healthy';
  });

});
