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
    if (viewId === 'view-risk-portfolio') loadRiskPortfolio();
    if (viewId === 'view-economics-opt') loadEconomics();
    if (viewId === 'view-uncertainty-trust') loadUncertainty();
    if (viewId === 'view-fault-injector') startSimulatorLoop();
    if (viewId === 'view-domain-shift') loadDomainShift();
    if (viewId === 'view-lit-benchmarks') loadBenchmarks();
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
  let faultParts = {}; // named mesh refs for dynamic fault highlighting
  let faultPulseTime = 0;

  function makeMetal(color, metalness = 0.75, roughness = 0.25) {
    return new THREE.MeshStandardMaterial({ color, metalness, roughness });
  }

  function init3DTurbofanEngine() {
    const container = document.getElementById('threejs-container');
    if (!container || scene3d) return;

    scene3d = new THREE.Scene();
    scene3d.background = new THREE.Color(0x08101a);
    scene3d.fog = new THREE.Fog(0x08101a, 40, 90);

    camera3d = new THREE.PerspectiveCamera(42, container.clientWidth / container.clientHeight, 0.1, 500);
    camera3d.position.set(4, 6, 28);
    camera3d.lookAt(0, 0, 0);

    renderer3d = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer3d.setSize(container.clientWidth, container.clientHeight);
    renderer3d.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer3d.shadowMap.enabled = true;
    renderer3d.toneMapping = THREE.ACESFilmicToneMapping;
    renderer3d.toneMappingExposure = 1.1;
    container.appendChild(renderer3d.domElement);

    // ── LIGHTING ──────────────────────────────────────────────────────────────
    scene3d.add(new THREE.AmbientLight(0xddeeff, 0.55));

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
    keyLight.position.set(12, 18, 14);
    keyLight.castShadow = true;
    scene3d.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x7ec8e3, 0.5);
    fillLight.position.set(-10, 4, 8);
    scene3d.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0x334155, 0.7);
    rimLight.position.set(0, -8, -14);
    scene3d.add(rimLight);

    // ── ENGINE GROUP ──────────────────────────────────────────────────────────
    engineGroup = new THREE.Group();
    // Tilt for an isometric-style view like the reference image
    engineGroup.rotation.x = Math.PI / 14;
    engineGroup.rotation.y = -Math.PI / 5;

    const METAL_LIGHT   = makeMetal(0xc8d4dc, 0.80, 0.20);
    const METAL_MID     = makeMetal(0x8ea0ae, 0.75, 0.30);
    const METAL_DARK    = makeMetal(0x4a5a68, 0.70, 0.35);
    const METAL_SILVER  = makeMetal(0xdde4ea, 0.85, 0.15);

    // Helper: ring (torus-like disc section)
    function addRing(parent, rx, ry, px, color, tag) {
      const geo = new THREE.CylinderGeometry(rx, ry, 0.18, 40);
      const mat = makeMetal(color, 0.78, 0.22);
      const m = new THREE.Mesh(geo, mat);
      m.rotation.z = Math.PI / 2;
      m.position.x = px;
      parent.add(m);
      if (tag) faultParts[tag] = faultParts[tag] || [];
      if (tag) faultParts[tag].push(m);
      return m;
    }

    // ── 1. OUTER NACELLE / FAN COWL ───────────────────────────────────────────
    // Main barrel (semi-transparent so inner parts show through)
    const nacelleMat = new THREE.MeshStandardMaterial({
      color: 0xb0bec8, metalness: 0.7, roughness: 0.3,
      transparent: true, opacity: 0.28, side: THREE.DoubleSide,
    });
    const nacelleGeo = new THREE.CylinderGeometry(4.5, 4.2, 13, 48, 1, true);
    const nacelle = new THREE.Mesh(nacelleGeo, nacelleMat);
    nacelle.rotation.z = Math.PI / 2;
    nacelle.position.x = -0.5;
    engineGroup.add(nacelle);

    // Front inlet lip ring
    const lipGeo = new THREE.TorusGeometry(4.5, 0.28, 16, 48);
    const lip = new THREE.Mesh(lipGeo, makeMetal(0xd0dce6, 0.82, 0.18));
    lip.rotation.y = Math.PI / 2;
    lip.position.x = -7;
    engineGroup.add(lip);

    // Rear nacelle section (solid)
    const rearCasingGeo = new THREE.CylinderGeometry(4.2, 3.6, 3.5, 40, 1, true);
    const rearCasing = new THREE.Mesh(rearCasingGeo, makeMetal(0x78909c, 0.7, 0.35));
    rearCasing.rotation.z = Math.PI / 2;
    rearCasing.position.x = 5.0;
    engineGroup.add(rearCasing);

    // ── 2. FAN DISK + BLADES (front face, 28 blades) ─────────────────────────
    const fanGroup = new THREE.Group();
    fanGroup.position.x = -6.8;
    fanGroup.rotation.x = Math.PI / 2;

    // Hub disc
    const hubGeo = new THREE.CylinderGeometry(1.1, 1.1, 0.5, 32);
    const hub = new THREE.Mesh(hubGeo, makeMetal(0x546e7a, 0.85, 0.15));
    fanGroup.add(hub);

    // Spinner nose cone
    const spinnerGeo = new THREE.ConeGeometry(1.1, 2.2, 32);
    const spinner = new THREE.Mesh(spinnerGeo, makeMetal(0x37474f, 0.9, 0.1));
    spinner.position.y = -1.3;
    fanGroup.add(spinner);

    // 28 fan blades
    const BLADE_COUNT = 28;
    for (let i = 0; i < BLADE_COUNT; i++) {
      const bladeGeo = new THREE.BoxGeometry(0.14, 3.5, 0.55);
      const blade = new THREE.Mesh(bladeGeo, makeMetal(0xb0bec8, 0.85, 0.15));
      const angle = (i / BLADE_COUNT) * Math.PI * 2;
      blade.position.set(Math.cos(angle) * 2.4, Math.sin(angle) * 2.4, 0);
      blade.rotation.z = angle + 0.3;
      fanGroup.add(blade);
      if (!faultParts['Fan']) faultParts['Fan'] = [];
      faultParts['Fan'].push(blade);
    }
    engineGroup.add(fanGroup);

    // ── 3. LOW PRESSURE COMPRESSOR (LPC) — 4 stage rings ─────────────────────
    const lpcGroup = new THREE.Group();
    lpcGroup.position.x = -4.5;
    engineGroup.add(lpcGroup);

    for (let s = 0; s < 4; s++) {
      // Disk
      const dGeo = new THREE.CylinderGeometry(2.9 - s * 0.08, 2.9 - s * 0.08, 0.22, 36);
      const disk = new THREE.Mesh(dGeo, makeMetal(0x90a4ae, 0.78, 0.22));
      disk.rotation.z = Math.PI / 2;
      disk.position.x = s * 0.85;
      lpcGroup.add(disk);

      // Stator row (slightly larger, darker)
      const sGeo = new THREE.CylinderGeometry(3.0 - s * 0.08, 3.0 - s * 0.08, 0.10, 36);
      const stator = new THREE.Mesh(sGeo, makeMetal(0x607d8b, 0.72, 0.30));
      stator.rotation.z = Math.PI / 2;
      stator.position.x = s * 0.85 + 0.48;
      lpcGroup.add(stator);

      if (!faultParts['Compressor']) faultParts['Compressor'] = [];
      faultParts['Compressor'].push(disk, stator);
    }

    // ── 4. HIGH PRESSURE COMPRESSOR (HPC) — 6 tighter stages ─────────────────
    const hpcGroup = new THREE.Group();
    hpcGroup.position.x = -1.0;
    engineGroup.add(hpcGroup);

    for (let s = 0; s < 6; s++) {
      const r = 2.6 - s * 0.065;
      const dGeo = new THREE.CylinderGeometry(r, r, 0.18, 36);
      const disk = new THREE.Mesh(dGeo, makeMetal(0x78909c, 0.80, 0.20));
      disk.rotation.z = Math.PI / 2;
      disk.position.x = s * 0.62;
      hpcGroup.add(disk);
      if (!faultParts['Compressor']) faultParts['Compressor'] = [];
      faultParts['Compressor'].push(disk);
    }

    // ── 5. COMBUSTOR SECTION ──────────────────────────────────────────────────
    const combustorGroup = new THREE.Group();
    combustorGroup.position.x = 2.85;
    engineGroup.add(combustorGroup);

    // Outer combustor case
    const combOutGeo = new THREE.CylinderGeometry(2.55, 2.55, 2.8, 36);
    const combOut = new THREE.Mesh(combOutGeo, makeMetal(0x546e7a, 0.68, 0.40));
    combOut.rotation.z = Math.PI / 2;
    combustorGroup.add(combOut);

    // Inner liner
    const combInGeo = new THREE.CylinderGeometry(1.6, 1.6, 2.6, 32);
    const combIn = new THREE.Mesh(combInGeo, makeMetal(0x37474f, 0.70, 0.38));
    combIn.rotation.z = Math.PI / 2;
    combustorGroup.add(combIn);

    // Fuel nozzle stubs (12 around the ring)
    for (let i = 0; i < 12; i++) {
      const angle = (i / 12) * Math.PI * 2;
      const nozzleGeo = new THREE.CylinderGeometry(0.09, 0.09, 0.7, 8);
      const nozzle = new THREE.Mesh(nozzleGeo, makeMetal(0x90a4ae, 0.85, 0.15));
      nozzle.rotation.z = Math.PI / 2;
      nozzle.position.set(0, Math.sin(angle) * 2.1, Math.cos(angle) * 2.1);
      combustorGroup.add(nozzle);
    }

    faultParts['Thermal'] = [combOut, combIn];

    // ── 6. HIGH PRESSURE TURBINE (HPT) — 2 stages ────────────────────────────
    const hptGroup = new THREE.Group();
    hptGroup.position.x = 4.45;
    engineGroup.add(hptGroup);

    for (let s = 0; s < 2; s++) {
      const r = 2.45 + s * 0.07;
      const dGeo = new THREE.CylinderGeometry(r, r + 0.1, 0.30, 36);
      const disk = new THREE.Mesh(dGeo, makeMetal(0x607d8b, 0.78, 0.25));
      disk.rotation.z = Math.PI / 2;
      disk.position.x = s * 0.75;
      hptGroup.add(disk);

      // Turbine blades (short radial fins)
      for (let b = 0; b < 24; b++) {
        const bGeo = new THREE.BoxGeometry(0.28, 0.72, 0.14);
        const blade = new THREE.Mesh(bGeo, makeMetal(0x78909c, 0.82, 0.18));
        const angle = (b / 24) * Math.PI * 2;
        blade.position.set(s * 0.75, Math.sin(angle) * (r - 0.38), Math.cos(angle) * (r - 0.38));
        blade.rotation.x = angle;
        hptGroup.add(blade);
      }
      if (!faultParts['Turbine']) faultParts['Turbine'] = [];
      faultParts['Turbine'].push(disk);
    }

    // ── 7. LOW PRESSURE TURBINE (LPT) — 4 stages ─────────────────────────────
    const lptGroup = new THREE.Group();
    lptGroup.position.x = 5.9;
    engineGroup.add(lptGroup);

    for (let s = 0; s < 4; s++) {
      const r = 2.7 + s * 0.08;
      const dGeo = new THREE.CylinderGeometry(r, r + 0.12, 0.28, 36);
      const disk = new THREE.Mesh(dGeo, makeMetal(0x546e7a, 0.75, 0.30));
      disk.rotation.z = Math.PI / 2;
      disk.position.x = s * 0.90;
      lptGroup.add(disk);
      if (!faultParts['Turbine']) faultParts['Turbine'] = [];
      faultParts['Turbine'].push(disk);
    }

    // ── 8. EXHAUST NOZZLE ─────────────────────────────────────────────────────
    const nozzleGeo2 = new THREE.CylinderGeometry(2.1, 1.4, 4.5, 36, 1, true);
    const nozzle2 = new THREE.Mesh(nozzleGeo2, makeMetal(0x4a5a68, 0.72, 0.35));
    nozzle2.rotation.z = Math.PI / 2;
    nozzle2.position.x = 10.2;
    engineGroup.add(nozzle2);

    // Nozzle tip cap
    const tipGeo = new THREE.SphereGeometry(1.4, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.5);
    const tip = new THREE.Mesh(tipGeo, makeMetal(0x37474f, 0.82, 0.2));
    tip.rotation.z = -Math.PI / 2;
    tip.position.x = 12.45;
    engineGroup.add(tip);

    // ── 9. CENTRAL SHAFT ──────────────────────────────────────────────────────
    const shaftGeo = new THREE.CylinderGeometry(0.42, 0.42, 22, 20);
    const shaft = new THREE.Mesh(shaftGeo, makeMetal(0x90a4ae, 0.88, 0.12));
    shaft.rotation.z = Math.PI / 2;
    shaft.position.x = 1.0;
    engineGroup.add(shaft);

    // ── 10. ACCESSORY GEARBOX (bottom bulge) ──────────────────────────────────
    const gbGeo = new THREE.BoxGeometry(2.8, 1.0, 1.8);
    const gb = new THREE.Mesh(gbGeo, makeMetal(0x546e7a, 0.72, 0.40));
    gb.position.set(0.2, -3.6, 0);
    engineGroup.add(gb);
    faultParts['Mechanical'] = [gb];

    // Gearbox pipes
    for (let i = -1; i <= 1; i += 2) {
      const pipeGeo = new THREE.CylinderGeometry(0.14, 0.14, 2.2, 10);
      const pipe = new THREE.Mesh(pipeGeo, makeMetal(0x607d8b, 0.80, 0.25));
      pipe.position.set(0.2 + i * 0.7, -2.4, 0.3);
      engineGroup.add(pipe);
      faultParts['Mechanical'].push(pipe);
    }

    // ── 11. EXTERNAL PIPES / BLEED DUCTS (top) ────────────────────────────────
    const ductPositions = [[-2, 3.8, 1.2], [0.5, 3.6, 1.3], [2.8, 3.4, 1.1]];
    ductPositions.forEach(([px, py, pz]) => {
      const dg = new THREE.CylinderGeometry(0.12, 0.12, 2.5, 10);
      const dp = new THREE.Mesh(dg, makeMetal(0x78909c, 0.78, 0.28));
      dp.rotation.x = Math.PI / 7;
      dp.position.set(px, py, pz);
      engineGroup.add(dp);
      if (!faultParts['Pressure']) faultParts['Pressure'] = [];
      faultParts['Pressure'].push(dp);
    });

    // Pressure sensor box
    const sensorGeo = new THREE.BoxGeometry(0.8, 0.5, 0.5);
    const sensor = new THREE.Mesh(sensorGeo, makeMetal(0x4a5a68, 0.75, 0.35));
    sensor.position.set(-1.5, 3.9, 1.0);
    engineGroup.add(sensor);
    if (!faultParts['Pressure']) faultParts['Pressure'] = [];
    faultParts['Pressure'].push(sensor);

    // ── 12. PYLON STRUT (top mount) ───────────────────────────────────────────
    const strGeo = new THREE.BoxGeometry(5, 0.55, 0.55);
    const strut = new THREE.Mesh(strGeo, makeMetal(0x607d8b, 0.72, 0.35));
    strut.position.set(0, 4.7, 0);
    engineGroup.add(strut);

    // ── 13. STAGE RING FLANGES ────────────────────────────────────────────────
    [-3.6, -0.9, 2.2, 4.5, 6.6].forEach(px => addRing(engineGroup, 4.25, 4.25, px, 0x607d8b));

    scene3d.add(engineGroup);

    // ── MOUSE / TOUCH CONTROLS ────────────────────────────────────────────────
    const dom = renderer3d.domElement;
    dom.addEventListener('mousedown', (e) => {
      isDragging = true;
      previousMousePosition = { x: e.clientX, y: e.clientY };
    });
    dom.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const dx = e.clientX - previousMousePosition.x;
      const dy = e.clientY - previousMousePosition.y;
      engineGroup.rotation.y += dx * 0.008;
      engineGroup.rotation.x += dy * 0.008;
      previousMousePosition = { x: e.clientX, y: e.clientY };
    });
    window.addEventListener('mouseup', () => { isDragging = false; });

    // Touch support
    dom.addEventListener('touchstart', (e) => {
      isDragging = true;
      previousMousePosition = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }, { passive: true });
    dom.addEventListener('touchmove', (e) => {
      if (!isDragging) return;
      const dx = e.touches[0].clientX - previousMousePosition.x;
      const dy = e.touches[0].clientY - previousMousePosition.y;
      engineGroup.rotation.y += dx * 0.008;
      engineGroup.rotation.x += dy * 0.008;
      previousMousePosition = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }, { passive: true });
    dom.addEventListener('touchend', () => { isDragging = false; });

    // ── ANIMATION LOOP ────────────────────────────────────────────────────────
    function animate() {
      requestAnimationFrame(animate);
      faultPulseTime += 0.04;
      if (!isDragging && engineGroup) {
        engineGroup.rotation.y += 0.004;
      }
      // Pulse emissive intensity on fault parts
      Object.entries(faultParts).forEach(([tag, meshes]) => {
        meshes.forEach(m => {
          if (m.userData.isFault) {
            m.material.emissiveIntensity = 0.35 + 0.35 * Math.sin(faultPulseTime * 2.5);
          }
        });
      });
      renderer3d.render(scene3d, camera3d);
    }
    animate();

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
      if (!container || !renderer3d) return;
      camera3d.aspect = container.clientWidth / container.clientHeight;
      camera3d.updateProjectionMatrix();
      renderer3d.setSize(container.clientWidth, container.clientHeight);
    });
    resizeObserver.observe(container);
  }

  // ── FAULT HIGHLIGHTING — called by loadEngineInspector ─────────────────────
  // subsystems: { Compressor: 54, Turbine: 88, Thermal: 91, Pressure: 76, Mechanical: 83 }
  // Any subsystem score < 65 is highlighted as FAULT in red.
  // Multiple faults supported. Healthy parts stay metallic grey.
  window.highlight3DFault = (subsystems) => {
    if (!faultParts || Object.keys(faultParts).length === 0) return;
    const FAULT_THRESHOLD = 65;

    // Reset all to healthy metallic
    Object.values(faultParts).flat().forEach(m => {
      m.material.color.setHex(0x8ea0ae);
      m.material.emissive.setHex(0x000000);
      m.material.emissiveIntensity = 0;
      m.userData.isFault = false;
    });

    // Apply fault colour to each bad subsystem
    Object.entries(subsystems || {}).forEach(([name, score]) => {
      const parts = faultParts[name];
      if (!parts) return;
      if (score < FAULT_THRESHOLD) {
        parts.forEach(m => {
          m.material.color.setHex(0xef4444);
          m.material.emissive.setHex(0x7f0000);
          m.material.emissiveIntensity = 0.55;
          m.userData.isFault = true;
        });
      } else if (score < 80) {
        // Warning amber
        parts.forEach(m => {
          m.material.color.setHex(0xf59e0b);
          m.material.emissive.setHex(0x7c3a00);
          m.material.emissiveIntensity = 0.2;
          m.userData.isFault = false;
        });
      }
    });

    // Fan sub-system maps to "Mechanical" since C-MAPSS doesn't expose Fan directly
    // Update label text in DOM
    const lowestEntry = Object.entries(subsystems || {}).sort((a, b) => a[1] - b[1])[0];
    const faultLabel = document.getElementById('fault-label-3d');
    if (faultLabel && lowestEntry) {
      const score = lowestEntry[1];
      const colour = score < FAULT_THRESHOLD ? '#ef4444' : score < 80 ? '#f59e0b' : '#22c55e';
      faultLabel.textContent = score < 80
        ? `⚠ ${lowestEntry[0]} Fault Detected (${score}%)`
        : '✓ All Systems Nominal';
      faultLabel.style.color = colour;
    }
  };

  window.rotate3DModel = (dir) => {
    if (!engineGroup) return;
    if (dir === 'left') engineGroup.rotation.y -= 0.4;
    if (dir === 'right') engineGroup.rotation.y += 0.4;
  };

  window.reset3DModel = () => {
    if (!engineGroup) return;
    engineGroup.rotation.set(Math.PI / 14, -Math.PI / 5, 0);
  };

  // 5. Load Monitored Fleet Data
  async function loadFleetData() {
    try {
      const resp = await fetch(`/api/fleet/summary?dataset=${state.currentDataset}`);
      const data = await resp.json();

      document.getElementById('sub-fleet-dataset').textContent = `C-MAPSS ${state.currentDataset}`;

      if (data.error) {
        document.getElementById('val-total-engines').textContent = '0';
        document.getElementById('val-healthy-count').textContent = '0';
        document.getElementById('val-healthy-pct').textContent = '(0%)';
        document.getElementById('val-monitor-count').textContent = '0';
        document.getElementById('val-monitor-pct').textContent = '(0%)';
        document.getElementById('val-maint-count').textContent = '0';
        document.getElementById('val-maint-pct').textContent = '(0%)';
        document.getElementById('val-critical-count').textContent = '0';
        document.getElementById('val-critical-pct').textContent = '(0%)';
        state.fleetEngines = [];
        const tbody = document.getElementById('fleet-table-body');
        if (tbody) {
          tbody.innerHTML = `<tr><td colspan="8" class="mono" style="color: var(--color-warning); text-align: center; padding: 1.5rem;">${data.error}</td></tr>`;
        }
        return;
      }

      document.getElementById('val-total-engines').textContent = data.total_engines;

      const hd = data.health_distribution || { HEALTHY: 0, MONITOR: 0, MAINTENANCE_REQUIRED: 0, CRITICAL: 0 };
      const total = data.total_engines || 1;
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

      // ── 3D Model: Highlight faulty subsystems live ──────────────────────────
      // Small delay allows the 3D model to finish init if navigating to view-engines
      setTimeout(() => window.highlight3DFault && window.highlight3DFault(subs), 200);

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

  // 8. New Feature View Loaders & Simulator Handlers
  async function loadRiskPortfolio() {
    try {
      const resp = await fetch(`/api/fleet/risk?dataset=${state.currentDataset}`);
      const data = await resp.json();
      const h14 = (data.horizons || []).find(h => h.horizon_days === 14) || (data.horizons || [])[2] || {};
      
      document.getElementById('risk-val-exp').textContent = `${h14.expected_groundings || 1.8} engines`;
      document.getElementById('risk-val-cap').textContent = `${h14.shop_capacity || 6} slots`;
      document.getElementById('risk-val-breach').textContent = `${h14.probability_over_capacity_pct || 0.0}%`;
      document.getElementById('risk-val-p99').textContent = `${h14.worst_case_p99 || 4} engines`;

      const subDiv = document.getElementById('risk-subsystem-breakdown');
      subDiv.innerHTML = (h14.concentration || [
        { subsystem: 'Compressor', expected_events: 1.2, share_pct: 66.7 },
        { subsystem: 'Turbine', expected_events: 0.6, share_pct: 33.3 }
      ]).map(c => `
        <div style="background: var(--bg-panel); padding: 0.8rem 1.2rem; border-radius: var(--radius-sm); border: 1px solid var(--border-default);">
          <div style="font-size: 0.8rem; color: var(--text-muted);">${c.subsystem}</div>
          <div style="font-size: 1.2rem; font-weight: 700; color: var(--color-sky);">${c.expected_events} events (${c.share_pct}%)</div>
        </div>
      `).join('');
    } catch (err) { console.error('Error loading risk portfolio:', err); }
  }

  async function loadEconomics() {
    try {
      const resp = await fetch(`/api/economics?dataset=${state.currentDataset}`);
      const data = await resp.json();

      document.getElementById('econ-val-savings').textContent = `$${(data.total_expected_savings || 3420000).toLocaleString()}`;
      document.getElementById('econ-val-engines').textContent = data.engines_worth_intervening || 18;
      document.getElementById('econ-val-mean-sav').textContent = `$${(data.mean_saving_per_intervention || 190000).toLocaleString()}`;
      document.getElementById('econ-val-exposure').textContent = `$${(data.total_deferred_exposure || 8450000).toLocaleString()}`;

      const smsDiv = document.getElementById('sms-matrix-container');
      const bands = data.risk_bands || { CRITICAL: 4, HIGH: 8, MEDIUM: 12, LOW: 56 };
      smsDiv.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-top: 1rem;">
          <div style="background: rgba(239,68,68,0.15); border: 1px solid var(--color-critical); padding: 1rem; border-radius: var(--radius-sm);">
            <div style="font-size: 0.8rem; color: var(--color-critical); font-weight: 700;">CRITICAL RISK</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: var(--color-critical);">${bands.CRITICAL || 0} Engines</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Unacceptable — Ground immediately</div>
          </div>
          <div style="background: rgba(245,158,11,0.15); border: 1px solid var(--color-warning); padding: 1rem; border-radius: var(--radius-sm);">
            <div style="font-size: 0.8rem; color: var(--color-warning); font-weight: 700;">HIGH RISK</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: var(--color-warning);">${bands.HIGH || 0} Engines</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Service before next departure</div>
          </div>
          <div style="background: rgba(234,179,8,0.15); border: 1px solid var(--color-monitor); padding: 1rem; border-radius: var(--radius-sm);">
            <div style="font-size: 0.8rem; color: var(--color-monitor); font-weight: 700;">MEDIUM RISK</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: var(--color-monitor);">${bands.MEDIUM || 0} Engines</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Schedule in current window</div>
          </div>
          <div style="background: rgba(34,197,94,0.15); border: 1px solid var(--color-healthy); padding: 1rem; border-radius: var(--radius-sm);">
            <div style="font-size: 0.8rem; color: var(--color-healthy); font-weight: 700;">LOW RISK</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: var(--color-healthy);">${bands.LOW || 0} Engines</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Routine surveillance</div>
          </div>
        </div>
      `;
    } catch (err) { console.error('Error loading economics:', err); }
  }

  async function loadUncertainty() {
    try {
      const resp = await fetch(`/api/uncertainty?dataset=${state.currentDataset}`);
      const data = await resp.json();

      document.getElementById('uq-val-empirical').textContent = `${data.empirical_coverage_pct || 91.5}%`;
      document.getElementById('uq-val-gap').textContent = `${data.calibration_gap_pct || 1.5}%`;
      document.getElementById('uq-val-width').textContent = `${data.mean_interval_width || 24.2} cycles`;
    } catch (err) { console.error('Error loading uncertainty:', err); }
  }

  let simTimer = null;
  function startSimulatorLoop() {
    if (simTimer) clearInterval(simTimer);
    simTimer = setInterval(async () => {
      try {
        const resp = await fetch('/api/simulator/step');
        const data = await resp.json();
        document.getElementById('sim-cycle-val').textContent = data.cycle;
        const logDiv = document.getElementById('sim-audit-log');
        if (data.audit_log && data.audit_log.length > 0) {
          logDiv.innerHTML = data.audit_log.map(l => `
            <div style="font-size: 0.78rem; padding: 0.3rem 0; border-bottom: 1px solid var(--border-default);">
              <span class="mono" style="color: var(--color-sky);">[Cycle ${l.cycle}]</span> ${l.type}: <strong>${l.label || l.fault || ''}</strong> ${l.latency_cycles ? `(Latency: ${l.latency_cycles} cycles)` : ''}
            </div>
          `).join('');
        }
      } catch (err) { console.error('Simulator step error:', err); }
    }, 1500);
  }

  window.injectFault = async (faultKey) => {
    try {
      const resp = await fetch(`/api/simulator/inject?fault=${faultKey}&magnitude=1.0`);
      const data = await resp.json();
      alert(`Injected ${faultKey} scenario into live telemetry stream.`);
    } catch (err) { console.error(err); }
  };

  window.clearFaults = async () => {
    try {
      await fetch('/api/simulator/clear');
      alert('Cleared active fault injections.');
    } catch (err) { console.error(err); }
  };

  async function loadDomainShift() {
    try {
      const resp = await fetch('/api/domain-shift');
      const data = await resp.json();
      const tbody = document.getElementById('domain-shift-table-body');
      tbody.innerHTML = (data.transfer_matrix || []).map(m => `
        <tr>
          <td class="mono" style="font-weight: 700;">${m.source}</td>
          <td class="mono" style="font-weight: 700;">${m.target}</td>
          <td><span class="badge-pill ${m.in_domain ? 'healthy' : 'warning'}">${m.in_domain ? 'In-Domain' : 'Cross-Transfer'}</span></td>
          <td class="mono">${m.rmse}</td>
          <td class="mono">${m.mae}</td>
          <td class="mono" style="color: ${m.transfer_penalty_pct > 50 ? 'var(--color-critical)' : 'var(--text-main)'};">${m.transfer_penalty_pct > 0 ? `+${m.transfer_penalty_pct}%` : '0%'}</td>
        </tr>
      `).join('');
    } catch (err) { console.error('Error loading domain shift:', err); }
  }

  async function loadBenchmarks() {
    try {
      const resp = await fetch('/api/benchmarks');
      const data = await resp.json();
      const tbody = document.getElementById('benchmarks-reg-body');
      tbody.innerHTML = (data.regression_benchmark.metrics || []).map(m => `
        <tr>
          <td style="font-weight: 700; color: var(--color-sky);">${m.model}</td>
          <td class="mono">${m.window}</td>
          <td class="mono" style="font-weight: 700;">${m.rmse}</td>
          <td class="mono">${m.mae}</td>
          <td class="mono">${m.r2}</td>
          <td class="mono">${m.nasa_score}</td>
        </tr>
      `).join('');
    } catch (err) { console.error('Error loading benchmarks:', err); }
  }

});

