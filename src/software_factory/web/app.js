const states = [
  "discovery", "planning", "implementing", "releasing", "testing", "reviewing", "packaging",
  "previewing", "completed",
];
const agentNames = {
  "team-lead": "Team Lead", "frontend-developer": "Frontend Developer",
  "backend-developer": "Backend Developer", "database-engineer": "Database Engineer",
  "qa-engineer": "QA Engineer", "requirements-analyst": "Requirements Analyst",
  "solution-architect": "Solution Architect", "security-reviewer": "Security Reviewer",
  "tool-curator": "Tool Curator", reviewer: "Delivery Reviewer",
  "infrastructure-engineer": "Infrastructure Engineer", "release-manager": "Release Manager",
  orchestrator: "Orchestrator", system: "System",
};

const elements = Object.fromEntries([
  "health", "task-form", "submit", "workspace", "state-badge", "steps", "events", "agents",
  "files", "result-panel", "result", "scorecard", "source-form", "source-file",
  "source-submit", "source-status", "artifact-link", "compare-runs", "comparison",
  "preview-link",
].map((id) => [id, document.querySelector(`#${id}`)]));
let pollTimer;
let eventStream;

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", "\"": "&quot;",
  })[character]);
}

function renderSteps(active) {
  const activeIndex = states.indexOf(active);
  elements.steps.innerHTML = states.map((state, index) => {
    const className = index < activeIndex || active === "completed"
      ? "done" : index === activeIndex ? "current" : "";
    return `<div class="step ${className}" title="${state}"></div>`;
  }).join("");
}

function renderEvents(events) {
  elements.events.innerHTML = events.map((event) => `
    <li class="event"><div><strong>${escapeHtml(agentNames[event.actor] || event.actor)}</strong>
    &mdash; ${escapeHtml(event.message)}<time>${new Date(event.created_at).toLocaleTimeString()}</time>
    </div></li>`).join("");
  const statuses = new Map();
  for (const event of events) {
    if (event.kind === "agent-started") statuses.set(event.actor, "running");
    if (event.kind === "agent-completed") statuses.set(event.actor, "done");
  }
  elements.agents.innerHTML = [...statuses].map(([id, status]) =>
    `<div class="agent"><strong>${escapeHtml(agentNames[id] || id)}</strong>
    <span>${escapeHtml(status)}</span></div>`
  ).join("") || "<span>No agents started</span>";
}

async function poll(sessionId) {
  const [sessionResponse, eventResponse, fileResponse] = await Promise.all([
    fetch(`/api/sessions/${sessionId}`), fetch(`/api/sessions/${sessionId}/events`),
    fetch(`/api/sessions/${sessionId}/files`),
  ]);
  const session = await sessionResponse.json();
  const events = await eventResponse.json();
  const files = await fileResponse.json();
  elements["state-badge"].textContent = session.state;
  renderSteps(session.state);
  renderEvents(events);
  elements.files.innerHTML = files.length
    ? files.map((file) => `<li>${escapeHtml(file)}</li>`).join("") : "<li>No files yet</li>";
  if (session.terminal) {
    clearInterval(pollTimer);
    pollTimer = undefined;
    eventStream?.close();
    elements.submit.disabled = false;
    elements["result-panel"].classList.remove("hidden");
    const scores = session.result?.scorecard?.dimensions || [];
    elements.scorecard.innerHTML = scores.map((item) => `
      <div class="score" title="${escapeHtml(item.evidence)}">
      <span>${escapeHtml(item.name.replaceAll("_", " "))}</span>
      <strong>${Math.round(item.score * 100)}%</strong></div>`).join("");
    elements.result.textContent = session.error || JSON.stringify(session.result, null, 2);
    if (session.result?.preview_url) {
      elements["preview-link"].href = new URL(
        session.result.preview_url, window.location.origin
      ).href;
      elements["preview-link"].classList.remove("hidden");
    }
  }
}

elements["task-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.submit.disabled = true;
  eventStream?.close();
  clearInterval(pollTimer);
  pollTimer = undefined;
  elements["result-panel"].classList.add("hidden");
  elements["preview-link"].classList.add("hidden");
  const response = await fetch("/api/sessions", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal: document.querySelector("#goal").value }),
  });
  if (!response.ok) {
    elements.submit.disabled = false;
    alert("Could not create the delivery session.");
    return;
  }
  const session = await response.json();
  elements.workspace.classList.remove("hidden");
  document.querySelector("#session-title").textContent = session.goal;
  elements["artifact-link"].href = `/api/sessions/${session.id}/artifact`;
  await poll(session.id);
  eventStream = new EventSource(`/api/sessions/${session.id}/stream`);
  eventStream.onmessage = () => poll(session.id);
  eventStream.onerror = () => {
    eventStream.close();
    if (!pollTimer) pollTimer = setInterval(() => poll(session.id), 1200);
  };
});

elements["preview-link"].addEventListener("click", (event) => {
  event.preventDefault();
  const target = elements["preview-link"].href;
  if (target && target !== `${window.location.origin}/#`) {
    window.location.assign(target);
  }
});

async function refreshWikiStatus() {
  const response = await fetch("/api/wiki/status");
  if (!response.ok) throw new Error("Wiki status unavailable");
  const status = await response.json();
  elements["source-status"].textContent =
    `${status.sources} sources / ${status.pages} pages / ${status.issues} lint issues`;
}

elements["source-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!elements["source-file"].files.length) return;
  elements["source-submit"].disabled = true;
  elements["source-status"].textContent = "Registering source and rebuilding wiki...";
  const body = new FormData();
  body.append("source", elements["source-file"].files[0]);
  const response = await fetch("/api/wiki/sources", { method: "POST", body });
  const payload = await response.json();
  elements["source-submit"].disabled = false;
  if (!response.ok) {
    elements["source-status"].textContent = payload.detail || "Ingestion failed.";
    return;
  }
  elements["source-file"].value = "";
  elements["source-status"].textContent =
    `Ingested ${payload.page} with ${payload.evidence_blocks} evidence blocks.`;
});

elements["compare-runs"].addEventListener("click", async () => {
  const sessions = await fetch("/api/sessions").then((response) => response.json());
  const selected = sessions.filter((item) => item.state === "completed").slice(0, 2);
  if (selected.length < 2) {
    elements.comparison.textContent = "Complete two sessions to compare them.";
    return;
  }
  const query = selected.map((item) => `ids=${encodeURIComponent(item.id)}`).join("&");
  const runs = await fetch(`/api/session-comparisons?${query}`).then((response) => response.json());
  const rows = runs.map((run) => {
    const score = run.scorecard ? `${Math.round(run.scorecard.total * 100)}%` : "n/a";
    const tokens = run.metrics.inputTokens + run.metrics.outputTokens;
    return `<tr><td title="${escapeHtml(run.goal)}">${escapeHtml(run.id.slice(0, 8))}</td>
      <td>${score}</td><td>${tokens}</td><td>${run.metrics.toolCalls}</td></tr>`;
  }).join("");
  elements.comparison.innerHTML = `<table><thead><tr><th>Run</th><th>Score</th>
    <th>Tokens</th><th>Tools</th></tr></thead><tbody>${rows}</tbody></table>`;
});

fetch("/api/health").then((response) => {
  if (!response.ok) throw new Error("offline");
  elements.health.classList.add("online");
  elements.health.lastChild.textContent = " Ready";
}).catch(() => { elements.health.lastChild.textContent = " Offline"; });

renderSteps("created");
refreshWikiStatus().catch(() => { elements["source-status"].textContent = "Wiki unavailable."; });
