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
    if (viewId === 'view-engines') {
      loadEngineInspector(state.selectedEngineId);
      setTimeout(init3DTurbofanEngine, 100);
    }
    if (viewId === 'view-telemetry') initLiveTelemetryCharts();
    if (viewId === 'view-analytics') initModelAnalyticsChart();
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

  // 4. Auth, Tab Switcher & Create Account Signup
  window.switchAuthTab = (tab) => {
    const btnSignin = document.getElementById('tab-auth-signin');
    const btnSignup = document.getElementById('tab-auth-signup');
    const formSignin = document.getElementById('auth-form');
    const formSignup = document.getElementById('auth-form-signup');

    if (tab === 'signin') {
      btnSignin.classList.add('active');
      btnSignin.style.borderBottom = '2px solid var(--color-cyan)';
      btnSignup.classList.remove('active');
      btnSignup.style.borderBottom = 'none';
      formSignin.style.display = 'block';
      formSignup.style.display = 'none';
    } else {
      btnSignup.classList.add('active');
      btnSignup.style.borderBottom = '2px solid var(--color-cyan)';
      btnSignin.classList.remove('active');
      btnSignin.style.borderBottom = 'none';
      formSignup.style.display = 'block';
      formSignin.style.display = 'none';
    }
  };

  window.handleSignup = (e) => {
    e.preventDefault();
    const name = document.getElementById('signup-name').value;
    const email = document.getElementById('signup-email').value;
    const role = document.getElementById('signup-role').value;

    document.getElementById('screen-auth').style.display = 'none';
    document.getElementById('app-platform').style.display = 'flex';
    document.getElementById('user-display-name').textContent = name;
    document.getElementById('user-display-role').textContent = role;
    loadFleetData();
  };

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
      document.getElementById('screen-auth').style.display = 'none';
      document.getElementById('app-platform').style.display = 'flex';
      loadFleetData();
    }
  }

  window.logout = () => {
    document.getElementById('app-platform').style.display = 'none';
    document.getElementById('screen-auth').style.display = 'flex';
  };

  // 4b. Three.js Rotatable 3D Turbofan Model Renderer
  let scene3d, camera3d, renderer3d, engineGroup;
  let isDragging = false, previousMousePosition = { x: 0, y: 0 };

  function init3DTurbofanEngine() {
    const container = document.getElementById('threejs-container');
    if (!container || scene3d) return;

    scene3d = new THREE.Scene();
    scene3d.background = new THREE.Color(0x05070c);

    camera3d = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera3d.position.set(0, 5, 25);

    renderer3d = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer3d.setSize(container.clientWidth, container.clientHeight);
    renderer3d.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer3d.domElement);

    // Ambient & Directional Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene3d.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x06b6d4, 1.2);
    dirLight1.position.set(10, 15, 10);
    scene3d.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xef4444, 0.8);
    dirLight2.position.set(-10, -5, -10);
    scene3d.add(dirLight2);

    // Build Detailed Turbofan Subsystems Group
    engineGroup = new THREE.Group();

    // 1. Fan Casing (Outer Cylinder)
    const casingGeo = new THREE.CylinderGeometry(4.2, 4.0, 14, 32, 1, true);
    const casingMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, opacity: 0.35, transparent: true, side: THREE.DoubleSide });
    const casing = new THREE.Mesh(casingGeo, casingMat);
    casing.rotation.z = Math.PI / 2;
    engineGroup.add(casing);

    // 2. Central Shaft Core
    const shaftGeo = new THREE.CylinderGeometry(0.5, 0.5, 15, 16);
    const shaftMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.8, roughness: 0.2 });
    const shaft = new THREE.Mesh(shaftGeo, shaftMat);
    shaft.rotation.z = Math.PI / 2;
    engineGroup.add(shaft);

    // 3. Front Fan Blades (Stage 1) - Cyan Highlight
    const fanGeo = new THREE.ConeGeometry(3.8, 1.5, 24);
    const fanMat = new THREE.MeshStandardMaterial({ color: 0x06b6d4, metalness: 0.6, roughness: 0.3 });
    const fan = new THREE.Mesh(fanGeo, fanMat);
    fan.rotation.z = -Math.PI / 2;
    fan.position.x = -6;
    engineGroup.add(fan);

    // 4. FAULTY High Pressure Compressor (HPC Stage) - HIGHLIGHTED CRITICAL RED WITH GLOW
    const hpcGeo = new THREE.CylinderGeometry(2.5, 3.2, 3.5, 24);
    const hpcMat = new THREE.MeshStandardMaterial({ color: 0xef4444, roughness: 0.2, emissive: 0x7f0000, emissiveIntensity: 0.6 });
    const hpc = new THREE.Mesh(hpcGeo, hpcMat);
    hpc.rotation.z = Math.PI / 2;
    hpc.position.x = -2.5;
    engineGroup.add(hpc);

    // 5. Combustor Chamber (Stage 3) - Amber Highlight
    const combGeo = new THREE.CylinderGeometry(2.4, 2.4, 2.5, 24);
    const combMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0x9a3412, emissiveIntensity: 0.4 });
    const comb = new THREE.Mesh(combGeo, combMat);
    comb.rotation.z = Math.PI / 2;
    comb.position.x = 0.8;
    engineGroup.add(comb);

    // 6. High Pressure & Low Pressure Turbine (LPT/HPT Stage 4) - Blue Highlight
    const turbGeo = new THREE.CylinderGeometry(3.0, 2.2, 3.5, 24);
    const turbMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.7, roughness: 0.3 });
    const turb = new THREE.Mesh(turbGeo, turbMat);
    turb.rotation.z = Math.PI / 2;
    turb.position.x = 4.2;
    engineGroup.add(turb);

    // Slightly tilt engine group for 3D perspective
    engineGroup.rotation.y = Math.PI / 6;
    engineGroup.rotation.x = Math.PI / 12;
    scene3d.add(engineGroup);

    // Mouse Controls for 3D Rotation
    const dom = renderer3d.domElement;
    dom.addEventListener('mousedown', (e) => {
      isDragging = true;
      previousMousePosition = { x: e.clientX, y: e.clientY };
    });

    dom.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const deltaMove = { x: e.clientX - previousMousePosition.x, y: e.clientY - previousMousePosition.y };
      engineGroup.rotation.y += deltaMove.x * 0.01;
      engineGroup.rotation.x += deltaMove.y * 0.01;
      previousMousePosition = { x: e.clientX, y: e.clientY };
    });

    window.addEventListener('mouseup', () => { isDragging = false; });

    // Animation Render Loop
    function animate() {
      requestAnimationFrame(animate);
      if (!isDragging && engineGroup) {
        engineGroup.rotation.y += 0.005; // Continuous subtle rotation
      }
      renderer3d.render(scene3d, camera3d);
    }
    animate();
  }

  window.rotate3DModel = (dir) => {
    if (!engineGroup) return;
    if (dir === 'left') engineGroup.rotation.y -= 0.4;
    if (dir === 'right') engineGroup.rotation.y += 0.4;
  };

  window.reset3DModel = () => {
    if (!engineGroup) return;
    engineGroup.rotation.set(Math.PI / 12, Math.PI / 6, 0);
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
          { label: 'Predicted RUL (Cycles)', data: ruls, borderColor: '#0284c7', borderWidth: 2, pointRadius: 1, yAxisID: 'y' },
          { label: 'Anomaly Score (0-100)', data: anoms, borderColor: '#ef4444', borderWidth: 2, pointRadius: 1, yAxisID: 'y1' }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
          y: { position: 'left', grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
          y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#ef4444' } }
        }
      }
    });
  }

  // 7b. Live Telemetry Streaming Charts Setup
  let s7Chart = null, s11Chart = null, modelChart = null;

  function initLiveTelemetryCharts() {
    const s7Ctx = document.getElementById('live-telemetry-s7-chart');
    const s11Ctx = document.getElementById('live-telemetry-s11-chart');
    if (!s7Ctx || !s11Ctx) return;

    if (s7Chart) s7Chart.destroy();
    if (s11Chart) s11Chart.destroy();

    const labels = Array.from({length: 20}, (_, i) => `t-${20-i}s`);
    const s7Data = Array.from({length: 20}, () => 550 + Math.random() * 8);
    const s11Data = Array.from({length: 20}, () => 47 + Math.random() * 2);

    s7Chart = new Chart(s7Ctx.getContext('2d'), {
      type: 'line',
      data: { labels, datasets: [{ label: 'S7 Temp (°R)', data: s7Data, borderColor: '#06b6d4', borderWidth: 2, fill: true, backgroundColor: 'rgba(6,182,212,0.1)' }] },
      options: { responsive: true, maintainAspectRatio: false, animation: false, scales: { x: { display: false }, y: { ticks: { color: '#94a3b8' } } } }
    });

    s11Chart = new Chart(s11Ctx.getContext('2d'), {
      type: 'line',
      data: { labels, datasets: [{ label: 'S11 Press (psia)', data: s11Data, borderColor: '#0284c7', borderWidth: 2, fill: true, backgroundColor: 'rgba(2,132,199,0.1)' }] },
      options: { responsive: true, maintainAspectRatio: false, animation: false, scales: { x: { display: false }, y: { ticks: { color: '#94a3b8' } } } }
    });

    // Continuously stream data points without expanding container
    setInterval(() => {
      if (s7Chart && s11Chart) {
        const nextS7 = 550 + Math.random() * 10;
        const nextS11 = 47 + Math.random() * 2.5;

        s7Chart.data.datasets[0].data.shift();
        s7Chart.data.datasets[0].data.push(nextS7);
        s7Chart.update();

        s11Chart.data.datasets[0].data.shift();
        s11Chart.data.datasets[0].data.push(nextS11);
        s11Chart.update();

        document.getElementById('live-s7-val').textContent = `${nextS7.toFixed(1)} °R`;
        document.getElementById('live-s11-val').textContent = `${nextS11.toFixed(1)} psia`;
      }
    }, 1500);
  }

  function initModelAnalyticsChart() {
    const ctx = document.getElementById('model-analytics-chart');
    if (!ctx) return;
    if (modelChart) modelChart.destroy();

    const engines = Array.from({length: 30}, (_, i) => `Eng #${i+1}`);
    const actualRUL = Array.from({length: 30}, () => Math.floor(Math.random() * 100) + 10);
    const predRUL = actualRUL.map(val => val + (Math.random() * 12 - 6));

    modelChart = new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: {
        labels: engines,
        datasets: [
          { label: 'Actual RUL', data: actualRUL, backgroundColor: 'rgba(2, 132, 199, 0.6)' },
          { label: 'Predicted RUL', data: predRUL, backgroundColor: 'rgba(6, 182, 212, 0.9)' }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
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
