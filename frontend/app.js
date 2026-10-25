/**
 * Smart QR Student Attendance & Library Entry System - Master JavaScript Controller
 * Handles client-side webcam streaming, real-time QR decoding with jsQR,
 * Web Audio API synthesized chimes, REST API communication, dynamic tables & export.
 */

class SmartQRApp {
  constructor() {
    this.apiBase = window.location.origin;
    this.video = document.getElementById('webcam');
    this.canvas = document.getElementById('qr-canvas');
    this.ctx = this.canvas ? this.canvas.getContext('2d', { willReadFrequently: true }) : null;
    
    this.isCameraRunning = false;
    this.mediaStream = null;
    this.currentFacingMode = 'environment';
    this.soundEnabled = true;
    
    // Scan cooldown dictionary: roll_no -> last_scanned_timestamp (ms)
    this.cooldowns = new Map();
    this.cooldownMs = 3500;
    
    // Audio Context for synthetic sound chimes
    this.audioCtx = null;
    
    this.init();
  }

  async init() {
    this.setupNavigation();
    this.setupCameraControls();
    this.setupFileDropzone();
    this.setupRegistrationForm();
    this.setupDashboardFilters();
    this.setupExportButtons();

    // Set today's date in filter input
    const today = new Date().toISOString().split('T')[0];
    const dateInput = document.getElementById('filter-date');
    if (dateInput) {
      dateInput.value = today;
    }

    // Initial data load
    await this.refreshKPIs();
    await this.loadStudentsDirectory();
    await this.loadAttendanceLogs();
    await this.loadLibraryLogs();
    this.loadDemoChips();

    // Auto-start camera if on scanner tab
    this.startCamera();
  }

  // =========================================================================
  // 1. Navigation & Tab Switching
  // =========================================================================
  setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        const targetTab = item.getAttribute('data-tab');
        
        // Update active class on nav
        navItems.forEach(n => n.classList.remove('active'));
        item.classList.add('active');

        // Switch active tab pane
        document.querySelectorAll('.tab-pane').forEach(pane => {
          pane.classList.remove('active');
        });
        const targetPane = document.getElementById(targetTab);
        if (targetPane) targetPane.classList.add('active');

        // Control camera lifecycle
        if (targetTab === 'tab-scanner') {
          if (!this.isCameraRunning) this.startCamera();
        } else {
          // Pause camera frame loop when away to save CPU
          if (this.isCameraRunning) this.stopCamera();
        }

        // Refresh views on tab change
        if (targetTab === 'tab-dashboard') this.loadAttendanceLogs();
        if (targetTab === 'tab-library') this.loadLibraryLogs();
        if (targetTab === 'tab-registration') this.loadStudentsDirectory();
      });
    });

    // Subtabs in Dashboard: Logs vs Roster
    const btnLogs = document.getElementById('subtab-btn-logs');
    const btnRoster = document.getElementById('subtab-btn-roster');
    const viewLogs = document.getElementById('subtab-view-logs');
    const viewRoster = document.getElementById('subtab-view-roster');

    if (btnLogs && btnRoster) {
      btnLogs.addEventListener('click', () => {
        btnLogs.classList.add('active');
        btnRoster.classList.remove('active');
        viewLogs.style.display = 'block';
        viewRoster.style.display = 'none';
      });

      btnRoster.addEventListener('click', () => {
        btnRoster.classList.add('active');
        btnLogs.classList.remove('active');
        viewLogs.style.display = 'none';
        viewRoster.style.display = 'block';
        this.loadRoster();
      });
    }
  }

  // =========================================================================
  // 2. Web Audio API Chimes (No External Audio Files Needed)
  // =========================================================================
  playSound(type = 'success') {
    if (!this.soundEnabled) return;
    try {
      if (!this.audioCtx) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        this.audioCtx = new AudioContextClass();
      }
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }

      const now = this.audioCtx.currentTime;
      if (type === 'success') {
        // High melodious chime (A5 -> D6)
        [880, 1174.66].forEach((freq, idx) => {
          const osc = this.audioCtx.createOscillator();
          const gain = this.audioCtx.createGain();
          osc.type = 'sine';
          osc.frequency.setValueAtTime(freq, now + idx * 0.1);
          gain.gain.setValueAtTime(0.18, now + idx * 0.1);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.1 + 0.18);
          osc.connect(gain);
          gain.connect(this.audioCtx.destination);
          osc.start(now + idx * 0.1);
          osc.stop(now + idx * 0.1 + 0.2);
        });
      } else if (type === 'warning') {
        // Amber warning tone (D5 -> A4)
        [587.33, 440].forEach((freq, idx) => {
          const osc = this.audioCtx.createOscillator();
          const gain = this.audioCtx.createGain();
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(freq, now + idx * 0.12);
          gain.gain.setValueAtTime(0.2, now + idx * 0.12);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.12 + 0.22);
          osc.connect(gain);
          gain.connect(this.audioCtx.destination);
          osc.start(now + idx * 0.12);
          osc.stop(now + idx * 0.12 + 0.25);
        });
      } else {
        // Low error buzz
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(150, now);
        gain.gain.setValueAtTime(0.25, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
        osc.connect(gain);
        gain.connect(this.audioCtx.destination);
        osc.start(now);
        osc.stop(now + 0.32);
      }
    } catch (e) {
      console.warn("Audio playback not supported or blocked by browser policy:", e);
    }
  }

  // =========================================================================
  // 3. Real-Time Webcam Streaming & QR Decoding (jsQR)
  // =========================================================================
  setupCameraControls() {
    const btnToggle = document.getElementById('btn-toggle-camera');
    const btnSwitch = document.getElementById('btn-switch-camera');
    const btnSound = document.getElementById('btn-sound-toggle');

    if (btnToggle) {
      btnToggle.addEventListener('click', () => {
        if (this.isCameraRunning) {
          this.stopCamera();
          btnToggle.innerHTML = `<span>📷</span> Start Camera`;
          btnToggle.classList.remove('btn-primary');
          btnToggle.classList.add('btn-secondary');
        } else {
          this.startCamera();
          btnToggle.innerHTML = `<span>📷</span> Stop Camera`;
          btnToggle.classList.add('btn-primary');
          btnToggle.classList.remove('btn-secondary');
        }
      });
    }

    if (btnSwitch) {
      btnSwitch.addEventListener('click', () => {
        this.currentFacingMode = this.currentFacingMode === 'environment' ? 'user' : 'environment';
        if (this.isCameraRunning) {
          this.stopCamera();
          this.startCamera();
        }
      });
    }

    if (btnSound) {
      btnSound.addEventListener('click', () => {
        this.soundEnabled = !this.soundEnabled;
        btnSound.innerHTML = this.soundEnabled ? `<span>🔊</span> Sound: On` : `<span>🔇</span> Sound: Off`;
      });
    }
  }

  async startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      this.renderHUD({
        status_code: 'ERROR',
        message: 'Camera API (getUserMedia) not supported in this browser. Use the image upload option below.'
      });
      return;
    }

    try {
      const constraints = {
        video: {
          facingMode: this.currentFacingMode,
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      };

      this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      this.video.srcObject = this.mediaStream;
      this.video.setAttribute('playsinline', true);
      await this.video.play();
      this.isCameraRunning = true;
      requestAnimationFrame(this.scanFrame.bind(this));
    } catch (err) {
      console.warn("Camera start failed:", err);
      this.isCameraRunning = false;
      const btnToggle = document.getElementById('btn-toggle-camera');
      if (btnToggle) btnToggle.innerHTML = `<span>📷</span> Start Camera`;
    }
  }

  stopCamera() {
    this.isCameraRunning = false;
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }
  }

  scanFrame() {
    if (!this.isCameraRunning) return;

    if (this.video.readyState === this.video.HAVE_ENOUGH_DATA) {
      this.canvas.height = this.video.videoHeight;
      this.canvas.width = this.video.videoWidth;
      this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

      const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);

      // Decode with jsQR
      if (typeof jsQR !== 'undefined') {
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
          inversionAttempts: "dontInvert",
        });

        if (code && code.data && code.data.trim()) {
          const payload = code.data.trim().toUpperCase();
          this.handleDetectedCode(payload);
        }
      }
    }

    requestAnimationFrame(this.scanFrame.bind(this));
  }

  handleDetectedCode(payload) {
    const now = Date.now();
    const lastScan = this.cooldowns.get(payload) || 0;

    // Enforce 3.5s cooldown per roll number to prevent multi-frame spam
    if (now - lastScan > this.cooldownMs) {
      this.cooldowns.set(payload, now);
      const entryTypeSelect = document.getElementById('scan-entry-type');
      const entryType = entryTypeSelect ? entryTypeSelect.value : 'Classroom Attendance';
      this.processScan(payload, entryType);
    }
  }

  // =========================================================================
  // 4. File Drag & Drop QR Scanner
  // =========================================================================
  setupFileDropzone() {
    const dropzone = document.getElementById('qr-dropzone');
    const fileInput = document.getElementById('qr-file-input');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length) {
        this.processUploadedImage(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) {
        this.processUploadedImage(fileInput.files[0]);
      }
    });
  }

  async processUploadedImage(file) {
    const reader = new FileReader();
    reader.onload = async (e) => {
      const img = new Image();
      img.onload = async () => {
        // Draw to offscreen canvas to decode via jsQR
        const oc = document.createElement('canvas');
        oc.width = img.width;
        oc.height = img.height;
        const octx = oc.getContext('2d');
        octx.drawImage(img, 0, 0);
        const imgData = octx.getImageData(0, 0, oc.width, oc.height);

        let decodedPayload = null;
        if (typeof jsQR !== 'undefined') {
          const code = jsQR(imgData.data, imgData.width, imgData.height);
          if (code && code.data) decodedPayload = code.data.trim().toUpperCase();
        }

        // Fallback to server OpenCV decoder if client-side jsQR didn't find it
        if (!decodedPayload) {
          const formData = new FormData();
          formData.append('file', file);
          try {
            const res = await fetch(`${this.apiBase}/api/attendance/decode-image`, {
              method: 'POST',
              body: formData
            });
            const data = await res.json();
            if (data.success && data.payload) {
              decodedPayload = data.payload;
            }
          } catch (err) {
            console.error("Server decode error:", err);
          }
        }

        if (decodedPayload) {
          const entryType = document.getElementById('scan-entry-type').value;
          this.processScan(decodedPayload, entryType);
        } else {
          this.playSound('error');
          this.renderHUD({
            status_code: 'ERROR',
            message: 'No valid QR code finder patterns detected in this file.'
          });
        }
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  // =========================================================================
  // 5. Backend Scan Submission & HUD Render
  // =========================================================================
  async processScan(rollNo, entryType = 'Classroom Attendance') {
    try {
      const res = await fetch(`${this.apiBase}/api/attendance/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roll_no: rollNo, entry_type: entryType })
      });
      const data = await res.json();

      if (data.status_code === 'LOGGED_SUCCESS') {
        this.playSound('success');
      } else if (data.status_code === 'ALREADY_LOGGED') {
        this.playSound('warning');
      } else {
        this.playSound('error');
      }

      this.renderHUD(data);
      this.refreshKPIs();
      this.loadAttendanceLogs();
      this.loadLibraryLogs();
    } catch (err) {
      console.error("Scan processing error:", err);
      this.renderHUD({
        status_code: 'ERROR',
        message: 'Network error connecting to attendance server.'
      });
    }
  }

  renderHUD(data) {
    const hud = document.getElementById('hud-display');
    if (!hud) return;

    if (data.status_code === 'LOGGED_SUCCESS') {
      const std = data.student;
      hud.innerHTML = `
        <div class="hud-result-box hud-success">
          <span class="hud-badge badge-success">✓ Marked Present</span>
          <h3 class="hud-student-name">${std.full_name}</h3>
          <div class="hud-student-roll">${std.roll_no}</div>
          <div class="hud-meta-grid">
            <span><b>Department:</b> ${std.branch}</span>
            <span><b>Semester:</b> ${std.semester}</span>
            <span><b>Timestamp:</b> ${data.scan_time}</span>
            <span><b>Session:</b> ${data.entry_type}</span>
          </div>
        </div>
      `;
    } else if (data.status_code === 'ALREADY_LOGGED') {
      const std = data.student;
      hud.innerHTML = `
        <div class="hud-result-box hud-warning">
          <span class="hud-badge badge-warning">⚠️ Already Logged Today</span>
          <h3 class="hud-student-name">${std ? std.full_name : data.roll_no}</h3>
          <div class="hud-student-roll">${data.roll_no || (std && std.roll_no)}</div>
          <p style="font-size: 13px; color: #fde68a; margin: 10px 0 14px 0;">
            ${data.message}
          </p>
          <div class="hud-meta-grid">
            <span><b>Original Check-in:</b> ${data.scan_time}</span>
            <span><b>Date:</b> ${data.scan_date}</span>
          </div>
        </div>
      `;
    } else {
      hud.innerHTML = `
        <div class="hud-result-box hud-error">
          <span class="hud-badge badge-error">❌ Unregistered QR</span>
          <h3 class="hud-student-name">Unrecognized Student ID</h3>
          <p style="font-size: 13px; color: #fca5a5; margin-top: 8px;">
            ${data.message || 'Payload does not exist in master student database.'}
          </p>
        </div>
      `;
    }
  }

  // =========================================================================
  // 6. One-Click Demo Chips (Viva Simulation)
  // =========================================================================
  async loadDemoChips() {
    const container = document.getElementById('demo-student-chips');
    if (!container) return;

    try {
      const res = await fetch(`${this.apiBase}/api/students`);
      const data = await res.json();
      const students = data.students || [];

      if (!students.length) {
        container.innerHTML = `<span style="font-size: 12px; color: var(--text-dim);">No students loaded. Seed sample students in registration tab.</span>`;
        return;
      }

      container.innerHTML = students.slice(0, 5).map(s => `
        <button class="btn btn-secondary btn-sm demo-chip-btn" data-roll="${s.roll_no}">
          ⚡ Scan ${s.roll_no} (${s.full_name.split(' ')[0]})
        </button>
      `).join('');

      container.querySelectorAll('.demo-chip-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const roll = btn.getAttribute('data-roll');
          const entryType = document.getElementById('scan-entry-type').value;
          this.processScan(roll, entryType);
        });
      });
    } catch (err) {
      console.warn("Could not load demo chips:", err);
    }
  }

  // =========================================================================
  // 7. Student Registration & ID Cards
  // =========================================================================
  setupRegistrationForm() {
    const form = document.getElementById('form-register-student');
    const btnSeed = document.getElementById('btn-seed-sample');

    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const roll = document.getElementById('reg-roll').value.trim().toUpperCase();
        const name = document.getElementById('reg-name').value.trim();
        const branch = document.getElementById('reg-branch').value;
        const sem = document.getElementById('reg-sem').value;

        if (!roll || !name) return;

        try {
          const res = await fetch(`${this.apiBase}/api/students`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roll_no: roll, full_name: name, branch, semester: sem })
          });
          const data = await res.json();

          if (res.ok && data.success) {
            // Render ID Pass Preview with base64 data URI for instant rendering
            const imgSrc = data.card_base64 || data.card_url;
            const preview = document.getElementById('id-pass-preview');
            preview.innerHTML = `
              <div class="id-pass-card" style="max-width: 420px; margin: 0 auto;">
                <img src="${imgSrc}" alt="ID Pass">
                <div class="id-pass-actions">
                  <span style="font-size: 12px; color: #fff; font-weight: 600;">${roll}</span>
                  <a href="${imgSrc}" download="${roll}_id_card.png" class="btn btn-primary btn-sm">
                    📥 Download Pass
                  </a>
                </div>
              </div>
            `;
            form.reset();
            this.loadStudentsDirectory();
            this.loadDemoChips();
            this.refreshKPIs();
          } else {
            alert(`Registration Error: ${data.detail || data.message}`);
          }
        } catch (err) {
          alert(`Network error registering student: ${err.message}`);
        }
      });
    }

    if (btnSeed) {
      btnSeed.addEventListener('click', async () => {
        btnSeed.disabled = true;
        btnSeed.textContent = "Seeding students...";
        try {
          const res = await fetch(`${this.apiBase}/api/students/seed`, { method: 'POST' });
          const data = await res.json();
          if (data.success) {
            await this.loadStudentsDirectory();
            await this.loadDemoChips();
            await this.refreshKPIs();
          }
        } catch (err) {
          console.error("Seed error:", err);
        } finally {
          btnSeed.disabled = false;
          btnSeed.innerHTML = `<span>➕</span> Seed 6 Sample Students`;
        }
      });
    }

    // Student Search Input
    const searchInput = document.getElementById('search-student-input');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const cards = document.querySelectorAll('.student-card-item');
        cards.forEach(card => {
          const text = card.textContent.toLowerCase();
          card.style.display = text.includes(query) ? 'block' : 'none';
        });
      });
    }
  }

  async loadStudentsDirectory() {
    const grid = document.getElementById('student-cards-grid');
    const countBadge = document.getElementById('students-count-badge');
    if (!grid) return;

    try {
      const res = await fetch(`${this.apiBase}/api/students`);
      const data = await res.json();
      const students = data.students || [];

      if (countBadge) countBadge.textContent = students.length;

      if (!students.length) {
        grid.innerHTML = `<p style="grid-column: 1 / -1; color: var(--text-dim); text-align: center; padding: 30px;">No students enrolled yet. Seed sample records or register a student above.</p>`;
        return;
      }

      grid.innerHTML = students.map(s => `
        <div class="id-pass-card student-card-item">
          <img src="/api/students/${s.roll_no}/card" onerror="this.onerror=null; this.src='/static/id_cards/${s.roll_no}_card.png'" alt="${s.roll_no}">
          <div class="id-pass-actions">
            <div>
              <div style="font-size: 13px; font-weight: 700; color: #fff;">${s.full_name}</div>
              <div style="font-size: 11px; color: var(--accent-cyan); font-family: var(--font-mono);">${s.roll_no}</div>
            </div>
            <div style="display: flex; gap: 6px;">
              <a href="/api/students/${s.roll_no}/card" download="${s.roll_no}_pass.png" class="btn btn-secondary btn-sm" title="Download ID Pass">
                📥
              </a>
              <button class="btn btn-danger btn-sm btn-delete-student" data-roll="${s.roll_no}" title="Delete Student">
                🗑️
              </button>
            </div>
          </div>
        </div>
      `).join('');

      // Attach delete handlers
      grid.querySelectorAll('.btn-delete-student').forEach(btn => {
        btn.addEventListener('click', async () => {
          const roll = btn.getAttribute('data-roll');
          if (confirm(`Are you sure you want to delete student ${roll}?`)) {
            await fetch(`${this.apiBase}/api/students/${roll}`, { method: 'DELETE' });
            this.loadStudentsDirectory();
            this.loadDemoChips();
            this.refreshKPIs();
          }
        });
      });
    } catch (err) {
      console.error("Directory fetch error:", err);
    }
  }

  // =========================================================================
  // 8. Attendance Logs & Analytics Dashboard
  // =========================================================================
  setupDashboardFilters() {
    const dateInput = document.getElementById('filter-date');
    const branchSelect = document.getElementById('filter-branch');
    const semSelect = document.getElementById('filter-sem');
    const typeSelect = document.getElementById('filter-type');

    [dateInput, branchSelect, semSelect, typeSelect].forEach(el => {
      if (el) el.addEventListener('change', () => this.loadAttendanceLogs());
    });
  }

  async loadAttendanceLogs() {
    const tbody = document.getElementById('attendance-tbody');
    if (!tbody) return;

    const dateVal = document.getElementById('filter-date')?.value || '';
    const branchVal = document.getElementById('filter-branch')?.value || 'All Branches';
    const semVal = document.getElementById('filter-sem')?.value || 'All Semesters';
    const typeVal = document.getElementById('filter-type')?.value || 'All Entry Types';

    let url = `${this.apiBase}/api/attendance/logs?`;
    if (dateVal) url += `date=${encodeURIComponent(dateVal)}&`;
    if (branchVal !== 'All Branches') url += `branch=${encodeURIComponent(branchVal)}&`;
    if (semVal !== 'All Semesters') url += `semester=${encodeURIComponent(semVal)}&`;
    if (typeVal !== 'All Entry Types') url += `entry_type=${encodeURIComponent(typeVal)}&`;

    try {
      const res = await fetch(url);
      const data = await res.json();
      const logs = data.logs || [];

      if (!logs.length) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 25px;">No attendance logs match the active filter criteria.</td></tr>`;
        return;
      }

      tbody.innerHTML = logs.map(l => `
        <tr>
          <td><span style="font-family: var(--font-mono); color: var(--text-dim);">#${l.log_id}</span></td>
          <td><b style="font-family: var(--font-mono); color: var(--accent-cyan);">${l.roll_no}</b></td>
          <td><b>${l.full_name}</b></td>
          <td>${l.branch}</td>
          <td>${l.semester}</td>
          <td>${l.scan_date}</td>
          <td>${l.check_in_time}</td>
          <td><span class="badge-pill pill-present">${l.status}</span></td>
          <td><span style="font-size: 12px; color: var(--text-muted);">${l.entry_type}</span></td>
        </tr>
      `).join('');
    } catch (err) {
      console.error("Attendance logs error:", err);
    }
  }

  async loadRoster() {
    const dateVal = document.getElementById('filter-date')?.value || '';
    const pList = document.getElementById('roster-present-list');
    const aList = document.getElementById('roster-absent-list');
    const pCount = document.getElementById('roster-present-count');
    const aCount = document.getElementById('roster-absent-count');

    if (!pList || !aList) return;

    try {
      const res = await fetch(`${this.apiBase}/api/attendance/summary?date=${encodeURIComponent(dateVal)}`);
      const data = await res.json();

      const present = data.present_students || [];
      const absent = data.absent_students || [];

      if (pCount) pCount.textContent = present.length;
      if (aCount) aCount.textContent = absent.length;

      pList.innerHTML = present.length ? present.map(s => `
        <div style="background: rgba(255,255,255,0.03); padding: 10px 14px; border-radius: var(--radius-sm); display: flex; justify-content: space-between;">
          <span><b>${s.full_name}</b> (${s.branch})</span>
          <span style="font-family: var(--font-mono); color: var(--accent-emerald);">${s.roll_no}</span>
        </div>
      `).join('') : `<p style="color: var(--text-dim); font-size: 13px;">No present students logged for this date.</p>`;

      aList.innerHTML = absent.length ? absent.map(s => `
        <div style="background: rgba(255,255,255,0.03); padding: 10px 14px; border-radius: var(--radius-sm); display: flex; justify-content: space-between;">
          <span><b>${s.full_name}</b> (${s.branch})</span>
          <span style="font-family: var(--font-mono); color: var(--accent-rose);">${s.roll_no}</span>
        </div>
      `).join('') : `<p style="color: var(--accent-emerald); font-size: 13px;">All registered students are present!</p>`;
    } catch (err) {
      console.error("Roster error:", err);
    }
  }

  // =========================================================================
  // 9. Library Turnstile Logs
  // =========================================================================
  async loadLibraryLogs() {
    const tbody = document.getElementById('library-tbody');
    if (!tbody) return;

    try {
      const res = await fetch(`${this.apiBase}/api/attendance/logs?entry_type=Library Gate Entry`);
      const data = await res.json();
      const logs = data.logs || [];

      const vCount = document.getElementById('lib-total-visits');
      const uCount = document.getElementById('lib-unique-readers');
      if (vCount) vCount.textContent = logs.length;
      if (uCount) uCount.textContent = new Set(logs.map(l => l.roll_no)).size;

      if (!logs.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 25px;">No library entries recorded today yet. Switch scan mode to 'Library Gate Entry' to test.</td></tr>`;
        return;
      }

      tbody.innerHTML = logs.map(l => `
        <tr>
          <td><span style="font-family: var(--font-mono); color: var(--text-dim);">#${l.log_id}</span></td>
          <td><b style="font-family: var(--font-mono); color: var(--accent-indigo);">${l.roll_no}</b></td>
          <td><b>${l.full_name}</b></td>
          <td>${l.branch}</td>
          <td>${l.check_in_time}</td>
          <td><span class="badge-pill pill-library">Gate Cleared</span></td>
        </tr>
      `).join('');
    } catch (err) {
      console.error("Library logs error:", err);
    }
  }

  // =========================================================================
  // 10. KPI Summaries & One-Click CSV/Excel Exports
  // =========================================================================
  async refreshKPIs() {
    try {
      const res = await fetch(`${this.apiBase}/api/stats`);
      const data = await res.json();

      const kEnrolled = document.getElementById('kpi-enrolled');
      const kPresent = document.getElementById('kpi-present');
      const kAbsent = document.getElementById('kpi-absent');
      const kRate = document.getElementById('kpi-rate');

      if (kEnrolled) kEnrolled.textContent = data.total_enrolled;
      if (kPresent) kPresent.textContent = data.total_present;
      if (kAbsent) kAbsent.textContent = data.total_absent;
      if (kRate) kRate.textContent = `${data.attendance_rate}%`;
    } catch (err) {
      console.warn("KPI update error:", err);
    }
  }

  setupExportButtons() {
    const btnCsv = document.getElementById('btn-export-csv');
    const btnExcel = document.getElementById('btn-export-excel');

    if (btnCsv) {
      btnCsv.addEventListener('click', () => {
        const dateVal = document.getElementById('filter-date')?.value || '';
        window.location.href = `${this.apiBase}/api/attendance/export/csv?date=${encodeURIComponent(dateVal)}`;
      });
    }

    if (btnExcel) {
      btnExcel.addEventListener('click', () => {
        const dateVal = document.getElementById('filter-date')?.value || '';
        window.location.href = `${this.apiBase}/api/attendance/export/excel?date=${encodeURIComponent(dateVal)}`;
      });
    }
  }
}

// Instantiate on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  window.app = new SmartQRApp();
});
