// Lightweight i18n helper (English / Spanish).
const dict = {
  en: {
    "app.title": "IoT Device Simulator",
    "ws.connected": "● connected",
    "ws.disconnected": "● disconnected",
    "toolbar.new": "+ New sensor",
    "toolbar.examples": "★ Examples",
    "toolbar.startAll": "▶ Start all",
    "toolbar.stopAll": "■ Stop all",
    "toolbar.export": "⬇ Export",
    "toolbar.import": "⬆ Import",
    "toolbar.reload": "↻ Reload",
    "toolbar.search": "Search…",
    "log.title": "Real-time log",
    "log.autoscroll": "autoscroll",
    "log.clear": "Clear",
    "log.search": "filter log…",
    "log.all": "all",
    "log.samples": "samples",
    "log.ingress": "ingress",
    "log.errors": "errors",
    "log.events": "events",
    "modal.newTitle": "New sensor",
    "modal.editTitle": "Edit sensor",
    "form.name": "Name",
    "form.interval": "Interval (s)",
    "form.jitter": "Jitter (s)",
    "form.startOnCreate": "start on save",
    "form.fields": "Fields",
    "form.outputs": "Outputs",
    "form.cancel": "Cancel",
    "form.save": "Save",
    "form.anomaly": "Anomaly injection",
    "form.encryption": "Payload encryption (AES-256-GCM)",
    "form.enabled": "enabled",
    "form.probability": "Probability",
    "form.minFactor": "Min factor",
    "form.maxFactor": "Max factor",
    "form.anomalyEnable": "Enable",
    "form.anomalyHint": "When triggered, a random numeric field is multiplied by a factor in the given range. The payload gains an _anomaly key for downstream detection.",
    "form.addField": "Add:",
    "form.addOutput": "Add:",
    "api.title": "REST API Reference",
    "api.intro": "Base URL: http://<host>:8000 · Interactive Swagger UI: /docs · WebSocket: ws://<host>:8000/ws",
    "api.swagger": "Open Swagger UI ↗",
    "toolbar.apiDocs": "{ } API",
    "card.running": "● running",
    "card.stopped": "○ stopped",
    "card.start": "Start",
    "card.stop": "Stop",
    "card.edit": "Edit",
    "card.clone": "Clone",
    "card.delete": "Delete",
    "card.messages": "messages",
    "card.errors": "errors",
    "card.empty": "No sensors yet. Click “+ New sensor” to begin.",
    "card.noData": "(no data yet)",
    "confirm.delete": "Delete sensor \"{name}\"?",
    "confirm.deleteAll": "Delete all sensors?",
    "confirm.importReplace": "Replace existing sensors with the imported configuration?",
    "alert.nameRequired": "Name is required.",
    "alert.fieldsRequired": "Add at least one field.",
    "alert.screenOnce": "Screen output can only be added once.",
    "alert.examplesFailed": "Could not load examples.",
    "metric.runningOf": "{run}/{total} running",
    "metric.msgs": "{n} msgs",
    "examples.title": "Example scenarios",
    "examples.hint": "Ready-to-run industry scenarios. Loading one adds its sensors to the current simulation (names are auto-suffixed on conflict).",
    "examples.load": "Load",
    "examples.sensorCount": "{n} sensor(s)",
  },
  es: {
    "app.title": "Simulador de Dispositivos IoT",
    "ws.connected": "● conectado",
    "ws.disconnected": "● desconectado",
    "toolbar.new": "+ Nuevo sensor",
    "toolbar.examples": "★ Ejemplos",
    "toolbar.startAll": "▶ Iniciar todos",
    "toolbar.stopAll": "■ Detener todos",
    "toolbar.export": "⬇ Exportar",
    "toolbar.import": "⬆ Importar",
    "toolbar.reload": "↻ Recargar",
    "toolbar.search": "Buscar…",
    "log.title": "Log en tiempo real",
    "log.autoscroll": "autoscroll",
    "log.clear": "Limpiar",
    "log.search": "filtrar log…",
    "log.all": "todo",
    "log.samples": "muestras",
    "log.ingress": "ingress",
    "log.errors": "errores",
    "log.events": "eventos",
    "modal.newTitle": "Nuevo sensor",
    "modal.editTitle": "Editar sensor",
    "form.name": "Nombre",
    "form.interval": "Intervalo (s)",
    "form.jitter": "Jitter (s)",
    "form.startOnCreate": "iniciar al guardar",
    "form.fields": "Campos",
    "form.outputs": "Salidas",
    "form.cancel": "Cancelar",
    "form.save": "Guardar",
    "form.anomaly": "Inyección de anomalías",
    "form.encryption": "Cifrado del payload (AES-256-GCM)",
    "form.enabled": "activado",
    "form.probability": "Probabilidad",
    "form.minFactor": "Factor mín.",
    "form.maxFactor": "Factor máx.",
    "form.anomalyEnable": "Activar",
    "form.anomalyHint": "Al activarse, un campo numérico aleatorio es multiplicado por un factor en el rango dado. El payload incluye la clave _anomaly para detección downstream.",
    "form.addField": "Añadir:",
    "form.addOutput": "Añadir:",
    "api.title": "Referencia API REST",
    "api.intro": "URL base: http://<host>:8000 · Swagger UI: /docs · WebSocket: ws://<host>:8000/ws",
    "api.swagger": "Abrir Swagger UI ↗",
    "toolbar.apiDocs": "{ } API",
    "card.running": "● ejecutando",
    "card.stopped": "○ parado",
    "card.start": "Iniciar",
    "card.stop": "Detener",
    "card.edit": "Editar",
    "card.clone": "Clonar",
    "card.delete": "Eliminar",
    "card.messages": "mensajes",
    "card.errors": "errores",
    "card.empty": "Aún no hay sensores. Pulsa “+ Nuevo sensor” para empezar.",
    "card.noData": "(sin datos aún)",
    "confirm.delete": "¿Eliminar sensor \"{name}\"?",
    "confirm.deleteAll": "¿Eliminar todos los sensores?",
    "confirm.importReplace": "¿Reemplazar los sensores actuales por la configuración importada?",
    "alert.nameRequired": "El nombre es obligatorio.",
    "alert.fieldsRequired": "Añade al menos un campo.",
    "alert.screenOnce": "La salida de pantalla solo se puede añadir una vez.",
    "alert.examplesFailed": "No se pudieron cargar los ejemplos.",
    "metric.runningOf": "{run}/{total} en ejecución",
    "metric.msgs": "{n} msgs",
    "examples.title": "Escenarios de ejemplo",
    "examples.hint": "Escenarios listos para usar. Al cargar uno se añaden sus sensores a la simulación actual (los nombres se renombran automáticamente si hay conflicto).",
    "examples.load": "Cargar",
    "examples.sensorCount": "{n} sensor(es)",
  },
};

let current = "en";

export function setLang(lang) {
  if (!dict[lang]) lang = "en";
  current = lang;
  try { localStorage.setItem("iot.lang", lang); } catch {}
  document.documentElement.lang = lang;
  applyTranslations();
}

export function getLang() { return current; }

export function t(key, vars) {
  let s = (dict[current] && dict[current][key]) || (dict.en[key] || key);
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

export function applyTranslations() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
}

// initial language pick
const saved = (() => { try { return localStorage.getItem("iot.lang"); } catch { return null; } })();
const navLang = (navigator.language || "en").slice(0, 2).toLowerCase();
setLang(saved || (dict[navLang] ? navLang : "en"));
