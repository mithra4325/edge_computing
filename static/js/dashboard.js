/**
 * AegisEdge Industrial Vision & Safety Compliance Dashboard
 * WebSocket Telemetry, Real-time Charts, Controls & History Audit
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons
  if (window.lucide) {
    lucide.createIcons();
  }

  // State Management
  const state = {
    audioAlertEnabled: true,
    lastViolationSoundTime: 0,
    historyFilter: 'all',
    historyItems: [],
    isPaused: false,
    latencyData: [],
    chartLabels: [],
    maxChartPoints: 30
  };

  // DOM Elements
  const el = {
    runtimeClock: document.getElementById('runtime-clock'),
    latencyVal: document.getElementById('kpi-latency-val'),
    latencySub: document.getElementById('kpi-latency-sub'),
    fpsVal: document.getElementById('kpi-fps-val'),
    framesTotal: document.getElementById('kpi-frames-total'),
    compliancePill: document.getElementById('compliance-pill'),
    complianceStatusText: document.getElementById('compliance-status-text'),
    complianceReason: document.getElementById('compliance-reason'),
    passRate: document.getElementById('kpi-pass-rate'),
    passCount: document.getElementById('kpi-pass-count'),
    failCount: document.getElementById('kpi-fail-count'),
    currentTotal: document.getElementById('kpi-current-total'),
    cntHelmet: document.getElementById('kpi-cnt-helmet'),
    cntGloves: document.getElementById('kpi-cnt-gloves'),
    cntBareHand: document.getElementById('kpi-cnt-bare-hand'),
    cntHead: document.getElementById('kpi-cnt-head'),
    hudFps: document.getElementById('hud-fps'),
    hudLatency: document.getElementById('hud-latency'),
    hudRes: document.getElementById('hud-res'),
    sourceBadge: document.getElementById('source-badge'),
    sourceSelect: document.getElementById('source-select'),
    ruleSelect: document.getElementById('rule-select'),
    sizeSelect: document.getElementById('size-select'),
    confSlider: document.getElementById('conf-slider'),
    confValDisplay: document.getElementById('conf-val-display'),
    iouSlider: document.getElementById('iou-slider'),
    iouValDisplay: document.getElementById('iou-val-display'),
    pauseBtn: document.getElementById('pause-stream-btn'),
    pauseText: document.getElementById('pause-text'),
    pauseIcon: document.getElementById('pause-icon'),
    audioToggleBtn: document.getElementById('audio-toggle-btn'),
    audioLabel: document.getElementById('audio-label'),
    audioIcon: document.getElementById('audio-icon'),
    snapshotBtn: document.getElementById('snapshot-btn'),
    manualUploadBtn: document.getElementById('manual-upload-btn'),
    fileUploader: document.getElementById('file-uploader'),
    hwCpuVal: document.getElementById('hw-cpu-val'),
    hwCpuBar: document.getElementById('hw-cpu-bar'),
    hwRamVal: document.getElementById('hw-ram-val'),
    hwRamBar: document.getElementById('hw-ram-bar'),
    chartAvgLat: document.getElementById('chart-avg-lat'),
    chartTotalDet: document.getElementById('chart-total-det'),
    historyTableBody: document.getElementById('history-table-body'),
    filterAllCnt: document.getElementById('filter-all-cnt'),
    filterPassCnt: document.getElementById('filter-pass-cnt'),
    filterFailCnt: document.getElementById('filter-fail-cnt'),
    clearHistoryBtn: document.getElementById('clear-history-btn'),
    exportCsvBtn: document.getElementById('export-csv-btn'),
    // Modal
    modal: document.getElementById('snapshot-modal'),
    modalTitle: document.getElementById('modal-title'),
    modalBadge: document.getElementById('modal-badge'),
    modalImage: document.getElementById('modal-image'),
    modalDetailsTime: document.getElementById('modal-details-time'),
    modalDetailsCounts: document.getElementById('modal-details-counts'),
    modalDetailsLat: document.getElementById('modal-details-lat'),
    modalDownloadBtn: document.getElementById('modal-download-btn'),
    modalCloseX: document.getElementById('modal-close-x'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    // Raspberry Pi 5 GPIO Indicators
    kpiLampYellow: document.getElementById('kpi-lamp-yellow'),
    kpiLampGreen: document.getElementById('kpi-lamp-green'),
    kpiLampRed: document.getElementById('kpi-lamp-red'),
    kpiGpioStateText: document.getElementById('kpi-gpio-state-text'),
    gpioModePill: document.getElementById('gpio-mode-pill'),
    panelLampYellow: document.getElementById('panel-lamp-yellow'),
    panelLampGreen: document.getElementById('panel-lamp-green'),
    panelLampRed: document.getElementById('panel-lamp-red')
  };

  // Audio Alarm Synthesizer (Web Audio API)
  let audioCtx = null;
  function playIndustrialAlertTone() {
    if (!state.audioAlertEnabled) return;
    const now = Date.now();
    if (now - state.lastViolationSoundTime < 3500) return; // Debounce audio alert
    state.lastViolationSoundTime = now;

    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(880, audioCtx.currentTime); // High pitch alarm
      osc.frequency.setValueAtTime(587, audioCtx.currentTime + 0.15);
      osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.3);

      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.45);

      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.45);
    } catch (e) {
      console.warn("Audio alert failed:", e);
    }
  }

  // Initialize Real-time Charts
  let latencyChart = null;
  let distributionChart = null;

  function initCharts() {
    const latCtx = document.getElementById('latencyChart').getContext('2d');
    const grad = latCtx.createLinearGradient(0, 0, 0, 160);
    grad.addColorStop(0, 'rgba(0, 240, 255, 0.4)');
    grad.addColorStop(1, 'rgba(0, 240, 255, 0.0)');

    latencyChart = new Chart(latCtx, {
      type: 'line',
      data: {
        labels: Array(30).fill(''),
        datasets: [{
          label: 'Total Latency (ms)',
          data: Array(30).fill(0),
          borderColor: '#00f0ff',
          borderWidth: 2,
          backgroundColor: grad,
          fill: true,
          tension: 0.3,
          pointRadius: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true }
        },
        scales: {
          x: { display: false },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: {
              color: '#8a99ad',
              font: { family: 'JetBrains Mono', size: 10 }
            },
            suggestedMin: 0,
            suggestedMax: 120
          }
        }
      }
    });

    const distCtx = document.getElementById('distributionChart').getContext('2d');
    distributionChart = new Chart(distCtx, {
      type: 'doughnut',
      data: {
        labels: ['Helmet', 'Gloves', 'Bare Hand', 'Bare Head'],
        datasets: [{
          data: [1, 1, 1, 1],
          backgroundColor: ['#32d74b', '#00b0ff', '#ff9f0a', '#ff1744'],
          borderColor: 'transparent',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        animation: { duration: 500 },
        plugins: {
          legend: {
            position: 'right',
            labels: {
              boxWidth: 10,
              color: '#8a99ad',
              font: { family: 'Inter', size: 11 }
            }
          }
        }
      }
    });
  }

  // Telemetry Update Handler
  function updateTelemetryUI(data) {
    if (!data) return;

    // System Telemetry
    if (data.system) {
      el.runtimeClock.textContent = data.system.runtime_str || '00:00:00';
      el.fpsVal.textContent = (data.system.fps || 0).toFixed(1);
      el.hudFps.textContent = (data.system.fps || 0).toFixed(1);
      el.framesTotal.textContent = `Frames: ${data.system.total_frames || 0}`;

      if (data.system.source_mode === 'webcam') {
        el.sourceBadge.textContent = 'ARDUCAM / WEBCAM';
        el.sourceSelect.value = 'webcam';
      } else {
        el.sourceBadge.textContent = 'SIMULATED FACTORY';
        el.sourceSelect.value = 'simulation';
      }

      if (data.system.cpu_percent !== undefined) {
        const cpu = Math.round(data.system.cpu_percent);
        el.hwCpuVal.textContent = `${cpu}%`;
        el.hwCpuBar.style.width = `${cpu}%`;
      }
      if (data.system.ram_percent !== undefined) {
        const ram = Math.round(data.system.ram_percent);
        el.hwRamVal.textContent = `${ram}%`;
        el.hwRamBar.style.width = `${ram}%`;
      }
    }

    // Latency Telemetry
    if (data.latency) {
      const tot = (data.latency.total_ms || 0).toFixed(1);
      el.latencyVal.textContent = tot;
      el.hudLatency.textContent = `${tot} ms`;
      el.latencySub.innerHTML = `<span>Pre: ${(data.latency.preprocess_ms || 0).toFixed(1)}ms</span> &bull; <span>Inf: ${(data.latency.inference_ms || 0).toFixed(1)}ms</span> &bull; <span>Post: ${(data.latency.postprocess_ms || 0).toFixed(1)}ms</span>`;
      el.chartAvgLat.textContent = `AVG: ${(data.latency.avg_ms || 0).toFixed(1)}ms`;

      // Update Latency Chart
      if (latencyChart && data.latency.history) {
        const hist = data.latency.history.slice(-30);
        while (hist.length < 30) hist.unshift(0);
        latencyChart.data.datasets[0].data = hist;
        latencyChart.update('none');
      }
    }

    // Counts Telemetry
    if (data.counts) {
      const cur = data.counts.current || {};
      const cum = data.counts.cumulative || {};

      el.currentTotal.textContent = cur.total || 0;
      el.cntHelmet.textContent = cur.helmet || 0;
      el.cntGloves.textContent = cur.gloves || 0;
      if (el.cntBareHand) el.cntBareHand.textContent = cur.bare_hand || 0;
      el.cntHead.textContent = cur.head || 0;

      // Update Distribution Chart
      if (distributionChart) {
        const h = cum.helmet || 0;
        const g = cum.gloves || 0;
        const bh = cum.bare_hand || 0;
        const hd = cum.head || 0;
        const totalCum = h + g + bh + hd;
        el.chartTotalDet.textContent = `${totalCum} DETECTIONS`;

        if (totalCum > 0) {
          distributionChart.data.datasets[0].data = [h, g, bh, hd];
          distributionChart.update();
        }
      }
    }

    // Safety Compliance Status
    if (data.compliance) {
      const comp = data.compliance;
      const status = comp.status || 'IDLE';

      el.complianceStatusText.textContent = status === 'FAIL' ? 'SAFETY VIOLATION' : (status === 'PASS' ? 'COMPLIANT' : 'SCANNING');
      el.complianceReason.textContent = comp.reason || 'Monitoring inspection area';
      el.compliancePill.className = `compliance-pill ${status.toLowerCase()}`;

      el.passRate.textContent = `${(comp.pass_rate_percent || 100).toFixed(1)}%`;
      el.passCount.textContent = comp.pass_count || 0;
      el.failCount.textContent = comp.fail_count || 0;

      if (status === 'FAIL') {
        playIndustrialAlertTone();
      }
    }

    // Thresholds Display
    if (data.thresholds) {
      if (data.thresholds.inference_size) {
        el.hudRes.textContent = `${data.thresholds.inference_size}x${data.thresholds.inference_size}`;
        el.sizeSelect.value = String(data.thresholds.inference_size);
      }
      if (data.thresholds.rule_mode) {
        el.ruleSelect.value = data.thresholds.rule_mode;
      }
    }

    // Raspberry Pi 5 GPIO Stack Lights Telemetry
    if (data.gpio) {
      const g = data.gpio;
      const isYellow = !!(g.yellow && g.yellow.active);
      const isGreen = !!(g.green && g.green.active);
      const isRed = !!(g.red && g.red.active);

      // Mini lamps in KPI row
      if (el.kpiLampYellow) el.kpiLampYellow.classList.toggle('active', isYellow);
      if (el.kpiLampGreen) el.kpiLampGreen.classList.toggle('active', isGreen);
      if (el.kpiLampRed) el.kpiLampRed.classList.toggle('active', isRed);

      // Large lamps in Sidebar Panel
      if (el.panelLampYellow) el.panelLampYellow.classList.toggle('active', isYellow);
      if (el.panelLampGreen) el.panelLampGreen.classList.toggle('active', isGreen);
      if (el.panelLampRed) el.panelLampRed.classList.toggle('active', isRed);

      // Status text
      if (el.kpiGpioStateText) {
        el.kpiGpioStateText.textContent = g.active_label || 'ALL LEDS OFF';
        if (isRed) {
          el.kpiGpioStateText.style.color = '#ff1744';
        } else if (isGreen) {
          el.kpiGpioStateText.style.color = '#00e676';
        } else if (isYellow) {
          el.kpiGpioStateText.style.color = '#ffd600';
        } else {
          el.kpiGpioStateText.style.color = 'var(--text-muted)';
        }
      }

      // Mode pill badge
      if (el.gpioModePill) {
        el.gpioModePill.textContent = g.is_hardware ? 'PI 5 HARDWARE' : 'SIMULATED GPIO';
        el.gpioModePill.className = g.is_hardware ? 'badge-tag pass' : 'badge-tag clear';
      }
    }
  }

  // WebSocket Connection Setup
  let socket = null;
  function connectWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws/telemetry`;

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('[Dashboard] WebSocket connected.');
    };

    socket.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        updateTelemetryUI(data);
      } catch (err) {
        console.error('[Dashboard] Telemetry parse error:', err);
      }
    };

    socket.onclose = () => {
      console.log('[Dashboard] WebSocket disconnected. Reconnecting in 2s...');
      setTimeout(connectWebSocket, 2000);
    };

    socket.onerror = (e) => {
      console.warn('[Dashboard] WebSocket error:', e);
      socket.close();
    };
  }

  // Fallback Polling
  function fetchPollingFallback() {
    fetch('/api/telemetry')
      .then(res => res.json())
      .then(data => updateTelemetryUI(data))
      .catch(e => console.warn('Telemetry poll error', e));
  }

  // Fetch Inspection History
  async function fetchHistory() {
    try {
      const res = await fetch('/api/history?limit=20');
      const items = await res.json();
      state.historyItems = items;
      renderHistoryTable();
    } catch (e) {
      console.warn('History fetch error:', e);
    }
  }

  function renderHistoryTable() {
    if (!el.historyTableBody) return;

    const filtered = state.historyItems.filter(item => {
      if (state.historyFilter === 'all') return true;
      return item.verdict === state.historyFilter;
    });

    // Update filter counts
    el.filterAllCnt.textContent = state.historyItems.length;
    el.filterPassCnt.textContent = state.historyItems.filter(i => i.verdict === 'PASS').length;
    el.filterFailCnt.textContent = state.historyItems.filter(i => i.verdict === 'FAIL').length;

    if (filtered.length === 0) {
      el.historyTableBody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; color: var(--text-dim); padding: 24px;">
            No ${state.historyFilter === 'all' ? '' : state.historyFilter} inspection events recorded yet.
          </td>
        </tr>
      `;
      return;
    }

    el.historyTableBody.innerHTML = filtered.map(item => {
      const verdictClass = item.verdict.toLowerCase();
      const countsStr = `H: ${item.counts?.helmet || 0} | G: ${item.counts?.gloves || 0} | BH: ${item.counts?.bare_hand || 0} | HD: ${item.counts?.head || 0}`;

      return `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-cyan);">${item.id}</td>
          <td style="font-family: var(--font-mono); color: var(--text-muted);">${item.timestamp}</td>
          <td>
            <img src="${item.thumbnail}" alt="Thumbnail" class="history-thumb" onclick="openSnapshotModal('${item.id}')">
          </td>
          <td>
            <span class="badge-tag ${verdictClass}">${item.verdict}</span>
          </td>
          <td style="font-family: var(--font-mono); font-size: 11px;">${countsStr}</td>
          <td style="font-family: var(--font-mono);">${item.confidence}%</td>
          <td style="font-family: var(--font-mono); color: var(--accent-cyan);">${item.latency_ms} ms</td>
          <td style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.reason}">
            ${item.reason}
          </td>
          <td>
            <button class="btn" style="padding: 3px 8px; font-size: 11px;" onclick="openSnapshotModal('${item.id}')">
              <i data-lucide="eye" style="width: 12px; height: 12px;"></i> VIEW
            </button>
          </td>
        </tr>
      `;
    }).join('');

    if (window.lucide) lucide.createIcons();
  }

  // Global window modal opener
  window.openSnapshotModal = function(id) {
    const item = state.historyItems.find(i => i.id === id);
    if (!item) return;

    el.modalTitle.textContent = `INSPECTION AUDIT EVENT ${item.id}`;
    el.modalBadge.textContent = item.verdict;
    el.modalBadge.className = `badge-tag ${item.verdict.toLowerCase()}`;
    el.modalImage.src = item.thumbnail;
    el.modalDetailsTime.textContent = `TIMESTAMP: ${item.full_timestamp || item.timestamp}`;
    el.modalDetailsCounts.textContent = `COUNTS: H:${item.counts?.helmet||0} G:${item.counts?.gloves||0} BH:${item.counts?.bare_hand||0} HD:${item.counts?.head||0}`;
    el.modalDetailsLat.textContent = `LATENCY: ${item.latency_ms} ms | CONF: ${item.confidence}%`;
    el.modalDownloadBtn.href = item.thumbnail;
    el.modalDownloadBtn.download = `${item.id}_snapshot.jpg`;

    el.modal.classList.add('open');
  };

  // Close modal handlers
  function closeModal() {
    el.modal.classList.remove('open');
  }
  el.modalCloseX.addEventListener('click', closeModal);
  el.modalCloseBtn.addEventListener('click', closeModal);
  el.modal.addEventListener('click', (e) => {
    if (e.target === el.modal) closeModal();
  });

  // Filter Buttons
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.historyFilter = btn.dataset.filter;
      renderHistoryTable();
    });
  });

  // Threshold Sliders Handlers
  el.confSlider.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    el.confValDisplay.textContent = `${Math.round(val * 100)}% (${val.toFixed(2)})`;
  });

  el.confSlider.addEventListener('change', async (e) => {
    const val = parseFloat(e.target.value);
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confidence: val })
    });
  });

  el.iouSlider.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    el.iouValDisplay.textContent = `${Math.round(val * 100)}% (${val.toFixed(2)})`;
  });

  el.iouSlider.addEventListener('change', async (e) => {
    const val = parseFloat(e.target.value);
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ iou: val })
    });
  });

  // Source Selector
  el.sourceSelect.addEventListener('change', async (e) => {
    const src = e.target.value;
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_mode: src })
    });
  });

  // Safety Rule Selector
  el.ruleSelect.addEventListener('change', async (e) => {
    const rule = e.target.value;
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rule_mode: rule })
    });
  });

  // Inference Size Selector
  el.sizeSelect.addEventListener('change', async (e) => {
    const size = parseInt(e.target.value, 10);
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inference_size: size })
    });
  });

  // Pause / Resume Stream
  el.pauseBtn.addEventListener('click', async () => {
    state.isPaused = !state.isPaused;
    el.pauseText.textContent = state.isPaused ? 'RESUME' : 'PAUSE';
    el.pauseBtn.style.color = state.isPaused ? 'var(--accent-warn)' : 'var(--text-main)';

    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_paused: state.isPaused })
    });
  });

  // Audio Toggle
  el.audioToggleBtn.addEventListener('click', () => {
    state.audioAlertEnabled = !state.audioAlertEnabled;
    el.audioLabel.textContent = state.audioAlertEnabled ? 'ALARM ON' : 'ALARM MUTED';
    el.audioToggleBtn.style.opacity = state.audioAlertEnabled ? '1.0' : '0.6';
  });

  // Snapshot Capture
  el.snapshotBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/snapshot', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        const a = document.createElement('a');
        a.href = data.image;
        a.download = data.filename;
        a.click();
        await fetchHistory();
      }
    } catch (e) {
      alert('Snapshot failed: ' + e);
    }
  });

  // Upload Custom Test Image
  el.manualUploadBtn.addEventListener('click', () => {
    el.fileUploader.click();
  });

  el.fileUploader.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/test_upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success') {
        // Display modal with test results
        el.modalTitle.textContent = `UPLOAD INSPECTION RESULT: ${file.name}`;
        el.modalBadge.textContent = data.verdict;
        el.modalBadge.className = `badge-tag ${data.verdict.toLowerCase()}`;
        el.modalImage.src = data.annotated_image;
        el.modalDetailsTime.textContent = `STATUS: ${data.reason}`;
        el.modalDetailsCounts.textContent = `COUNTS: H:${data.counts.helmet} G:${data.counts.gloves} HD:${data.counts.head}`;
        el.modalDetailsLat.textContent = `LATENCY: ${data.latency_ms} ms`;
        el.modalDownloadBtn.href = data.annotated_image;
        el.modalDownloadBtn.download = `tested_${file.name}`;
        el.modal.classList.add('open');

        await fetchHistory();
      }
    } catch (err) {
      alert('Test image upload failed: ' + err);
    }
    el.fileUploader.value = '';
  });

  // Clear History
  el.clearHistoryBtn.addEventListener('click', async () => {
    if (confirm('Are you sure you want to reset inspection history and stats?')) {
      await fetch('/api/history/clear', { method: 'POST' });
      await fetchHistory();
    }
  });

  // Export CSV Audit Log
  el.exportCsvBtn.addEventListener('click', () => {
    if (!state.historyItems || state.historyItems.length === 0) {
      alert('No inspection records to export.');
      return;
    }

    const headers = ['Event ID', 'Timestamp', 'Verdict', 'Helmets', 'Gloves', 'Bare Hands', 'Bare Heads', 'Confidence (%)', 'Latency (ms)', 'Remarks'];
    const rows = state.historyItems.map(i => [
      i.id,
      i.full_timestamp || i.timestamp,
      i.verdict,
      i.counts?.helmet || 0,
      i.counts?.gloves || 0,
      i.counts?.bare_hand || 0,
      i.counts?.head || 0,
      i.confidence,
      i.latency_ms,
      `"${(i.reason || '').replace(/"/g, '""')}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `edge_inspection_audit_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  // Periodic Tasks
  initCharts();
  connectWebSocket();
  fetchHistory();
  setInterval(fetchHistory, 2500);
});
