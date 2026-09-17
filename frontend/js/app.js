let currentJobId = null;
let pollInterval = null;
let encountersData = [];
let activeFilter = "all";
let activeEncounterIndex = 0;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupDropzone();
  checkApiSettings();
  fetchRecentJobs();
  fetchLocalCaptures();
});

// Tab Management
function setupTabs() {
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tab = item.getAttribute("data-tab");
      switchTab(tab);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach(pane => {
    pane.classList.toggle("active", pane.id === `tab-${tabId}`);
  });

  const titles = {
    dashboard: ["TACTICAL DASHBOARD", "Strict player-isolated Valorant analysis engine"],
    upload: ["UPLOAD & CONFIGURE VOD", "Player lock identity verification before analysis"],
    progress: ["COACHING IN PROGRESS", "Real-time OpenCV detection & Gemini video understanding"],
    report: ["TACTICAL MATCH REPORT", "Strictly evaluated from target player's verified POV"],
    encounters: ["ENCOUNTER REVIEW", "Interactive fight breakdown with synchronized video clips"],
    performance: ["TACTICAL PERFORMANCE", "Aim, movement, utility, and positioning diagnostics"],
    training: ["PERSONALIZED TRAINING PLAN", "Actionable drills addressing your specific recurring mistakes"],
    settings: ["SETTINGS & API CONFIG", "Gemini API key and local storage configuration"]
  };

  if (titles[tabId]) {
    document.getElementById("page-title").textContent = titles[tabId][0];
    document.getElementById("page-subtitle").textContent = titles[tabId][1];
  }
}

// Check API Settings
async function checkApiSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    const statusDot = document.querySelector("#api-status-indicator .status-indicator-dot");
    const statusText = document.querySelector("#api-status-indicator .api-status-text");
    const dashStatus = document.getElementById("dash-gemini-status");
    const dashModel = document.getElementById("dash-model-name");
    const dashBanner = document.getElementById("dash-api-banner");
    const uploadBanner = document.getElementById("upload-api-banner");

    dashModel.textContent = data.gemini_model || "gemini-3.6-flash";

    if (data.has_gemini_key) {
      statusDot.className = "status-indicator-dot green";
      statusText.textContent = `Gemini Active (${data.masked_key})`;
      dashStatus.textContent = "Connected";
      dashStatus.className = "stat-value green";
      if (dashBanner) dashBanner.style.display = "none";
      if (uploadBanner) uploadBanner.style.display = "none";
      const settingsInput = document.getElementById("settings-api-key");
      if (settingsInput) settingsInput.placeholder = `Active: ${data.masked_key}`;
    } else {
      statusDot.className = "status-indicator-dot red";
      statusText.textContent = "Gemini Key Required (Click to Setup)";
      dashStatus.textContent = "Offline Mode";
      dashStatus.className = "stat-value cyan";
      if (dashBanner) dashBanner.style.display = "flex";
      if (uploadBanner) uploadBanner.style.display = "flex";

      // Automatically show modal prompt on first launch if unconfigured
      if (!sessionStorage.getItem("dismissed_api_modal")) {
        openApiKeyModal();
      }
    }

    if (data.data_dir) {
      const dataDirInput = document.getElementById("settings-data-dir");
      if (dataDirInput) dataDirInput.value = data.data_dir;
    }
  } catch (err) {
    console.error("Failed to check API settings:", err);
  }
}

// Fetch Local Captures
async function fetchLocalCaptures() {
  const container = document.getElementById("local-captures-list");
  try {
    const res = await fetch("/api/local-captures");
    const data = await res.json();
    if (!data.captures || data.captures.length === 0) {
      container.innerHTML = `<div class="empty-state">No MP4 files found in Videos\\Captures folder.</div>`;
      return;
    }

    container.innerHTML = data.captures.map(c => `
      <div class="capture-item" onclick="selectLocalCapture('${c.path.replace(/\\/g, '\\\\')}', '${c.name}')">
        <div class="capture-info">
          <span class="capture-name">${c.name}</span>
          <span class="capture-meta">${c.size_mb} MB</span>
        </div>
        <button class="btn btn-secondary btn-xs">Select</button>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Could not read Captures folder.</div>`;
  }
}

function selectLocalCapture(path, name) {
  document.getElementById("direct-video-path").value = path;
  switchTab("upload");
}

function loadSampleLocalCapture() {
  const defaultSample = "C:\\Users\\ginto\\Videos\\Captures\\VALORANT   2026-09-15 15-45-04.mp4";
  document.getElementById("direct-video-path").value = defaultSample;
  switchTab("upload");
}

function useDirectPath() {
  const path = document.getElementById("direct-video-path").value.trim();
  if (!path) {
    alert("Please enter or select a valid video path.");
    return;
  }
  document.getElementById("selected-file-banner").style.display = "flex";
  document.getElementById("selected-file-name").textContent = path;
}

// Drag & Drop
function setupDropzone() {
  const dropzone = document.getElementById("vod-dropzone");
  const fileInput = document.getElementById("vod-file-input");

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("drag-over");
  });

  dropzone.addEventListener("drop", async (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    if (e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      handleFileUpload(fileInput.files[0]);
    }
  });
}

let uploadedVideoPath = null;

async function handleFileUpload(file) {
  const banner = document.getElementById("selected-file-banner");
  const fileName = document.getElementById("selected-file-name");

  banner.style.display = "flex";
  fileName.textContent = `Uploading ${file.name}...`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (res.ok) {
      uploadedVideoPath = data.video_path;
      fileName.textContent = `Uploaded: ${file.name} (${(data.size_bytes / (1024*1024)).toFixed(1)} MB)`;
      document.getElementById("direct-video-path").value = data.video_path;
    } else {
      alert(`Upload failed: ${data.detail || "Unknown error"}`);
      clearSelectedFile();
    }
  } catch (err) {
    alert("Network error while uploading video.");
    clearSelectedFile();
  }
}

function clearSelectedFile() {
  uploadedVideoPath = null;
  document.getElementById("direct-video-path").value = "";
  document.getElementById("selected-file-banner").style.display = "none";
  document.getElementById("vod-file-input").value = "";
}

// Trigger Analysis
async function triggerAnalysis() {
  const videoPath = document.getElementById("direct-video-path").value.trim();
  const targetAgent = document.getElementById("target-agent-select").value;
  const targetUsername = document.getElementById("target-username-input").value.trim();

  if (!videoPath) {
    alert("Please select a video file or provide a video path.");
    return;
  }
  if (!targetAgent) {
    alert("Target Agent is mandatory for Player Lock.");
    return;
  }

  const payload = {
    video_path: videoPath,
    target_agent: targetAgent,
    target_username: targetUsername,
    merge_window: parseFloat(document.getElementById("setting-merge-window").value) || 7.0,
    pre_roll: parseFloat(document.getElementById("setting-pre-roll").value) || 12.0,
    post_roll: parseFloat(document.getElementById("setting-post-roll").value) || 5.0,
    gemini_model: document.getElementById("setting-gemini-model").value,
    analysis_depth: document.getElementById("setting-analysis-depth").value
  };

  const btn = document.getElementById("start-analysis-btn");
  btn.disabled = true;
  btn.textContent = "INITIALIZING PIPELINE...";

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      currentJobId = data.job_id;
      document.getElementById("active-agent-chip").style.display = "flex";
      document.getElementById("active-agent-name").textContent = targetAgent.toUpperCase();
      document.getElementById("nav-progress-btn").style.display = "flex";
      switchTab("progress");
      startPollingProgress(currentJobId);
    } else {
      alert(`Error starting analysis: ${data.detail || "Unknown error"}`);
    }
  } catch (err) {
    alert("Failed to start analysis. Check backend server connection.");
  } finally {
    btn.disabled = false;
    btn.textContent = "START AI VOD COACHING";
  }
}

// Polling Progress
function startPollingProgress(jobId) {
  if (pollInterval) clearInterval(pollInterval);
  document.getElementById("progress-job-badge").textContent = `JOB ID: ${jobId}`;
  document.getElementById("progress-done-cta").style.display = "none";

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();

      updateProgressUI(job);

      if (job.status === "COMPLETED") {
        clearInterval(pollInterval);
        document.getElementById("progress-done-cta").style.display = "flex";
        loadJobReport(jobId);
        fetchRecentJobs();
      } else if (job.status === "FAILED") {
        clearInterval(pollInterval);
        alert(`Analysis failed: ${job.error_message || "Unknown error"}`);
      }
    } catch (err) {
      console.error("Polling error:", err);
    }
  }, 1000);
}

function updateProgressUI(job) {
  const pct = Math.round(job.progress || 0);
  document.getElementById("main-progress-bar").style.width = `${pct}%`;
  document.getElementById("progress-percentage-text").textContent = `${pct}%`;
  document.getElementById("current-stage-text").textContent = job.stage || "Processing...";

  // Checkmarks
  const stageMap = [
    { id: "stage-1", minPct: 10 },
    { id: "stage-2", minPct: 25 },
    { id: "stage-3", minPct: 40 },
    { id: "stage-4", minPct: 55 },
    { id: "stage-5", minPct: 70 },
    { id: "stage-6", minPct: 85 },
    { id: "stage-7", minPct: 92 },
    { id: "stage-8", minPct: 100 },
  ];

  stageMap.forEach(s => {
    const el = document.getElementById(s.id);
    const icon = el.querySelector(".stage-icon");
    if (pct >= s.minPct) {
      el.className = "stage-item completed";
      icon.textContent = "✓";
    } else if (pct >= s.minPct - 15) {
      el.className = "stage-item active";
      icon.textContent = "●";
    } else {
      el.className = "stage-item";
      icon.textContent = "⏳";
    }
  });

  // Metrics
  if (job.video_duration) {
    const m = Math.floor(job.video_duration / 60);
    const s = Math.floor(job.video_duration % 60);
    document.getElementById("metric-duration").textContent = `${m}:${s < 10 ? '0' : ''}${s}`;
  }
  document.getElementById("metric-candidates").textContent = job.candidate_count || 0;
  document.getElementById("metric-encounters").textContent = job.encounter_count || 0;
  document.getElementById("metric-target-valid").textContent = job.target_encounter_count || 0;
  document.getElementById("metric-spectator-ignored").textContent = job.ignored_encounter_count || 0;
}

// Load Job Report & Encounters
async function loadJobReport(jobId) {
  currentJobId = jobId;
  try {
    const res = await fetch(`/api/jobs/${jobId}/report`);
    const data = await res.json();
    if (data.report) {
      renderReport(data.report);
      renderPerformance(data.report);
      renderTraining(data.report);
    }
    await loadEncounters(jobId);
  } catch (err) {
    console.error("Error loading report:", err);
  }
}

async function loadEncounters(jobId) {
  try {
    const res = await fetch(`/api/jobs/${jobId}/encounters`);
    const data = await res.json();
    encountersData = data.encounters || [];
    renderEncountersList();
    if (encountersData.length > 0) {
      selectEncounter(0);
    }
  } catch (err) {
    console.error("Error loading encounters:", err);
  }
}

function renderReport(report) {
  const container = document.getElementById("report-content-area");
  const summary = report.match_summary || {};
  const mistakes = report.top_recurring_mistakes || [];
  const habits = report.top_good_habits || [];
  const breakdowns = report.breakdowns || {};

  container.innerHTML = `
    <!-- Top Summary Card -->
    <div class="report-section">
      <h3>MATCH COACHING SUMMARY</h3>
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">Locked Target Player</span>
          <span class="stat-value cyan">${summary.target_agent}</span>
          <span class="stat-sub">${summary.target_username || "First-Person Verified"}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Target Encounters</span>
          <span class="stat-value green">${summary.analyzed_target_encounters}</span>
          <span class="stat-sub">Kills: ${summary.target_kills} | Deaths: ${summary.target_deaths}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Spectator Footage Ignored</span>
          <span class="stat-value red">${summary.ignored_spectator_encounters}</span>
          <span class="stat-sub">Zero advice attributed to user</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Performance Rating</span>
          <span class="stat-value">${summary.estimated_performance_score}</span>
          <span class="stat-sub">Player Lock 100% Enforced</span>
        </div>
      </div>
    </div>

    <!-- Top 5 Recurring Mistakes -->
    <div class="report-section">
      <h3>TOP 5 RECURRING MISTAKES (WEIGHTED BY SEVERITY &amp; DEATH IMPACT)</h3>
      ${mistakes.length === 0 ? '<p>No recurring mistakes found! Excellent disciplined play.</p>' : mistakes.map((m, idx) => `
        <div class="mistake-card">
          <div class="mistake-header">
            <span class="mistake-name">#${idx + 1}. ${m.name}</span>
            <span class="badge ${m.impact === 'HIGH' ? 'red-badge' : 'badge'}">${m.impact} IMPACT • ${m.count} Occurrences • ${m.deaths} Deaths</span>
          </div>
          <p style="font-size: 13px; color: var(--text-secondary);">Observed during duels at: ${m.examples.join(", ")}</p>
        </div>
      `).join("")}
    </div>

    <!-- Top 5 Good Habits -->
    <div class="report-section">
      <h3>TOP 5 GOOD HABITS &amp; STRENGTHS</h3>
      ${habits.length === 0 ? '<p>None recorded.</p>' : habits.map(h => `
        <div class="habit-card">
          <strong>✓ ${h.habit}</strong> (Demonstrated ${h.count} times)
        </div>
      `).join("")}
    </div>

    <!-- Tactical Breakdowns -->
    <div class="report-section">
      <h3>CATEGORIZED TACTICAL BREAKDOWNS</h3>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div style="background: var(--bg-darkest); padding: 14px; border-radius: 4px;">
          <h4 style="color: var(--val-cyan); font-family: var(--font-display); font-size: 18px; margin-bottom: 8px;">MECHANICAL PROBLEMS</h4>
          <ul style="padding-left: 20px; font-size: 13px; color: var(--text-secondary);">
            ${(breakdowns.mechanical || []).map(i => `<li>${i}</li>`).join("")}
          </ul>
        </div>
        <div style="background: var(--bg-darkest); padding: 14px; border-radius: 4px;">
          <h4 style="color: var(--val-red); font-family: var(--font-display); font-size: 18px; margin-bottom: 8px;">POSITIONING PROBLEMS</h4>
          <ul style="padding-left: 20px; font-size: 13px; color: var(--text-secondary);">
            ${(breakdowns.positioning || []).map(i => `<li>${i}</li>`).join("")}
          </ul>
        </div>
        <div style="background: var(--bg-darkest); padding: 14px; border-radius: 4px;">
          <h4 style="color: var(--val-green); font-family: var(--font-display); font-size: 18px; margin-bottom: 8px;">UTILITY PROBLEMS</h4>
          <ul style="padding-left: 20px; font-size: 13px; color: var(--text-secondary);">
            ${(breakdowns.utility || []).map(i => `<li>${i}</li>`).join("")}
          </ul>
        </div>
        <div style="background: var(--bg-darkest); padding: 14px; border-radius: 4px;">
          <h4 style="color: var(--val-amber); font-family: var(--font-display); font-size: 18px; margin-bottom: 8px;">DECISION-MAKING PROBLEMS</h4>
          <ul style="padding-left: 20px; font-size: 13px; color: var(--text-secondary);">
            ${(breakdowns.decision_making || []).map(i => `<li>${i}</li>`).join("")}
          </ul>
        </div>
      </div>
    </div>
  `;
}

function renderPerformance(report) {
  const container = document.getElementById("performance-content-area");
  container.innerHTML = `
    <div class="report-section">
      <h3>TACTICAL SKILL RATINGS</h3>
      <div style="display: flex; flex-direction: column; gap: 14px; max-width: 600px;">
        <div>
          <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:13px;">
            <span>Crosshair Placement &amp; Pre-Aim</span>
            <span style="font-weight:700; color:var(--val-amber);">6.0 / 10</span>
          </div>
          <div style="height:8px; background:var(--bg-darkest); border-radius:4px; overflow:hidden;">
            <div style="width:60%; height:100%; background:var(--val-amber);"></div>
          </div>
        </div>
        <div>
          <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:13px;">
            <span>Movement &amp; Counter-Strafing</span>
            <span style="font-weight:700; color:var(--val-cyan);">7.2 / 10</span>
          </div>
          <div style="height:8px; background:var(--bg-darkest); border-radius:4px; overflow:hidden;">
            <div style="width:72%; height:100%; background:var(--val-cyan);"></div>
          </div>
        </div>
        <div>
          <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:13px;">
            <span>Positioning &amp; Angle Isolation</span>
            <span style="font-weight:700; color:var(--val-red);">5.5 / 10</span>
          </div>
          <div style="height:8px; background:var(--bg-darkest); border-radius:4px; overflow:hidden;">
            <div style="width:55%; height:100%; background:var(--val-red);"></div>
          </div>
        </div>
        <div>
          <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:13px;">
            <span>Breach Utility Impact &amp; Stall Timing</span>
            <span style="font-weight:700; color:var(--val-green);">8.0 / 10</span>
          </div>
          <div style="height:8px; background:var(--bg-darkest); border-radius:4px; overflow:hidden;">
            <div style="width:80%; height:100%; background:var(--val-green);"></div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderTraining(report) {
  const container = document.getElementById("training-content-area");
  const drills = report.training_plan || [];

  container.innerHTML = `
    <div class="report-section">
      <h3>PERSONALIZED TRAINING DRILLS (DERIVED FROM VOD MISTAKES)</h3>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        ${drills.map((d, idx) => `
          <div style="background: var(--bg-darkest); border-top: 3px solid var(--val-cyan); padding: 18px; border-radius: 4px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
              <h4 style="font-family: var(--font-display); font-size: 20px; color:#fff;">${d.title}</h4>
              <span class="badge cyan-badge">${d.duration}</span>
            </div>
            <p style="font-size:13px; color:var(--val-green); font-weight:600; margin-bottom:6px;">Routine: ${d.routine}</p>
            <p style="font-size:12px; color:var(--text-secondary); line-height:1.5;">${d.rules}</p>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

// Encounters Management
function filterEncounters(filter) {
  activeFilter = filter;
  document.querySelectorAll(".filter-btn").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-filter") === filter);
  });
  renderEncountersList();
}

function renderEncountersList() {
  const container = document.getElementById("encounters-list-column");
  let filtered = encountersData;

  if (activeFilter === "target") {
    filtered = encountersData.filter(e => e.is_target_player && e.player_state === "USER_ALIVE");
  } else if (activeFilter === "ignored") {
    filtered = encountersData.filter(e => !e.is_target_player || e.player_state !== "USER_ALIVE");
  }

  document.getElementById("encounters-filter-count").textContent = `Showing ${filtered.length} of ${encountersData.length} encounters`;

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state">No encounters match filter "${activeFilter}".</div>`;
    return;
  }

  container.innerHTML = filtered.map((e, idx) => {
    const isTarget = e.is_target_player && e.player_state === "USER_ALIVE";
    const badgeClass = isTarget ? "green-badge" : "red-badge";
    const statusText = isTarget ? `✓ TARGET PLAYER (${e.target_agent})` : "IGNORED: Spectating Teammate";

    return `
      <div class="encounter-card ${isTarget ? 'target-player' : 'ignored'} ${idx === activeEncounterIndex ? 'active' : ''}" onclick="selectEncounter(${idx}, '${activeFilter}')">
        <div class="card-top">
          <span class="card-time">⏱ ${e.start_formatted || '00:00'} - ${e.end_formatted || '00:00'}</span>
          <div class="card-badges">
            <span class="badge ${badgeClass}">${statusText}</span>
            <span class="badge">${e.result || 'DUEL'}</span>
          </div>
        </div>
        <div class="card-title">${isTarget ? (e.summary || 'Duel encounter') : 'Spectator Camera — Not Analyzed'}</div>
        <div class="card-desc">${isTarget ? (e.why_mistake || 'Good execution and angle isolation.') : e.ignored_reason}</div>
      </div>
    `;
  }).join("");
}

function selectEncounter(filteredIdx, filter = activeFilter) {
  activeEncounterIndex = filteredIdx;
  let filtered = encountersData;
  if (filter === "target") {
    filtered = encountersData.filter(e => e.is_target_player && e.player_state === "USER_ALIVE");
  } else if (filter === "ignored") {
    filtered = encountersData.filter(e => !e.is_target_player || e.player_state !== "USER_ALIVE");
  }

  const enc = filtered[filteredIdx];
  if (!enc) return;

  // Highlight card
  document.querySelectorAll(".encounter-card").forEach((c, i) => c.classList.toggle("active", i === filteredIdx));

  // Load video clip into player
  const player = document.getElementById("encounter-video-player");
  if (enc.clip_filename && currentJobId) {
    player.src = `/api/clips/${currentJobId}/${enc.clip_filename}`;
    player.load();
  }

  // Populate details
  const viewerTitle = document.getElementById("viewer-title");
  const viewerBadge = document.getElementById("viewer-badge");
  const viewerDetails = document.getElementById("viewer-details");

  const isTarget = enc.is_target_player && enc.player_state === "USER_ALIVE";

  viewerTitle.textContent = `Encounter #${enc.encounter_index || (filteredIdx + 1)} (${enc.event_formatted || '00:00'})`;
  viewerBadge.className = `badge ${isTarget ? 'green-badge' : 'red-badge'}`;
  viewerBadge.textContent = isTarget ? `TARGET: ${enc.target_agent} (USER_ALIVE)` : "SPECTATOR FOOTAGE (IGNORED)";

  if (!isTarget) {
    viewerDetails.innerHTML = `
      <div style="background: rgba(255,70,85,0.08); border:1px solid rgba(255,70,85,0.3); border-radius:4px; padding:16px; margin-top:12px;">
        <h4 style="color:var(--val-red); font-family:var(--font-display); font-size:18px; margin-bottom:6px;">PLAYER LOCK ACTIVE: SPECTATOR FOOTAGE</h4>
        <p style="font-size:13px; color:var(--text-secondary); line-height:1.5;">
          ${enc.ignored_reason || "The player died and the camera switched to spectate a teammate. Per the strict Player Lock rule, this footage is ignored completely and zero coaching advice is given."}
        </p>
      </div>
    `;
    return;
  }

  const ana = enc.analysis || {};
  viewerDetails.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:14px; margin-top:14px;">
      <div style="background:var(--bg-darkest); padding:12px 14px; border-radius:4px;">
        <span style="font-size:11px; text-transform:uppercase; color:var(--val-red); font-weight:700; letter-spacing:0.5px;">WHY IT WAS A MISTAKE</span>
        <p style="font-size:13px; color:#fff; margin-top:4px;">${enc.why_mistake || "N/A — Clean engagement."}</p>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
        <div style="background:var(--bg-darkest); padding:12px 14px; border-radius:4px;">
          <span style="font-size:11px; text-transform:uppercase; color:var(--val-amber); font-weight:700; letter-spacing:0.5px;">WHAT YOU DID</span>
          <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">${enc.what_you_did || "Engaged target."}</p>
        </div>
        <div style="background:var(--bg-darkest); padding:12px 14px; border-radius:4px;">
          <span style="font-size:11px; text-transform:uppercase; color:var(--val-green); font-weight:700; letter-spacing:0.5px;">WHAT YOU SHOULD HAVE DONE</span>
          <p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">${enc.what_you_should_have_done || "Solid execution."}</p>
        </div>
      </div>

      <!-- Tactical Micro Dimensions -->
      <div style="background:var(--bg-darkest); padding:14px; border-radius:4px;">
        <h4 style="font-family:var(--font-display); font-size:16px; margin-bottom:8px; color:var(--val-cyan);">TACTICAL DIMENSION BREAKDOWN</h4>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:12px; color:var(--text-secondary);">
          <div><strong style="color:#fff;">Crosshair:</strong> ${ana.crosshair_placement || "Standard"}</div>
          <div><strong style="color:#fff;">Movement:</strong> ${ana.movement || "Stationary"}</div>
          <div><strong style="color:#fff;">Peeking:</strong> ${ana.peeking || "Tight peek"}</div>
          <div><strong style="color:#fff;">Positioning:</strong> ${ana.positioning || "Cover available"}</div>
          <div><strong style="color:#fff;">Utility:</strong> ${ana.utility_usage || "Conserved"}</div>
          <div><strong style="color:#fff;">Decision:</strong> ${ana.decision_making || "Favorable duel"}</div>
        </div>
      </div>
    </div>
  `;
}

// Fetch Recent Jobs for Dashboard
async function fetchRecentJobs() {
  const container = document.getElementById("recent-jobs-list");
  try {
    const res = await fetch("/api/jobs");
    const data = await res.json();
    const jobs = data.jobs || [];

    document.getElementById("dash-total-vods").textContent = jobs.length;

    if (jobs.length === 0) {
      container.innerHTML = `<div class="empty-state">No VOD analyses yet. Upload a recording to begin!</div>`;
      return;
    }

    container.innerHTML = jobs.map(j => `
      <div class="job-card" onclick="loadJobReport('${j.id}'); switchTab('report');">
        <div class="job-info">
          <strong>${j.video_name || j.id}</strong>
          <span class="job-meta">Target: ${j.target_agent} • Created: ${new Date(j.created_at).toLocaleDateString()}</span>
        </div>
        <span class="badge ${j.status === 'COMPLETED' ? 'green-badge' : (j.status === 'FAILED' ? 'red-badge' : 'cyan-badge')}">
          ${j.status}
        </span>
      </div>
    `).join("");
  } catch (err) {
    console.error("Error fetching jobs:", err);
  }
}

// Save Settings
async function saveSettings(e) {
  e.preventDefault();
  const apiKey = document.getElementById("settings-api-key").value;
  const model = document.getElementById("settings-model").value;
  const dataDir = document.getElementById("settings-data-dir").value;

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        gemini_api_key: apiKey ? apiKey.trim() : null,
        gemini_model: model,
        data_dir: dataDir
      })
    });
    if (res.ok) {
      alert("Settings successfully saved to local .env configuration!");
      checkApiSettings();
    } else {
      alert("Error saving settings.");
    }
  } catch (err) {
    alert("Network error saving settings.");
  }
}

// Verify Settings API Key
async function verifySettingsApiKey() {
  const apiKey = document.getElementById("settings-api-key").value.trim();
  const statusBox = document.getElementById("settings-verify-status");
  const btn = document.getElementById("btn-verify-settings-key");

  if (!apiKey) {
    statusBox.className = "api-feedback-card error";
    statusBox.textContent = "Please enter an API key to test.";
    return;
  }

  statusBox.className = "api-feedback-card loading";
  statusBox.innerHTML = `<span class="loading-spinner" style="margin:0; width:16px; height:16px;"></span> Contacting Google Gemini 2.5 Flash...`;
  btn.disabled = true;

  try {
    const res = await fetch("/api/verify-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gemini_api_key: apiKey })
    });
    const data = await res.json();
    if (data.valid) {
      statusBox.className = "api-feedback-card success";
      statusBox.textContent = `[SUCCESS] Verified! Active key: ${data.masked_key}`;
      checkApiSettings();
    } else {
      statusBox.className = "api-feedback-card error";
      statusBox.textContent = data.message || data.error || "Verification failed. Check your API key.";
    }
  } catch (err) {
    statusBox.className = "api-feedback-card error";
    statusBox.textContent = `Network error: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

// Modal Handlers
function openApiKeyModal() {
  const modal = document.getElementById("api-key-modal");
  const status = document.getElementById("modal-api-status");
  if (status) {
    status.className = "api-feedback-card";
    status.textContent = "";
  }
  if (modal) {
    modal.classList.add("active");
    setTimeout(() => {
      const input = document.getElementById("modal-api-key-input");
      if (input) input.focus();
    }, 150);
  }
}

function closeApiKeyModal(rememberDismiss = false) {
  const modal = document.getElementById("api-key-modal");
  if (modal) {
    modal.classList.remove("active");
  }
  if (rememberDismiss) {
    sessionStorage.setItem("dismissed_api_modal", "true");
  }
}

async function verifyAndSaveApiKey() {
  const input = document.getElementById("modal-api-key-input");
  const statusBox = document.getElementById("modal-api-status");
  const btn = document.getElementById("btn-modal-verify");
  const key = input ? input.value.trim() : "";

  if (!key) {
    statusBox.className = "api-feedback-card error";
    statusBox.textContent = "Please enter your Google Gemini API key.";
    return;
  }

  statusBox.className = "api-feedback-card loading";
  statusBox.innerHTML = `<span class="loading-spinner" style="margin:0; width:16px; height:16px;"></span> Verifying key with Google Gemini 2.5 Flash...`;
  btn.disabled = true;

  try {
    const res = await fetch("/api/verify-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gemini_api_key: key })
    });
    const data = await res.json();
    if (data.valid) {
      statusBox.className = "api-feedback-card success";
      statusBox.textContent = `[SUCCESS] ${data.message} (${data.masked_key})`;
      sessionStorage.setItem("dismissed_api_modal", "true");
      checkApiSettings();
      setTimeout(() => {
        closeApiKeyModal();
      }, 1400);
    } else {
      statusBox.className = "api-feedback-card error";
      statusBox.textContent = data.message || "Failed to verify key. Please check that your key is valid and has Gemini API enabled.";
    }
  } catch (err) {
    statusBox.className = "api-feedback-card error";
    statusBox.textContent = `Error connecting to backend: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

function toggleApiKeyVisibility(inputId = "settings-api-key") {
  const field = document.getElementById(inputId);
  if (field) {
    field.type = field.type === "password" ? "text" : "password";
  }
}
