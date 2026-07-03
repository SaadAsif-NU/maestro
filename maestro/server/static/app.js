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
  nodes: new Map(), // id -> {el, role, status, tokens, thought, cx, cy, thoughtEl, tokEl, toolEl, feedEl}
  researchers: [],
  edges: [], // {source, target, pathEl}
  ws: null,
  running: false,
  startTime: 0,
  timer: null,
  tokens: 0,
  tools: 0,
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
  $("goal").addEventListener("keydown", (e) => {
    if (e.key === "Enter") startRun();
  });
  fetch("/health")
    .then((r) => r.json())
    .then((d) => ($("brain-badge").textContent = `brain: ${d.brain}`))
    .catch(() => {});
  window.addEventListener("resize", () => {
    layout();
    redrawEdges();
  });
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
  $("run-btn").disabled = true;
  setStatus("running", "orchestrating");
  startTimer();

  let runId;
  try {
    const resp = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ goal, researchers: 2 }),
    });
    const data = await resp.json();
    runId = data.run_id;
    $("brain-badge").textContent = `brain: ${data.brain}`;
  } catch (err) {
    setStatus("error", "failed to start");
    finishRun();
    return;
  }
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

function finishRun() {
  state.running = false;
  $("run-btn").disabled = false;
  stopTimer();
}

function resetUI() {
  $("nodes").innerHTML = "";
  $("graph").innerHTML = "";
  $("feed").innerHTML = "";
  $("graph-empty").style.display = "none";
  $("deliverable-panel").classList.add("hidden");
  $("deliverable").innerHTML = "";
  state.nodes.clear();
  state.researchers = [];
  state.edges = [];
  state.tokens = 0;
  state.tools = 0;
  $("m-agents").textContent = "0";
  $("m-tokens").textContent = "0";
  $("m-tools").textContent = "0";
  $("m-time").textContent = "0.0s";
}

// ---------- timers / metrics ----------
function startTimer() {
  state.startTime = performance.now();
  state.timer = setInterval(() => {
    const s = (performance.now() - state.startTime) / 1000;
    $("m-time").textContent = `${s.toFixed(1)}s`;
  }, 100);
}
function stopTimer() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
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
      onStatus(evt.agent_id, evt.role, evt.data.status);
      break;
    case "token":
      onToken(evt.agent_id, evt.role, evt.data.text);
      break;
    case "tool_call":
      onToolCall(evt.agent_id, evt.role, evt.data.tool, evt.data.argument);
      break;
    case "tool_result":
      onToolResult(evt.role, evt.data.tool, evt.data.result);
      break;
    case "agent_completed":
      onCompleted(evt.agent_id);
      break;
    case "run_completed":
      onRunCompleted(evt.data);
      break;
    case "error":
      setStatus("error", "error");
      feed("error", "system", evt.data.message || "run failed");
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
  $("nodes").appendChild(el);
  const node = {
    el,
    role,
    tokens: 0,
    thought: "",
    thoughtEl: el.querySelector(".node-thought"),
    tokEl: el.querySelector(".node-tokens"),
    toolEl: el.querySelector(".node-tool"),
    feedEl: null,
  };
  state.nodes.set(id, node);
  if (role === "researcher") state.researchers.push(id);
  $("m-agents").textContent = String(state.nodes.size);
  layout();
  redrawEdges();
}

function layout() {
  const wrap = $("graph-wrap");
  const W = wrap.clientWidth;
  const H = wrap.clientHeight;
  const svg = $("graph");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

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
    if (a && b && a.cx != null && b.cx != null) {
      edge.pathEl.setAttribute("d", edgePath(a, b));
    }
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
function onStatus(id, role, status) {
  const n = state.nodes.get(id);
  if (!n) return;
  n.el.classList.remove("thinking", "using_tool", "done");
  if (status === "thinking") {
    n.el.classList.add("thinking");
    n.feedEl = null; // next tokens start a fresh transcript line
    if (!n.pulsedIn) {
      n.pulsedIn = true;
      pulseInto(id); // animate the handoff edge as work reaches this agent
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
  n.thought = (n.thought + text).slice(-160);
  n.thoughtEl.textContent = n.thought;
  n.tokEl.textContent = `${n.tokens} tok`;
  state.tokens += 1;
  $("m-tokens").textContent = String(state.tokens);
  // stream into the live feed, one growing line per thinking burst
  if (!n.feedEl) n.feedEl = feed(role, role, "");
  n.feedEl.textContent += text;
  autoscrollFeed();
}

function onToolCall(id, role, tool, argument) {
  const n = state.nodes.get(id);
  if (n) {
    n.toolEl.textContent = tool;
    n.toolEl.classList.add("show");
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

function onToolResult(role, tool, result) {
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
  $("m-tokens").textContent = String(data.total_tokens ?? state.tokens);
  $("m-tools").textContent = String(data.total_tool_calls ?? state.tools);
  renderDeliverable(data.deliverable || "", data);
}

// ---------- feed ----------
function feed(role, tag, text) {
  const item = document.createElement("div");
  item.className = "feed-item";
  const color = ROLE_COLORS[role] || "var(--muted)";
  const tagEl = document.createElement("span");
  tagEl.className = "feed-tag";
  tagEl.style.color = color;
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

// ---------- deliverable ----------
function renderDeliverable(md, data) {
  $("deliverable").innerHTML = renderMarkdown(md);
  const meta = `${data.agents ?? state.nodes.size} agents · ${
    data.total_tokens ?? state.tokens
  } tokens · ${data.total_tool_calls ?? state.tools} tool calls · ${(
    (data.elapsed_ms ?? 0) / 1000
  ).toFixed(1)}s`;
  $("deliverable-meta").textContent = meta;
  const panel = $("deliverable-panel");
  panel.classList.remove("hidden");
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
