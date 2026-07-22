// IoT Device Simulator — UI logic (ES module)
import { setLang, getLang, t, applyTranslations } from "/static/i18n.js";

// ─── DOM helpers ───────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const sensorsEl  = $("sensors");
const logEl      = $("log");
const wsStatus   = $("wsStatus");

let editingId  = null;
let lastList   = [];
let sensorSearch = "";
let logSearch    = "";

// ─── REST helpers ──────────────────────────────────────────────────────────
async function api(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 204) return null;
  if (!r.ok) {
    let detail;
    try { detail = (await r.json()).detail || ""; }
    catch { detail = await r.text(); }
    throw new Error(detail || `HTTP ${r.status}`);
  }
  return r.json();
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ─── Data loading ──────────────────────────────────────────────────────────
async function loadSensors() {
  try { lastList = await api("GET", "/api/sensors"); }
  catch { lastList = []; }
  renderSensors();
}

async function loadMetrics() {
  try {
    const m = await api("GET", "/api/metrics");
    $("metric-running").textContent = t("metric.runningOf", {
      run: m.sensors_running, total: `${m.sensors_total}/${m.max_sensors}`,
    });
    $("metric-msgs").textContent = t("metric.msgs", { n: m.total_messages });
  } catch {}
}

// ─── Rendering ─────────────────────────────────────────────────────────────
function renderSensors() {
  const filter = sensorSearch.trim().toLowerCase();
  const items = !filter ? lastList
    : lastList.filter(s => s.name.toLowerCase().includes(filter) || s.id.includes(filter));

  sensorsEl.innerHTML = "";
  if (!items.length) {
    sensorsEl.innerHTML = `<div class="empty">${t("card.empty")}</div>`;
    return;
  }
  for (const s of items) sensorsEl.appendChild(renderCard(s));
}

function renderCard(s) {
  const card = document.createElement("article");
  card.className = "card";
  card.dataset.sid = s.id;
  card.innerHTML = `
    <div class="card-head">
      <div>
        <h3 class="card-name">${escapeHtml(s.name)}</h3>
        <div class="card-id">#${s.id}</div>
        <div class="card-sub">
          ${s.interval_sec}s${s.jitter_sec ? ` ±${s.jitter_sec}s` : ""} ·
          <span data-msgs>${s.messages_sent}</span> ${t("card.messages")}${
            s.errors ? ` · <span data-errs style="color:var(--bad)">${s.errors} ${t("card.errors")}</span>` : `<span data-errs></span>`
          }
        </div>
      </div>
      <span class="pill ${s.running ? "run" : "stop"}" data-pill>${
        s.running ? t("card.running") : t("card.stopped")
      }</span>
    </div>
    <div class="targets" data-targets>→ ${escapeHtml((s.outputs_summary || []).join(", ")) || "—"}</div>
    <pre class="payload" data-payload>${
      s.last_payload ? escapeHtml(JSON.stringify(s.last_payload, null, 2)) : t("card.noData")
    }</pre>
    <div class="card-actions">
      ${s.running
        ? `<button class="btn-danger  btn-mini" data-act="stop">${t("card.stop")}</button>`
        : `<button class="btn-success btn-mini" data-act="start">${t("card.start")}</button>`
      }
      <button class="btn-ghost btn-mini" data-act="edit">${t("card.edit")}</button>
      <button class="btn-ghost btn-mini" data-act="clone">${t("card.clone")}</button>
      <button class="btn-ghost btn-mini right" data-act="delete">${t("card.delete")}</button>
    </div>`;
  card.addEventListener("click", (ev) => onCardClick(ev, s));
  return card;
}

async function onCardClick(ev, s) {
  const btn = ev.target.closest("button[data-act]");
  if (!btn) return;
  const act = btn.dataset.act;
  btn.disabled = true;
  try {
    if (act === "start")  await api("POST", `/api/sensors/${s.id}/start`);
    else if (act === "stop")  await api("POST", `/api/sensors/${s.id}/stop`);
    else if (act === "clone") await api("POST", `/api/sensors/${s.id}/clone`);
    else if (act === "delete") {
      if (!confirm(t("confirm.delete", { name: s.name }))) return;
      await api("DELETE", `/api/sensors/${s.id}`);
    } else if (act === "edit") {
      openEditor(s); return;
    }
    await loadSensors(); await loadMetrics();
  } catch (e) { alert(e.message); }
  finally { btn.disabled = false; }
}

function updateCardLive(evt) {
  const card = sensorsEl.querySelector(`.card[data-sid="${evt.sensor_id}"]`);
  if (!card) return;
  const pre = card.querySelector("[data-payload]");
  if (pre) pre.textContent = JSON.stringify(evt.payload, null, 2);
  const tg = card.querySelector("[data-targets]");
  if (tg) tg.textContent = "→ " + (evt.targets || []).join(", ");
  const m = card.querySelector("[data-msgs]");
  if (m) m.textContent = evt.count;
  const errs = card.querySelector("[data-errs]");
  if (errs && evt.errors) {
    errs.textContent = ` · ${evt.errors} ${t("card.errors")}`;
    errs.style.color = "var(--bad)";
  }
}

// ─── Log ───────────────────────────────────────────────────────────────────
function logEntryMatchesFilter(div, typeFilter, text) {
  if (typeFilter !== "all") {
    const cls = div.className;
    if (typeFilter === "event" && !["created","deleted","updated"].some(c => cls.includes(c))) return false;
    if (typeFilter !== "event" && !cls.includes(typeFilter)) return false;
  }
  if (text) {
    const raw = div.textContent.toLowerCase();
    if (!raw.includes(text)) return false;
  }
  return true;
}

function refilterLog() {
  const typeFilter = $("logFilter").value;
  const text = logSearch.trim().toLowerCase();
  for (const el of logEl.children) {
    el.hidden = !logEntryMatchesFilter(el, typeFilter, text);
  }
}

function appendLog(evt) {
  const div = document.createElement("div");
  div.className = "log-entry " + (evt.type || "");
  const time = new Date().toLocaleTimeString("en-GB", { hour12: false });

  if (evt.type === "sample") {
    const isAnomaly = evt.payload && evt.payload._anomaly;
    div.innerHTML = `
      <span class="time">${time}</span>
      <span class="name">${escapeHtml(evt.sensor_name)}</span>
      <span class="arrow">→ ${escapeHtml((evt.targets || []).join(", "))}${isAnomaly ? " ⚡" : ""}</span>
      <span class="data">${escapeHtml(JSON.stringify(evt.payload))}</span>`;
  } else if (evt.type === "ingress") {
    div.innerHTML = `<span class="time">${time}</span>` +
      `<span class="name">[INGRESS ${escapeHtml(evt.source || "")}]</span>` +
      `<span class="data">${escapeHtml(JSON.stringify(evt.payload))}</span>`;
  } else if (evt.type === "error") {
    div.innerHTML = `<span class="time">${time}</span>` +
      `<span class="name">${escapeHtml(evt.sensor_name || "ERR")}</span>` +
      `<span class="data">ERROR: ${escapeHtml(evt.message || "")}</span>`;
  } else {
    const icon = { created: "+", deleted: "−", updated: "~" }[evt.type] || "·";
    div.innerHTML = `<span class="time">${time}</span>` +
      `<span class="data">[${icon}] ${evt.type?.toUpperCase()} ${escapeHtml(evt.sensor_name || "")} ${evt.sensor_id || ""}</span>`;
  }

  // apply current filter immediately
  const typeFilter = $("logFilter").value;
  const text = logSearch.trim().toLowerCase();
  div.hidden = !logEntryMatchesFilter(div, typeFilter, text);

  logEl.appendChild(div);
  while (logEl.children.length > 600) logEl.removeChild(logEl.firstChild);
  if ($("autoscroll").checked && !div.hidden) logEl.scrollTop = logEl.scrollHeight;
}

// ─── WebSocket ─────────────────────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen  = () => { wsStatus.textContent = t("ws.connected");    wsStatus.classList.add("on"); };
  ws.onclose = () => {
    wsStatus.textContent = t("ws.disconnected"); wsStatus.classList.remove("on");
    setTimeout(connectWS, 2000);
  };
  ws.onerror = () => { try { ws.close(); } catch {} };
  ws.onmessage = (ev) => {
    let data; try { data = JSON.parse(ev.data); } catch { return; }
    appendLog(data);
    if (data.type === "sample") updateCardLive(data);
    if (["created", "deleted", "updated"].includes(data.type)) {
      loadSensors(); loadMetrics();
    }
  };
}

// ─── Terminal panel resize ─────────────────────────────────────────────────
(function initResize() {
  const panel  = $("terminalPanel");
  const handle = $("termResize");
  let startY, startH;
  handle.addEventListener("mousedown", (e) => {
    startY = e.clientY; startH = panel.offsetHeight;
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", () => document.removeEventListener("mousemove", onMove), { once: true });
  });
  function onMove(e) {
    const delta = startY - e.clientY;
    const newH  = Math.max(120, Math.min(window.innerHeight * .85, startH + delta));
    panel.style.height = newH + "px";
    document.documentElement.style.setProperty("--term-height", newH + "px");
  }
})();

// ─── Editor modal ──────────────────────────────────────────────────────────
const FIELD_DEFAULTS = {
  timestamp:      { type: "timestamp",     name: "ts",    fmt: "iso" },
  fixed_number:   { type: "fixed_number",  name: "value", value: 42 },
  random_number:  { type: "random_number", name: "temp",  min: 0, max: 100, decimals: 2 },
  fixed_string:   { type: "fixed_string",  name: "label", value: "ok" },
  random_string:  { type: "random_string", name: "token", length: 8, charset: "alnum" },
  pattern_string: { type: "pattern_string","name": "id",  pattern: "DEV-{d:4}-{seq}" },
  file:           { type: "file",          name: "value", path: "/app/sample_data/values.txt", mode: "loop" },
  gaussian_number:{ type: "gaussian_number",name: "reading", mean: 20, stddev: 2, decimals: 2 },
  random_walk:    { type: "random_walk",   name: "level", start: 50, step: 1, min: 0, max: 100, decimals: 2 },
  sine_wave:      { type: "sine_wave",     name: "cycle", amplitude: 10, offset: 20, period_sec: 60, phase: 0, noise: 0, decimals: 2 },
  boolean:        { type: "boolean",       name: "flag",  p_true: 0.5 },
  enum:           { type: "enum",          name: "state", values: ["ok","warn","fault"], weights: [] },
  uuid:           { type: "uuid",          name: "uuid" },
  geo_point:      { type: "geo_point",     name: "location", lat: 40.4168, lon: -3.7038, radius_m: 500, decimals: 6 },
};
const OUTPUT_DEFAULTS = {
  screen:      { type: "screen",      enabled: true },
  mqtt:        { type: "mqtt",        enabled: true, host: "broker.hivemq.com", port: 1883,
                 topic: "iot/sim/{sensor}", qos: 0, retain: false, tls: false },
  kafka:       { type: "kafka",       enabled: true, bootstrap_servers: "localhost:9092", topic: "iot-sim" },
  tcp_json:    { type: "tcp_json",    enabled: true, host: "127.0.0.1", port: 5050 },
  file_output: { type: "file_output", enabled: true, path: "/app/output/sensor.log", mode: "append", format: "jsonl" },
  http:        { type: "http",        enabled: true, url: "http://localhost:9000/ingest", method: "POST",
                 timeout_sec: 5, verify_tls: true },
  amqp:        { type: "amqp",        enabled: true, url: "amqp://guest:guest@localhost:5672/",
                 exchange: "", routing_key: "iot.sim.{sensor}" },
  coap:        { type: "coap",        enabled: true, uri: "coap://localhost:5683/ingest", method: "POST" },
};
const FIELD_SCHEMA = {
  timestamp:      [["fmt",    "select", ["iso","epoch_ms","epoch_s"]]],
  fixed_number:   [["value",  "number"]],
  random_number:  [["min","number"],["max","number"],["decimals","number"]],
  fixed_string:   [["value",  "text"]],
  random_string:  [["length", "number"],["charset","select",["alnum","alpha","digits","hex"]]],
  pattern_string: [["pattern","text"]],
  file:           [["path",   "text"],["mode","select",["loop","sequential","random"]]],
  gaussian_number:[["mean","number"],["stddev","number"],["decimals","number"],["min","number"],["max","number"]],
  random_walk:    [["start","number"],["step","number"],["min","number"],["max","number"],["decimals","number"]],
  sine_wave:      [["amplitude","number"],["offset","number"],["period_sec","number"],["phase","number"],["noise","number"],["decimals","number"]],
  boolean:        [["p_true","number"]],
  enum:           [["values","list"],["weights","numlist"]],
  uuid:           [],
  geo_point:      [["lat","number"],["lon","number"],["radius_m","number"],["decimals","number"]],
};
// Encryption sub-fields appended to every transport output (not screen).
const ENC_SCHEMA = [
  ["enc_enabled","checkbox"],
  ["enc_key_b64","text"],
  ["enc_key_env","text"],
];
const OUTPUT_SCHEMA = {
  screen:      [],
  mqtt:        [["host","text"],["port","number"],["topic","text"],["qos","select",[0,1,2]],
                ["retain","checkbox"],["tls","checkbox"],["username","text"],["password","text"],["client_id","text"]],
  kafka:       [["bootstrap_servers","text"],["topic","text"],["key_field","text"]],
  tcp_json:    [["host","text"],["port","number"]],
  file_output: [["path","text"],["mode","select",["append","overwrite"]],["format","select",["jsonl","json_pretty"]]],
  http:        [["url","text"],["method","select",["POST","PUT"]],["bearer_token","text"],
                ["basic_user","text"],["basic_pass","text"],["timeout_sec","number"],["verify_tls","checkbox"]],
  amqp:        [["url","text"],["exchange","text"],["routing_key","text"]],
  coap:        [["uri","text"],["method","select",["POST","PUT"]]],
};
// Outputs that support optional payload encryption.
const ENCRYPTABLE = new Set(["mqtt","kafka","tcp_json","file_output","http","amqp","coap"]);

function openEditor(existing) {
  editingId = existing ? existing.id : null;
  $("modalTitle").textContent = existing ? t("modal.editTitle") : t("modal.newTitle");
  $("f-name").value     = existing ? existing.name : "";
  $("f-interval").value = existing ? existing.interval_sec : 1;
  $("f-jitter").value   = existing ? (existing.jitter_sec ?? 0) : 0;
  $("f-running").checked = existing ? !!existing.running : true;

  const a = existing?.anomaly ?? { enabled: false, probability: 0.05, min_factor: 1.5, max_factor: 3 };
  $("f-anomaly-enabled").checked = !!a.enabled;
  $("f-anomaly-prob").value = a.probability ?? 0.05;
  $("f-anomaly-min").value  = a.min_factor  ?? 1.5;
  $("f-anomaly-max").value  = a.max_factor  ?? 3;

  $("fields-container").innerHTML  = "";
  $("outputs-container").innerHTML = "";
  if (existing) {
    (existing.fields  || []).forEach(f => $("fields-container").appendChild(buildBlock("field",  f)));
    (existing.outputs || []).forEach(o => $("outputs-container").appendChild(buildBlock("output", o)));
  } else {
    $("fields-container").appendChild(buildBlock("field",  { ...FIELD_DEFAULTS.timestamp }));
    $("fields-container").appendChild(buildBlock("field",  { ...FIELD_DEFAULTS.random_number }));
    $("outputs-container").appendChild(buildBlock("output", { ...OUTPUT_DEFAULTS.screen }));
  }
  $("modalBg").hidden = false;
  setTimeout(() => $("f-name").focus(), 50);
}

function closeEditor() { $("modalBg").hidden = true; }

function buildBlock(kind, obj) {
  const el = document.createElement("div");
  el.className = "subblock";
  el.dataset.kind = obj.type;
  el.innerHTML = `
    <div class="subblock-head">
      <span class="subblock-kind">${obj.type}</span>
      <button class="btn-icon" data-remove aria-label="Remove">×</button>
    </div>
    <div class="form-grid"></div>`;
  const grid = el.querySelector(".form-grid");

  if (kind === "field") grid.appendChild(makeInput("name", t("form.name"), "text", obj.name ?? ""));
  if (kind === "output") {
    const w = document.createElement("label");
    w.className = "check-label";
    w.innerHTML = `<input type="checkbox" data-key="enabled" ${obj.enabled !== false ? "checked" : ""}/> <span>${t("form.enabled")}</span>`;
    grid.appendChild(w);
  }
  const schema = (kind === "field" ? FIELD_SCHEMA : OUTPUT_SCHEMA)[obj.type] || [];
  for (const [key, type, options] of schema) {
    grid.appendChild(makeInput(key, key, type, obj[key], options));
  }
  // Optional payload encryption for transport outputs.
  if (kind === "output" && ENCRYPTABLE.has(obj.type)) {
    const enc = obj.encryption || {};
    const flat = {
      enc_enabled: !!enc.enabled,
      enc_key_b64: enc.key_b64 ?? "",
      enc_key_env: enc.key_env ?? "",
    };
    const sep = document.createElement("div");
    sep.className = "enc-sep col-2";
    sep.textContent = "🔒 " + t("form.encryption");
    grid.appendChild(sep);
    for (const [key, type] of ENC_SCHEMA) {
      grid.appendChild(makeInput(key, key.replace("enc_", ""), type, flat[key]));
    }
  }
  el.querySelector("[data-remove]").addEventListener("click", () => el.remove());
  return el;
}

function makeInput(key, label, type, value, options) {
  if (type === "checkbox") {
    const w = document.createElement("label");
    w.className = "check-label";
    w.innerHTML = `<input type="checkbox" data-key="${key}" ${value ? "checked" : ""}/> <span>${escapeHtml(label)}</span>`;
    return w;
  }
  const w = document.createElement("label");
  w.className = "field";
  w.innerHTML = `<span>${escapeHtml(label)}</span>`;
  let inp;
  if (type === "select") {
    inp = document.createElement("select");
    for (const opt of options) {
      const o = document.createElement("option");
      o.value = String(opt); o.textContent = String(opt); inp.appendChild(o);
    }
  } else {
    inp = document.createElement("input");
    inp.type = type === "number" ? "number" : "text";
    if (type === "number") inp.step = "any";
    if (type === "list")    { inp.dataset.list = "str"; inp.placeholder = "a, b, c"; }
    if (type === "numlist") { inp.dataset.list = "num"; inp.placeholder = "1, 2, 3"; }
  }
  // Arrays render as comma-separated text.
  if (Array.isArray(value)) inp.value = value.join(", ");
  else if (value !== undefined && value !== null) inp.value = value;
  inp.dataset.key = key;
  w.appendChild(inp);
  return w;
}

function collectBlock(block) {
  const obj = { type: block.dataset.kind };
  block.querySelectorAll("[data-key]").forEach(inp => {
    const k = inp.dataset.key;
    if (inp.dataset.list) {
      const parts = inp.value.split(",").map(s => s.trim()).filter(s => s !== "");
      obj[k] = inp.dataset.list === "num" ? parts.map(Number) : parts;
    } else if (inp.type === "checkbox") obj[k] = inp.checked;
    else if (inp.type === "number" && inp.value !== "") obj[k] = Number(inp.value);
    else obj[k] = inp.value || null;
  });
  // Reassemble encryption block from flat enc_* keys.
  if ("enc_enabled" in obj) {
    const enabled = obj.enc_enabled;
    const keyB64 = obj.enc_key_b64, keyEnv = obj.enc_key_env;
    delete obj.enc_enabled; delete obj.enc_key_b64; delete obj.enc_key_env;
    if (enabled || keyB64 || keyEnv) {
      obj.encryption = {
        enabled: !!enabled, algorithm: "AES-256-GCM",
        key_b64: keyB64 || null, key_env: keyEnv || null,
      };
    }
  }
  // Empty numlist (weights) should be omitted, not sent as [].
  if (Array.isArray(obj.weights) && obj.weights.length === 0) delete obj.weights;
  return obj;
}

async function saveSensor() {
  const cfg = {
    name: $("f-name").value.trim(),
    interval_sec: Number($("f-interval").value) || 1,
    jitter_sec:   Number($("f-jitter").value)   || 0,
    running: $("f-running").checked,
    fields:  Array.from($("fields-container").children).map(collectBlock),
    outputs: Array.from($("outputs-container").children).map(collectBlock),
    anomaly: {
      enabled:     $("f-anomaly-enabled").checked,
      probability: Number($("f-anomaly-prob").value) || 0,
      min_factor:  Number($("f-anomaly-min").value)  || 1,
      max_factor:  Number($("f-anomaly-max").value)  || 1,
    },
  };
  if (!cfg.name)         { alert(t("alert.nameRequired")); return; }
  if (!cfg.fields.length){ alert(t("alert.fieldsRequired")); return; }
  // strip nulls from optional keys
  cfg.fields.forEach(f => Object.keys(f).forEach(k => { if (f[k] === null) delete f[k]; }));
  cfg.outputs.forEach(o => Object.keys(o).forEach(k => { if (o[k] === null) delete o[k]; }));
  try {
    if (editingId) await api("PUT", `/api/sensors/${editingId}`, cfg);
    else           await api("POST", "/api/sensors", cfg);
    closeEditor();
    await loadSensors(); await loadMetrics();
  } catch (e) { alert(e.message); }
}

// ─── Import / Export ───────────────────────────────────────────────────────
async function exportConfig() {
  const r = await fetch("/api/config/export");
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: "iot-sim-config.json" });
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

async function importConfigFromFile(file) {
  const text = await file.text();
  const replace = confirm(t("confirm.importReplace"));
  // import-raw auto-detects JSON or YAML (YAML is a JSON superset).
  const r = await fetch(`/api/config/import-raw?replace=${replace}`, {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: text,
  });
  if (!r.ok) {
    let detail; try { detail = (await r.json()).detail; } catch { detail = await r.text(); }
    alert(detail || `HTTP ${r.status}`); return;
  }
  await loadSensors(); await loadMetrics();
}

// ─── Examples ────────────────────────────────────────────────────────────
async function openExamples() {
  let list;
  try { list = await api("GET", "/api/examples"); }
  catch { alert(t("alert.examplesFailed")); return; }
  const box = $("examplesList");
  box.innerHTML = "";
  if (!list.length) { box.innerHTML = `<div class="empty">${t("card.empty")}</div>`; }
  for (const ex of list) {
    const el = document.createElement("div");
    el.className = "example-card";
    el.innerHTML = `
      <div class="example-info">
        <h4>${escapeHtml(ex.name)}</h4>
        <p>${escapeHtml(ex.description)}</p>
        <span class="example-meta">${t("examples.sensorCount", { n: ex.sensors })} · ${escapeHtml(ex.id)}</span>
      </div>
      <button class="btn-primary btn-mini" data-load="${escapeHtml(ex.id)}">${t("examples.load")}</button>`;
    el.querySelector("[data-load]").addEventListener("click", async (e) => {
      e.target.disabled = true;
      try {
        await api("POST", `/api/examples/${ex.id}/import`);
        $("examplesModalBg").hidden = true;
        await loadSensors(); await loadMetrics();
      } catch (err) { alert(err.message); e.target.disabled = false; }
    });
    box.appendChild(el);
  }
  $("examplesModalBg").hidden = false;
}

// ─── Theme ─────────────────────────────────────────────────────────────────
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("iot.theme", theme); } catch {}
}
function toggleTheme() {
  setTheme((document.documentElement.dataset.theme || "dark") === "dark" ? "light" : "dark");
}
(() => {
  let s = null; try { s = localStorage.getItem("iot.theme"); } catch {}
  setTheme(s || "dark");
})();

// ─── API docs — dynamic URL injection ─────────────────────────────────────
let _apiUrlsPatched = false;

function patchApiUrls() {
  if (_apiUrlsPatched) return;
  _apiUrlsPatched = true;

  const base    = window.location.origin;
  const wsProto = location.protocol === "https:" ? "wss" : "ws";
  const wsBase  = `${wsProto}://${location.host}`;

  const intro = $("apiIntroText");
  if (intro) {
    intro.innerHTML =
      `Base URL: <code>${base}</code>&nbsp;&nbsp;·&nbsp;&nbsp;` +
      `Swagger UI: <a href="/docs" target="_blank">/docs</a>&nbsp;&nbsp;·&nbsp;&nbsp;` +
      `WebSocket: <code>${wsBase}/ws</code>&nbsp;&nbsp;·&nbsp;&nbsp;` +
      `TCP Ingress: <code>${location.hostname}:5050</code>`;
  }

  document.querySelectorAll(".api-ex").forEach(el => {
    el.textContent = el.textContent
      .replaceAll("http://localhost:8000", base)
      .replaceAll("ws://localhost:8000",  wsBase)
      .replaceAll("localhost 5050",       `${location.hostname} 5050`);
  });
}

// ─── Wire-up ───────────────────────────────────────────────────────────────
$("btnNew").addEventListener("click", () => openEditor(null));
$("btnReload").addEventListener("click", () => { loadSensors(); loadMetrics(); });
$("btnCancel").addEventListener("click", closeEditor);
$("btnCancel2").addEventListener("click", closeEditor);
$("btnSave").addEventListener("click", saveSensor);
$("btnClear").addEventListener("click", () => { logEl.innerHTML = ""; });

$("btnStartAll").addEventListener("click", async () => {
  await api("POST", "/api/sensors/start-all"); loadSensors(); loadMetrics();
});
$("btnStopAll").addEventListener("click", async () => {
  await api("POST", "/api/sensors/stop-all"); loadSensors(); loadMetrics();
});
$("btnExport").addEventListener("click", exportConfig);
$("btnImport").addEventListener("click", () => $("importFile").click());
$("importFile").addEventListener("change", (e) => {
  const f = e.target.files?.[0]; if (f) importConfigFromFile(f); e.target.value = "";
});
$("btnExamples").addEventListener("click", openExamples);
$("btnExamplesClose").addEventListener("click", () => { $("examplesModalBg").hidden = true; });
$("btnExamplesClose2").addEventListener("click", () => { $("examplesModalBg").hidden = true; });
$("examplesModalBg").addEventListener("click", (e) => {
  if (e.target === $("examplesModalBg")) $("examplesModalBg").hidden = true;
});

// API docs modal
$("btnApiDocs").addEventListener("click", () => { patchApiUrls(); $("apiModalBg").hidden = false; });
$("btnApiClose").addEventListener("click",  () => { $("apiModalBg").hidden = true; });
$("btnApiClose2").addEventListener("click", () => { $("apiModalBg").hidden = true; });
$("apiModalBg").addEventListener("click", (e) => { if (e.target === $("apiModalBg")) $("apiModalBg").hidden = true; });

// theme + lang
$("themeToggle").addEventListener("click", toggleTheme);
$("lang").addEventListener("change", (e) => {
  setLang(e.target.value); applyTranslations(); loadSensors(); loadMetrics();
});
$("lang").value = getLang();

// sensor search
$("search").addEventListener("input", (e) => { sensorSearch = e.target.value; renderSensors(); });

// log search
$("logSearch").addEventListener("input", (e) => { logSearch = e.target.value; refilterLog(); });
$("logFilter").addEventListener("change", refilterLog);

// field/output add buttons
document.querySelectorAll("[data-add]").forEach(b => b.addEventListener("click", () => {
  $(`fields-container`).appendChild(buildBlock("field", { ...FIELD_DEFAULTS[b.dataset.add] }));
}));
document.querySelectorAll("[data-add-out]").forEach(b => b.addEventListener("click", () => {
  const type = b.dataset.addOut;
  if (type === "screen") {
    const already = Array.from($("outputs-container").children).some(el => el.dataset.kind === "screen");
    if (already) { alert(t("alert.screenOnce")); return; }
  }
  $("outputs-container").appendChild(buildBlock("output", { ...OUTPUT_DEFAULTS[type] }));
}));

// Esc / backdrop to close editor
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!$("modalBg").hidden) closeEditor();
    if (!$("apiModalBg").hidden) $("apiModalBg").hidden = true;
    if (!$("examplesModalBg").hidden) $("examplesModalBg").hidden = true;
  }
});
$("modalBg").addEventListener("click", (e) => { if (e.target === $("modalBg")) closeEditor(); });

// ─── Boot ──────────────────────────────────────────────────────────────────
loadSensors();
loadMetrics();
connectWS();
setInterval(loadMetrics, 5000);
