"use strict";

const ROLE_COLORS = {
  orchestrator: "var(--orchestrator)",
  researcher: "var(--researcher)",
  analyst: "var(--analyst)",
  critic: "var(--critic)",
  writer: "var(--writer)",
};

const EXAMPLES = [
  "Design a go-to-market strategy for a B2B SaaS analytics product",
  "Evaluate whether we should build or buy a vector search engine",
  "Draft a 90-day plan to improve net revenue retention above 120 percent",
  "Assess the risks of migrating our monolith to microservices",
];

const $ = (id) => document.getElementById(id);

const state = {
  nodes: new Map(),
  researchers: [],
  edges: [],
  ws: null,
  running: false,
  isLive: false,
  runId: null,
  teamSize: 2,
  startTime: 0,
  timer: null,
  tokens: 0,
  tools: 0,
  deliverableMd: "",
  history: [],
};

// ---------- setup ----------
function init() {
  const ex = $("examples");
  EXAMPLES.forEach((text) => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = text;
    chip.onclick = () => {
      $("goal").value = text;
      startRun();
    };
    ex.appendChild(chip);
  });

  $("run-btn").onclick = startRun;
  $("stop-btn").onclick = stopRun;
  $("goal").addEventListener("keydown", (e) => {
    if (e.key === "Enter") startRun();
  });

  $("team-size").querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      state.teamSize = Number(b.dataset.n);
      $("team-size")
        .querySelectorAll("button")
        .forEach((x) => x.classList.toggle("active", x === b));
    };
  });

  $("copy-btn").onclick = copyDeliverable;
  $("download-btn").onclick = downloadDeliverable;
  $("drawer-close").onclick = closeDrawer;
  $("drawer-scrim").onclick = closeDrawer;
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });

  fetch("/health")
    .then((r) => r.json())
    .then((d) => ($("brain-badge").textContent = `brain: ${d.brain}`))
    .catch(() => {});
  window.addEventListener("resize", () => {
    layout();
    redrawEdges();
  });
  $("goal").focus();
}

function setStatus(kind, label) {
  const pill = $("status-pill");
  pill.className = `pill pill-${kind}`;
  pill.textContent = label;
}

// ---------- run lifecycle ----------
async function startRun() {
  if (state.running) return;
  const goal = $("goal").value.trim();
  if (!goal) {
    $("goal").focus();
    return;
  }
  resetUI();
  state.running = true;
  state.isLive = true;
  $("run-btn").disabled = true;
  $("stop-btn").classList.remove("hidden");
  setStatus("running", "orchestrating");
  startTimer();

  let data;
  try {
    const resp = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ goal, researchers: state.teamSize }),
    });
    data = await resp.json();
  } catch (err) {
    setStatus("error", "failed to start");
    finishRun();
    return;
  }
  state.runId = data.run_id;
  $("brain-badge").textContent = `brain: ${data.brain}`;
  addHistory(data.run_id, goal, "running");
  openSocket(data.run_id);
}

function loadRun(runId, goal) {
  if (state.running) return;
  resetUI();
  state.running = true;
  state.isLive = false;
  state.runId = runId;
  $("run-btn").disabled = true;
  $("graph-hint").textContent = "replaying";
  setStatus("running", "replaying");
  startTimer();
  openSocket(runId);
}

function openSocket(runId) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/runs/${runId}/events`);
  state.ws = ws;
  ws.onmessage = (e) => handleEvent(JSON.parse(e.data));
  ws.onclose = () => finishRun();
  ws.onerror = () => setStatus("error", "connection error");
}

async function stopRun() {
  if (!state.runId || !state.isLive) return;
  $("stop-btn").disabled = true;
  try {
    await fetch(`/api/runs/${state.runId}/cancel`, { method: "POST" });
  } catch (err) {
    /* the socket close will settle the UI */
  }
}

function finishRun() {
  state.running = false;
  state.isLive = false;
  $("run-btn").disabled = false;
  $("stop-btn").classList.add("hidden");
  $("stop-btn").disabled = false;
  $("graph-hint").textContent = "live orchestration";
  stopTimer();
}

function resetUI() {
  $("nodes").innerHTML = "";
  $("graph").innerHTML = "";
  $("feed").innerHTML = "";
  $("graph-empty").style.display = "none";
  $("deliverable-panel").classList.add("hidden");
  $("deliverable").innerHTML = "";
  closeDrawer();
  state.nodes.clear();
  state.researchers = [];
  state.edges = [];
  state.tokens = 0;
  state.tools = 0;
  $("m-agents").textContent = "0";
  $("m-tokens").textContent = "0";
  $("m-tools").textContent = "0";
  $("m-time").textContent = "0.0s";
  $("m-rate").textContent = "tokens";
}

// ---------- timers / metrics ----------
function startTimer() {
  state.startTime = performance.now();
  state.timer = setInterval(() => {
    const s = (performance.now() - state.startTime) / 1000;
    $("m-time").textContent = `${s.toFixed(1)}s`;
    if (s > 0.2) $("m-rate").textContent = `${Math.round(state.tokens / s)} tok/s`;
  }, 100);
}
function stopTimer() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
}

// ---------- history ----------
function addHistory(runId, goal, status) {
  state.history.unshift({ runId, goal, status });
  renderHistory();
}
function updateHistory(runId, status) {
  const item = state.history.find((h) => h.runId === runId);
  if (item) item.status = status;
  renderHistory();
}
function renderHistory() {
  const wrap = $("history");
  wrap.innerHTML = "";
  if (state.history.length === 0) {
    wrap.classList.add("hidden");
    return;
  }
  wrap.classList.remove("hidden");
  state.history.slice(0, 6).forEach((h) => {
    const pill = document.createElement("div");
    pill.className = "run-pill";
    pill.title = `Replay: ${h.goal}`;
    pill.innerHTML = `<span class="rdot ${h.status}"></span><span class="goal">${escapeHtml(
      h.goal
    )}</span>`;
    pill.onclick = () => loadRun(h.runId, h.goal);
    wrap.appendChild(pill);
  });
}

// ---------- event handling ----------
function handleEvent(evt) {
  switch (evt.type) {
    case "agent_spawned":
      addNode(evt.agent_id, evt.role, evt.data.title);
      break;
    case "edge":
      addEdge(evt.data.source, evt.data.target);
      break;
    case "agent_status":
      onStatus(evt.agent_id, evt.data.status);
      break;
    case "token":
      onToken(evt.agent_id, evt.role, evt.data.text);
      break;
    case "tool_call":
      onToolCall(evt.agent_id, evt.data.tool, evt.data.argument);
      break;
    case "tool_result":
      onToolResult(evt.agent_id, evt.role, evt.data.tool, evt.data.result);
      break;
    case "agent_completed":
      onCompleted(evt.agent_id);
      break;
    case "run_completed":
      onRunCompleted(evt.data);
      break;
    case "run_cancelled":
      setStatus("error", "cancelled");
      if (state.runId) updateHistory(state.runId, "cancelled");
      feed("system", "system", "run cancelled");
      break;
    case "error":
      setStatus("error", "error");
      if (state.runId) updateHistory(state.runId, "failed");
      feed("system", "system", evt.data.message || "run failed");
      break;
  }
}

// ---------- graph ----------
function addNode(id, role, title) {
  if (state.nodes.has(id)) return;
  const el = document.createElement("div");
  el.className = "node";
  el.style.setProperty("--nc", ROLE_COLORS[role] || "var(--accent)");
  el.innerHTML = `
    <div class="node-head">
      <span class="node-dot"></span>
      <span class="node-role">${role}</span>
      <span class="node-check">✓</span>
    </div>
    <div class="node-title">${escapeHtml(title || role)}</div>
    <div class="node-thought"></div>
    <div class="node-foot">
      <span class="node-tokens">0 tok</span>
      <span class="node-tool"></span>
    </div>`;
  el.onclick = () => openDrawer(id);
  $("nodes").appendChild(el);
  state.nodes.set(id, {
    el,
    role,
    title: title || role,
    tokens: 0,
    thought: "",
    full: "",
    toolCalls: [],
    thoughtEl: el.querySelector(".node-thought"),
    tokEl: el.querySelector(".node-tokens"),
    toolEl: el.querySelector(".node-tool"),
    feedEl: null,
    pulsedIn: false,
  });
  if (role === "researcher") state.researchers.push(id);
  $("m-agents").textContent = String(state.nodes.size);
  layout();
  redrawEdges();
}

function layout() {
  const wrap = $("graph-wrap");
  const W = wrap.clientWidth;
  const H = wrap.clientHeight;
  $("graph").setAttribute("viewBox", `0 0 ${W} ${H}`);
  const place = (id, x, y) => {
    const n = state.nodes.get(id);
    if (!n) return;
    n.cx = x;
    n.cy = y;
    n.el.style.left = `${x}px`;
    n.el.style.top = `${y}px`;
  };
  place("orchestrator", W / 2, H * 0.09);
  const rs = state.researchers;
  rs.forEach((id, i) => {
    const x = rs.length === 1 ? W / 2 : W * 0.22 + (W * 0.56 * i) / (rs.length - 1);
    place(id, x, H * 0.31);
  });
  place("analyst", W / 2, H * 0.53);
  place("critic", W / 2, H * 0.72);
  place("writer", W / 2, H * 0.91);
}

function addEdge(source, target) {
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("class", "edge");
  $("graph").appendChild(path);
  state.edges.push({ source, target, pathEl: path });
  redrawEdges();
}
function edgePath(a, b) {
  const dy = (b.cy - a.cy) * 0.5;
  return `M ${a.cx} ${a.cy} C ${a.cx} ${a.cy + dy}, ${b.cx} ${b.cy - dy}, ${b.cx} ${b.cy}`;
}
function redrawEdges() {
  for (const edge of state.edges) {
    const a = state.nodes.get(edge.source);
    const b = state.nodes.get(edge.target);
    if (a && b && a.cx != null && b.cx != null) edge.pathEl.setAttribute("d", edgePath(a, b));
  }
}
function pulseInto(targetId) {
  for (const edge of state.edges) {
    if (edge.target !== targetId) continue;
    const a = state.nodes.get(edge.source);
    const b = state.nodes.get(edge.target);
    if (!a || !b || a.cx == null || b.cx == null) continue;
    edge.pathEl.classList.add("active");
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("r", "3.5");
    dot.setAttribute("class", "pulse-dot");
    const motion = document.createElementNS("http://www.w3.org/2000/svg", "animateMotion");
    motion.setAttribute("dur", "0.85s");
    motion.setAttribute("path", edgePath(a, b));
    motion.setAttribute("fill", "freeze");
    dot.appendChild(motion);
    $("graph").appendChild(dot);
    setTimeout(() => {
      dot.remove();
      edge.pathEl.classList.remove("active");
    }, 900);
  }
}

// ---------- node updates ----------
function onStatus(id, status) {
  const n = state.nodes.get(id);
  if (!n) return;
  n.el.classList.remove("thinking", "using_tool", "done");
  if (status === "thinking") {
    n.el.classList.add("thinking");
    n.feedEl = null;
    if (!n.pulsedIn) {
      n.pulsedIn = true;
      pulseInto(id);
    }
  } else if (status === "using_tool") {
    n.el.classList.add("using_tool");
  } else if (status === "done") {
    n.el.classList.add("done");
  }
}

function onToken(id, role, text) {
  const n = state.nodes.get(id);
  if (!n) return;
  n.tokens += 1;
  n.full += text;
  n.thought = (n.thought + text).slice(-160);
  n.thoughtEl.textContent = n.thought;
  n.tokEl.textContent = `${n.tokens} tok`;
  state.tokens += 1;
  $("m-tokens").textContent = String(state.tokens);
  if (!n.feedEl) n.feedEl = feed(role, role, "");
  n.feedEl.textContent += text;
  autoscrollFeed();
  refreshDrawer(id);
}

function onToolCall(id, tool, argument) {
  const n = state.nodes.get(id);
  if (n) {
    n.toolEl.textContent = tool;
    n.toolEl.classList.add("show");
    n.toolCalls.push({ tool, argument, result: "" });
    refreshDrawer(id);
  }
  state.tools += 1;
  $("m-tools").textContent = String(state.tools);
  const item = document.createElement("div");
  item.className = "feed-item feed-tool";
  item.innerHTML = `<span class="feed-tag" style="color:var(--critic)">tool</span>${escapeHtml(
    tool
  )}(<span class="arrow">${escapeHtml(argument)}</span>)`;
  $("feed").appendChild(item);
  autoscrollFeed();
}

function onToolResult(id, role, tool, result) {
  const n = state.nodes.get(id);
  if (n && n.toolCalls.length) {
    n.toolCalls[n.toolCalls.length - 1].result = result;
    refreshDrawer(id);
  }
  const excerpt = result.length > 130 ? result.slice(0, 130) + "..." : result;
  const item = feed(role, "result", excerpt);
  item.parentElement.classList.add("feed-tool");
}

function onCompleted(id) {
  const n = state.nodes.get(id);
  if (n) n.toolEl.classList.remove("show");
}

function onRunCompleted(data) {
  setStatus("done", "delivered");
  stopTimer();
  $("m-tokens").textContent = String(data.total_tokens ?? state.tokens);
  $("m-tools").textContent = String(data.total_tool_calls ?? state.tools);
  const secs = (data.elapsed_ms ?? 0) / 1000;
  if (secs > 0) {
    $("m-time").textContent = `${secs.toFixed(1)}s`;
    $("m-rate").textContent = `${Math.round((data.total_tokens ?? state.tokens) / secs)} tok/s`;
  }
  if (state.runId) updateHistory(state.runId, "completed");
  renderDeliverable(data.deliverable || "", data);
}

// ---------- feed ----------
function feed(role, tag, text) {
  const item = document.createElement("div");
  item.className = "feed-item";
  const tagEl = document.createElement("span");
  tagEl.className = "feed-tag";
  tagEl.style.color = ROLE_COLORS[role] || "var(--muted)";
  tagEl.textContent = tag;
  const textEl = document.createElement("span");
  textEl.className = "feed-text";
  textEl.textContent = text;
  item.appendChild(tagEl);
  item.appendChild(textEl);
  $("feed").appendChild(item);
  autoscrollFeed();
  return textEl;
}
function autoscrollFeed() {
  const f = $("feed");
  f.scrollTop = f.scrollHeight;
}

// ---------- agent drawer ----------
function openDrawer(id) {
  state.drawerId = id;
  refreshDrawer(id, true);
  $("drawer").classList.add("open");
  $("drawer-scrim").classList.add("open");
}
function closeDrawer() {
  state.drawerId = null;
  $("drawer").classList.remove("open");
  $("drawer-scrim").classList.remove("open");
}
function refreshDrawer(id, force) {
  if (state.drawerId !== id && !force) return;
  if (state.drawerId !== id) return;
  const n = state.nodes.get(id);
  if (!n) return;
  $("drawer-role").textContent = n.role;
  $("drawer-role").style.color = ROLE_COLORS[n.role] || "var(--accent)";
  $("drawer-title").textContent = n.title;
  $("drawer-stats").innerHTML =
    `<div class="drawer-stat"><b>${n.tokens}</b>tokens</div>` +
    `<div class="drawer-stat"><b>${n.toolCalls.length}</b>tool calls</div>`;
  $("drawer-tools").innerHTML = n.toolCalls
    .map(
      (t) =>
        `<div class="drawer-tool">${escapeHtml(t.tool)}(${escapeHtml(t.argument)})<br>&rarr; ${escapeHtml(
          t.result || "..."
        )}</div>`
    )
    .join("");
  $("drawer-body").textContent = n.full || "(no output yet)";
}

// ---------- deliverable ----------
function renderDeliverable(md, data) {
  state.deliverableMd = md;
  $("deliverable").innerHTML = renderMarkdown(md);
  $("deliverable-meta").textContent = `${data.agents ?? state.nodes.size} agents · ${
    data.total_tokens ?? state.tokens
  } tokens · ${data.total_tool_calls ?? state.tools} tool calls · ${(
    (data.elapsed_ms ?? 0) / 1000
  ).toFixed(1)}s`;
  const panel = $("deliverable-panel");
  panel.classList.remove("hidden");
  panel.classList.remove("arrived");
  void panel.offsetWidth; // restart the arrival animation
  panel.classList.add("arrived");
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function copyDeliverable() {
  if (!state.deliverableMd) return;
  navigator.clipboard.writeText(state.deliverableMd).then(() => flash($("copy-btn"), "Copied"));
}
function downloadDeliverable() {
  if (!state.deliverableMd) return;
  const blob = new Blob([state.deliverableMd], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "maestro-deliverable.md";
  a.click();
  URL.revokeObjectURL(url);
}
function flash(btn, text) {
  const original = btn.textContent;
  btn.textContent = text;
  setTimeout(() => (btn.textContent = original), 1400);
}

function renderMarkdown(md) {
  const lines = md.split("\n");
  let html = "";
  let inList = false;
  const flush = () => {
    if (inList) {
      html += "</ul>";
      inList = false;
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.startsWith("## ")) {
      flush();
      html += `<h2>${escapeHtml(line.slice(3))}</h2>`;
    } else if (line.startsWith("# ")) {
      flush();
      html += `<h1>${escapeHtml(line.slice(2))}</h1>`;
    } else if (line.startsWith("- ")) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${escapeHtml(line.slice(2))}</li>`;
    } else if (line.trim() === "") {
      flush();
    } else {
      flush();
      html += `<p>${escapeHtml(line)}</p>`;
    }
  }
  flush();
  return html;
}

function escapeHtml(s) {
  return String(s).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

init();
