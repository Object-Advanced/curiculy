const TITLES = {
  dashboard: "Home",
  assignments: "Calendar",
  students: "My day",
  curricula: "Curriculum catalog",
  portfolios: "Portfolios",
  settings: "Settings",
  "my-work": "My work",
};

const THEME_KEY = "theme";

const SETTINGS_PANELS = {
  students: "students",
  exceptions: "exceptions",
  years: "school-years",
  enrollments: "enrollments",
  admin: "admin",
};

const SETTINGS_ALIASES = {
  calendar: "#/settings/exceptions",
  years: "#/settings/school-years",
  "school-years": "#/settings/school-years",
  enrollments: "#/settings/enrollments",
  admin: "#/settings/admin",
};

const EXCEPTION_KINDS = ["vacation", "appointment", "sick", "holiday", "other"];
const DEFAULT_EXCEPTION_COLORS = {
  holiday: "#c2410c",
  vacation: "#2563eb",
  sick: "#7c3aed",
  appointment: "#0f766e",
  other: "#dc2626",
};
const SOURCE_TYPES = ["manual", "barcode", "parsed_textbook"];
const LESSON_CATEGORIES = ["Not graded", "Daily Work", "Quiz", "Test", "Routine/Break"];
const AUTH_TOKEN_KEY = "auth_token";

const PERIODS = ["day", "week", "month"];
// The backend anchors weeks on Monday, so the grid has to start there too.
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ALL_STUDENTS = "all";
const DEFAULT_STUDENT_COLOR = "#356b46";
const STUDENT_COLOR_PALETTE = [
  "#356b46",
  "#5a9a6a",
  "#1f7a5c",
  "#8fbc6a",
  "#164a32",
  "#6bbf8a",
];
const studentEditor = { id: null };
const lessonBuilder = {
  planId: null,
  tab: "assignments",
  lines: [],
  weights: [],
};
let lessonLineSeq = 1;
const applyPlanState = { planId: null, title: "" };
const recalibrate = {
  studentId: null,
  step: 1,
  options: null,
  strategy: "extend_year",
  busy: false,
};

const STATUSES = ["assigned", "in_progress", "completed", "skipped", "excused"];
const REPORT_TYPES = [
  ["state_evaluation_log", "State Evaluation Log"],
  ["reading_list", "Reading List"],
  ["work_samples", "Work Samples"],
  ["custom", "Custom"],
];
const SCORE_TYPES = [
  "percentage",
  "letter",
  "points",
  "pass_fail",
  "complete_incomplete",
  "custom",
];

// Dates are handled in UTC throughout. The API speaks plain YYYY-MM-DD, and
// parsing those in local time shifts them a day for anyone west of Greenwich.
const UTC = { timeZone: "UTC" };
const FULL_DATE = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  ...UTC,
});
const MEDIUM_DATE = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  ...UTC,
});
const MONTH_YEAR = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", ...UTC });
const SHORT_DATE = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  ...UTC,
});
const SHORT_TIME = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
});
const EVIDENCE_DRAG_TYPE = "application/x-curiculy-evidence";
const EVIDENCE_INBOX_COLLAPSED_KEY = "evidence-inbox-collapsed";
const PAPERCLIP_ICON = `<svg class="cal-event-clip-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M21.44 11.05l-9.19 9.19a6 6 0 1 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 1 1-2.83-2.83l8.49-8.48"/></svg>`;

function emptyPortfolioCustom() {
  return {
    studentIds: [],
    allStudents: false,
    startDate: "",
    endDate: "",
    includeAttendance: true,
    includeLessons: true,
    includeAssignments: true,
    includeBooks: true,
    includeBooksCompleted: true,
    includeBooksInProgress: true,
    includeBooksIncomplete: true,
    includeAttachments: true,
    includeNotes: true,
  };
}

const state = {
  household: null,
  students: [],
  curricula: [],
  years: [],
  enrollments: [],
  exceptions: [],
  attendance: [],
  currentPeriod: "week",
  currentAnchorDate: null,
  calendarStudentId: null,
  calendar: null,
  evidenceStaging: [],
  curriculumFilter: "unscheduled",
  catalogKind: "books",
  curriculumPlans: [],
  dashboardAssignments: [],
  dashboardCourses: [],
  inviteKeys: [],
  captureTokenStatus: { active: false, created_at: null, expires_at: null },
  captureTokenSecret: "",
  devMode: false,
  schoolYear: null,
  exceptionColors: null,
  dashboardMonth: null,
  sessionUser: null,
  notifications: { unread_count: 0, notifications: [] },
  kidWork: [],
  homework: { session: null, assignmentId: null, busy: false },
  switchUsers: [],
  studentLoginEmail: "",
  portfolio: {
    studentId: null,
    schoolYearId: null,
    reportType: "state_evaluation_log",
    custom: emptyPortfolioCustom(),
  },
};

function $(id) {
  return document.getElementById(id);
}

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function syncThemeToggle() {
  const button = $("theme-toggle");
  if (!button) return;
  const dark = currentTheme() === "dark";
  button.setAttribute("aria-pressed", String(dark));
  button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  const icon = button.querySelector(".theme-toggle-icon");
  const label = button.querySelector(".theme-toggle-label");
  if (icon) icon.textContent = dark ? "☀️" : "🌙";
  if (label) label.textContent = dark ? "Light mode" : "Dark mode";
}

function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  if (next === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    /* private mode */
  }
  syncThemeToggle();
  if (dashboardChartStats && $("todayProgressChart")) {
    paintDashboardCharts(dashboardChartStats);
  }
}

function toggleTheme() {
  applyTheme(currentTheme() === "dark" ? "light" : "dark");
}

function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem(THEME_KEY);
  } catch {
    saved = null;
  }
  if (saved === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

initTheme();

function routeSegments() {
  const hash = (window.location.hash.replace(/^#\/?/, "") || "dashboard").replace(/\/+$/, "");
  return hash.split("/").filter(Boolean);
}

function routeName() {
  const [name] = routeSegments();
  if (name === "my-work") return "my-work";
  if (name in SETTINGS_ALIASES) return "settings";
  return TITLES[name] ? name : "dashboard";
}

function settingsPanel() {
  const [name, panel] = routeSegments();
  const panels = new Set(Object.values(SETTINGS_PANELS));
  if (name === "settings" && panel === SETTINGS_PANELS.admin && !currentUserIsAdmin()) {
    return SETTINGS_PANELS.students;
  }
  if (name === "settings" && panels.has(panel)) return panel;
  if (name === "calendar") return SETTINGS_PANELS.exceptions;
  if (name === "years" || name === "school-years") return SETTINGS_PANELS.years;
  if (name === "enrollments") return SETTINGS_PANELS.enrollments;
  if (name === "admin") return currentUserIsAdmin() ? SETTINGS_PANELS.admin : SETTINGS_PANELS.students;
  return SETTINGS_PANELS.students;
}

function emptyToNull(value) {
  const trimmed = (value || "").trim();
  return trimmed === "" ? null : trimmed;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseISODate(text) {
  const [year, month, day] = text.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function toISODate(date) {
  return date.toISOString().slice(0, 10);
}

function todayISO() {
  const now = new Date();
  return toISODate(new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())));
}

function mondayIndex(date) {
  return (date.getUTCDay() + 6) % 7;
}

function shiftAnchor(iso, period, direction) {
  const date = parseISODate(iso);
  if (period === "month") {
    // Snapping to the 1st first stops 31 January + 1 month landing in March.
    date.setUTCDate(1);
    date.setUTCMonth(date.getUTCMonth() + direction);
  } else {
    date.setUTCDate(date.getUTCDate() + direction * (period === "week" ? 7 : 1));
  }
  return toISODate(date);
}

function addDays(iso, count) {
  const date = parseISODate(iso);
  date.setUTCDate(date.getUTCDate() + count);
  return toISODate(date);
}

function calendarDateWindow(period, anchorISO) {
  const anchor = parseISODate(anchorISO);
  if (period === "day") {
    const iso = toISODate(anchor);
    return { start: iso, end: iso };
  }
  if (period === "week") {
    const start = parseISODate(anchorISO);
    start.setUTCDate(start.getUTCDate() - mondayIndex(start));
    const end = new Date(start);
    end.setUTCDate(start.getUTCDate() + 6);
    return { start: toISODate(start), end: toISODate(end) };
  }
  const start = new Date(Date.UTC(anchor.getUTCFullYear(), anchor.getUTCMonth(), 1));
  const end = new Date(Date.UTC(anchor.getUTCFullYear(), anchor.getUTCMonth() + 1, 0));
  return { start: toISODate(start), end: toISODate(end) };
}

function weekMondayISO(iso) {
  return calendarDateWindow("week", iso || todayISO()).start;
}

function dayRange(startISO, endISO) {
  const days = [];
  const cursor = parseISODate(startISO);
  const last = parseISODate(endISO);
  while (cursor <= last) {
    days.push(toISODate(cursor));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return days;
}

function humanize(value) {
  const text = String(value ?? "").replaceAll("_", " ");
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

const SYNC_DB_NAME = "curiculy-sync";
const SYNC_DB_VERSION = 1;
const OUTBOX_STORE = "outbox";
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const OFFLINE_QUEUED = Object.freeze({ __offlineQueued: true });

function isOfflineQueued(result) {
  return result === OFFLINE_QUEUED || Boolean(result && result.__offlineQueued);
}

function isNetworkFailure(error) {
  return error instanceof TypeError;
}

function shouldQueueRequest(options) {
  const method = String(options.method || "GET").toUpperCase();
  return MUTATING_METHODS.has(method) && !options.skipAuth && !options.skipOutbox;
}

function openSyncDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(SYNC_DB_NAME, SYNC_DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(OUTBOX_STORE)) {
        db.createObjectStore(OUTBOX_STORE, { keyPath: "id", autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("IndexedDB open failed"));
  });
}

function idbReq(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function idbTxDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

async function outboxAdd(record) {
  const db = await openSyncDb();
  try {
    const tx = db.transaction(OUTBOX_STORE, "readwrite");
    tx.objectStore(OUTBOX_STORE).add(record);
    await idbTxDone(tx);
  } finally {
    db.close();
  }
}

async function outboxAll() {
  const db = await openSyncDb();
  try {
    return await idbReq(db.transaction(OUTBOX_STORE, "readonly").objectStore(OUTBOX_STORE).getAll());
  } finally {
    db.close();
  }
}

async function outboxDelete(id) {
  const db = await openSyncDb();
  try {
    const tx = db.transaction(OUTBOX_STORE, "readwrite");
    tx.objectStore(OUTBOX_STORE).delete(id);
    await idbTxDone(tx);
  } finally {
    db.close();
  }
}

function serializeRequestBody(body) {
  if (body == null || body === "") {
    return { bodyKind: "empty", body: null };
  }
  if (typeof FormData !== "undefined" && body instanceof FormData) {
    const parts = [];
    for (const [name, value] of body.entries()) {
      if (typeof value === "string") {
        parts.push({ name, kind: "string", value });
        continue;
      }
      const type = value.type || "application/octet-stream";
      const filename = value.name || "file";
      const blob = value.slice(0, value.size, type);
      parts.push({ name, kind: "blob", blob, filename, type });
    }
    return { bodyKind: "formdata", body: parts };
  }
  if (typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams) {
    return { bodyKind: "urlencoded", body: body.toString() };
  }
  if (typeof Blob !== "undefined" && body instanceof Blob) {
    return {
      bodyKind: "blob",
      body: body.slice(0, body.size, body.type),
      type: body.type,
    };
  }
  return { bodyKind: "text", body: typeof body === "string" ? body : String(body) };
}

function restoreRequestBody(record) {
  if (record.bodyKind === "formdata") {
    const form = new FormData();
    for (const part of record.body || []) {
      if (part.kind === "blob") {
        form.append(part.name, part.blob, part.filename || "file");
      } else {
        form.append(part.name, part.value);
      }
    }
    return form;
  }
  if (record.bodyKind === "urlencoded" || record.bodyKind === "text") {
    return record.body;
  }
  if (record.bodyKind === "blob") {
    return record.body;
  }
  return undefined;
}

function replayHeaders(record) {
  const headers = { ...(record.headers || {}) };
  if (record.bodyKind === "formdata") {
    delete headers["Content-Type"];
    delete headers["content-type"];
  }
  return headers;
}

async function flushOutbox() {
  const items = await outboxAll();
  let incomplete = false;
  for (const item of items) {
    try {
      const response = await fetch(item.url, {
        method: item.method,
        headers: replayHeaders(item),
        body: restoreRequestBody(item),
      });
      if (response.ok) {
        await outboxDelete(item.id);
        continue;
      }
      incomplete = true;
    } catch {
      incomplete = true;
    }
  }
  if (incomplete) {
    throw new Error("Outbox sync incomplete");
  }
}

function registerOutboxSync() {
  if ("serviceWorker" in navigator) {
    return navigator.serviceWorker.ready
      .then((sw) => sw.sync.register("sync-outbox"))
      .catch(() => {
        if (navigator.serviceWorker.controller) {
          navigator.serviceWorker.controller.postMessage({ type: "sync-outbox" });
          return;
        }
        return flushOutbox().catch(() => {});
      });
  }
  return flushOutbox().catch(() => {});
}

async function enqueueOutboxRequest(path, fetchOptions) {
  const serialized = serializeRequestBody(fetchOptions.body);
  const headers = { ...(fetchOptions.headers || {}) };
  if (serialized.bodyKind === "formdata") {
    delete headers["Content-Type"];
    delete headers["content-type"];
  }
  await outboxAdd({
    url: `/api${path}`,
    method: String(fetchOptions.method || "POST").toUpperCase(),
    headers,
    bodyKind: serialized.bodyKind,
    body: serialized.body,
    createdAt: Date.now(),
  });
  showOfflineSavedToast();
  await registerOutboxSync();
  return OFFLINE_QUEUED;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  // FormData has to set its own multipart boundary; a JSON content-type
  // would stop the browser from attaching the file.
  if (options.body instanceof URLSearchParams) {
    headers["Content-Type"] = headers["Content-Type"] || "application/x-www-form-urlencoded";
  } else if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  const token = getAuthToken();
  if (token && !options.skipAuth) {
    headers.Authorization = `Bearer ${token}`;
  }
  const queueable = shouldQueueRequest(options);
  const fetchOptions = { ...options, headers };
  delete fetchOptions.skipAuth;
  delete fetchOptions.skipOutbox;

  if (queueable && typeof navigator !== "undefined" && navigator.onLine === false) {
    return enqueueOutboxRequest(path, fetchOptions);
  }

  let res;
  try {
    res = await fetch(`/api${path}`, fetchOptions);
  } catch (error) {
    if (queueable && isNetworkFailure(error)) {
      return enqueueOutboxRequest(path, fetchOptions);
    }
    throw error;
  }
  const text = await res.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    if (res.status === 401 && !options.skipAuth) {
      handleUnauthorized();
    }
    const detail = body && typeof body === "object" ? body.detail : body;
    let message;
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      message = typeof first === "string" ? first : first.msg || `Request failed (${res.status})`;
    } else {
      message = `Request failed (${res.status})`;
    }
    const error = new Error(message);
    error.status = res.status;
    throw error;
  }
  return body;
}

function flash(message, isError = false) {
  const el = $("flash");
  el.hidden = !message;
  el.textContent = message || "";
  el.classList.toggle("error", Boolean(isError));
}

let uploadQueue = 0;
let uploadFailures = 0;
let uploadToastEpoch = 0;
let uploadToastTimer = null;
let lastUploadError = "";
let queueUploads = 0;
let queueEmails = 0;
let batchUploads = false;
let batchEmails = false;
let offlineQueuedPending = false;

function uploadingLabel() {
  const files = queueUploads;
  const emails = queueEmails;
  if (emails && !files) {
    return emails === 1 ? "Sending email..." : `Sending ${emails} emails...`;
  }
  if (files && !emails) {
    return files === 1 ? "Uploading 1 file..." : `Uploading ${files} files...`;
  }
  const fileBit = files === 1 ? "1 file" : `${files} files`;
  const emailBit = emails === 1 ? "1 email" : `${emails} emails`;
  return `Sending ${fileBit} and ${emailBit}...`;
}

function uploadToastElement() {
  let el = $("upload-toast");
  if (el) {
    el.classList.remove("is-leaving");
    return el;
  }
  el = document.createElement("div");
  el.id = "upload-toast";
  el.className = "toast toast-progress";
  el.setAttribute("role", "status");
  el.innerHTML = `
    <span class="toast-accent" aria-hidden="true"></span>
    <div class="toast-body">
      <p class="toast-title"></p>
      <p class="toast-detail" hidden></p>
    </div>
    <span class="toast-icon" aria-hidden="true"></span>
    <span class="toast-bar" aria-hidden="true"></span>`;
  $("toast-container").appendChild(el);
  return el;
}

function setUploadToast(state, title, detail = "") {
  const el = uploadToastElement();
  el.classList.remove("toast-progress", "toast-success", "toast-error");
  el.classList.add(`toast-${state}`);
  el.setAttribute("role", state === "error" ? "alert" : "status");
  el.querySelector(".toast-title").textContent = title;
  const detailEl = el.querySelector(".toast-detail");
  if (detail) {
    detailEl.hidden = false;
    detailEl.textContent = detail;
  } else {
    detailEl.hidden = true;
    detailEl.textContent = "";
  }
}

function showUploadProgressToast() {
  uploadToastEpoch += 1;
  if (uploadToastTimer) {
    clearTimeout(uploadToastTimer);
    uploadToastTimer = null;
  }
  setUploadToast("progress", uploadingLabel());
}

function dismissUploadToast(epoch) {
  const el = $("upload-toast");
  if (!el || epoch !== uploadToastEpoch) return;
  el.classList.add("is-leaving");
  const remove = () => {
    if (epoch !== uploadToastEpoch) return;
    el.remove();
  };
  el.addEventListener("animationend", remove, { once: true });
  setTimeout(remove, 400);
}

function finishToastTitle(ok) {
  if (ok && offlineQueuedPending) {
    offlineQueuedPending = false;
    return "Saved for offline sync.";
  }
  if (batchEmails && !batchUploads) {
    return ok ? "Email Sent!" : "Email Failed";
  }
  if (batchUploads && !batchEmails) {
    return ok ? "Upload Complete" : "Upload Failed";
  }
  return ok ? "All sent" : "Send Failed";
}

function showOfflineSavedToast() {
  if (uploadQueue > 0) {
    offlineQueuedPending = true;
    return;
  }
  uploadToastEpoch += 1;
  if (uploadToastTimer) {
    clearTimeout(uploadToastTimer);
    uploadToastTimer = null;
  }
  setUploadToast("success", "Saved for offline sync.");
  const epoch = uploadToastEpoch;
  uploadToastTimer = setTimeout(() => dismissUploadToast(epoch), 3000);
}

function finishUploadToast(ok) {
  setUploadToast(ok ? "success" : "error", finishToastTitle(ok), ok ? "" : lastUploadError);
  const epoch = uploadToastEpoch;
  uploadToastTimer = setTimeout(() => dismissUploadToast(epoch), 3000);
}

function showToast(kind, title, detail = "") {
  const container = $("toast-container");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast toast-${kind}`;
  el.setAttribute("role", kind === "error" ? "alert" : "status");
  el.innerHTML = `
    <span class="toast-accent" aria-hidden="true"></span>
    <div class="toast-body">
      <p class="toast-title"></p>
      <p class="toast-detail" hidden></p>
    </div>
    <span class="toast-icon" aria-hidden="true"></span>
    <span class="toast-bar" aria-hidden="true"></span>`;
  el.querySelector(".toast-title").textContent = title;
  const detailEl = el.querySelector(".toast-detail");
  if (detail) {
    detailEl.hidden = false;
    detailEl.textContent = detail;
  }
  container.appendChild(el);
  window.setTimeout(() => {
    el.classList.add("is-leaving");
    el.addEventListener("animationend", () => el.remove(), { once: true });
    window.setTimeout(() => el.remove(), 400);
  }, 3200);
}

function beginBackgroundJob(kind) {
  if (uploadQueue === 0) {
    uploadFailures = 0;
    lastUploadError = "";
    batchUploads = false;
    batchEmails = false;
    queueUploads = 0;
    queueEmails = 0;
    offlineQueuedPending = false;
  }
  if (kind === "email") {
    queueEmails += 1;
    batchEmails = true;
  } else {
    queueUploads += 1;
    batchUploads = true;
  }
  uploadQueue += 1;
  showUploadProgressToast();
}

function studentName(id) {
  const student = state.students.find((item) => item.id === id);
  return student ? student.name : `Student #${id}`;
}

function firstName(name) {
  const text = String(name || "").trim();
  return text.split(/\s+/)[0] || "there";
}

function validStudentColor(value) {
  return typeof value === "string" && /^#[0-9A-Fa-f]{6}$/.test(value)
    ? value
    : "";
}

function colorWithAlpha(hex, alpha) {
  const raw = validStudentColor(hex) || DEFAULT_STUDENT_COLOR;
  const r = parseInt(raw.slice(1, 3), 16);
  const g = parseInt(raw.slice(3, 5), 16);
  const b = parseInt(raw.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function rosterColor(id) {
  const student = state.students.find((item) => item.id === id);
  return validStudentColor(student?.color_hex);
}

function studentColor(id) {
  return rosterColor(id) || DEFAULT_STUDENT_COLOR;
}

function nextStudentColor() {
  const taken = new Set(
    state.students.map((student) =>
      (validStudentColor(student.color_hex) || DEFAULT_STUDENT_COLOR).toLowerCase()
    )
  );
  return (
    STUDENT_COLOR_PALETTE.find((color) => !taken.has(color.toLowerCase())) ||
    STUDENT_COLOR_PALETTE[state.students.length % STUDENT_COLOR_PALETTE.length]
  );
}

function studentChartColor(student) {
  const id = student?.student_id ?? student?.id;
  return rosterColor(id) || validStudentColor(student?.color_hex) || DEFAULT_STUDENT_COLOR;
}

function studentColorStyle(studentOrId) {
  const hex =
    typeof studentOrId === "object"
      ? rosterColor(studentOrId?.id) ||
        validStudentColor(studentOrId?.color_hex) ||
        DEFAULT_STUDENT_COLOR
      : studentColor(studentOrId);
  return `--student-color: ${hex}`;
}

function assignmentColorStyle(item) {
  const hex =
    rosterColor(item.student_id) ||
    validStudentColor(item.color_hex) ||
    DEFAULT_STUDENT_COLOR;
  return `--student-color: ${hex}`;
}

function curriculumTitle(id) {
  const item = state.curricula.find((entry) => entry.id === id);
  return item ? item.title : `Curriculum #${id}`;
}

function yearName(id) {
  const item = state.years.find((entry) => entry.id === id);
  return item ? item.name : `Year #${id}`;
}

const HOUSEHOLD_ICONS = [
  { id: "letter", label: "Letter from name" },
  { id: "apple", emoji: "🍎", label: "Apple" },
  { id: "books", emoji: "📚", label: "Books" },
  { id: "pencil", emoji: "✏️", label: "Pencil" },
  { id: "backpack", emoji: "🎒", label: "Backpack" },
  { id: "school", emoji: "🏫", label: "Schoolhouse" },
  { id: "notebook", emoji: "📝", label: "Notebook" },
  { id: "cap", emoji: "🎓", label: "Graduation cap" },
  { id: "crayon", emoji: "🖍️", label: "Crayon" },
  { id: "globe", emoji: "🌍", label: "Globe" },
  { id: "abacus", emoji: "🧮", label: "Abacus" },
  { id: "telescope", emoji: "🔭", label: "Telescope" },
  { id: "tree", emoji: "🌳", label: "Tree" },
];

function householdInitial(name) {
  const words = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "C";
  const start = words[0].toLowerCase() === "the" && words.length > 1 ? 1 : 0;
  const letter = words[start].charAt(0);
  return letter ? letter.toUpperCase() : "C";
}

function householdIconId(household) {
  const id = String(household?.icon || "letter").trim().toLowerCase();
  return HOUSEHOLD_ICONS.some((item) => item.id === id) ? id : "letter";
}

function householdAvatarGlyph(household) {
  const id = householdIconId(household);
  if (id !== "letter") {
    const match = HOUSEHOLD_ICONS.find((item) => item.id === id);
    if (match?.emoji) return match.emoji;
  }
  return household?.letter || householdInitial(household?.name);
}

function paintHouseholdChrome(household) {
  state.household = household;
  if (currentUserIsChild()) return;
  const name = household?.name || "Household";
  const label = $("household-label");
  if (label) {
    label.textContent = name;
    label.title = name;
  }
  const avatar = $("user-avatar");
  if (avatar) {
    const glyph = householdAvatarGlyph(household);
    avatar.textContent = glyph;
    avatar.classList.toggle("is-emoji", householdIconId(household) !== "letter");
  }
}

function deviceTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    return "";
  }
}

// "Today" on the server follows the household's time zone. Households made
// before that existed have none, so the first parent visit fills it in.
async function rememberDeviceTimeZone(household) {
  const zone = deviceTimeZone();
  if (!zone || household?.timezone || currentUserIsChild()) return household;
  try {
    const updated = await api("/household", {
      method: "PATCH",
      body: JSON.stringify({ timezone: zone }),
      skipOutbox: true,
    });
    return updated || household;
  } catch {
    return household;
  }
}

async function loadHousehold() {
  const household = await api("/household");
  paintHouseholdChrome(household);
  if (!household?.timezone) {
    paintHouseholdChrome(await rememberDeviceTimeZone(household));
  }
}

async function useDeviceTimeZone() {
  const zone = deviceTimeZone();
  if (!zone) return;
  try {
    const updated = await api("/household", {
      method: "PATCH",
      body: JSON.stringify({ timezone: zone }),
    });
    if (!isOfflineQueued(updated)) paintHouseholdChrome(updated);
    render();
    flash(`Time zone set to ${zone}.`);
  } catch (error) {
    flash(error.message, true);
  }
}

async function setHouseholdIcon(icon) {
  const id = String(icon || "letter").trim().toLowerCase();
  try {
    const result = await api("/household", {
      method: "PATCH",
      body: JSON.stringify({ icon: id }),
    });
    if (isOfflineQueued(result)) {
      paintHouseholdChrome({
        ...(state.household || {}),
        icon: id === "letter" ? null : id,
      });
    } else {
      paintHouseholdChrome(result);
    }
    render();
    flash("Saved.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function loadStudents() {
  state.students = await api("/students");
}

let planStatusPollTimer = 0;
let pdfImportBusy = false;
let paperTemplateBusy = false;
let paperImportBusy = false;
let paperImportPhase = "";
let paperImportPlanId = 0;
let paperImportPollTimer = 0;
const PLAN_STATUS_POLL_MS = 4000;
const PAPER_IMPORT_POLL_MS = 2500;

function stopPlanStatusPolling() {
  if (planStatusPollTimer) {
    window.clearTimeout(planStatusPollTimer);
    planStatusPollTimer = 0;
  }
}

function anyPlanProcessing() {
  return (state.curriculumPlans || []).some((item) => item.status === "processing");
}

function planStatusSnapshot(plans) {
  return (plans || [])
    .map((item) => `${item.id}:${item.status}:${item.lesson_count}`)
    .join("|");
}

function notifyPlanStatusChanges(previousPlans, nextPlans) {
  const previous = new Map((previousPlans || []).map((plan) => [plan.id, plan.status]));
  for (const plan of nextPlans || []) {
    if (plan.id === paperImportPlanId) continue;
    if (previous.get(plan.id) !== "processing") continue;
    if (plan.status === "ready") {
      const count = Number(plan.lesson_count) || 0;
      const lessonLabel = count === 1 ? "1 lesson" : `${count} lessons`;
      showToast("success", `${plan.title} is ready`, `${lessonLabel} parsed from the PDF.`);
    } else if (plan.status === "failed") {
      showToast("error", `${plan.title} could not be parsed`);
    }
  }
}

function syncPlanStatusPolling() {
  stopPlanStatusPolling();
  if (!anyPlanProcessing()) return;
  planStatusPollTimer = window.setTimeout(async () => {
    planStatusPollTimer = 0;
    const previousPlans = state.curriculumPlans;
    const previous = planStatusSnapshot(previousPlans);
    try {
      state.curriculumPlans = await api("/curriculum/plans");
      notifyPlanStatusChanges(previousPlans, state.curriculumPlans);
      if (
        routeName() === "curricula" &&
        catalogKind() === "plans" &&
        planStatusSnapshot(state.curriculumPlans) !== previous
      ) {
        render();
      }
    } catch {
      // Keep polling; the catalog refresh is best-effort.
    }
    if (anyPlanProcessing()) syncPlanStatusPolling();
  }, PLAN_STATUS_POLL_MS);
}

async function loadCurricula() {
  const [curricula, plans] = await Promise.all([
    api("/curricula"),
    api("/curriculum/plans"),
  ]);
  state.curricula = curricula;
  state.curriculumPlans = plans;
  syncPlanStatusPolling();
}

async function loadYears() {
  state.years = await api("/school-years");
}

async function loadPortfolioFilters() {
  await Promise.all([loadStudents(), loadYears()]);
}

async function loadEnrollments() {
  state.enrollments = await api("/enrollments");
}

async function loadExceptions() {
  state.exceptions = await api("/exceptions");
}

async function loadSchoolYearSettings() {
  state.schoolYear = await api("/settings/school-year");
}

async function loadExceptionColors() {
  try {
    state.exceptionColors = await api("/settings/exception-colors");
  } catch {
    state.exceptionColors = { ...DEFAULT_EXCEPTION_COLORS };
  }
}

async function refresh() {
  if (currentUserIsChild()) {
    await loadKidWorkspace();
    return;
  }
  await Promise.all([
    loadHousehold(),
    loadStudents(),
    loadCurricula(),
    loadYears(),
    loadEnrollments(),
    loadExceptions(),
    loadSchoolYearSettings(),
    loadExceptionColors(),
  ]);
}

async function loadStudentList() {
  await loadStudents();
}

async function loadInviteKeys() {
  if (!currentUserIsAdmin()) {
    state.inviteKeys = [];
    return;
  }
  state.inviteKeys = await api("/admin/invites");
}

async function loadCaptureTokenStatus() {
  state.captureTokenStatus = { active: false, created_at: null, expires_at: null };
  if (currentUserIsChild() || tokenIsDemo()) {
    return;
  }
  try {
    const status = await api("/auth/capture-token");
    state.captureTokenStatus = {
      active: Boolean(status && status.active),
      created_at: status && status.created_at ? status.created_at : null,
      expires_at: status && status.expires_at ? status.expires_at : null,
    };
  } catch {
    state.captureTokenStatus = { active: false, created_at: null, expires_at: null };
  }
}

async function loadSettings() {
  const panel = settingsPanel();
  const extras = [loadHousehold(), loadExceptionColors()];
  if (panel === SETTINGS_PANELS.admin) {
    extras.push(loadInviteKeys());
    await Promise.all(extras);
    return;
  }
  if (panel === SETTINGS_PANELS.exceptions) {
    extras.push(loadStudents(), loadExceptions());
    await Promise.all(extras);
    return;
  }
  if (panel === SETTINGS_PANELS.years) {
    extras.push(loadYears());
    await Promise.all(extras);
    return;
  }
  if (panel === SETTINGS_PANELS.enrollments) {
    extras.push(loadStudents(), loadCurricula(), loadYears(), loadEnrollments());
    await Promise.all(extras);
    return;
  }
  extras.push(loadStudents(), loadCaptureTokenStatus());
  await Promise.all(extras);
}

// List views paint from these loaders so a hash change never shows a stale
// catalog, student roster, or calendar of exceptions. Assignments fetch after
// paint because loadCalendar patches the grid that render() just built.
const LOADERS = {
  dashboard: refresh,
  students: loadStudentList,
  curricula: loadCurricula,
  portfolios: loadPortfolioFilters,
  settings: loadSettings,
  "my-work": loadKidWorkspace,
};

let routeGeneration = 0;

async function showRoute() {
  if (typeof isLoginOpen === "function" && isLoginOpen()) return;
  if (currentUserIsChild()) {
    const [name] = routeSegments();
    if (name !== "my-work") {
      history.replaceState(null, "", "#/my-work");
    }
  }
  let [name] = routeSegments();
  if (name === "evidence") {
    history.replaceState(null, "", "#/assignments");
    name = "assignments";
  }
  if (SETTINGS_ALIASES[name]) {
    history.replaceState(null, "", SETTINGS_ALIASES[name]);
  }
  const route = routeName();
  const generation = (routeGeneration += 1);
  const loader = LOADERS[route];
  if (loader) {
    try {
      await loader();
    } catch (error) {
      flash(error.message, true);
    }
  }
  if (generation !== routeGeneration) return;
  render();
}

function optionList(items, labelFn, includeHousehold = false) {
  const options = items
    .map((item) => `<option value="${item.id}">${escapeHtml(labelFn(item))}</option>`)
    .join("");
  if (includeHousehold) {
    return `<option value="">Whole household</option>${options}`;
  }
  return `<option value="" disabled selected>Select…</option>${options}`;
}

function enumOptions(values, selected) {
  return values
    .map(
      (value) =>
        `<option value="${value}"${value === selected ? " selected" : ""}>${escapeHtml(humanize(value))}</option>`
    )
    .join("");
}

function exceptionRows(items) {
  if (!items.length) {
    return `<p class="empty">No dentist visits, sick days, or vacations yet.</p>`;
  }
  return `<div class="list">${items
    .map(
      (item) => `
      <div class="list-row">
        <span class="tag">${escapeHtml(item.kind)}</span>
        <strong>${escapeHtml(item.title)}</strong>
        <p class="meta">${escapeHtml(item.start_date)} → ${escapeHtml(item.end_date)} · ${
          item.student_id ? escapeHtml(studentName(item.student_id)) : "Whole household"
        }</p>
      </div>`
    )
    .join("")}</div>`;
}

function exceptionColorMap() {
  return { ...DEFAULT_EXCEPTION_COLORS, ...(state.exceptionColors || {}) };
}

function exceptionColor(kind) {
  const colors = exceptionColorMap();
  return colors[kind] || colors.other;
}

function contrastingInk(hex) {
  const raw = validStudentColor(hex) || DEFAULT_EXCEPTION_COLORS.other;
  const r = parseInt(raw.slice(1, 3), 16);
  const g = parseInt(raw.slice(3, 5), 16);
  const b = parseInt(raw.slice(5, 7), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 >= 160 ? "#1a1a1a" : "#ffffff";
}

function exceptionsOnDate(iso) {
  return (state.exceptions || []).filter(
    (item) => iso >= item.start_date && iso <= item.end_date
  );
}

function dashboardMonthISO() {
  if (!state.dashboardMonth) state.dashboardMonth = todayISO().slice(0, 7);
  return state.dashboardMonth;
}

function shiftDashboardMonth(direction) {
  const [year, month] = dashboardMonthISO().split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1 + direction, 1));
  state.dashboardMonth = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
  const host = $("dash-cal");
  if (host) host.outerHTML = renderDashboardCalendar();
}

async function saveExceptionColor(kind, hex) {
  const cleaned = validStudentColor(hex);
  if (!cleaned) return;
  const swatch = document.querySelector(
    `.exception-color-pick:has([data-kind="${kind}"]) .exception-color-dot`
  );
  if (swatch) swatch.style.background = cleaned;
  try {
    state.exceptionColors = await api("/settings/exception-colors", {
      method: "PUT",
      body: JSON.stringify({ [kind]: cleaned }),
    });
  } catch (error) {
    flash(error.message, true);
  }
}

async function resetExceptionColors() {
  try {
    state.exceptionColors = await api("/settings/exception-colors", {
      method: "PUT",
      body: JSON.stringify(DEFAULT_EXCEPTION_COLORS),
    });
    render();
    flash("Exception colors reset.");
  } catch (error) {
    flash(error.message, true);
  }
}

function exceptionBubble(items) {
  return items
    .map((item) => {
      const who = item.student_id ? studentName(item.student_id) : "";
      const extra =
        who && !String(item.title).toLowerCase().includes(who.toLowerCase())
          ? `<span>${escapeHtml(who)}</span>`
          : "";
      return `<p>${escapeHtml(item.title)}${extra}</p>`;
    })
    .join("");
}

const HOLIDAY_THEMES = [
  { id: "christmas", re: /christmas|xmas|\badvent\b|nativity|boxing day/, emoji: "🎄", vibe: "Twinkle lights and cocoa weather" },
  { id: "thanksgiving", re: /thanksgiv/, emoji: "🍂", vibe: "Pie, people, and a long table" },
  { id: "easter", re: /\beaster\b|good friday|resurrection/, emoji: "🐰", vibe: "Pastels, gardens, and a little wonder" },
  { id: "halloween", re: /halloween|all hallows/, emoji: "🎃", vibe: "Crisp air and porch lights" },
  { id: "newyear", re: /new year/, emoji: "✨", vibe: "A fresh page in the family book" },
  { id: "valentine", re: /valentine/, emoji: "💌", vibe: "Notes, kindness, and extra hugs" },
  { id: "patrick", re: /st\.?\s*patrick|saint patrick/, emoji: "☘️", vibe: "Green days and lucky stories" },
  { id: "independence", re: /independence|july 4|4th of july|fourth of july/, emoji: "🎆", vibe: "Sparklers, flags, and late light" },
  { id: "mlk", re: /martin luther|\bmlk\b/, emoji: "✊", vibe: "Courage, words, and a longer table" },
  { id: "memorial", re: /memorial day/, emoji: "🇺🇸", vibe: "Remembering, then a long weekend" },
  { id: "labor", re: /labor day/, emoji: "🌞", vibe: "One last summer Saturday" },
  { id: "presidents", re: /presidents'? day/, emoji: "🎩", vibe: "Stories from the White House" },
  { id: "veterans", re: /veterans/, emoji: "🎖️", vibe: "Thank-you notes and quiet pride" },
  { id: "springbreak", re: /spring break/, emoji: "🌷", vibe: "A breather before the last push" },
  { id: "winterbreak", re: /winter break|christmas break|holiday break/, emoji: "❄️", vibe: "Slow mornings and extra stories" },
  { id: "summer", re: /summer break|summer vacation/, emoji: "🏖️", vibe: "Bare feet and library stacks" },
];

const MONTH_MOODS = [
  { id: "jan", title: "Snow-day season", blurb: "Cocoa, quiet pages, and a brand-new year to fill." },
  { id: "feb", title: "Kindness month", blurb: "Little notes, brave reading, and extra warmth." },
  { id: "mar", title: "Green-shoots season", blurb: "Windows open a crack. Stories start to stretch." },
  { id: "apr", title: "Puddle-jumping days", blurb: "Rain on the roof, eggs in the grass, questions everywhere." },
  { id: "may", title: "Garden month", blurb: "Flowers, field trips, and finishing strong." },
  { id: "jun", title: "Sun-on-the-porch days", blurb: "Longer light and library stacks that travel outside." },
  { id: "jul", title: "Sparkler season", blurb: "Flags, fireflies, and reading under a fan." },
  { id: "aug", title: "Backpack season", blurb: "New pencils, familiar faces, and a fresh first page." },
  { id: "sep", title: "Apple month", blurb: "Crisp mornings and the good kind of busy." },
  { id: "oct", title: "Crunchy-leaf days", blurb: "Pumpkins on the step and mysteries in the read-aloud." },
  { id: "nov", title: "Harvest month", blurb: "Lists of thanks, pie plans, and cozy chapters." },
  { id: "dec", title: "Twinkle season", blurb: "Lights in the window and stories that glow." },
];

function clockGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function familyGreetingName() {
  const name = String(state.household?.name || "").trim();
  if (!name) return "family";
  if (/family$/i.test(name)) return name;
  return `${name} family`;
}

function monthMood(iso = todayISO()) {
  const month = parseISODate(iso).getUTCMonth();
  return MONTH_MOODS[month] || MONTH_MOODS[0];
}

function holidayThemeFor(title, kind) {
  const text = String(title || "").toLowerCase();
  const match = HOLIDAY_THEMES.find((theme) => theme.re.test(text));
  if (match) return match;
  if (kind === "vacation") {
    return { id: "vacation", emoji: "🧳", vibe: "A pause in the school-year story" };
  }
  if (kind === "holiday") {
    return { id: "holiday", emoji: "🎉", vibe: "A marked day on the family calendar" };
  }
  return { id: "break", emoji: "🌤️", vibe: "A little extra breathing room" };
}

function daysBetweenISO(fromISO, toISO) {
  return Math.round((parseISODate(toISO) - parseISODate(fromISO)) / 86400000);
}

function upcomingCelebrations(limit = 4) {
  const today = todayISO();
  const rows = (state.exceptions || [])
    .filter((item) => item.kind === "holiday" || item.kind === "vacation")
    .filter((item) => item.end_date >= today)
    .sort((a, b) => a.start_date.localeCompare(b.start_date) || a.id - b.id);
  const seen = new Set();
  const unique = [];
  for (const item of rows) {
    const key = `${item.title}|${item.start_date}|${item.end_date}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
    if (unique.length >= limit) break;
  }
  return unique;
}

function celebrationTiming(item) {
  const today = todayISO();
  const ongoing = item.start_date <= today && item.end_date >= today;
  const untilStart = daysBetweenISO(today, item.start_date);
  const untilEnd = daysBetweenISO(today, item.end_date);
  return { ongoing, untilStart, untilEnd };
}

function formatBreakSpan(item) {
  const start = SHORT_DATE.format(parseISODate(item.start_date));
  if (item.start_date === item.end_date) return start;
  return `${start} – ${SHORT_DATE.format(parseISODate(item.end_date))}`;
}

function countdownCopy(item) {
  const { ongoing, untilStart, untilEnd } = celebrationTiming(item);
  if (ongoing) {
    if (untilEnd <= 0) return { value: "Today", unit: "it’s happening", now: true };
    return {
      value: String(untilEnd),
      unit: untilEnd === 1 ? "day left in it" : "days left in it",
      now: true,
    };
  }
  if (untilStart <= 0) return { value: "Today", unit: "is the day", now: true };
  if (untilStart === 1) return { value: "Tomorrow", unit: "just about here", now: false };
  return { value: String(untilStart), unit: untilStart === 1 ? "day to go" : "days to go", now: false };
}

function mulberry32(seed) {
  return function rand() {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffleCopy(items, rand) {
  const next = [...items];
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1));
    [next[i], next[j]] = [next[j], next[i]];
  }
  return next;
}

function gradeBand(grade) {
  const g = String(grade || "").trim().toLowerCase();
  if (!g) return "elem";
  if (/pre-?k|tk|kinder|^k$/.test(g)) return "early";
  const n = parseInt(g, 10);
  if (Number.isFinite(n)) {
    if (n <= 2) return "early";
    if (n <= 5) return "elem";
    return "older";
  }
  return "elem";
}

function puzzleWords(text) {
  const skip = new Set([
    "the", "and", "for", "with", "from", "this", "that", "lesson", "read",
    "chapter", "pages", "page", "week", "unit", "into", "your", "have",
  ]);
  return String(text || "")
    .split(/[^A-Za-z]+/)
    .map((word) => word.trim())
    .filter((word) => word.length >= 4 && word.length <= 10 && !skip.has(word.toLowerCase()));
}

function buildDailySpark(student, assignments) {
  const iso = todayISO();
  const seed = Number.parseInt(`${student.id}${iso.replaceAll("-", "")}`, 10) || student.id;
  const rand = mulberry32(seed);
  const band = gradeBand(student.grade);
  const titles = (assignments || [])
    .filter((item) => item.scheduled_date === iso)
    .map((item) => item.resource_title || item.title)
    .filter(Boolean);
  const source = titles[Math.floor(rand() * Math.max(titles.length, 1))] || "";
  const words = puzzleWords(source);
  const word = words[Math.floor(rand() * Math.max(words.length, 1))] || "";

  if (word && rand() < 0.55) {
    let scrambled = word;
    for (let i = 0; i < 8 && scrambled.toLowerCase() === word.toLowerCase(); i += 1) {
      scrambled = shuffleCopy(word.split(""), rand).join("");
    }
    return {
      kind: "scramble",
      kicker: source ? `From today’s reading` : "Word play",
      prompt: `Unscramble this word: ${scrambled.toUpperCase()}`,
      answer: word,
      hint: source ? `It’s hiding in “${source}.”` : "Sound it out one letter at a time.",
    };
  }

  if (band === "early") {
    const count = 3 + Math.floor(rand() * 5);
    const icon = ["⭐", "🍎", "🌸", "🦆", "🔵"][Math.floor(rand() * 5)];
    const correct = String(count);
    const choices = shuffleCopy(
      [...new Set([count, count + 1, Math.max(1, count - 1), count + 2])].map(String),
      rand
    );
    return {
      kind: "choice",
      kicker: "Quick count",
      prompt: `How many do you see?`,
      visual: icon.repeat(count),
      choices,
      answer: correct,
      hint: "Tap each one as you count.",
    };
  }

  if (band === "elem") {
    const a = 4 + Math.floor(rand() * 8);
    const b = 3 + Math.floor(rand() * 7);
    const op = rand() < 0.5 ? "+" : "×";
    const correct = op === "+" ? a + b : a * b;
    const choices = shuffleCopy(
      [...new Set([correct, correct + 1, correct - 1, correct + (op === "+" ? 2 : a)])].map(String),
      rand
    );
    return {
      kind: "choice",
      kicker: "Warm-up",
      prompt: `What’s ${a} ${op} ${b}?`,
      choices,
      answer: String(correct),
      hint: op === "+" ? "Count up from the first number." : "Think equal groups.",
    };
  }

  const riddles = [
    { prompt: "I have a spine but I’m not a dinosaur. I open, but I’m not a door. What am I?", answer: "a book", hint: "You’re probably holding one later today." },
    { prompt: "The more you take from me, the bigger I get. What am I?", answer: "a hole", hint: "Think about digging." },
    { prompt: "I travel the world but stay in a corner. What am I?", answer: "a stamp", hint: "Mail." },
  ];
  const riddle = riddles[Math.floor(rand() * riddles.length)];
  return {
    kind: "think",
    kicker: "Brain stretch",
    prompt: riddle.prompt,
    answer: riddle.answer,
    hint: riddle.hint,
  };
}

function localTalkPrompt(student, assignments) {
  const name = firstName(student?.name);
  const today = (assignments || []).filter((item) => item.scheduled_date === todayISO());
  const item = today[0];
  if (!item) {
    return {
      prompt: `${name}, what’s one thing you hope to notice or try today?`,
      about: null,
    };
  }
  const about = item.resource_title || item.title;
  return {
    prompt: `${name}, you’re in “${about}” today. What do you think happens next, or what’s the most interesting part so far?`,
    about,
  };
}

function sparkSolvedKey(studentId) {
  return `curiculy-spark-${studentId}-${todayISO()}`;
}

function classWeekdays() {
  const raw = state.schoolYear?.weekdays;
  const days = Array.isArray(raw)
    ? raw.map(Number).filter((day) => Number.isInteger(day) && day >= 0 && day <= 6)
    : [];
  const unique = [...new Set(days)].sort((a, b) => a - b);
  return unique.length ? unique : [0, 1, 2, 3, 4];
}

function renderDashboardCalendar() {
  const monthISO = dashboardMonthISO();
  const [year, month] = monthISO.split("-").map(Number);
  const first = new Date(Date.UTC(year, month - 1, 1));
  const lastDate = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const today = todayISO();
  const kindsUsed = new Set();
  const visibleDays = classWeekdays();
  const visibleSet = new Set(visibleDays);
  const columns = visibleDays.length;
  const cells = [];
  const startWeekday = mondayIndex(first);
  let leading = 0;
  for (let i = 0; i < startWeekday; i += 1) {
    if (visibleSet.has(i)) leading += 1;
  }
  for (let blank = 0; blank < leading; blank += 1) {
    cells.push('<span class="dash-cal-day is-pad" aria-hidden="true"></span>');
  }
  for (let day = 1; day <= lastDate; day += 1) {
    const date = new Date(Date.UTC(year, month - 1, day));
    const iso = toISODate(date);
    if (!visibleSet.has(mondayIndex(date))) continue;
    const hits = exceptionsOnDate(iso);
    const marked = hits.length > 0;
    for (const item of hits) kindsUsed.add(item.kind);
    const color = marked ? exceptionColor(hits[0].kind) : "";
    const label = marked
      ? hits.map((item) => item.title).join(", ")
      : `${iso}`;
    cells.push(`
      <span class="dash-cal-day${marked ? " is-marked" : ""}${iso === today ? " is-today" : ""}"${
        marked
          ? ` style="--mark:${color};--mark-ink:${contrastingInk(color)}" tabindex="0"`
          : ""
      } aria-label="${escapeHtml(label)}">
        <span class="dash-cal-num">${day}</span>
        ${marked ? `<span class="dash-cal-tip" role="tooltip">${exceptionBubble(hits)}</span>` : ""}
      </span>`);
  }
  while (columns && cells.length % columns !== 0) {
    cells.push('<span class="dash-cal-day is-pad" aria-hidden="true"></span>');
  }
  const legend = EXCEPTION_KINDS.filter((kind) => kindsUsed.has(kind))
    .map(
      (kind) =>
        `<span class="dash-cal-key"><i style="background:${exceptionColor(kind)}"></i>${escapeHtml(
          humanize(kind)
        )}</span>`
    )
    .join("");
  const headers = visibleDays.map((index) => WEEKDAYS[index][0]);
  return `
    <section class="card dash-cal-card cols-${columns}" id="dash-cal" style="--dash-cal-cols:${columns}">
      <header class="dash-cal-head">
        <h2>This month</h2>
        <div class="dash-cal-nav">
          <button type="button" class="ghost icon-button" data-action="dash-cal-prev" aria-label="Previous month">&lsaquo;</button>
          <p class="dash-cal-label">${escapeHtml(MONTH_YEAR.format(first))}</p>
          <button type="button" class="ghost icon-button" data-action="dash-cal-next" aria-label="Next month">&rsaquo;</button>
        </div>
      </header>
      <div class="dash-cal-weekdays">${headers.map((day) => `<span>${day}</span>`).join("")}</div>
      <div class="dash-cal-days">${cells.join("")}</div>
      ${
        legend
          ? `<p class="dash-cal-legend">${legend}</p>`
          : `<p class="empty dash-cal-empty">No holds this month.</p>`
      }
    </section>`;
}

function renderUpcomingBreaks() {
  const upcoming = upcomingCelebrations(4);
  if (!upcoming.length) {
    return `
      <section class="card break-board">
        <div class="break-hero" data-break="break">
          <p class="break-kicker">Next celebration</p>
          <p class="break-empty-hero">No holidays or vacations are on the calendar yet.</p>
          <p class="break-vibe">Mark a break in School year settings and it will show up here with a countdown.</p>
        </div>
      </section>`;
  }
  const next = upcoming[0];
  const theme = holidayThemeFor(next.title, next.kind);
  const count = countdownCopy(next);
  const list = upcoming
    .map((item, index) => {
      const timing = celebrationTiming(item);
      const when = timing.ongoing
        ? timing.untilEnd <= 0
          ? "Today"
          : `${timing.untilEnd} day${timing.untilEnd === 1 ? "" : "s"} left`
        : timing.untilStart <= 0
          ? "Today"
          : timing.untilStart === 1
            ? "Tomorrow"
            : `In ${timing.untilStart} days`;
      return `
        <li class="break-row${index === 0 ? " is-next" : ""}">
          <span class="break-row-when">${escapeHtml(when)}</span>
          <span>
            <strong>${escapeHtml(item.title)}</strong>
            <span class="meta">${escapeHtml(formatBreakSpan(item))} · ${escapeHtml(humanize(item.kind))}</span>
          </span>
        </li>`;
    })
    .join("");
  return `
    <section class="card break-board">
      <div class="break-hero" data-break="${escapeHtml(theme.id)}">
        <span class="break-emoji" aria-hidden="true">${theme.emoji}</span>
        <p class="break-kicker">${count.now ? "Right now" : "Counting down"}</p>
        <p class="break-value">${escapeHtml(count.value)}</p>
        <p class="break-unit">${escapeHtml(count.unit)}</p>
        <h2>${escapeHtml(next.title)}</h2>
        <p class="break-vibe">${escapeHtml(theme.vibe)}</p>
        <p class="break-when">${escapeHtml(formatBreakSpan(next))}</p>
      </div>
      <div class="break-list-wrap">
        <h3>Coming up</h3>
        <ol class="break-list">${list}</ol>
      </div>
    </section>`;
}

function renderDashboard() {
  const enrollmentsByStudent = Object.fromEntries(state.students.map((student) => [student.id, []]));
  for (const enrollment of state.enrollments) {
    (enrollmentsByStudent[enrollment.student_id] ||= []).push(enrollment);
  }
  const mood = monthMood();
  const next = upcomingCelebrations(1)[0];
  let nextHint = "Whenever you add a holiday or vacation, we’ll count it down here.";
  if (next) {
    const count = countdownCopy(next);
    if (count.now) nextHint = `${next.title} is on the calendar right now.`;
    else if (count.value === "Tomorrow") nextHint = `${next.title} is tomorrow.`;
    else nextHint = `${next.title} is in ${count.value} days.`;
  }
  return `
    <div id="dashboard-view" class="home-view" data-month="${mood.id}">
      <section class="home-hero">
        <p class="home-kicker">${escapeHtml(mood.title)}</p>
        <h2>${escapeHtml(clockGreeting())}, ${escapeHtml(familyGreetingName())}.</h2>
        <p class="home-lede">${escapeHtml(mood.blurb)} ${escapeHtml(nextHint)}</p>
        <div class="home-pulse" aria-label="Today at a glance">
          <div class="home-pulse-stat">
            <span>Today’s lessons</span>
            <strong id="home-lessons-today">…</strong>
          </div>
          <div class="home-pulse-stat">
            <span>Finished this week</span>
            <strong id="home-lessons-week">…</strong>
          </div>
          <div class="home-pulse-stat">
            <span>Kids at the table</span>
            <strong>${state.students.length || "—"}</strong>
          </div>
        </div>
      </section>
      <div class="home-stage">
      <div class="home-break-row">
        ${renderDashboardCalendar()}
        ${renderUpcomingBreaks()}
      </div>
      <section class="kpi-dashboard" aria-label="How school is going">
        <article class="card kpi-card kpi-today">
          <header class="kpi-card-head">
            <h2>How today is going</h2>
            <p id="today-progress-meta" class="meta"></p>
          </header>
          <div class="kpi-chart" id="today-progress-wrap">
            <canvas id="todayProgressChart" aria-label="Today's completion by student"></canvas>
            <p id="today-progress-empty" class="empty" hidden>No lessons scheduled today.</p>
          </div>
        </article>
        <article class="card kpi-card kpi-week">
          <header class="kpi-card-head">
            <h2>This week</h2>
            <p id="weekly-trend-meta" class="meta"></p>
          </header>
          <div class="kpi-chart" id="weekly-trend-wrap">
            <canvas id="weeklyTrendChart" aria-label="Completed assignments over the last 7 days"></canvas>
            <p id="weekly-trend-empty" class="empty" hidden>Add a student to see weekly progress.</p>
          </div>
        </article>
      </section>
      </div>
      <section class="home-family">
        <header class="home-family-head">
          <h2>The kids</h2>
          <p class="meta">Open someone’s day to see their list, a little puzzle, and a question about what they’re reading.</p>
        </header>
        <div class="grid-cards">
          ${
            state.students.length
              ? state.students
                  .map((student) => {
                    const enrolled = enrollmentsByStudent[student.id] || [];
                    const books = enrolled
                      .slice(0, 2)
                      .map((row) => escapeHtml(curriculumTitle(row.curriculum_id)))
                      .join(" · ");
                    return `<article class="card student-card" style="${studentColorStyle(student)}">
                      <h3>${escapeHtml(student.name)}</h3>
                      <p class="meta">${escapeHtml(student.grade ? `Grade ${student.grade}` : "Grade unset")}</p>
                      <p class="student-card-copy">${books || "No books on the schedule yet."}</p>
                      <div class="student-card-actions">
                        <a class="button small" href="#/students/${student.id}">Open their day</a>
                        <button type="button" class="ghost small" data-action="student-calendar"
                                data-student-id="${student.id}">Calendar</button>
                      </div>
                    </article>`;
                  })
                  .join("")
              : `<p class="empty">Add children in <a href="#/settings/students">Settings</a> and this house starts to feel like home.</p>`
          }
        </div>
      </section>
    </div>
  `;
}

function paintHomePulse(stats) {
  const todayEl = $("home-lessons-today");
  const weekEl = $("home-lessons-week");
  if (!todayEl && !weekEl) return;
  const today = stats?.today_progress || [];
  const done = today.reduce((sum, row) => sum + (Number(row.completed) || 0), 0);
  const total = today.reduce((sum, row) => sum + (Number(row.total) || 0), 0);
  const week = (stats?.weekly_trend || []).reduce(
    (sum, row) =>
      sum + (row.completed || []).reduce((inner, count) => inner + (Number(count) || 0), 0),
    0
  );
  if (todayEl) {
    todayEl.textContent = total ? `${done} of ${total}` : "A free day";
  }
  if (weekEl) {
    weekEl.textContent = String(week);
  }
}

let dashboardStatsRequest = 0;
let dashboardChartStats = null;
let todayProgressChart = null;
let weeklyTrendChart = null;
let kpiPluginRegistered = false;

const kpiCenterTextPlugin = {
  id: "kpiCenterText",
  afterDraw(chart) {
    if (chart.canvas?.id !== "todayProgressChart") return;
    const meta = chart.options.plugins?.kpiCenterText;
    if (!meta) return;
    const { ctx, chartArea } = chart;
    const x = (chartArea.left + chartArea.right) / 2;
    const y = (chartArea.top + chartArea.bottom) / 2;
    const total = meta.total || 0;
    const completed = meta.completed || 0;
    const pct = total ? Math.round((completed / total) * 100) : 0;
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = cssVar("--text-primary");
    ctx.font = `700 1.65rem ${Chart.defaults.font.family}`;
    ctx.fillText(total ? `${pct}%` : "—", x, y - 10);
    ctx.fillStyle = cssVar("--text-secondary");
    ctx.font = `500 0.75rem ${Chart.defaults.font.family}`;
    ctx.fillText(total ? `${completed} of ${total}` : "No lessons", x, y + 14);
    ctx.restore();
  },
};

function destroyDashboardCharts() {
  if (typeof Chart !== "undefined") {
    const todayCanvas = $("todayProgressChart");
    const weekCanvas = $("weeklyTrendChart");
    if (todayCanvas) Chart.getChart(todayCanvas)?.destroy();
    if (weekCanvas) Chart.getChart(weekCanvas)?.destroy();
  }
  todayProgressChart = null;
  weeklyTrendChart = null;
}

function setKpiEmpty(wrapId, emptyId, isEmpty, message) {
  const wrap = $(wrapId);
  const empty = $(emptyId);
  if (wrap) wrap.classList.toggle("is-empty", Boolean(isEmpty));
  if (empty) {
    empty.hidden = !isEmpty;
    if (message) empty.textContent = message;
  }
}

function chartTheme() {
  return {
    text: cssVar("--text-secondary") || "#64748b",
    grid: cssVar("--border-color") || "#d9e2dc",
    tooltipBg: cssVar("--bg-surface") || "#ffffff",
    tooltipText: cssVar("--text-primary") || "#334155",
    surface: cssVar("--bg-surface") || "#ffffff",
  };
}

function applyChartDefaults() {
  if (typeof Chart === "undefined") return;
  Chart.defaults.font.family = 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = chartTheme().text;
  if (!kpiPluginRegistered) {
    Chart.register(kpiCenterTextPlugin);
    kpiPluginRegistered = true;
  }
}

function todayProgressSlices(progress) {
  const labels = [];
  const data = [];
  const backgroundColor = [];
  const slices = [];
  for (const student of progress) {
    const total = Number(student.total) || 0;
    if (!total) continue;
    const completed = Math.min(Math.max(Number(student.completed) || 0, 0), total);
    const remaining = total - completed;
    const color = studentChartColor(student);
    if (completed > 0) {
      labels.push(student.name);
      data.push(completed);
      backgroundColor.push(color);
      slices.push(student);
    }
    if (remaining > 0) {
      labels.push(`${student.name} remaining`);
      data.push(remaining);
      backgroundColor.push(colorWithAlpha(color, 0.22));
      slices.push(student);
    }
  }
  return { labels, data, backgroundColor, slices };
}

function paintTodayProgressChart(progress) {
  const canvas = $("todayProgressChart");
  const meta = $("today-progress-meta");
  if (!canvas) return;
  const totals = progress.reduce(
    (sum, student) => {
      sum.total += Number(student.total) || 0;
      sum.completed += Number(student.completed) || 0;
      return sum;
    },
    { total: 0, completed: 0 }
  );
  if (meta) {
    meta.textContent = totals.total
      ? `${totals.completed} of ${totals.total} complete`
      : "";
  }
  const slices = todayProgressSlices(progress);
  if (!slices.data.length) {
    setKpiEmpty(
      "today-progress-wrap",
      "today-progress-empty",
      true,
      progress.length ? "No lessons scheduled today." : "Add a student to see today's progress."
    );
    return;
  }
  setKpiEmpty("today-progress-wrap", "today-progress-empty", false);
  const theme = chartTheme();
  todayProgressChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: slices.labels,
      datasets: [
        {
          data: slices.data,
          backgroundColor: slices.backgroundColor,
          borderColor: theme.surface,
          borderWidth: 2,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        kpiCenterText: { total: totals.total, completed: totals.completed },
        legend: {
          position: "bottom",
          onClick() {},
          labels: {
            color: theme.text,
            boxWidth: 12,
            padding: 14,
            generateLabels() {
              return progress
                .filter((student) => Number(student.total) > 0)
                .map((student) => {
                  const color = studentChartColor(student);
                  return {
                    text: student.name,
                    fillStyle: color,
                    strokeStyle: color,
                    hidden: false,
                  };
                });
            },
          },
        },
        tooltip: {
          backgroundColor: theme.tooltipBg,
          titleColor: theme.tooltipText,
          bodyColor: theme.tooltipText,
          borderColor: theme.grid,
          borderWidth: 1,
          callbacks: {
            title(items) {
              const student = slices.slices[items[0]?.dataIndex];
              return student ? student.name : "";
            },
            label(ctx) {
              const student = slices.slices[ctx.dataIndex];
              if (!student) return ctx.label;
              const pct = student.total
                ? Math.round((student.completed / student.total) * 100)
                : 0;
              const remaining = String(ctx.label || "").endsWith(" remaining");
              return `${remaining ? "Remaining" : "Completed"}: ${ctx.raw} · ${student.completed} of ${student.total} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

function trendDayLabel(iso) {
  const date = parseISODate(iso);
  return `${WEEKDAYS[mondayIndex(date)]} ${date.getUTCDate()}`;
}

function paintWeeklyTrendChart(stats) {
  const canvas = $("weeklyTrendChart");
  const meta = $("weekly-trend-meta");
  if (!canvas) return;
  const series = stats.weekly_trend || [];
  const dates = stats.trend_dates || [];
  const completed = series.reduce(
    (sum, student) =>
      sum + (student.completed || []).reduce((inner, count) => inner + (Number(count) || 0), 0),
    0
  );
  if (meta) {
    meta.textContent = series.length ? `${completed} completed` : "";
  }
  if (!series.length) {
    setKpiEmpty(
      "weekly-trend-wrap",
      "weekly-trend-empty",
      true,
      "Add a student to see weekly progress."
    );
    return;
  }
  setKpiEmpty("weekly-trend-wrap", "weekly-trend-empty", false);
  const theme = chartTheme();
  weeklyTrendChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: dates.map(trendDayLabel),
      datasets: series.map((student) => ({
        label: student.name,
        data: student.completed || [],
        backgroundColor: studentChartColor(student),
        borderRadius: 4,
        maxBarThickness: 36,
        stack: "completed",
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: theme.text, boxWidth: 12, padding: 14 },
        },
        tooltip: {
          backgroundColor: theme.tooltipBg,
          titleColor: theme.tooltipText,
          bodyColor: theme.tooltipText,
          borderColor: theme.grid,
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          ticks: { color: theme.text },
          border: { color: theme.grid },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          ticks: { color: theme.text, precision: 0, stepSize: 1 },
          grid: { color: theme.grid },
          border: { display: false },
        },
      },
    },
  });
}

function paintDashboardCharts(stats) {
  destroyDashboardCharts();
  dashboardChartStats = stats;
  if (typeof Chart === "undefined") {
    setKpiEmpty("today-progress-wrap", "today-progress-empty", true, "Charts could not load.");
    setKpiEmpty("weekly-trend-wrap", "weekly-trend-empty", true, "Charts could not load.");
    return;
  }
  applyChartDefaults();
  paintTodayProgressChart(stats.today_progress || []);
  paintWeeklyTrendChart(stats);
}

async function loadDashboardStats() {
  if (!$("todayProgressChart") || !$("weeklyTrendChart")) return;
  const token = (dashboardStatsRequest += 1);
  try {
    const stats = await api("/dashboard/stats");
    if (token !== dashboardStatsRequest || !$("todayProgressChart")) return;
    paintHomePulse(stats);
    paintDashboardCharts(stats);
  } catch (error) {
    if (token !== dashboardStatsRequest || !$("todayProgressChart")) return;
    dashboardChartStats = null;
    destroyDashboardCharts();
    paintHomePulse(null);
    setKpiEmpty("today-progress-wrap", "today-progress-empty", true, error.message);
    setKpiEmpty("weekly-trend-wrap", "weekly-trend-empty", true, error.message);
    flash(error.message, true);
  }
}

function selectedDashboardStudentId() {
  const [, raw] = routeSegments();
  const fromHash = raw ? Number(raw) : NaN;
  if (state.students.some((student) => student.id === fromHash)) {
    return fromHash;
  }
  return state.students.length ? state.students[0].id : null;
}

function isCompleteStatus(status) {
  return status === "completed";
}

function renderStudents() {
  if (!state.students.length) {
    return `
      <section class="card student-dashboard">
        <header class="view-header">
          <h2>Someone’s day</h2>
        </header>
        <p class="empty">Add a child in <a href="#/settings/students">Settings</a> to open their dashboard.</p>
      </section>
    `;
  }

  const studentId = selectedDashboardStudentId();
  const student = state.students.find((item) => item.id === studentId) || state.students[0];
  const mood = monthMood();
  return `
    <section class="student-dashboard kid-home" data-month="${mood.id}" style="${studentColorStyle(student)}">
      <nav class="student-tabs" role="tablist" aria-label="Kids">
        ${state.students
          .map(
            (item) => `
          <a href="#/students/${item.id}" role="tab" class="student-tab${
            item.id === student.id ? " active" : ""
          }" aria-selected="${item.id === student.id}" style="${studentColorStyle(item)}">
            <span class="student-swatch" aria-hidden="true"></span>${escapeHtml(firstName(item.name))}
          </a>`
          )
          .join("")}
      </nav>
      <header class="kid-hero">
        <p class="kid-kicker">${escapeHtml(mood.title)}</p>
        <h2>Hey ${escapeHtml(firstName(student.name))} — let’s have a good day.</h2>
        <p class="kid-blurb">${escapeHtml(mood.blurb)}</p>
        <details class="kid-grownup">
          <summary>Grown-up tools</summary>
          <div class="kid-grownup-actions">
            <button type="button" class="ghost" data-action="open-recalibrate"
                    data-student-id="${student.id}">Recalibrate schedule</button>
            <button type="button" class="ghost" data-action="print-weekly-checklist"
                    data-student-id="${student.id}">Print weekly checklist</button>
          </div>
        </details>
      </header>
      <div class="kid-grid">
        <section class="card kid-panel">
          <h2>Today’s adventures</h2>
          <div id="today-checklist"><p class="empty">Loading…</p></div>
        </section>
        <aside class="kid-side">
          <section class="card spark-card" id="kid-spark">
            <p class="empty">Picking a puzzle…</p>
          </section>
          <section class="card talk-card" id="kid-talk">
            <p class="empty">Thinking of a question…</p>
          </section>
          <section class="card">
            <h2>Books in motion</h2>
            <div id="active-courses"><p class="empty">Loading…</p></div>
          </section>
        </aside>
      </div>
    </section>
  `;
}

function checklistItem(item) {
  const done = isCompleteStatus(item.status);
  const details = [item.subject_name, item.resource_title].filter(Boolean).join(" · ");
  return `
    <div class="checklist-item${done ? " is-complete" : ""}" data-checklist-id="${item.id}"
         style="${assignmentColorStyle(item)}">
      <input type="checkbox" data-action="toggle-complete" data-id="${item.id}"
             ${done ? "checked" : ""} aria-label="Mark ${escapeHtml(item.title)} complete">
      <button type="button" class="checklist-copy" data-assignment-id="${item.id}">
        <span class="checklist-title">${escapeHtml(item.title)}</span>
        ${details ? `<span class="meta">${escapeHtml(details)}</span>` : ""}
      </button>
      <span class="celebrate-burst" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>
    </div>
  `;
}

function renderTodayChecklist(items) {
  const today = todayISO();
  const todays = items.filter((item) => item.scheduled_date === today);
  if (!todays.length) {
    return `<p class="empty">Nothing scheduled for today.</p>`;
  }
  const done = todays.filter((item) => isCompleteStatus(item.status)).length;
  return `
    <p class="meta checklist-progress">${done} of ${todays.length} complete</p>
    <div class="checklist">${todays.map(checklistItem).join("")}</div>
  `;
}

function courseProgressPercent(course) {
  if (!course.total_assignments) return 0;
  return (course.completed_assignments / course.total_assignments) * 100;
}

function renderActiveCourses(courses) {
  if (!courses.length) {
    return `<p class="empty">No books are on the schedule yet.</p>`;
  }
  return `<div class="list">${courses
    .map((course) => {
      const total = course.total_assignments;
      const completed = course.completed_assignments;
      const pct = courseProgressPercent(course);
      const lessons = total === 1 ? "Lesson" : "Lessons";
      return `
        <div class="list-row course-row" data-curriculum-id="${course.curriculum_id}">
          <div class="course-head">
            <strong>${escapeHtml(course.title)}</strong>
            <span class="meta" data-course-count>${completed} / ${total} ${lessons}</span>
          </div>
          <div class="course-progress-track">
            <progress class="course-progress" max="${Math.max(total, 1)}" value="${completed}"
                      aria-label="${completed} of ${total} ${lessons.toLowerCase()}"></progress>
            <span class="course-progress-fill" style="width: ${pct}%"></span>
          </div>
        </div>`;
    })
    .join("")}</div>`;
}

function renderSparkCard(student, assignments) {
  const spark = buildDailySpark(student, assignments);
  const solved = sessionStorage.getItem(sparkSolvedKey(student.id)) === spark.answer;
  const hint = spark.hint
    ? `<button type="button" class="ghost small" data-action="spark-hint">Need a hint?</button>
       <p class="spark-hint" hidden>${escapeHtml(spark.hint)}</p>`
    : "";
  let play = "";
  if (spark.kind === "choice") {
    play = `<div class="spark-choices">${(spark.choices || [])
      .map(
        (choice) =>
          `<button type="button" class="spark-choice" data-action="spark-choice" data-value="${escapeHtml(
            choice
          )}">${escapeHtml(choice)}</button>`
      )
      .join("")}</div>`;
  } else if (spark.kind === "scramble") {
    play = `<form class="spark-guess" data-form="spark-guess">
      <input name="guess" maxlength="24" autocomplete="off" aria-label="Your guess" ${
        solved ? `value="${escapeHtml(spark.answer)}" disabled` : ""
      }>
      <button type="submit"${solved ? " disabled" : ""}>Check</button>
    </form>`;
  } else {
    play = `<button type="button" class="ghost" data-action="spark-reveal"${
      solved ? " hidden" : ""
    }>Show me</button>`;
  }
  const visual = spark.visual
    ? `<p class="spark-visual" aria-hidden="true">${escapeHtml(spark.visual)}</p>`
    : "";
  return `
    <section class="card spark-card${solved ? " is-solved" : ""}" id="kid-spark" data-answer="${escapeHtml(
      spark.answer
    )}">
      <p class="spark-kicker">${escapeHtml(spark.kicker)}</p>
      <h2>Today’s puzzle</h2>
      <p class="spark-prompt">${escapeHtml(spark.prompt)}</p>
      ${visual}
      ${play}
      <p class="spark-feedback" ${solved ? "" : "hidden"}>Nice — ${escapeHtml(spark.answer)}.</p>
      ${hint}
    </section>`;
}

function renderTalkCard(student, assignments, ai) {
  const local = localTalkPrompt(student, assignments);
  const prompt = ai?.question || local.prompt;
  const about = ai?.about || local.about;
  const source = ai?.question ? "From what you’re learning" : about ? "A question for you" : "A little wonder";
  return `
    <section class="card talk-card" id="kid-talk">
      <p class="spark-kicker">${escapeHtml(source)}</p>
      <h2>Talk it out</h2>
      <p class="talk-prompt">${escapeHtml(prompt)}</p>
      ${about && !ai?.question ? `<p class="meta">Today’s trail: ${escapeHtml(about)}</p>` : ""}
    </section>`;
}

function paintKidSpark(student, assignments) {
  const sparkHost = $("kid-spark");
  if (sparkHost) sparkHost.outerHTML = renderSparkCard(student, assignments);
}

function paintKidTalk(student, assignments, ai) {
  const talkHost = $("kid-talk");
  if (talkHost) talkHost.outerHTML = renderTalkCard(student, assignments, ai);
}

function markSparkSolved(card, ok) {
  if (!card) return;
  const feedback = card.querySelector(".spark-feedback");
  const answer = card.dataset.answer || "";
  card.classList.toggle("is-solved", ok);
  card.classList.toggle("is-wrong", !ok);
  if (feedback) {
    feedback.hidden = false;
    feedback.textContent = ok ? `Nice — ${answer}.` : "Try once more. You’ve got this.";
  }
  if (ok) {
    const studentId = selectedDashboardStudentId();
    if (studentId) sessionStorage.setItem(sparkSolvedKey(studentId), answer);
    const input = card.querySelector("input[name='guess']");
    const submit = card.querySelector("button[type='submit']");
    if (input) {
      input.value = answer;
      input.disabled = true;
    }
    if (submit) submit.disabled = true;
    card.querySelector("[data-action='spark-reveal']")?.setAttribute("hidden", "hidden");
  }
}

function paintStudentDashboard() {
  const checklist = $("today-checklist");
  const courses = $("active-courses");
  if (!checklist || !courses) return;
  checklist.innerHTML = renderTodayChecklist(state.dashboardAssignments);
  courses.innerHTML = renderActiveCourses(state.dashboardCourses);
}

let dashboardRequest = 0;

async function loadStudentDashboard(studentId) {
  const id = studentId ?? selectedDashboardStudentId();
  const checklist = $("today-checklist");
  const courses = $("active-courses");
  if (!id || !checklist || !courses) return;
  const student = state.students.find((item) => item.id === id);

  const token = (dashboardRequest += 1);
  const today = todayISO();
  try {
    const [data, courseRows] = await Promise.all([
      api(`/students/${id}/assignments?start_date=${today}`),
      api(`/students/${id}/courses`),
    ]);
    if (token !== dashboardRequest || !$("today-checklist")) return;
    state.dashboardAssignments = data.assignments || [];
    state.dashboardCourses = courseRows || [];
    paintStudentDashboard();
    if (student) {
      paintKidSpark(student, state.dashboardAssignments);
      paintKidTalk(student, state.dashboardAssignments, null);
    }
    const spark = await api(`/students/${id}/spark`).catch(() => null);
    if (token !== dashboardRequest || !$("kid-talk")) return;
    if (student && spark?.question) {
      paintKidTalk(student, state.dashboardAssignments, spark);
    }
  } catch (error) {
    if (token !== dashboardRequest || !$("today-checklist")) return;
    checklist.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    courses.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    flash(error.message, true);
  }
}

function celebrateChecklistItem(row) {
  if (!row) return;
  row.classList.remove("celebrate");
  // Restart the burst if the same row is completed again in this session.
  void row.offsetWidth;
  row.classList.add("celebrate");
  row.addEventListener(
    "animationend",
    () => row.classList.remove("celebrate"),
    { once: true }
  );
}

function adjustCourseProgress(curriculumId, delta) {
  if (curriculumId == null) return null;
  const course = state.dashboardCourses.find((item) => item.curriculum_id === curriculumId);
  if (!course) return null;
  course.completed_assignments = Math.max(
    0,
    Math.min(course.total_assignments, course.completed_assignments + delta)
  );
  return course;
}

function updateCourseProgressUI(course) {
  if (!course) return;
  const row = document.querySelector(`[data-curriculum-id="${course.curriculum_id}"]`);
  if (!row) {
    const courses = $("active-courses");
    if (courses) courses.innerHTML = renderActiveCourses(state.dashboardCourses);
    return;
  }
  const total = course.total_assignments;
  const completed = course.completed_assignments;
  const pct = courseProgressPercent(course);
  const lessons = total === 1 ? "Lesson" : "Lessons";
  const bar = row.querySelector("progress");
  const fill = row.querySelector(".course-progress-fill");
  const count = row.querySelector("[data-course-count]");
  if (bar) {
    bar.max = Math.max(total, 1);
    bar.value = completed;
    bar.setAttribute("aria-label", `${completed} of ${total} ${lessons.toLowerCase()}`);
  }
  if (fill) fill.style.width = `${pct}%`;
  if (count) count.textContent = `${completed} / ${total} ${lessons}`;
}

async function toggleAssignmentComplete(assignmentId, completed) {
  const row = document.querySelector(`[data-checklist-id="${assignmentId}"]`);
  const checkbox = row?.querySelector("[data-action='toggle-complete']");
  const previous =
    state.dashboardAssignments.find((entry) => entry.id === assignmentId) ||
    (state.kidWork || []).find((entry) => entry.id === assignmentId);
  try {
    let item = await api(`/assignments/${assignmentId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: completed ? "completed" : "assigned" }),
    });
    if (isOfflineQueued(item)) {
      item = {
        ...(previous || {}),
        id: assignmentId,
        status: completed ? "completed" : "assigned",
      };
    }
    const wasComplete = isCompleteStatus(previous?.status);
    const nowComplete = isCompleteStatus(item.status);
    state.dashboardAssignments = state.dashboardAssignments.map((entry) =>
      entry.id === item.id ? { ...entry, ...item } : entry
    );
    state.kidWork = (state.kidWork || []).map((entry) =>
      entry.id === item.id ? { ...entry, ...item } : entry
    );
    if (wasComplete !== nowComplete) {
      updateCourseProgressUI(
        adjustCourseProgress(item.curriculum_id, nowComplete ? 1 : -1)
      );
    }
    const checklist = $("today-checklist");
    if (checklist) checklist.innerHTML = renderTodayChecklist(state.dashboardAssignments);
    if (routeName() === "my-work") {
      render();
    }
    if (completed) {
      celebrateChecklistItem(document.querySelector(`[data-checklist-id="${assignmentId}"]`));
    }
  } catch (error) {
    if (checkbox) checkbox.checked = !completed;
    flash(error.message, true);
  }
}

function renderStudentSettings() {
  const editing = studentEditor.id
    ? state.students.find((student) => student.id === studentEditor.id)
    : null;
  const color = editing
    ? validStudentColor(editing.color_hex) || DEFAULT_STUDENT_COLOR
    : nextStudentColor();
  return `
    <div class="layout">
      <div>
      <form class="card form-grid" data-form="student">
        <h2>${editing ? "Edit student" : "Add a student"}</h2>
        ${editing ? `<input type="hidden" name="id" value="${editing.id}">` : ""}
        <label>Name<input name="name" required maxlength="255" value="${editing ? escapeHtml(editing.name) : ""}"></label>
        <label>Grade<input name="grade" maxlength="64" value="${editing ? escapeHtml(editing.grade || "") : ""}"></label>
        <label>Color
          <input name="color_hex" type="color" value="${color}" aria-label="Student color">
        </label>
        <label>Notes<textarea name="notes">${editing ? escapeHtml(editing.notes || "") : ""}</textarea></label>
        <div class="form-actions">
          <button type="submit">Save student</button>
          ${
            editing
              ? `<button type="button" class="danger ghost" data-action="delete-student"
                         data-student-id="${editing.id}">Delete Student</button>
                 <button type="button" class="ghost" data-action="cancel-edit-student">Cancel</button>`
              : ""
          }
        </div>
      </form>
      ${editing ? renderStudentPinSettings(editing) : ""}
      </div>
      <section class="card">
        <h2>Household children</h2>
        ${
          state.students.length
            ? `<p class="muted">Click a student to edit their name, grade, or color.</p>
            <div class="list">${state.students
                .map(
                  (student) => `
              <div class="list-row is-clickable${
                editing && editing.id === student.id ? " is-selected" : ""
              }" data-action="edit-student" data-student-id="${student.id}" role="button" tabindex="0">
                <div class="item-title">
                  <span class="student-swatch" style="${studentColorStyle(student)}" aria-hidden="true"></span>
                  ${escapeHtml(student.name)}
                </div>
                <p class="meta">${escapeHtml(student.grade || "Grade unset")}${
                    student.notes ? ` · ${escapeHtml(student.notes)}` : ""
                  }</p>
              </div>`
                )
                .join("")}</div>`
            : `<p class="empty">No students yet.</p>`
        }
      </section>
    </div>
    ${renderCaptureTokenSettings()}
  `;
}

function captureTokenExpiryLabel(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

function renderCaptureTokenSettings() {
  if (currentUserIsChild()) {
    return "";
  }
  if (tokenIsDemo()) {
    return `
      <section class="card">
        <h2>Chrome capture token</h2>
        <p class="muted">Demo mode has no household lockbox, so capture tokens are not issued here.</p>
      </section>`;
  }
  const status = state.captureTokenStatus || { active: false };
  const secret = state.captureTokenSecret || "";
  const until = captureTokenExpiryLabel(status.expires_at);
  const summary = status.active
    ? `A capture token is active${until ? ` until ${escapeHtml(until)}` : ""}. Generating a new one disconnects the old one on the student’s computer.`
    : "No capture token is active. Generate one, then paste it into the Chrome extension on the student’s computer.";
  return `
    <section class="card">
      <div class="invite-toolbar">
        <div>
          <h2>Chrome capture token</h2>
          <p class="muted">${summary}</p>
        </div>
        <div class="form-actions">
          <button type="button" data-action="generate-capture-token">
            ${status.active ? "Generate new token" : "Generate token"}
          </button>
          ${
            status.active
              ? `<button type="button" class="ghost danger" data-action="revoke-capture-token">Revoke</button>`
              : ""
          }
        </div>
      </div>
      ${
        secret
          ? `<label>Copy this token now. It is not shown again.
              <span class="capture-token-row">
                <input class="capture-token-secret" type="text" readonly
                       value="${escapeHtml(secret)}" aria-label="Capture token">
                <button type="button" class="ghost" data-action="copy-capture-token">Copy</button>
              </span>
            </label>`
          : `<p class="muted">This token can only upload screenshots. It is not a parent login.</p>`
      }
    </section>`;
}

function renderStudentPinSettings(student) {
  const hasLogin = Boolean(student.has_login);
  return `
    <section class="card pin-settings">
      <h3>Student login PIN</h3>
      <p class="muted">${
        hasLogin
          ? "This child can sign in by picking their name and entering a PIN."
          : "Set a PIN so this child can sign in and use homework help."
      }</p>
      <label>${hasLogin ? "New PIN" : "PIN"}
        <input id="student-pin-input" name="student_pin" type="password" inputmode="numeric"
               pattern="[0-9]*" minlength="4" maxlength="8" autocomplete="off">
      </label>
      <div class="form-actions">
        <button type="button" data-action="set-student-pin" data-student-id="${student.id}">
          ${hasLogin ? "Change PIN" : "Set PIN"}
        </button>
        ${
          hasLogin
            ? `<button type="button" class="ghost danger" data-action="clear-student-pin"
                       data-student-id="${student.id}">Remove login</button>`
            : ""
        }
      </div>
    </section>`;
}

function catalogKind() {
  return state.catalogKind === "plans" ? "plans" : "books";
}

function renderCatalogKindTabs() {
  const kind = catalogKind();
  const tabs = [
    ["books", "Literature & Books"],
    ["plans", "Structured Pacing Guides"],
  ];
  return `
    <div class="segmented catalog-kind-tabs" role="tablist" aria-label="Catalog type">
      ${tabs
        .map(
          ([value, label]) => `
        <button type="button" role="tab" data-action="catalog-kind" data-kind="${value}"
                class="${value === kind ? "active" : ""}"
                aria-selected="${value === kind}">
          ${label}
        </button>`
        )
        .join("")}
    </div>`;
}

function pacingPlanStatusBadge(item) {
  if (item.status === "processing") {
    const paper = item.title === "Paper Import" || item.id === paperImportPlanId;
    return `<span class="tag plan-processing" aria-live="polite">
      <span class="plan-spinner" aria-hidden="true"></span>
      ${paper ? "Transcribing handwriting" : "Parsing with AI"}
    </span>`;
  }
  if (item.status === "failed") {
    const paper = item.title === "Paper Import";
    return `<span class="tag plan-failed">${paper ? "Handwriting failed" : "AI parsing failed"}</span>`;
  }
  return "";
}

function planIsProcessing(planId) {
  const plan = (state.curriculumPlans || []).find((item) => item.id === Number(planId));
  return Boolean(plan && plan.status === "processing");
}

function pacingPlanCard(item) {
  const publisher = item.publisher || "No publisher";
  const subject = item.subject || "No subject";
  const grade = item.grade_level || "No grade";
  const count = Number(item.lesson_count) || 0;
  const lessonLabel = count === 1 ? "1 lesson" : `${count} lessons`;
  const days = Number(item.frequency_days) || 5;
  const weeks = Number(item.total_weeks) || 36;
  const processing = item.status === "processing";
  const failed = item.status === "failed";
  const paper = item.title === "Paper Import" || item.id === paperImportPlanId;
  const disabledAttrs = processing
    ? ' disabled aria-disabled="true" title="Wait for AI processing to finish"'
    : "";
  const meta = processing
    ? paper
      ? "Transcribing handwriting with Ollama. Edit and Apply unlock when it finishes."
      : "The AI is reading this PDF. Edit and Apply unlock when it finishes."
    : failed
      ? paper
        ? "Handwriting extraction failed. You can edit the plan by hand or try another photo."
        : "Parsing did not find lessons. You can edit the plan by hand or delete it."
      : `${publisher} · ${subject} · ${grade} · ${lessonLabel} · ${days} day${days === 1 ? "" : "s"}/week · ${weeks} week${weeks === 1 ? "" : "s"}`;
  const rowClass = processing ? " is-processing" : failed ? " is-failed" : "";
  return `
    <div class="list-row${rowClass}">
      ${pacingPlanStatusBadge(item)}
      <strong>${escapeHtml(item.title)}</strong>
      <p class="meta">${escapeHtml(meta)}</p>
      <div class="list-row-actions">
        <button type="button" class="ghost small" data-action="edit-lesson-plan"
                data-plan-id="${item.id}"${disabledAttrs}>Edit</button>
        <button type="button" class="small" data-action="apply-lesson-plan"
                data-plan-id="${item.id}"${disabledAttrs}>Apply this lesson plan</button>
        <button type="button" class="ghost small" data-action="archive-lesson-plan"
                data-plan-id="${item.id}">Archive</button>
        <button type="button" class="ghost small danger" data-action="delete-lesson-plan"
                data-plan-id="${item.id}">Delete</button>
      </div>
    </div>`;
}

function pendingPdfImportCard() {
  return `
    <div class="list-row is-processing">
      <span class="tag plan-processing" aria-live="polite">
        <span class="plan-spinner" aria-hidden="true"></span>
        Uploading PDF
      </span>
      <strong>New pacing guide</strong>
      <p class="meta">Sending the file to the AI parser…</p>
    </div>`;
}

function pendingPaperImportCard() {
  const scanning = paperImportPhase === "scanning";
  return `
    <div class="list-row is-processing">
      <span class="tag plan-processing" aria-live="polite">
        <span class="plan-spinner" aria-hidden="true"></span>
        ${scanning ? "Scanning page" : "Reading handwriting"}
      </span>
      <strong>Paper import</strong>
      <p class="meta">${scanning ? "Scanning page geometry..." : "Transcribing handwriting with Ollama..."}</p>
    </div>`;
}

function renderPacingGuidesCatalog() {
  const plans = state.curriculumPlans || [];
  const showPendingPdf = pdfImportBusy;
  const showPendingPaper = paperImportBusy && paperImportPhase === "scanning";
  const listHtml =
    plans.length || showPendingPdf || showPendingPaper
      ? `<div class="list">${showPendingPdf ? pendingPdfImportCard() : ""}${showPendingPaper ? pendingPaperImportCard() : ""}${plans.map(pacingPlanCard).join("")}</div>`
      : `<p class="empty">No pacing guides yet. Create a lesson plan, import a CSV, import a PDF, or photograph a paper template.</p>`;
  return `
    <section class="card">
      <div class="card-heading">
        <h2>Structured Pacing Guides</h2>
        <div class="card-heading-actions">
          <button type="button" class="small" data-action="create-lesson-plan">
            + Create Lesson Plan
          </button>
          <button type="button" class="ghost small" data-action="import-curriculum-csv">
            Import Curriculum (CSV)
          </button>
          <button type="button" class="ghost small" data-action="import-curriculum-pdf"
                  ${pdfImportBusy ? "disabled" : ""}>
            ${pdfImportBusy ? "Uploading PDF…" : "Import PDF (AI)"}
          </button>
          <button type="button" id="btn-download-paper-template" class="ghost small btn btn-secondary"
                  data-action="download-paper-template" ${paperTemplateBusy ? "disabled" : ""}>
            Download Paper Template
          </button>
          <button type="button" id="btn-import-paper" class="small btn btn-primary"
                  data-action="import-paper" ${paperImportBusy ? "disabled" : ""}>
            ${paperImportBusy ? "Importing paper…" : "Import from Paper"}
          </button>
        </div>
      </div>
      ${listHtml}
    </section>`;
}

function lessonBuilderForm() {
  return $("lesson-builder-form");
}

function lessonBuilderField(name) {
  return lessonBuilderForm()?.querySelector(`[name="${name}"]`);
}

function newLessonLine(week, day, extras = {}) {
  return {
    uid: lessonLineSeq++,
    id: extras.id || null,
    week,
    day,
    title: extras.title || "",
    category: extras.category || "Daily Work",
    time_slot: extras.time_slot || "",
    notes: extras.notes || "",
    resources: Array.isArray(extras.resources) ? extras.resources.slice() : [],
  };
}

function timeSlotSortKey(value) {
  const text = (value || "").trim();
  if (!text) return [99, 0];
  const match = text.match(/(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?/i);
  if (!match) return [50, 0];
  let hour = Number(match[1]);
  const minute = Number(match[2] || 0);
  const ampm = (match[3] || "").toLowerCase().replace(/\./g, "");
  if (ampm.startsWith("p") && hour < 12) hour += 12;
  if (ampm.startsWith("a") && hour === 12) hour = 0;
  return [hour, minute];
}

function compareLessonLines(a, b) {
  const week = a.week - b.week;
  if (week) return week;
  const day = a.day - b.day;
  if (day) return day;
  const [hourA, minuteA] = timeSlotSortKey(a.time_slot);
  const [hourB, minuteB] = timeSlotSortKey(b.time_slot);
  if (hourA !== hourB) return hourA - hourB;
  if (minuteA !== minuteB) return minuteA - minuteB;
  return a.uid - b.uid;
}

function sortedLessonLines() {
  return [...lessonBuilder.lines].sort(compareLessonLines);
}

function findLessonLine(uid) {
  return lessonBuilder.lines.find((line) => line.uid === Number(uid));
}

function builderFrequency() {
  return Math.min(7, Math.max(1, Number(lessonBuilderField("frequency_days")?.value) || 5));
}

function builderWeeks() {
  return Math.min(52, Math.max(1, Number(lessonBuilderField("total_weeks")?.value) || 36));
}

function linesForSlot(week, day) {
  return sortedLessonLines().filter((line) => line.week === week && line.day === day);
}

function slotTemplate(week, day) {
  return linesForSlot(week, day).filter(lessonLineHasContent);
}

function cloneTemplateToSlot(template, week, day) {
  lessonBuilder.lines = lessonBuilder.lines.filter(
    (line) => !(line.week === week && line.day === day)
  );
  if (!template.length) {
    lessonBuilder.lines.push(newLessonLine(week, day));
    return;
  }
  for (const item of template) {
    lessonBuilder.lines.push(
      newLessonLine(week, day, {
        title: item.title,
        category: item.category,
        time_slot: item.time_slot,
        notes: item.notes,
      })
    );
  }
}

function ensureBuilderGrid() {
  const weeks = Number(lessonBuilderField("total_weeks")?.value) || lessonBuilder.total_weeks || 36;
  const days = Number(lessonBuilderField("frequency_days")?.value) || 5;
  const totalWeeks = Math.min(52, Math.max(1, weeks));
  const frequency = Math.min(7, Math.max(1, days));
  lessonBuilder.lines = lessonBuilder.lines.filter(
    (line) => line.week >= 1 && line.week <= totalWeeks && line.day >= 1 && line.day <= frequency
  );
  const seen = new Set(lessonBuilder.lines.map((line) => `${line.week}-${line.day}`));
  for (let week = 1; week <= totalWeeks; week += 1) {
    for (let day = 1; day <= frequency; day += 1) {
      if (!seen.has(`${week}-${day}`)) {
        lessonBuilder.lines.push(newLessonLine(week, day));
      }
    }
  }
}

function lessonLineHasContent(line) {
  return Boolean(
    (line.title || "").trim() || (line.notes || "").trim() || (line.resources || []).length
  );
}

function defaultLessonWeights() {
  return [
    { category: "Daily Work", weight: 40 },
    { category: "Quiz", weight: 30 },
    { category: "Test", weight: 30 },
  ];
}

function resetLessonBuilder() {
  lessonBuilder.planId = null;
  lessonBuilder.tab = "assignments";
  lessonBuilder.lines = [];
  lessonBuilder.weights = defaultLessonWeights();
  const form = lessonBuilderForm();
  if (!form) return;
  form.reset();
  lessonBuilderField("frequency_days").value = "5";
  lessonBuilderField("total_weeks").value = "36";
  ensureBuilderGrid();
}

function hydrateLessonBuilder(plan) {
  lessonBuilder.planId = plan.id;
  lessonBuilderField("title").value = plan.title || "";
  lessonBuilderField("subject").value = plan.subject || "";
  lessonBuilderField("grade_level").value = plan.grade_level || "";
  lessonBuilderField("frequency_days").value = String(plan.frequency_days || 5);
  lessonBuilderField("total_weeks").value = String(plan.total_weeks || 36);
  const weights = plan.grading_weights || {};
  lessonBuilder.weights = Object.keys(weights).length
    ? Object.entries(weights).map(([category, weight]) => ({
        category,
        weight: Number(weight),
      }))
    : defaultLessonWeights();
  lessonBuilder.lines = (plan.lessons || []).map((lesson) =>
    newLessonLine(lesson.week_number || 1, lesson.day_number, {
      id: lesson.id,
      title: lesson.title || "",
      category: lesson.category || "Daily Work",
      time_slot: lesson.time_slot || "",
      notes: lesson.notes || "",
      resources: lesson.resources || [],
    })
  );
  ensureBuilderGrid();
  if (!(plan.lessons || []).length) {
    lessonBuilderError(
      "No assignments were extracted from this PDF. If it is a scanned schedule, re-import it, or stack subjects on Week 1, Day 1 and replicate them."
    );
  }
}

function lessonBuilderError(message) {
  const el = $("lesson-builder-error");
  el.hidden = !message;
  el.textContent = message || "";
}

function isLessonBuilderOpen() {
  return Boolean($("lesson-plan-modal")) && !$("lesson-plan-modal").hidden;
}

function setLessonBuilderTab(tab) {
  lessonBuilder.tab = tab === "notes" || tab === "grading" ? tab : "assignments";
  $("lesson-builder-form")
    .querySelectorAll("[data-action='lesson-builder-tab']")
    .forEach((button) => {
      const active = button.dataset.tab === lessonBuilder.tab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
  renderLessonBuilderPanel();
}

function categoryOptions(selected) {
  const current = selected || "Daily Work";
  const values = LESSON_CATEGORIES.includes(current)
    ? LESSON_CATEGORIES
    : [current, ...LESSON_CATEGORIES];
  return values
    .map(
      (value) =>
        `<option value="${escapeHtml(value)}"${value === current ? " selected" : ""}>${escapeHtml(value)}</option>`
    )
    .join("");
}

function lineResourceChips(line) {
  if (!line.resources.length) return "";
  return `<div class="builder-resources">${line.resources
    .map(
      (url, index) => `
        <span class="builder-resource">
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>
          <button type="button" data-action="remove-lesson-resource" data-uid="${line.uid}"
                  data-index="${index}" aria-label="Remove resource">&times;</button>
        </span>`
    )
    .join("")}</div>`;
}

function renderAssignmentsTab() {
  const rows = sortedLessonLines()
    .map(
      (line) => `
      <tr data-uid="${line.uid}">
        <td class="builder-slot">Week ${line.week}, Day ${line.day}</td>
        <td class="builder-time">
          <input name="line-time-slot" maxlength="64" placeholder="8:30–9:00"
                 value="${escapeHtml(line.time_slot || "")}" data-uid="${line.uid}"
                 aria-label="Time slot for week ${line.week} day ${line.day}">
        </td>
        <td>
          <input name="line-title" maxlength="255" value="${escapeHtml(line.title)}"
                 data-uid="${line.uid}" aria-label="Assignment title for week ${line.week} day ${line.day}">
          ${lineResourceChips(line)}
        </td>
        <td>
          <select data-action="lesson-line-category" data-uid="${line.uid}"
                  aria-label="Category for week ${line.week} day ${line.day}">
            ${categoryOptions(line.category)}
          </select>
        </td>
        <td>
          <select data-action="lesson-line-menu" data-uid="${line.uid}" aria-label="Row options">
            <option value="">Options</option>
            <option value="resource">Add resource link</option>
            <option value="extra">Add extra assignment</option>
            <option value="delete">Delete</option>
          </select>
        </td>
      </tr>`
    )
    .join("");
  return `
    <div class="lesson-builder-toolbar">
      <label>To every day, add this:
        <span class="isbn-lookup-row">
          <input id="lesson-every-day" maxlength="255" placeholder="Morning basket, copywork…">
          <button type="button" class="ghost" data-action="lesson-every-day">Add</button>
        </span>
      </label>
      <button type="button" class="ghost" data-action="lesson-autogenerate">Auto-Generate Pattern</button>
    </div>
    <div class="lesson-builder-toolbar lesson-builder-routine-actions">
      <button type="button" class="ghost" data-action="lesson-replicate-day1"
              title="Clone Week 1 Day 1’s subjects, times, and categories onto every other school day">
        Replicate Day 1 to All Days
      </button>
      <button type="button" class="ghost" data-action="lesson-fill-routine"
              title="Copy each Week 1 weekday’s stack onto the same weekday in later weeks">
        Fill Routine across Weeks
      </button>
    </div>
    <p class="muted">Stack several subjects on Week 1, Day 1 (Bible, Phonics, Math…). Ctrl + Enter adds another block to that day. Replicate Day 1 copies that stack everywhere; Fill Routine copies Week 1 onto the remaining weeks.</p>
    <div class="lesson-builder-scroll">
      <table class="builder-table">
        <thead>
          <tr><th>Day</th><th>Time</th><th>Assignment</th><th>Category</th><th>Row</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function renderNotesTab() {
  const rows = sortedLessonLines()
    .map(
      (line) => `
      <tr data-uid="${line.uid}">
        <td class="builder-slot">Week ${line.week}, Day ${line.day}${
          line.time_slot ? ` · ${escapeHtml(line.time_slot)}` : ""
        }</td>
        <td>${escapeHtml(line.title || "Untitled")}</td>
        <td>
          <textarea data-action="lesson-line-notes" data-uid="${line.uid}" rows="2"
                    aria-label="Notes for week ${line.week} day ${line.day}">${escapeHtml(line.notes)}</textarea>
        </td>
      </tr>`
    )
    .join("");
  return `
    <p class="muted">Instructions for each day. These copy onto the student’s assignment when you apply the plan.</p>
    <div class="lesson-builder-scroll">
      <table class="builder-table">
        <thead>
          <tr><th>Day</th><th>Assignment</th><th>Notes</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function weightSum() {
  return lessonBuilder.weights.reduce((sum, row) => sum + (Number(row.weight) || 0), 0);
}

function renderGradingTab() {
  const sum = weightSum();
  const weightRows = lessonBuilder.weights
    .map(
      (row, index) => `
      <div class="weight-row">
        <label>Category
          <input data-action="lesson-weight-category" data-index="${index}" maxlength="64"
                 value="${escapeHtml(row.category)}">
        </label>
        <label>Weight %
          <input data-action="lesson-weight-value" data-index="${index}" type="number" min="0" max="100"
                 step="1" value="${escapeHtml(String(row.weight ?? ""))}">
        </label>
        <button type="button" class="ghost small" data-action="lesson-weight-remove" data-index="${index}">Remove</button>
      </div>`
    )
    .join("");
  const weekOptions = Array.from(
    { length: Number(lessonBuilderField("total_weeks")?.value) || 36 },
    (_, index) => `<option value="${index + 1}">Week ${index + 1}</option>`
  ).join("");
  const dayOptions = Array.from(
    { length: Number(lessonBuilderField("frequency_days")?.value) || 5 },
    (_, index) => `<option value="${index + 1}">Day ${index + 1}</option>`
  ).join("");
  const resourceItems = sortedLessonLines()
    .flatMap((line) =>
      line.resources.map(
        (url, index) => `
        <div class="resource-item">
          <span>Week ${line.week}, Day ${line.day} · <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a></span>
          <button type="button" class="ghost small" data-action="remove-lesson-resource"
                  data-uid="${line.uid}" data-index="${index}">Remove</button>
        </div>`
      )
    )
    .join("");
  return `
    <section>
      <h3>Category weights</h3>
      <div class="weight-rows">${weightRows || `<p class="empty">No grading categories yet.</p>`}</div>
      <button type="button" class="ghost small" data-action="lesson-weight-add">Add category</button>
      <p class="weight-sum${sum === 100 ? "" : " is-warn"}">Total: ${sum}%${sum === 100 ? "" : " (aim for 100%)"}</p>
    </section>
    <section>
      <h3>Resource links</h3>
      <div class="resource-add">
        <label>Week<select id="lesson-resource-week">${weekOptions}</select></label>
        <label>Day<select id="lesson-resource-day">${dayOptions}</select></label>
        <label>URL<input id="lesson-resource-url" type="url" maxlength="512" placeholder="https://"></label>
        <button type="button" data-action="lesson-resource-add">Attach</button>
      </div>
      <div class="resource-manager">${resourceItems || `<p class="empty">No links attached yet.</p>`}</div>
    </section>`;
}

function renderLessonBuilderPanel() {
  const panel = $("lesson-builder-panel");
  if (!panel) return;
  if (lessonBuilder.tab === "notes") panel.innerHTML = renderNotesTab();
  else if (lessonBuilder.tab === "grading") panel.innerHTML = renderGradingTab();
  else panel.innerHTML = renderAssignmentsTab();
}

function openLessonBuilderNew() {
  lastFocused = document.activeElement;
  resetLessonBuilder();
  $("lesson-builder-title").textContent = "Create Lesson Plan";
  lessonBuilderError("");
  setLessonBuilderTab("assignments");
  $("lesson-plan-modal").hidden = false;
  document.body.classList.add("modal-open");
  lessonBuilderField("title")?.focus();
}

async function openLessonBuilderEdit(planId) {
  if (planIsProcessing(planId)) {
    flash("This lesson plan is still being processed.", true);
    return;
  }
  lastFocused = document.activeElement;
  lessonBuilderError("");
  try {
    const plan = await api(`/curriculum/plans/${planId}`);
    hydrateLessonBuilder(plan);
    $("lesson-builder-title").textContent = "Edit Lesson Plan";
    setLessonBuilderTab("assignments");
    $("lesson-plan-modal").hidden = false;
    document.body.classList.add("modal-open");
    lessonBuilderField("title")?.focus();
  } catch (error) {
    flash(error.message, true);
  }
}

function closeLessonBuilder() {
  const modal = $("lesson-plan-modal");
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  lessonBuilderError("");
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus();
  }
}

function builderPayload() {
  ensureBuilderGrid();
  const weights = {};
  for (const row of lessonBuilder.weights) {
    const category = (row.category || "").trim();
    if (!category) continue;
    weights[category] = Number(row.weight) || 0;
  }
  return {
    title: (lessonBuilderField("title")?.value || "").trim(),
    subject: emptyToNull(lessonBuilderField("subject")?.value),
    grade_level: emptyToNull(lessonBuilderField("grade_level")?.value),
    frequency_days: Number(lessonBuilderField("frequency_days")?.value) || 5,
    total_weeks: Number(lessonBuilderField("total_weeks")?.value) || 36,
    grading_weights: Object.keys(weights).length ? weights : null,
    lessons: sortedLessonLines()
      .filter(lessonLineHasContent)
      .map((line) => {
        const item = {
          week_number: line.week,
          day_number: line.day,
          title: (line.title || "").trim(),
          notes: emptyToNull(line.notes),
          category: emptyToNull(line.category),
          time_slot: emptyToNull(line.time_slot),
          resources: line.resources,
        };
        if (line.id) item.id = line.id;
        return item;
      }),
  };
}

async function saveLessonPlan({ closeAfter }) {
  const payload = builderPayload();
  if (!payload.title) {
    lessonBuilderError("Add a title for this lesson plan.");
    lessonBuilderField("title")?.focus();
    return;
  }
  const path = lessonBuilder.planId
    ? `/curriculum/plans/${lessonBuilder.planId}`
    : "/curriculum/plans";
  const method = lessonBuilder.planId ? "PUT" : "POST";
  const buttons = $("lesson-plan-modal").querySelectorAll("footer button");
  buttons.forEach((button) => {
    button.disabled = true;
  });
  lessonBuilderError("");
  try {
    const saved = await api(path, { method, body: JSON.stringify(payload) });
    if (isOfflineQueued(saved)) return;
    hydrateLessonBuilder(saved);
    $("lesson-builder-title").textContent = "Edit Lesson Plan";
    state.curriculumPlans = await api("/curriculum/plans");
    render();
    if (closeAfter) {
      closeLessonBuilder();
    } else {
      renderLessonBuilderPanel();
    }
    flash("Lesson plan saved.");
  } catch (error) {
    lessonBuilderError(error.message);
  } finally {
    buttons.forEach((button) => {
      button.disabled = false;
    });
  }
}

function addLessonToEveryDay() {
  const input = $("lesson-every-day");
  const title = (input?.value || "").trim();
  if (!title) return;
  const slots = new Map();
  for (const line of sortedLessonLines()) {
    const key = `${line.week}-${line.day}`;
    if (!slots.has(key)) slots.set(key, []);
    slots.get(key).push(line);
  }
  for (const lines of slots.values()) {
    const empty = lines.find((line) => !(line.title || "").trim());
    if (empty) empty.title = title;
    else lessonBuilder.lines.push(newLessonLine(lines[0].week, lines[0].day, { title }));
  }
  if (input) input.value = "";
  renderLessonBuilderPanel();
}

function autogenerateLessonPattern() {
  ensureBuilderGrid();
  const days = builderFrequency();
  const weeks = builderWeeks();
  let stack = null;
  for (let week = 1; week <= weeks; week += 1) {
    for (let day = 1; day <= days; day += 1) {
      const filled = slotTemplate(week, day);
      if (filled.length >= 2) {
        stack = { week, day, items: filled };
        break;
      }
    }
    if (stack) break;
  }
  if (stack) {
    for (let week = 1; week <= weeks; week += 1) {
      let weekHasContent = false;
      for (let day = 1; day <= days; day += 1) {
        if (slotTemplate(week, day).length) {
          weekHasContent = true;
          break;
        }
      }
      if (!weekHasContent && week !== stack.week) continue;
      for (let day = 1; day <= days; day += 1) {
        if (week === stack.week && day === stack.day) continue;
        if (!slotTemplate(week, day).length) {
          cloneTemplateToSlot(stack.items, week, day);
        }
      }
    }
    renderLessonBuilderPanel();
    flash("Copied the daily subject stack onto empty days in that week.");
    return;
  }
  let n = 1;
  for (const line of sortedLessonLines()) {
    if ((line.title || "").trim()) continue;
    line.title = `Lesson ${n}`;
    n += 1;
  }
  renderLessonBuilderPanel();
}

function replicateDay1ToAllDays() {
  ensureBuilderGrid();
  const template = slotTemplate(1, 1);
  if (!template.length) {
    lessonBuilderError("Add assignments on Week 1, Day 1 first, then replicate that day’s stack.");
    return;
  }
  const days = builderFrequency();
  const weeks = builderWeeks();
  for (let week = 1; week <= weeks; week += 1) {
    for (let day = 1; day <= days; day += 1) {
      if (week === 1 && day === 1) continue;
      cloneTemplateToSlot(template, week, day);
    }
  }
  lessonBuilderError("");
  renderLessonBuilderPanel();
  flash("Copied Week 1, Day 1 to every school day.");
}

function fillRoutineAcrossWeeks() {
  ensureBuilderGrid();
  const days = builderFrequency();
  const weeks = builderWeeks();
  const day1 = slotTemplate(1, 1);
  if (!day1.length) {
    lessonBuilderError("Add a Week 1, Day 1 routine first, then fill it across later weeks.");
    return;
  }
  let otherWeek1Filled = false;
  for (let day = 2; day <= days; day += 1) {
    if (slotTemplate(1, day).length) {
      otherWeek1Filled = true;
      break;
    }
  }
  if (!otherWeek1Filled) {
    for (let day = 2; day <= days; day += 1) {
      cloneTemplateToSlot(day1, 1, day);
    }
  }
  for (let week = 2; week <= weeks; week += 1) {
    for (let day = 1; day <= days; day += 1) {
      cloneTemplateToSlot(slotTemplate(1, day), week, day);
    }
  }
  lessonBuilderError("");
  renderLessonBuilderPanel();
  flash("Copied the Week 1 routine across the remaining weeks.");
}

function addExtraLessonLine(uid, title = "") {
  const line = findLessonLine(uid);
  if (!line) return null;
  const extra = newLessonLine(line.week, line.day, { title, category: line.category });
  const index = lessonBuilder.lines.indexOf(line);
  lessonBuilder.lines.splice(index + 1, 0, extra);
  return extra;
}

function deleteLessonLine(uid) {
  const line = findLessonLine(uid);
  if (!line) return;
  const siblings = lessonBuilder.lines.filter(
    (item) => item.week === line.week && item.day === line.day
  );
  if (siblings.length > 1) {
    lessonBuilder.lines = lessonBuilder.lines.filter((item) => item.uid !== line.uid);
    return;
  }
  line.id = null;
  line.title = "";
  line.notes = "";
  line.time_slot = "";
  line.resources = [];
  line.category = "Daily Work";
}

function addResourceToLine(uid, url) {
  const line = findLessonLine(uid);
  const cleaned = (url || "").trim();
  if (!line || !cleaned) return;
  if (!line.resources.includes(cleaned)) line.resources.push(cleaned);
}

function firstLineForSlot(week, day) {
  return (
    sortedLessonLines().find((line) => line.week === week && line.day === day) ||
    null
  );
}

function attachResourceToSlot() {
  const week = Number($("lesson-resource-week")?.value);
  const day = Number($("lesson-resource-day")?.value);
  const url = ($("lesson-resource-url")?.value || "").trim();
  if (!week || !day || !url) return;
  const line = firstLineForSlot(week, day);
  if (!line) return;
  if (!line.resources.includes(url)) line.resources.push(url);
  renderLessonBuilderPanel();
}

function applyPlanError(message) {
  const el = $("apply-plan-error");
  el.hidden = !message;
  el.textContent = message || "";
}

function applyPlanWeekdays() {
  return [...$("apply-plan-weekdays").querySelectorAll("input:checked")].map((box) =>
    Number(box.value)
  );
}

function isApplyPlanOpen() {
  return Boolean($("apply-plan-modal")) && !$("apply-plan-modal").hidden;
}

function openApplyPlan(planId) {
  if (planIsProcessing(planId)) {
    flash("This lesson plan is still being processed.", true);
    return;
  }
  const plan = (state.curriculumPlans || []).find((item) => item.id === Number(planId));
  if (!state.students.length) {
    flash("Add a student before applying a lesson plan.", true);
    return;
  }
  applyPlanState.planId = Number(planId);
  applyPlanState.title = plan ? plan.title : "this lesson plan";
  applyPlanError("");
  $("apply-plan-title").textContent = "Apply this lesson plan";
  $("apply-plan-copy").textContent = `Schedule “${applyPlanState.title}” on a student’s calendar. Empty days still take a school date so later weeks stay aligned.`;
  const form = $("apply-plan-form");
  fillSelect(form.querySelector('[name="student_id"]'), state.students, (item) => item.name);
  form.querySelector('[name="start_date"]').value = todayISO();
  const savedDays = classWeekdays().map(String);
  $("apply-plan-weekdays")
    .querySelectorAll("input")
    .forEach((box) => {
      box.checked = savedDays.includes(box.value);
    });
  lastFocused = document.activeElement;
  $("apply-plan-modal").hidden = false;
  document.body.classList.add("modal-open");
  form.querySelector('[name="student_id"]').focus();
}

function closeApplyPlan() {
  const modal = $("apply-plan-modal");
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  applyPlanError("");
  applyPlanState.planId = null;
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus();
  }
}

async function submitApplyPlan() {
  const form = $("apply-plan-form");
  const studentId = Number(form.querySelector('[name="student_id"]').value);
  const startDate = form.querySelector('[name="start_date"]').value;
  const targetDays = applyPlanWeekdays();
  if (!applyPlanState.planId) return;
  if (!studentId) {
    applyPlanError("Choose a student.");
    return;
  }
  if (!startDate) {
    applyPlanError("Choose a start date.");
    return;
  }
  if (!targetDays.length) {
    applyPlanError("Pick at least one school day.");
    return;
  }
  applyPlanError("");
  try {
    const result = await api(`/curriculum/plans/${applyPlanState.planId}/apply`, {
      method: "POST",
      body: JSON.stringify({
        student_id: studentId,
        start_date: startDate,
        target_days: targetDays,
      }),
    });
    if (isOfflineQueued(result)) return;
    closeApplyPlan();
    await refresh();
    if (routeName() === "assignments") await loadCalendar();
    render();
    const from = MEDIUM_DATE.format(parseISODate(result.first_scheduled_date));
    const to = MEDIUM_DATE.format(parseISODate(result.last_scheduled_date));
    flash(`${result.assignments_created} lessons scheduled, ${from} to ${to}.`);
  } catch (error) {
    applyPlanError(error.message);
  }
}

async function archiveLessonPlan(planId) {
  const plan = (state.curriculumPlans || []).find((item) => item.id === Number(planId));
  const title = plan ? plan.title : "this lesson plan";
  if (!window.confirm(`Archive “${title}”? It will leave this list.`)) {
    return;
  }
  try {
    const result = await api(`/curriculum/plans/${planId}/archive`, {
      method: "POST",
      body: JSON.stringify({ is_archived: true }),
    });
    if (isOfflineQueued(result)) return;
    state.curriculumPlans = await api("/curriculum/plans");
    render();
    flash("Lesson plan archived.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function deleteLessonPlan(planId) {
  const plan = (state.curriculumPlans || []).find((item) => item.id === Number(planId));
  const title = plan ? plan.title : "this lesson plan";
  if (!window.confirm(`Delete “${title}”? This cannot be undone.`)) return;
  try {
    const result = await api(`/curriculum/plans/${planId}`, { method: "DELETE" });
    if (isOfflineQueued(result)) return;
    state.curriculumPlans = await api("/curriculum/plans");
    render();
    flash("Lesson plan deleted.");
  } catch (error) {
    flash(error.message, true);
  }
}

function handleLessonBuilderInput(event) {
  const titleInput = event.target.closest("input[name='line-title']");
  if (titleInput) {
    const line = findLessonLine(titleInput.dataset.uid);
    if (line) line.title = titleInput.value;
    return;
  }
  const timeSlot = event.target.closest("input[name='line-time-slot']");
  if (timeSlot) {
    const line = findLessonLine(timeSlot.dataset.uid);
    if (line) line.time_slot = timeSlot.value;
    return;
  }
  const notes = event.target.closest("[data-action='lesson-line-notes']");
  if (notes) {
    const line = findLessonLine(notes.dataset.uid);
    if (line) line.notes = notes.value;
    return;
  }
  const categoryName = event.target.closest("[data-action='lesson-weight-category']");
  if (categoryName) {
    const row = lessonBuilder.weights[Number(categoryName.dataset.index)];
    if (row) row.category = categoryName.value;
    return;
  }
  const weightValue = event.target.closest("[data-action='lesson-weight-value']");
  if (weightValue) {
    const row = lessonBuilder.weights[Number(weightValue.dataset.index)];
    if (row) row.weight = Number(weightValue.value) || 0;
    const sum = $("lesson-builder-panel")?.querySelector(".weight-sum");
    if (sum) {
      const total = weightSum();
      sum.textContent = `Total: ${total}%${total === 100 ? "" : " (aim for 100%)"}`;
      sum.classList.toggle("is-warn", total !== 100);
    }
  }
}

function handleLessonBuilderChange(event) {
  const grid = event.target.closest("[data-action='lesson-builder-grid']");
  if (grid) {
    ensureBuilderGrid();
    renderLessonBuilderPanel();
    return;
  }
  const category = event.target.closest("[data-action='lesson-line-category']");
  if (category) {
    const line = findLessonLine(category.dataset.uid);
    if (line) line.category = category.value;
    return;
  }
  const menu = event.target.closest("[data-action='lesson-line-menu']");
  if (!menu) return;
  const uid = menu.dataset.uid;
  const action = menu.value;
  menu.value = "";
  if (action === "resource") {
    const url = window.prompt("Resource URL");
    if (url) addResourceToLine(uid, url);
    renderLessonBuilderPanel();
  } else if (action === "extra") {
    const extra = addExtraLessonLine(uid);
    renderLessonBuilderPanel();
    $("lesson-builder-panel")
      ?.querySelector(`input[name='line-title'][data-uid='${extra?.uid}']`)
      ?.focus();
  } else if (action === "delete") {
    deleteLessonLine(uid);
    renderLessonBuilderPanel();
  }
}

function handleLessonBuilderClick(event) {
  const control = event.target.closest("[data-action]");
  if (!control) return;
  switch (control.dataset.action) {
    case "close-lesson-builder":
      closeLessonBuilder();
      break;
    case "lesson-builder-tab":
      setLessonBuilderTab(control.dataset.tab);
      break;
    case "save-lesson-draft":
      saveLessonPlan({ closeAfter: false });
      break;
    case "save-lesson-close":
      saveLessonPlan({ closeAfter: true });
      break;
    case "lesson-every-day":
      addLessonToEveryDay();
      break;
    case "lesson-autogenerate":
      autogenerateLessonPattern();
      break;
    case "lesson-replicate-day1":
      replicateDay1ToAllDays();
      break;
    case "lesson-fill-routine":
      fillRoutineAcrossWeeks();
      break;
    case "lesson-weight-add":
      lessonBuilder.weights.push({ category: "", weight: 0 });
      renderLessonBuilderPanel();
      break;
    case "lesson-weight-remove":
      lessonBuilder.weights.splice(Number(control.dataset.index), 1);
      renderLessonBuilderPanel();
      break;
    case "lesson-resource-add":
      attachResourceToSlot();
      break;
    case "remove-lesson-resource": {
      const line = findLessonLine(control.dataset.uid);
      if (line) line.resources.splice(Number(control.dataset.index), 1);
      renderLessonBuilderPanel();
      break;
    }
    default:
      break;
  }
}

function handleLessonBuilderKeydown(event) {
  if (!(event.ctrlKey || event.metaKey) || event.key !== "Enter") return;
  const input = event.target.closest("input[name='line-title']");
  if (!input || !isLessonBuilderOpen()) return;
  event.preventDefault();
  const extra = addExtraLessonLine(input.dataset.uid);
  renderLessonBuilderPanel();
  $("lesson-builder-panel")
    ?.querySelector(`input[name='line-title'][data-uid='${extra?.uid}']`)
    ?.focus();
}

function handleApplyPlanClick(event) {
  if (event.target.closest("[data-action='close-apply-plan']")) {
    closeApplyPlan();
  }
}

function curriculumCounts() {
  let unscheduled = 0;
  let scheduled = 0;
  for (const item of state.curricula) {
    if (item.is_scheduled) scheduled += 1;
    else unscheduled += 1;
  }
  return { unscheduled, scheduled, all: state.curricula.length };
}

function curriculumCard(item) {
  const details = [item.subject, item.publisher_name, item.description]
    .filter(Boolean)
    .join(" · ");
  const status = item.is_scheduled ? "Scheduled" : "Unscheduled";
  const actions = item.is_scheduled
    ? `<button type="button" class="ghost small" data-action="auto-schedule"
               data-curriculum-id="${item.id}">Auto-schedule</button>
       <button type="button" class="ghost small danger" data-action="unschedule-curriculum"
               data-curriculum-id="${item.id}">Remove from schedule</button>`
    : `<button type="button" class="small" data-action="auto-schedule"
               data-curriculum-id="${item.id}">Auto-schedule a book</button>
       <button type="button" class="ghost small danger" data-action="delete-curriculum"
               data-curriculum-id="${item.id}">Delete</button>`;
  return `
    <div class="list-row">
      <span class="tag">${escapeHtml(status)}</span>
      <span class="tag">${escapeHtml(item.source_type)}</span>
      <strong>${escapeHtml(item.title)}</strong>
      <p class="meta">${escapeHtml(details || "No extra details")}</p>
      <div class="list-row-actions">${actions}</div>
    </div>`;
}

function renderCurricula() {
  const kind = catalogKind();
  if (kind === "plans") {
    return `
      <div class="catalog-page">
        ${renderCatalogKindTabs()}
        ${renderPacingGuidesCatalog()}
      </div>
    `;
  }
  const filter = state.curriculumFilter || "unscheduled";
  const counts = curriculumCounts();
  const visible = state.curricula.filter((item) => {
    if (filter === "scheduled") return item.is_scheduled;
    if (filter === "unscheduled") return !item.is_scheduled;
    return true;
  });
  const emptyMessage =
    filter === "scheduled"
      ? "No scheduled curricula."
      : filter === "unscheduled"
        ? "No unscheduled curricula."
        : "The catalog is empty.";
  const tabs = [
    ["unscheduled", "Unscheduled", counts.unscheduled],
    ["scheduled", "Scheduled", counts.scheduled],
    ["all", "All", counts.all],
  ];
  return `
    <div class="catalog-page">
      ${renderCatalogKindTabs()}
      <div class="layout">
        <form class="card form-grid" data-form="curriculum">
          <h2>Add curriculum</h2>
          <div class="isbn-block">
            <label>ISBN / Barcode Scan
              <span class="isbn-lookup-row">
                <input name="isbn" maxlength="64" placeholder="978-0-306-40615-7" autocomplete="off"
                       inputmode="numeric" aria-describedby="isbn-lookup-status">
                <button type="button" class="ghost" data-action="lookup-isbn">Lookup</button>
              </span>
            </label>
            <p id="isbn-lookup-status" class="isbn-status muted" data-isbn-status hidden></p>
          </div>
          <label>ISBN / Custom SKU (Optional)
            <input name="sku" maxlength="64" autocomplete="off" placeholder="SAXON-3-TG">
          </label>
          <p class="muted">Adding a barcode or SKU helps you and others find this book instantly later.</p>
          <label>Title<input name="title" required maxlength="255"></label>
          <label>Publisher<input name="publisher" maxlength="255"></label>
          <label>Subject<input name="subject" list="subject-suggestions" autocomplete="off"></label>
          <label>Description<textarea name="description"></textarea></label>
          <label>Source
            <select name="source_type">
              ${SOURCE_TYPES.map((value) => `<option value="${value}">${value.replaceAll("_", " ")}</option>`).join("")}
            </select>
          </label>
          <button type="submit">Save curriculum</button>
        </form>
        <section class="card">
          <h2>Catalog</h2>
          <div class="segmented catalog-filters" role="tablist" aria-label="Catalog schedule filter">
            ${tabs
              .map(
                ([value, label, count]) => `
              <button type="button" role="tab" data-action="curriculum-filter" data-filter="${value}"
                      class="${value === filter ? "active" : ""}"
                      aria-selected="${value === filter}">
                ${label} (${count})
              </button>`
              )
              .join("")}
          </div>
          ${
            visible.length
              ? `<div class="list">${visible.map(curriculumCard).join("")}</div>`
              : `<p class="empty">${emptyMessage}</p>`
          }
        </section>
      </div>
    </div>
  `;
}

function renderYears() {
  return `
    <div class="layout">
      <form class="card form-grid" data-form="year">
        <h2>Add school year</h2>
        <label>Name<input name="name" required placeholder="2026-2027"></label>
        <label>Start date<input name="start_date" type="date" required></label>
        <label>End date<input name="end_date" type="date" required></label>
        <button type="submit">Save school year</button>
      </form>
      <section class="card">
        <h2>Years</h2>
        ${
          state.years.length
            ? `<div class="list">${state.years
                .map(
                  (item) => `
              <div class="list-row">
                <strong>${escapeHtml(item.name)}</strong>
                <p class="meta">${escapeHtml(item.start_date)} → ${escapeHtml(item.end_date)}</p>
              </div>`
                )
                .join("")}</div>`
            : `<p class="empty">No school years yet.</p>`
        }
      </section>
    </div>
  `;
}

function renderEnrollments() {
  const canEnroll = state.students.length && state.curricula.length && state.years.length;
  return `
    <div class="layout">
      <form class="card form-grid" data-form="enrollment">
        <h2>Enroll a student</h2>
        ${
          canEnroll
            ? `
          <label>Student<select name="student_id" required>${optionList(state.students, (s) => s.name)}</select></label>
          <label>Curriculum<select name="curriculum_id" required>${optionList(state.curricula, (c) => c.title)}</select></label>
          <label>School year<select name="school_year_id" required>${optionList(state.years, (y) => y.name)}</select></label>
          <label>Start date (optional)<input name="start_date" type="date"></label>
          <label>End date (optional)<input name="end_date" type="date"></label>
          <button type="submit">Save enrollment</button>`
            : `<p class="empty">Add at least one student, curriculum, and school year first.</p>`
        }
      </form>
      <section class="card">
        <h2>Active enrollments</h2>
        ${
          state.enrollments.length
            ? `<div class="list">${state.enrollments
                .map(
                  (row) => `
              <div class="list-row">
                <strong>${escapeHtml(studentName(row.student_id))}</strong>
                <p class="meta">${escapeHtml(curriculumTitle(row.curriculum_id))} · ${escapeHtml(yearName(row.school_year_id))}</p>
              </div>`
                )
                .join("")}</div>`
            : `<p class="empty">No enrollments yet.</p>`
        }
      </section>
    </div>
  `;
}

function renderExceptionSettings() {
  return `
    <div class="layout">
      <form class="card form-grid" data-form="exception">
        <h2>Add exception</h2>
        <p class="muted">Vacations, appointments, and sick days. Retroactive dates are allowed; rescheduling comes later.</p>
        <label>Kind
          <select name="kind" required>
            ${EXCEPTION_KINDS.map((kind) => `<option value="${kind}">${kind}</option>`).join("")}
          </select>
        </label>
        <label>Title<input name="title" required maxlength="255"></label>
        <label>Applies to
          <select name="student_id">${optionList(state.students, (s) => s.name, true)}</select>
        </label>
        <label>Start date<input name="start_date" type="date" required></label>
        <label>End date<input name="end_date" type="date" required></label>
        <label>Notes<textarea name="notes"></textarea></label>
        <button type="submit">Save exception</button>
      </form>
      <section class="card">
        <h2>Calendar exceptions</h2>
        ${exceptionRows(state.exceptions)}
      </section>
    </div>
  `;
}

function renderAdminSettings() {
  const keys = state.inviteKeys || [];
  return `
    <div class="layout">
      <section class="card">
        <div class="invite-toolbar">
          <div>
            <h2>Invite keys</h2>
            <p class="muted">Each key lets one household create an account and provisions their lockbox.</p>
          </div>
          <button type="button" data-action="generate-invite">Generate invite key</button>
        </div>
        ${
          keys.length
            ? `<div class="list">${keys
                .map(
                  (item) => `
              <div class="list-row">
                <strong class="invite-key">${escapeHtml(item.key)}</strong>
                <p class="meta">Unused${
                  item.expires_at ? ` · expires ${escapeHtml(String(item.expires_at).slice(0, 10))}` : ""
                }</p>
              </div>`
                )
                .join("")}</div>`
            : `<p class="empty">No active invite keys.</p>`
        }
      </section>
    </div>
  `;
}

function renderExceptionColorSettings() {
  const colors = exceptionColorMap();
  return `
    <section class="card exception-color-pref">
      <div>
        <h2>Dashboard calendar colors</h2>
        <p class="muted">Days off on the family dashboard use these colors. Hover a square to see the title, like a birthday or holiday.</p>
      </div>
      <div class="exception-color-row">
        ${EXCEPTION_KINDS.map(
          (kind) => `
          <label class="exception-color-pick">
            <span class="exception-color-dot" style="background:${colors[kind]}"></span>
            ${escapeHtml(humanize(kind))}
            <input type="color" data-action="exception-color" data-kind="${kind}"
                   value="${colors[kind]}" aria-label="${escapeHtml(humanize(kind))} color">
          </label>`
        ).join("")}
        <button type="button" class="ghost small" data-action="reset-exception-colors">Reset colors</button>
      </div>
    </section>`;
}

function renderSettings() {
  const panel = settingsPanel();
  const tabs = [
    [SETTINGS_PANELS.students, "Students"],
    [SETTINGS_PANELS.exceptions, "Exceptions"],
    [SETTINGS_PANELS.years, "School Years"],
    [SETTINGS_PANELS.enrollments, "Enrollments"],
  ];
  if (currentUserIsAdmin()) {
    tabs.push([SETTINGS_PANELS.admin, "Admin"]);
  }
  const body = {
    [SETTINGS_PANELS.students]: renderStudentSettings,
    [SETTINGS_PANELS.exceptions]: renderExceptionSettings,
    [SETTINGS_PANELS.years]: renderYears,
    [SETTINGS_PANELS.enrollments]: renderEnrollments,
    [SETTINGS_PANELS.admin]: renderAdminSettings,
  };
  const dark = currentTheme() === "dark";
  const householdName = String(state.household?.name || "").trim();
  const householdValue =
    householdName && householdName !== DEFAULT_HOUSEHOLD_NAME ? householdName : "";
  const selectedIcon = householdIconId(state.household);
  const letter = state.household?.letter || householdInitial(householdName);
  const zone = state.household?.timezone || "";
  const deviceZone = deviceTimeZone();
  const zoneCopy = zone
    ? `School days follow ${escapeHtml(zone)}.`
    : "No time zone yet; “today” follows the server clock.";
  const zoneAction =
    deviceZone && deviceZone !== zone
      ? `<button type="button" class="ghost small" data-action="use-device-timezone">Use this device’s time zone (${escapeHtml(deviceZone)})</button>`
      : "";
  return `
    <section class="settings-hub">
      <section class="card household-pref">
        <div class="household-pref-top">
          <div>
            <h2>Household</h2>
            <p class="muted">This name and icon appear in the sidebar on every page.</p>
          </div>
          <form class="household-name-form" data-form="household">
            <label>Household name
              <input name="name" required maxlength="255" value="${escapeHtml(householdValue)}"
                     placeholder="The Rivera family" autocomplete="organization">
            </label>
            <button type="submit">Save name</button>
          </form>
        </div>
        <div class="household-timezone">
          <p class="muted">${zoneCopy}</p>
          ${zoneAction}
        </div>
        <fieldset class="household-icon-picker">
          <legend>Sidebar icon</legend>
          <p class="muted">The letter skips a leading “The”. Or pick a school icon.</p>
          <div class="household-icon-grid" role="radiogroup" aria-label="Household icon">
            ${HOUSEHOLD_ICONS.map((icon) => {
              const selected = icon.id === selectedIcon;
              const glyph = icon.id === "letter" ? letter : icon.emoji;
              return `
                <button type="button" class="household-icon-choice${selected ? " is-selected" : ""}"
                        data-action="set-household-icon" data-icon="${icon.id}"
                        aria-pressed="${selected}" title="${escapeHtml(icon.label)}"
                        aria-label="${escapeHtml(icon.label)}">
                  <span aria-hidden="true">${escapeHtml(glyph)}</span>
                </button>`;
            }).join("")}
          </div>
        </fieldset>
      </section>
      <section class="card theme-pref">
        <div>
          <h2>Appearance</h2>
          <p class="muted">Light and nature-inspired by default. Switch to a polished dark mode any time.</p>
        </div>
        <button type="button" id="theme-toggle" class="theme-toggle" data-action="toggle-theme"
                aria-pressed="${dark}"
                aria-label="${dark ? "Switch to light mode" : "Switch to dark mode"}">
          <span class="theme-toggle-icon" aria-hidden="true">${dark ? "☀️" : "🌙"}</span>
          <span class="theme-toggle-label">${dark ? "Light mode" : "Dark mode"}</span>
        </button>
      </section>
      ${renderExceptionColorSettings()}
      <div class="segmented settings-tabs" role="tablist" aria-label="Settings sections">
        ${tabs
          .map(
            ([value, label]) => `
          <button type="button" role="tab" data-action="settings-panel" data-panel="${value}"
                  class="${value === panel ? "active" : ""}"
                  aria-selected="${value === panel}">
            ${label}
          </button>`
          )
          .join("")}
      </div>
      ${(body[panel] || renderStudentSettings)()}
    </section>
  `;
}

function anchorDate() {
  if (!state.currentAnchorDate) {
    state.currentAnchorDate = todayISO();
  }
  return state.currentAnchorDate;
}

function selectedStudentId() {
  if (!state.students.length) {
    state.calendarStudentId = null;
    return null;
  }
  if (state.calendarStudentId === ALL_STUDENTS) {
    return ALL_STUDENTS;
  }
  const known = state.students.some((student) => student.id === state.calendarStudentId);
  if (!known) {
    state.calendarStudentId = state.students[0].id;
  }
  return state.calendarStudentId;
}

function selectedPortfolioStudentId() {
  if (!state.students.length) {
    state.portfolio.studentId = null;
    return null;
  }
  const known = state.students.some((student) => student.id === state.portfolio.studentId);
  if (!known) {
    state.portfolio.studentId = state.students[0].id;
  }
  return state.portfolio.studentId;
}

function selectedPortfolioYearId() {
  if (!state.years.length) {
    state.portfolio.schoolYearId = null;
    return null;
  }
  const known = state.years.some((year) => year.id === state.portfolio.schoolYearId);
  if (!known) {
    state.portfolio.schoolYearId = state.years[0].id;
  }
  return state.portfolio.schoolYearId;
}

function isAllStudentsView() {
  return selectedStudentId() === ALL_STUDENTS;
}

function isDispatchView() {
  return isAllStudentsView() && state.currentPeriod === "day";
}

function calendarEventOptions() {
  return {
    showStudent: isAllStudentsView() && state.currentPeriod !== "day",
  };
}

function evidenceClipMarkup(count) {
  const n = Number(count) || 0;
  if (!n) return "";
  const countHtml = n > 1 ? `<span class="cal-event-clip-count">${n}</span>` : "";
  return `<span class="cal-event-clip" aria-label="${n} attached">${PAPERCLIP_ICON}${countHtml}</span>`;
}

function rangeLabel(period, startISO, endISO) {
  if (period === "day") {
    return FULL_DATE.format(parseISODate(startISO));
  }
  if (period === "month") {
    return MONTH_YEAR.format(parseISODate(startISO));
  }
  return `${MEDIUM_DATE.format(parseISODate(startISO))} – ${MEDIUM_DATE.format(parseISODate(endISO))}`;
}

function assignmentCurriculumLabel(item) {
  if (item.curriculum_id != null) {
    const match = state.curricula.find((entry) => entry.id === item.curriculum_id);
    if (match) return match.title;
  }
  return item.resource_title || item.unit_title || "";
}

function assignmentEventLabel(item, { showStudent = false } = {}) {
  const subject = (item.subject_name || "").trim();
  const curriculum = assignmentCurriculumLabel(item);
  let label;
  if (subject && curriculum) {
    label = `${subject} - ${curriculum}`;
  } else {
    label = subject || curriculum || item.title || "Assignment";
  }
  if (showStudent) {
    label = `${studentName(item.student_id)}: ${label}`;
  }
  return label;
}

function eventStatusClass(item) {
  if (isCompleteStatus(item.status)) return "status-completed";
  if (item.scheduled_date && item.scheduled_date < todayISO()) return "status-overdue";
  return "status-scheduled";
}

function assignmentTile(item, { showStudent = false } = {}) {
  const label = assignmentEventLabel(item, { showStudent });
  const statusClass = eventStatusClass(item);
  const count = Number(item.evidence_count) || 0;
  return `<button type="button" class="cal-event ${statusClass}" data-assignment-id="${item.id}" data-evidence-count="${count}" title="${escapeHtml(label)}" style="${assignmentColorStyle(item)}"><span class="cal-event-label">${escapeHtml(label)}</span>${evidenceClipMarkup(count)}</button>`;
}

function groupByDate(assignments) {
  const byDate = new Map();
  for (const item of assignments) {
    const bucket = byDate.get(item.scheduled_date);
    if (bucket) {
      bucket.push(item);
    } else {
      byDate.set(item.scheduled_date, [item]);
    }
  }
  return byDate;
}

function isWeekend(iso) {
  return mondayIndex(parseISODate(iso)) >= 5;
}

function hasWeekendAssignments(assignments) {
  return assignments.some((item) => isWeekend(item.scheduled_date));
}

function attendanceRecord(studentId, iso) {
  return (state.attendance || []).find(
    (row) => row.student_id === studentId && row.date === iso
  );
}

function exceptionAttendanceStatus(studentId, iso) {
  let household = null;
  for (const item of state.exceptions || []) {
    if (item.kind !== "sick" && item.kind !== "vacation") continue;
    if (iso < item.start_date || iso > item.end_date) continue;
    const mapped = item.kind === "sick" ? "Sick" : "Vacation";
    if (item.student_id === studentId) return mapped;
    if (item.student_id == null && household == null) household = mapped;
  }
  return household;
}

function attendanceDisplayStatus(studentId, iso) {
  const row = attendanceRecord(studentId, iso);
  if (row && (row.status === "Sick" || row.status === "Vacation")) {
    return row.status;
  }
  const exception = exceptionAttendanceStatus(studentId, iso);
  if (exception) return exception;
  return row ? row.status : null;
}

function attendanceStudents() {
  if (isAllStudentsView()) return state.students;
  const studentId = selectedStudentId();
  return state.students.filter((student) => student.id === studentId);
}

function attendanceHeader(studentId, iso, { compact = false } = {}) {
  const status = attendanceDisplayStatus(studentId, iso);
  const name = studentName(studentId);
  const group = `attendance-${studentId}-${iso}`;
  const compactClass = compact ? " is-compact" : "";
  if (status === "Sick" || status === "Vacation") {
    const label = status === "Sick" ? "SICK DAY" : "VACATION";
    return `
      <div class="attendance-header attendance-exception-block${compactClass}" style="${studentColorStyle(studentId)}">
        <p class="attendance-exception">${label}</p>
      </div>`;
  }
  const yesChecked = status === "Present" ? " checked" : "";
  const noChecked = status === "Absent" ? " checked" : "";
  return `
    <div class="attendance-header${compactClass}" style="${studentColorStyle(studentId)}">
      <span class="attendance-label">Attendance ${escapeHtml(name)}</span>
      <span class="attendance-radios">
        <label>
          <input type="radio" name="${group}" value="Present"
                 data-control="attendance" data-student-id="${studentId}"
                 data-date="${iso}"${yesChecked}>
          Yes
        </label>
        <label>
          <input type="radio" name="${group}" value="Absent"
                 data-control="attendance" data-student-id="${studentId}"
                 data-date="${iso}"${noChecked}>
          No
        </label>
      </span>
    </div>`;
}

function attendanceHeadersForDay(iso) {
  const students = attendanceStudents();
  const compact = students.length > 1;
  return students.map((student) => attendanceHeader(student.id, iso, { compact })).join("");
}

function upsertLocalAttendance(record) {
  const rows = state.attendance ? [...state.attendance] : [];
  const index = rows.findIndex(
    (row) => row.student_id === record.student_id && row.date === record.date
  );
  if (index === -1) {
    rows.push(record);
  } else {
    rows[index] = { ...rows[index], ...record };
  }
  state.attendance = rows;
}

async function saveAttendance(studentId, iso, status) {
  try {
    const result = await api("/attendance", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId, date: iso, status }),
    });
    if (isOfflineQueued(result)) {
      upsertLocalAttendance({ student_id: studentId, date: iso, status });
      return;
    }
    upsertLocalAttendance(result);
  } catch (error) {
    flash(error.message, true);
    await refreshVisibleAssignmentBoard();
  }
}

function calendarGrid(data, { showStudent = false, showAttendance = true } = {}) {
  const byDate = groupByDate(data.assignments);
  const hideWeekends = !hasWeekendAssignments(data.assignments);
  const columns = hideWeekends ? 5 : 7;
  const today = todayISO();
  const period = data.period || state.currentPeriod;
  const cells = [];

  // The API returns the 1st of the month, which is rarely a Monday, so the grid
  // is padded to keep every date under its own weekday column. A Saturday or
  // Sunday start disappears entirely when weekends are hidden, because the
  // first visible cell is the following Monday.
  const startWeekday = mondayIndex(parseISODate(data.start_date));
  const leadingBlanks = hideWeekends && startWeekday >= 5 ? 0 : startWeekday;
  for (let blank = 0; blank < leadingBlanks; blank += 1) {
    cells.push(`<div class="cal-cell is-blank" aria-hidden="true"></div>`);
  }

  for (const iso of dayRange(data.start_date, data.end_date)) {
    if (hideWeekends && isWeekend(iso)) continue;
    const tiles = byDate.get(iso) || [];
    cells.push(`
      <div class="cal-cell${iso === today ? " is-today" : ""}">
        <p class="cal-daynum">${parseISODate(iso).getUTCDate()}</p>
        ${showAttendance ? attendanceHeadersForDay(iso) : ""}
        <div class="cal-events">
          ${
            tiles.length
              ? tiles.map((item) => assignmentTile(item, { showStudent })).join("")
              : `<p class="cal-quiet">&nbsp;</p>`
          }
        </div>
      </div>`);
  }

  while (cells.length % columns !== 0) {
    cells.push(`<div class="cal-cell is-blank" aria-hidden="true"></div>`);
  }

  const headers = WEEKDAYS.slice(0, columns);
  const periodClass = period === "week" ? " is-week" : " is-month";
  return `
    <div class="cal-board${hideWeekends ? " hide-weekend" : ""}${periodClass}">
      <div class="cal-weekdays">${headers.map((day) => `<span>${day}</span>`).join("")}</div>
      <div class="cal-grid">${cells.join("")}</div>
    </div>`;
}

function calendarList(data, { showAttendance = true } = {}) {
  const studentId = selectedStudentId();
  const iso = data.start_date;
  const header =
    showAttendance && studentId && studentId !== ALL_STUDENTS ? attendanceHeader(studentId, iso) : "";
  const tiles = data.assignments.length
    ? `<div class="tile-stack">${data.assignments.map((item) => assignmentTile(item)).join("")}</div>`
    : `<p class="empty">Nothing scheduled for this day.</p>`;
  return `<div class="day-board">${header}${tiles}</div>`;
}

function dispatchBoard(data, { showAttendance = true } = {}) {
  const byStudent = new Map();
  for (const item of data.assignments || []) {
    const bucket = byStudent.get(item.student_id);
    if (bucket) {
      bucket.push(item);
    } else {
      byStudent.set(item.student_id, [item]);
    }
  }
  const iso = data.start_date;
  const columns = state.students.map((student) => {
    const assignments = byStudent.get(student.id) || [];
    const tiles = assignments.map((item) => assignmentTile(item));
    return `
      <div class="dispatch-column" style="${studentColorStyle(student)}">
        ${showAttendance ? attendanceHeader(student.id, iso) : ""}
        <h3 class="dispatch-student">${escapeHtml(student.name)}</h3>
        ${
          tiles.length
            ? `<div class="tile-stack">${tiles.join("")}</div>`
            : `<p class="empty">Nothing scheduled.</p>`
        }
      </div>`;
  });
  return `<div class="dispatch-board">${columns.join("")}</div>`;
}

function renderAssignments() {
  if (!state.students.length) {
    return `<section class="card"><p class="empty">Add a student in <a href="#/settings/students">Settings</a> to see their calendar.</p></section>`;
  }
  const studentId = selectedStudentId();
  const period = state.currentPeriod;
  const allStudents = isAllStudentsView();
  return `
    <section class="card calendar">
      <div class="calendar-toolbar">
        <label class="inline-field">Student
          <select data-control="student">
            <option value="${ALL_STUDENTS}"${allStudents ? " selected" : ""}>All Students</option>
            ${state.students
              .map(
                (student) =>
                  `<option value="${student.id}"${student.id === studentId ? " selected" : ""}>${escapeHtml(student.name)}</option>`
              )
              .join("")}
          </select>
        </label>
        <div class="segmented" role="group" aria-label="Calendar period">
          ${PERIODS.map(
            (value) => `
            <button type="button" data-action="period" data-period="${value}"
                    class="${value === period ? "active" : ""}" aria-pressed="${value === period}">
              ${humanize(value)}
            </button>`
          ).join("")}
        </div>
        <div class="calendar-nav">
          <button type="button" class="ghost" data-action="prev" aria-label="Previous ${period}">&lsaquo; Previous</button>
          <button type="button" class="ghost" data-action="today">Today</button>
          <button type="button" class="ghost" data-action="next" aria-label="Next ${period}">Next &rsaquo;</button>
        </div>
        ${
          allStudents
            ? ""
            : `<button type="button" class="add-assignment" data-action="toggle-assignment-form"
                aria-controls="assignment-form" aria-expanded="false">+ Add assignment</button>`
        }
        ${
          allStudents
            ? ""
            : `<button type="button" class="add-assignment ghost" data-action="open-recalibrate">Recalibrate Schedule</button>
               <button type="button" class="add-assignment ghost" data-action="print-weekly-checklist"
                       data-student-id="${studentId}" data-start-date="${weekMondayISO(anchorDate())}">Print Weekly Checklist</button>`
        }
        <button type="button" class="add-assignment ghost" data-action="auto-schedule">Auto-schedule a book</button>
      </div>
      ${
        allStudents
          ? ""
          : `<form id="assignment-form" class="assignment-form" data-form="assignment" hidden>
        <h3>New assignment for ${escapeHtml(studentName(studentId))}</h3>
        <div class="field-row">
          <label>Title<input name="title" required maxlength="255" placeholder="Lesson 12 problem set"></label>
          <label>Scheduled<input name="scheduled_date" type="date" required value="${anchorDate()}"></label>
        </div>
        <div class="field-row">
          <label>Status<select name="status">${enumOptions(STATUSES, "assigned")}</select></label>
          <label>Completed<input name="completion_date" type="date"></label>
        </div>
        <label>Notes<textarea name="notes"></textarea></label>
        <div class="form-actions">
          <button type="submit">Save assignment</button>
          <button type="button" class="ghost" data-action="toggle-assignment-form">Cancel</button>
        </div>
      </form>`
      }
      <div class="calendar-range">
        <div>
          <h2 id="calendar-range-label">Loading…</h2>
          ${
            allStudents
              ? `<p class="calendar-shared-note italic">Showing shared lessons only. Private lessons appear on individual student calendars.</p>`
              : ""
          }
        </div>
        <p id="calendar-range-count" class="meta"></p>
      </div>
      <div class="${
        period === "month"
          ? "calendar-stage is-month"
          : `calendar-stage${evidenceInboxIsCollapsed() ? " is-inbox-collapsed" : ""}`
      }">
        ${period === "month" ? "" : evidenceInboxPanelHtml()}
        <div id="calendar-body" class="calendar-body" aria-live="polite">
          <p class="empty">Loading assignments…</p>
        </div>
      </div>
    </section>`;
}

let calendarRequest = 0;

async function loadCalendar() {
  const studentId = selectedStudentId();
  const body = $("calendar-body");
  if (!studentId || !body) return;

  const period = state.currentPeriod;
  const token = (calendarRequest += 1);
  const query = new URLSearchParams({ period, start_date: anchorDate() });
  const window_ = calendarDateWindow(period, anchorDate());
  const attendanceQuery = new URLSearchParams({
    start_date: window_.start,
    end_date: window_.end,
  });
  try {
    const assignmentPath =
      studentId === ALL_STUDENTS
        ? `/calendar?${query}`
        : `/students/${studentId}/assignments?${query}`;
    const [data, attendance, exceptions] = await Promise.all([
      api(assignmentPath),
      api(`/attendance?${attendanceQuery}`),
      api("/exceptions"),
    ]);
    // Clicking through periods quickly can land responses out of order; only the
    // newest request is allowed to paint.
    if (token !== calendarRequest || !$("calendar-body")) return;
    state.calendar = data;
    state.attendance = Array.isArray(attendance) ? attendance : [];
    if (Array.isArray(exceptions)) state.exceptions = exceptions;
    $("calendar-range-label").textContent = rangeLabel(period, data.start_date, data.end_date);
    $("calendar-range-count").textContent =
      data.count === 1 ? "1 assignment" : `${data.count} assignments`;
    if (studentId === ALL_STUDENTS) {
      $("calendar-body").innerHTML = isDispatchView()
        ? dispatchBoard(data)
        : calendarGrid(data, { showStudent: true });
    } else {
      $("calendar-body").innerHTML = period === "day" ? calendarList(data) : calendarGrid(data);
    }
    paintEvidenceInbox();
  } catch (error) {
    if (token !== calendarRequest || !$("calendar-body")) return;
    $("calendar-body").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    flash(error.message, true);
    paintEvidenceInbox();
  }
}

async function loadAssignmentsPage() {
  paintEvidenceInbox();
  await Promise.all([loadCalendar(), loadEvidenceStaging()]);
}

async function refreshVisibleAssignmentBoard() {
  await loadCalendar();
}

function capturedDayISO(capturedAt) {
  const date = new Date(capturedAt);
  if (Number.isNaN(date.getTime())) return "";
  return toISODate(new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())));
}

function stagingDayLabel(dayISO) {
  if (!dayISO) return "Unknown day";
  if (dayISO === todayISO()) return "Today";
  if (dayISO === addDays(todayISO(), -1)) return "Yesterday";
  return SHORT_DATE.format(parseISODate(dayISO));
}

function groupStagingByDay(rows, { ascending = false } = {}) {
  const groups = new Map();
  for (const row of rows || []) {
    const day = capturedDayISO(row.captured_at);
    const bucket = groups.get(day);
    if (bucket) bucket.push(row);
    else groups.set(day, [row]);
  }
  return [...groups.entries()].sort((left, right) => {
    if (left[0] === right[0]) return 0;
    const cmp = left[0] < right[0] ? -1 : 1;
    return ascending ? cmp : -cmp;
  });
}

function stagingThumbMarkup(row) {
  const captured = new Date(row.captured_at);
  const time = Number.isNaN(captured.getTime()) ? "" : SHORT_TIME.format(captured);
  const fileAttr = `data-evidence-file="${escapeHtml(row.file_path || "")}"`;
  const image = isImagePath(row.file_path)
    ? `<img ${fileAttr} alt="Screenshot${time ? ` from ${escapeHtml(time)}` : ""}" draggable="false">`
    : `<span class="evidence-inbox-file">${escapeHtml((row.file_path || "").split("/").pop() || "File")}</span>`;
  return `
    <figure class="evidence-inbox-thumb" draggable="true" data-evidence-id="${row.id}" role="listitem">
      ${image}
      ${time ? `<figcaption>${escapeHtml(time)}</figcaption>` : ""}
    </figure>`;
}

function calendarShowsEvidenceInbox() {
  return state.currentPeriod === "day" || state.currentPeriod === "week";
}

function evidenceInboxIsCollapsed() {
  try {
    return localStorage.getItem(EVIDENCE_INBOX_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

function stagingRowsForVisibleWindow() {
  if (!calendarShowsEvidenceInbox()) return [];
  const window_ = calendarDateWindow(state.currentPeriod, anchorDate());
  return (state.evidenceStaging || []).filter((row) => {
    const day = capturedDayISO(row.captured_at);
    if (!day) return true;
    return day >= window_.start && day <= window_.end;
  });
}

function evidenceInboxCountLabel(n) {
  return n > 99 ? "99+" : String(n);
}

function evidenceInboxBodyHtml(rows) {
  const period = state.currentPeriod;
  if (!rows.length) {
    const when = period === "day" ? "this day" : "this week";
    const elsewhere = (state.evidenceStaging || []).length - rows.length;
    const extra = elsewhere > 0
      ? ` ${elsewhere} still unfiled on other days.`
      : " Captures from the Chrome extension land here until you file them onto a lesson.";
    return `<p class="empty">No unsorted screenshots for ${when}.${extra}</p>`;
  }
  const hint = `<p class="evidence-inbox-hint">Drag a screenshot onto a lesson to file it.</p>`;
  if (period === "day") {
    return `${hint}
      <div class="evidence-inbox-thumbs" role="list">
        ${rows.map(stagingThumbMarkup).join("")}
      </div>`;
  }
  const groups = groupStagingByDay(rows, { ascending: true });
  return `
    ${hint}
    ${groups
      .map(
        ([day, items]) => `
      <section class="evidence-inbox-day">
        <h3>${escapeHtml(stagingDayLabel(day))}</h3>
        <div class="evidence-inbox-thumbs" role="list">
          ${items.map(stagingThumbMarkup).join("")}
        </div>
      </section>`
      )
      .join("")}`;
}

function evidenceInboxPanelHtml() {
  const collapsed = evidenceInboxIsCollapsed();
  const visible = stagingRowsForVisibleWindow();
  const n = visible.length;
  return `
    <aside class="evidence-inbox${collapsed ? " is-collapsed" : ""}" aria-labelledby="evidence-inbox-title">
      <header class="evidence-inbox-head">
        <h2 id="evidence-inbox-title">Unsorted Evidence</h2>
        <span id="evidence-inbox-count" class="nav-count"${n ? "" : " hidden"}>${evidenceInboxCountLabel(n)}</span>
        <button type="button" class="ghost evidence-inbox-toggle" data-action="toggle-evidence-inbox"
                aria-expanded="${collapsed ? "false" : "true"}" aria-controls="evidence-inbox-body">
          ${collapsed ? "Show" : "Hide"}
        </button>
      </header>
      <div id="evidence-inbox-body" class="evidence-inbox-body">
        ${evidenceInboxBodyHtml(visible)}
      </div>
    </aside>`;
}

function syncEvidenceInboxBadge() {
  const badge = $("evidence-inbox-count");
  if (!badge) return;
  const n = stagingRowsForVisibleWindow().length;
  badge.hidden = n === 0;
  badge.textContent = evidenceInboxCountLabel(n);
}

function paintEvidenceInbox() {
  const body = $("evidence-inbox-body");
  if (body) {
    body.innerHTML = evidenceInboxBodyHtml(stagingRowsForVisibleWindow());
    hydrateEvidenceImages(body);
  }
  syncEvidenceInboxBadge();
}

function toggleEvidenceInbox() {
  const aside = document.querySelector(".evidence-inbox");
  const stage = document.querySelector(".calendar-stage");
  if (!aside) return;
  const collapsed = !aside.classList.contains("is-collapsed");
  try {
    localStorage.setItem(EVIDENCE_INBOX_COLLAPSED_KEY, collapsed ? "1" : "0");
  } catch {
    // Private mode can refuse localStorage; the toggle still works for this view.
  }
  aside.classList.toggle("is-collapsed", collapsed);
  stage?.classList.toggle("is-inbox-collapsed", collapsed);
  const button = aside.querySelector("[data-action='toggle-evidence-inbox']");
  if (button) {
    button.setAttribute("aria-expanded", collapsed ? "false" : "true");
    button.textContent = collapsed ? "Show" : "Hide";
  }
}

async function loadEvidenceStaging() {
  try {
    const rows = await api("/evidence/staging");
    state.evidenceStaging = Array.isArray(rows) ? rows : [];
  } catch (error) {
    if (error.status === 401) return;
    state.evidenceStaging = [];
    if ($("evidence-inbox-body")) {
      $("evidence-inbox-body").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    }
    syncEvidenceInboxBadge();
    return;
  }
  paintEvidenceInbox();
}

function assignmentRowsForBoard() {
  return state.calendar ? state.calendar.assignments : [];
}

function removeStagingThumb(evidenceId) {
  state.evidenceStaging = (state.evidenceStaging || []).filter((row) => row.id !== evidenceId);
  paintEvidenceInbox();
}

function markAssignmentHasEvidence(assignmentId, record) {
  const tile = document.querySelector(`.cal-event[data-assignment-id="${assignmentId}"]`);
  const count = (Number(tile?.dataset.evidenceCount) || 0) + 1;
  const item = assignmentRowsForBoard().find((row) => row.id === assignmentId);
  if (item) item.evidence_count = count;
  if (!tile) return;
  tile.dataset.evidenceCount = String(count);
  const clip = tile.querySelector(".cal-event-clip");
  if (!clip) {
    tile.insertAdjacentHTML("beforeend", evidenceClipMarkup(count));
  } else {
    clip.setAttribute("aria-label", `${count} attached`);
    const n = clip.querySelector(".cal-event-clip-count");
    if (count > 1) {
      if (n) n.textContent = String(count);
      else clip.insertAdjacentHTML("beforeend", `<span class="cal-event-clip-count">${count}</span>`);
    }
  }
  if (record?.file_path && isImagePath(record.file_path)) {
    const mini = `<img class="cal-event-mini" data-evidence-file="${escapeHtml(record.file_path)}" alt="" draggable="false">`;
    const existing = tile.querySelector(".cal-event-mini");
    if (existing) existing.outerHTML = mini;
    else tile.insertAdjacentHTML("beforeend", mini);
    hydrateEvidenceImages(tile);
  }
}

const linkingEvidenceIds = new Set();
let ignoreAssignmentClickUntil = 0;

async function linkStagedEvidence(evidenceId, assignmentId) {
  if (linkingEvidenceIds.has(evidenceId)) return;
  linkingEvidenceIds.add(evidenceId);
  const thumb = document.querySelector(`.evidence-inbox-thumb[data-evidence-id="${evidenceId}"]`);
  thumb?.classList.add("is-linking");
  try {
    const record = await api("/evidence/link", {
      method: "POST",
      body: JSON.stringify({ evidence_id: evidenceId, assignment_id: assignmentId }),
    });
    if (isOfflineQueued(record)) {
      flash("Evidence will be filed when you’re back online.");
      return;
    }
    removeStagingThumb(evidenceId);
    markAssignmentHasEvidence(assignmentId, record);
    flash("Screenshot filed.");
  } catch (error) {
    flash(error.message, true);
  } finally {
    linkingEvidenceIds.delete(evidenceId);
    document
      .querySelector(`.evidence-inbox-thumb[data-evidence-id="${evidenceId}"]`)
      ?.classList.remove("is-linking");
  }
}

function evidencePageIsOpen() {
  return Boolean($("evidence-inbox-body"));
}

function assignmentDropCard(node) {
  if (!evidencePageIsOpen()) return null;
  return node && typeof node.closest === "function"
    ? node.closest(".cal-event[data-assignment-id]")
    : null;
}

function clearAssignmentDropTargets(except) {
  document.querySelectorAll(".cal-event.is-drop-target").forEach((card) => {
    if (card !== except) card.classList.remove("is-drop-target");
  });
}

function evidenceIdFromDrag(event) {
  const transfer = event.dataTransfer;
  if (!transfer) return null;
  const raw = transfer.getData(EVIDENCE_DRAG_TYPE) || transfer.getData("text/plain") || "";
  const id = Number(String(raw).trim());
  return Number.isInteger(id) && id > 0 ? id : null;
}

function handleEvidenceDragStart(event) {
  const thumb = event.target.closest?.(".evidence-inbox-thumb[data-evidence-id]");
  if (!thumb) return;
  const id = String(thumb.dataset.evidenceId);
  try {
    event.dataTransfer.setData(EVIDENCE_DRAG_TYPE, id);
  } catch {
    // Some browsers only accept a few MIME types; text/plain is the payload.
  }
  event.dataTransfer.setData("text/plain", id);
  event.dataTransfer.effectAllowed = "link";
  thumb.classList.add("is-dragging");
}

function handleEvidenceDragEnd() {
  document.querySelectorAll(".evidence-inbox-thumb.is-dragging").forEach((el) => {
    el.classList.remove("is-dragging");
  });
  clearAssignmentDropTargets();
}

function handleAssignmentDragEnter(event) {
  const card = assignmentDropCard(event.target);
  if (!card) return;
  event.preventDefault();
}

function handleAssignmentDragOver(event) {
  const card = assignmentDropCard(event.target);
  if (!card) {
    clearAssignmentDropTargets();
    return;
  }
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = "link";
  if (!card.classList.contains("is-drop-target")) {
    clearAssignmentDropTargets(card);
    card.classList.add("is-drop-target");
  }
}

function handleAssignmentDragLeave(event) {
  const card = assignmentDropCard(event.target);
  if (!card) return;
  const next = event.relatedTarget;
  if (next && card.contains(next)) return;
  card.classList.remove("is-drop-target");
}

function handleAssignmentDrop(event) {
  const card = assignmentDropCard(event.target);
  if (!card) return;
  event.preventDefault();
  card.classList.remove("is-drop-target");
  ignoreAssignmentClickUntil = Date.now() + 500;
  const evidenceId = evidenceIdFromDrag(event);
  const assignmentId = Number(card.dataset.assignmentId);
  if (!evidenceId || !assignmentId) return;
  linkStagedEvidence(evidenceId, assignmentId);
}

function recalibrateError(message) {
  const el = $("recalibrate-error");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function isRecalibrateOpen() {
  const modal = $("recalibrate-modal");
  return Boolean(modal) && !modal.hidden;
}

function countLabel(n, singular, plural) {
  return `${n} ${n === 1 ? singular : plural}`;
}

function formatISODate(iso) {
  if (!iso) return "";
  return MEDIUM_DATE.format(parseISODate(iso));
}

function selectedRecalibrateStrategy() {
  const checked = document.querySelector('#recalibrate-modal input[name="recalibrate-strategy"]:checked');
  return checked?.value || "extend_year";
}

function showRecalibrateStep(step) {
  const modal = $("recalibrate-modal");
  if (!modal) return;
  recalibrate.step = step;
  modal.querySelectorAll("[data-recalibrate-step]").forEach((panel) => {
    panel.classList.toggle("is-active", Number(panel.dataset.recalibrateStep) === step);
  });
  modal.querySelectorAll("[data-recalibrate-dot]").forEach((dot) => {
    const n = Number(dot.dataset.recalibrateDot);
    dot.classList.toggle("is-active", n === step);
  });
  const title = modal.querySelector(".wizard-step.is-active h2");
  const card = modal.querySelector(".recalibrate-card");
  if (title && card) card.setAttribute("aria-labelledby", title.id);
  recalibrateError("");
  const focusTarget = modal.querySelector(
    ".wizard-step.is-active input, .wizard-step.is-active button:not([disabled])"
  );
  focusTarget?.focus();
}

function paintRecalibrateOptions(data) {
  recalibrate.options = data;
  const name = studentName(recalibrate.studentId);
  const overdue = data.overdue_count || 0;
  const schoolDays = data.overdue_school_days || 0;
  const copy = $("recalibrate-overdue-copy");
  const stat = $("recalibrate-overdue-stat");
  const countEl = $("recalibrate-overdue-count");
  const labelEl = $("recalibrate-overdue-label");
  const next = $("recalibrate-next");
  if (countEl) countEl.textContent = String(overdue);
  if (labelEl) labelEl.textContent = overdue === 1 ? "overdue assignment" : "overdue assignments";
  if (stat) stat.hidden = false;
  if (copy) {
    copy.textContent = overdue
      ? `${name} has ${countLabel(overdue, "assignment", "assignments")} overdue across ${countLabel(schoolDays, "school day", "school days")}.`
      : `${name} is caught up — nothing is overdue.`;
  }
  if (next) next.disabled = overdue < 1;

  const extend = data.strategies?.extend_year || {};
  const weekends = data.strategies?.add_weekends || {};
  const extendCopy = $("recalibrate-extend-copy");
  const weekendsCopy = $("recalibrate-weekends-copy");
  if (extendCopy) {
    const end = formatISODate(extend.new_end_date);
    extendCopy.textContent = end
      ? `Extends the end of the year through ${end} (${countLabel(extend.required_days || 0, "calendar day", "calendar days")} to clear the backlog).`
      : "Extends the end of the year.";
  }
  if (weekendsCopy) {
    const saturdays = weekends.saturdays_used || 0;
    weekendsCopy.textContent = saturdays
      ? `Temporarily catch up on weekends (${countLabel(saturdays, "Saturday", "Saturdays")} used).`
      : "Temporarily catch up on weekends.";
  }
  paintRecalibrateConfirm();
}

function paintRecalibrateConfirm() {
  const copy = $("recalibrate-confirm-copy");
  if (!copy) return;
  const data = recalibrate.options;
  if (!data) {
    copy.textContent = "";
    return;
  }
  const strategy = selectedRecalibrateStrategy();
  recalibrate.strategy = strategy;
  const detail = data.strategies?.[strategy] || {};
  const moved = detail.assignments_moved || data.uncompleted_count || 0;
  const end = formatISODate(detail.new_end_date);
  const plan =
    strategy === "add_weekends"
      ? "Saturdays will be class days until the original cadence is caught up."
      : "Uncompleted work will be pushed forward on the usual class days.";
  copy.textContent = `${plan} ${countLabel(moved, "assignment", "assignments")} will move. Completed work stays put.${
    end ? ` The last leftover lesson lands on ${end}.` : ""
  }`;
}

async function openRecalibrate(studentId) {
  if (!state.students.length) {
    flash("Add a student before recalibrating a schedule.", true);
    return;
  }
  const id = Number(studentId);
  if (!id) {
    flash("Select a student to recalibrate their schedule.", true);
    return;
  }
  recalibrate.studentId = id;
  recalibrate.options = null;
  recalibrate.strategy = "extend_year";
  recalibrate.busy = false;
  const extendRadio = document.querySelector('#recalibrate-modal input[name="recalibrate-strategy"][value="extend_year"]');
  if (extendRadio) extendRadio.checked = true;
  const heading = $("recalibrate-heading");
  if (heading) heading.textContent = `Recalibrate ${studentName(id)}`;
  const copy = $("recalibrate-overdue-copy");
  if (copy) copy.textContent = "Checking the calendar…";
  const stat = $("recalibrate-overdue-stat");
  if (stat) stat.hidden = true;
  const next = $("recalibrate-next");
  if (next) next.disabled = true;
  const confirm = $("recalibrate-confirm");
  if (confirm) confirm.disabled = false;
  recalibrateError("");

  lastFocused = document.activeElement;
  $("recalibrate-modal").hidden = false;
  document.body.classList.add("modal-open");
  showRecalibrateStep(1);

  try {
    const data = await api(`/recalibrate/${id}/options`);
    if (recalibrate.studentId !== id || !isRecalibrateOpen()) return;
    paintRecalibrateOptions(data);
  } catch (error) {
    if (!isRecalibrateOpen()) return;
    recalibrateError(error.message);
  }
}

let weeklyManifestBusy = false;

async function printWeeklyChecklist(studentId, startDate) {
  const id = Number(studentId);
  if (!id || Number.isNaN(id)) {
    flash("Select a student to print their weekly checklist.", true);
    return;
  }
  if (weeklyManifestBusy) return;
  weeklyManifestBusy = true;
  const monday = startDate || weekMondayISO(todayISO());
  const params = new URLSearchParams({
    student_id: String(id),
    start_date: monday,
  });
  const token = getAuthToken();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    const res = await fetch(`/api/reports/weekly-manifest?${params}`, { headers });
    if (!res.ok) {
      if (res.status === 401) handleUnauthorized();
      let message = `Request failed (${res.status})`;
      try {
        const body = await res.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch {
        /* not JSON */
      }
      throw new Error(message);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const opened = window.open(url, "_blank", "noopener");
    if (!opened) {
      const link = document.createElement("a");
      link.href = url;
      link.download = `weekly-checklist-${monday}.pdf`;
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      link.remove();
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (error) {
    flash(error.message || "Could not open the weekly checklist.", true);
  } finally {
    weeklyManifestBusy = false;
  }
}

function closeRecalibrate() {
  const modal = $("recalibrate-modal");
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  recalibrate.studentId = null;
  recalibrate.options = null;
  recalibrate.busy = false;
  recalibrateError("");
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus();
  }
}

async function confirmRecalibrate() {
  if (recalibrate.busy || !recalibrate.studentId) return;
  const strategy = selectedRecalibrateStrategy();
  recalibrate.strategy = strategy;
  const confirm = $("recalibrate-confirm");
  recalibrate.busy = true;
  if (confirm) confirm.disabled = true;
  recalibrateError("");
  try {
    const result = await api(`/recalibrate/${recalibrate.studentId}/execute`, {
      method: "POST",
      body: JSON.stringify({ strategy, options: {} }),
    });
    const moved = result.assignments_moved || 0;
    closeRecalibrate();
    showToast(
      "success",
      "Schedule recalibrated",
      moved
        ? `${countLabel(moved, "assignment", "assignments")} moved. Completed work was left in place.`
        : "Nothing needed to move."
    );
    render();
  } catch (error) {
    recalibrate.busy = false;
    if (confirm) confirm.disabled = false;
    recalibrateError(error.message);
    showToast("error", "Recalibration failed", error.message);
  }
}

function handleRecalibrateClick(event) {
  if (event.target.closest("[data-action='close-recalibrate']")) {
    closeRecalibrate();
    return;
  }
  if (event.target.closest("[data-action='recalibrate-next']")) {
    if (recalibrate.step === 1 && !(recalibrate.options?.overdue_count > 0)) return;
    paintRecalibrateConfirm();
    showRecalibrateStep(Math.min(3, recalibrate.step + 1));
    return;
  }
  if (event.target.closest("[data-action='recalibrate-back']")) {
    showRecalibrateStep(Math.max(1, recalibrate.step - 1));
    return;
  }
  if (event.target.closest("[data-action='confirm-recalibrate']")) {
    confirmRecalibrate();
  }
}

function handleRecalibrateChange(event) {
  if (!event.target.closest('input[name="recalibrate-strategy"]')) return;
  paintRecalibrateConfirm();
}

function toggleAssignmentForm(open) {
  const form = $("assignment-form");
  if (!form) return;
  const opening = open === undefined ? form.hidden : open;
  form.hidden = !opening;
  const toggle = document.querySelector(".add-assignment");
  if (toggle) {
    toggle.setAttribute("aria-expanded", String(opening));
  }
  if (opening) {
    form.querySelector('[name="title"]').focus();
  } else {
    form.reset();
  }
}

async function createAssignment(data) {
  const item = await api("/assignments", {
    method: "POST",
    body: JSON.stringify({
      student_id: selectedStudentId(),
      title: data.title,
      scheduled_date: data.scheduled_date,
      status: data.status,
      completion_date: emptyToNull(data.completion_date),
      notes: emptyToNull(data.notes),
    }),
  });
  toggleAssignmentForm(false);
  if (isOfflineQueued(item)) return;
  await loadCalendar();
  // A parent can date the new work anywhere, including outside the week or
  // month on screen, where the reloaded calendar simply will not show it.
  const window_ = state.calendar;
  const outside =
    window_ &&
    (item.scheduled_date < window_.start_date || item.scheduled_date > window_.end_date);
  flash(outside ? "Assignment added outside the dates on screen." : "Assignment added.");
}

/** Repaint one tile after an edit, or the whole view when the tile has moved. */
async function syncCalendarTile(previous, item) {
  const tile = document.querySelector(`.cal-event[data-assignment-id="${item.id}"]`);
  // A rescheduled assignment changes cell, and can leave the window entirely
  // along with the header count, so only an in-place edit is patched.
  if (!tile || previous.scheduled_date !== item.scheduled_date) {
    await refreshVisibleAssignmentBoard();
    return;
  }
  tile.outerHTML = assignmentTile(item, calendarEventOptions());
  const rows = assignmentRowsForBoard();
  const index = rows.findIndex((row) => row.id === item.id);
  if (index !== -1) {
    rows[index] = item;
  }
}

/* ---- Auto-schedule a book ---- */

// Roughly a school term, so the deadline field opens on something plausible
// rather than on today, which would ask for a whole book in no days at all.
const DEFAULT_TERM_DAYS = 120;

const DEFAULT_PAGES_PER_DAY = 10;

// Monday to Friday, matching the API's own default. 0 is Monday.
const DEFAULT_SCHOOL_WEEKDAYS = ["0", "1", "2", "3", "4"];

// The preview response is kept whole. The commit has to send back the lessons
// the API generated, with only the titles the parent edited changed, and
// recomputing the page splits on this side would be a second implementation of
// the generator waiting to disagree with the first.
const pacing = { resources: null, books: [], preview: null };

// Shared by both dialogs; only one is ever open, and whichever closes hands
// focus back to the control that opened it.
let lastFocused = null;

function pacingField(name) {
  return $("pacing-form").elements[name];
}

function pacingError(message) {
  const el = $("pacing-error");
  el.hidden = !message;
  el.textContent = message || "";
}

function showPacingStep(step) {
  $("pacing-form").hidden = step !== "form";
  $("pacing-preview").hidden = step !== "preview";
  $("pacing-actions").hidden = step !== "preview";
}

function pacingWeekdays() {
  return [...$("pacing-weekdays").querySelectorAll("input:checked")].map((box) => Number(box.value));
}

function resetPacingWeekdays() {
  const saved = classWeekdays().map(String);
  for (const box of $("pacing-weekdays").querySelectorAll("input")) {
    box.checked = saved.includes(box.value);
  }
}

function pacingMethod() {
  return pacingField("pacing_method").value || "deadline";
}

function updatePacingMethodUI(method) {
  const byPace = method === "pace";
  pacingField("pacing_method").value = method;
  $("deadline-fields").hidden = byPace;
  $("pace-fields").hidden = !byPace;
  // Hidden required fields still fail HTML5 validation, so the date picker has
  // to drop required when it is not the pacing mode in use.
  pacingField("target_completion_date").required = !byPace;
  pacingField("pages_per_day").required = byPace;
  $("pacing-weekdays-help").textContent = byPace
    ? "Each school day covers this many pages. Weekends and unticked days are skipped."
    : "One a day places a lesson on every school day. Higher counts stack extra lessons on each of those days.";
  $("pacing-modal").querySelectorAll('[data-action="pacing-method"]').forEach((button) => {
    const active = button.dataset.method === method;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function numberOrNull(value) {
  const trimmed = String(value ?? "").trim();
  return trimmed === "" ? null : Number(trimmed);
}

function fillPacingStudents() {
  const container = $("pacing-students");
  const selected =
    state.calendarStudentId === ALL_STUDENTS
      ? new Set(state.students.map((student) => student.id))
      : new Set(
          [state.calendarStudentId].filter((id) =>
            state.students.some((student) => student.id === id)
          )
        );
  if (!selected.size && state.students.length) {
    selected.add(state.students[0].id);
  }
  container.innerHTML = state.students
    .map(
      (student) => `
      <label class="weekday-toggle">
        <input type="checkbox" name="student_ids" value="${student.id}"
               ${selected.has(student.id) ? "checked" : ""}>
        ${escapeHtml(student.name)}
      </label>`
    )
    .join("");
}

function selectedPacingStudentIds() {
  return [...$("pacing-students").querySelectorAll("input:checked")].map((box) =>
    Number(box.value)
  );
}

function fillSelect(select, items, labelFn, selectedId) {
  select.innerHTML = items
    .map((item) => `<option value="${item.id}">${escapeHtml(labelFn(item))}</option>`)
    .join("");
  if (selectedId != null && items.some((item) => item.id === selectedId)) {
    select.value = String(selectedId);
  }
}

function openAutoSchedule(curriculumId) {
  if (!state.students.length) {
    flash("Add a student before auto-scheduling a book.", true);
    return;
  }
  if (!state.curricula.length) {
    flash("Add a curriculum before auto-scheduling a book.", true);
    return;
  }

  pacing.preview = null;
  pacingError("");
  showPacingStep("form");

  fillPacingStudents();
  const curricula = pacingField("curriculum_id");
  const chosen = curriculumId ?? state.curricula[0].id;
  fillSelect(curricula, state.curricula, (item) => item.title, chosen);

  const today = todayISO();
  pacingField("start_date").value = today;
  pacingField("target_completion_date").value = addDays(today, DEFAULT_TERM_DAYS);
  pacingField("start_page").value = "1";
  pacingField("end_page").value = "";
  pacingField("target_lessons").value = "";
  pacingField("pages_per_day").value = String(DEFAULT_PAGES_PER_DAY);
  updatePacingMethodUI("deadline");
  // Reset with everything else, so an earlier run cannot leave the dialog
  // reopening with no school days ticked at all.
  resetPacingWeekdays();

  lastFocused = document.activeElement;
  $("pacing-modal").hidden = false;
  document.body.classList.add("modal-open");
  curricula.focus();
  loadPacingBooks(chosen);
}

function closeAutoSchedule() {
  const modal = $("pacing-modal");
  if (modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  pacing.preview = null;
  pacingError("");
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus();
  }
}

/** Resolve a curriculum into its current edition and the books paged against it. */
async function loadPacingBooks(curriculumId) {
  const books = pacingField("book_id");
  const note = $("pacing-edition");
  pacing.resources = null;
  pacing.books = [];
  books.disabled = true;
  books.innerHTML = `<option value="" disabled selected>Loading…</option>`;
  note.textContent = "";
  applyBookPages();

  try {
    const data = await api(`/curricula/${curriculumId}/resources`);
    pacing.resources = data;
    // Only a resource with a resolved book has pages to divide up; an answer key
    // recorded without an ISBN cannot be paced.
    pacing.books = data.resources
      .filter((resource) => resource.book_edition)
      .map((resource) => ({
        id: resource.book_edition.id,
        title: resource.book_edition.work.title,
        label: `${resource.book_edition.work.title} · ${humanize(resource.kind)}`,
        pageCount: resource.book_edition.page_count,
      }));

    if (!pacing.books.length) {
      books.innerHTML = `<option value="" disabled selected>No books linked</option>`;
      note.textContent = `${data.curriculum_title} (${data.edition_label}) has no resource with a resolved ISBN, so there is no page range to schedule.`;
      applyBookPages();
      return;
    }
    fillSelect(books, pacing.books, (item) => item.label);
    for (const option of books.options) {
      const book = pacing.books.find((item) => String(item.id) === option.value);
      const pageCount = Number(book?.pageCount);
      if (Number.isFinite(pageCount) && pageCount > 0) {
        option.dataset.pageCount = String(pageCount);
      }
    }
    books.value = String(pacing.books[0].id);
    books.disabled = false;
    note.textContent = `${data.curriculum_title} · ${data.edition_label}`;
    applyBookPages();
  } catch (error) {
    books.innerHTML = `<option value="" disabled selected>Unavailable</option>`;
    applyBookPages();
    pacingError(error.message);
  }
}

/** Page count of the book currently chosen in the Auto-schedule dropdown. */
function selectedBookPageCount() {
  const select = pacingField("book_id");
  const optionCount = Number(select.selectedOptions[0]?.dataset.pageCount);
  if (Number.isFinite(optionCount) && optionCount > 0) {
    return optionCount;
  }
  const book = pacing.books.find((item) => String(item.id) === select.value) || pacing.books[0];
  const count = Number(book?.pageCount ?? book?.page_count);
  return Number.isFinite(count) && count > 0 ? count : null;
}

/** Open the page range on the whole book, when the catalog knows how long it is. */
function applyBookPages() {
  const pageCount = selectedBookPageCount();
  pacingField("end_page").value = pageCount != null ? String(pageCount) : "";
}

function householdExceptionDates() {
  const dates = new Set();
  for (const item of state.exceptions || []) {
    if (item.student_id != null) continue;
    for (const iso of dayRange(item.start_date, item.end_date)) {
      dates.add(iso);
    }
  }
  return dates;
}

function countSchoolDays(startISO, endISO, weekdays, excluded) {
  if (!startISO || !endISO) return 0;
  const allowed = new Set(weekdays);
  const skip = excluded instanceof Set ? excluded : new Set(excluded || []);
  let count = 0;
  for (const iso of dayRange(startISO, endISO)) {
    if (skip.has(iso)) continue;
    if (allowed.has(mondayIndex(parseISODate(iso)))) count += 1;
  }
  return count;
}

/** Map the Lessons dropdown (lessons per school day) onto the API's total count. */
function previewTargetLessons(weekdays, startPage, endPage) {
  const perDay = numberOrNull(pacingField("target_lessons").value);
  if (perDay == null) return null;
  const days = countSchoolDays(
    pacingField("start_date").value,
    pacingField("target_completion_date").value,
    weekdays,
    householdExceptionDates()
  );
  if (days < 1) return null;
  const pages = endPage - startPage + 1;
  return Math.min(perDay * days, Math.max(pages, 1));
}

async function generatePacingPreview() {
  pacingError("");
  const weekdays = pacingWeekdays();
  const bookId = numberOrNull(pacingField("book_id").value);
  const startPage = numberOrNull(pacingField("start_page").value);
  const endPage = numberOrNull(pacingField("end_page").value);

  if (!selectedPacingStudentIds().length) {
    pacingError("Pick at least one student.");
    return;
  }

  if (!bookId) {
    pacingError("Pick a book to schedule.");
    return;
  }
  if (!weekdays.length) {
    pacingError("Pick at least one school day.");
    return;
  }
  if (endPage < startPage) {
    pacingError(`End page ${endPage} comes before start page ${startPage}.`);
    return;
  }

  const method = pacingMethod();
  const payload = {
    book_id: bookId,
    start_page: startPage,
    end_page: endPage,
    start_date: pacingField("start_date").value,
    active_weekdays: weekdays,
    excluded_dates: [...householdExceptionDates()],
  };
  if (method === "pace") {
    const pagesPerDay = numberOrNull(pacingField("pages_per_day").value);
    if (pagesPerDay == null || pagesPerDay < 1) {
      pacingError("Pages per day must be at least 1.");
      return;
    }
    payload.pages_per_day = pagesPerDay;
  } else {
    // A date input's value is already a plain YYYY-MM-DD string, which is what
    // the API reads. It is passed straight through: routing it through a Date
    // is what shifts a day for anyone west of Greenwich.
    payload.target_completion_date = pacingField("target_completion_date").value;
    payload.target_lessons = previewTargetLessons(weekdays, startPage, endPage);
  }

  const submit = $("pacing-form").querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    pacing.preview = await api("/pacing/generate-preview", {
      method: "POST",
      skipOutbox: true,
      body: JSON.stringify(payload),
    });
    renderPacingPreview(pacing.preview);
    showPacingStep("preview");
    $("pacing-course-title").focus();
  } catch (error) {
    pacingError(error.message);
  } finally {
    submit.disabled = false;
  }
}

function pacingMathRows(data) {
  const math = data.pacing;
  const last = data.lessons[data.lessons.length - 1];
  return [
    ["Lessons", math.total_lessons],
    ["School days", math.available_days],
    ["Pages", `${math.total_pages} · ${math.pages_per_lesson} a lesson`],
    [
      "Pace",
      math.is_rigorous
        ? `${math.lessons_per_day} lessons a day`
        : math.day_interval === 1
          ? "Every school day"
          : `Every ${math.day_interval} school days`,
    ],
    ["Last lesson", MEDIUM_DATE.format(parseISODate(last.scheduled_date))],
  ];
}

function renderPacingPreview(data) {
  const math = data.pacing;
  const warning = $("pacing-warning");
  const message =
    math.warning ||
    (math.is_rigorous
      ? `This schedule stacks ${math.lessons_per_day} lessons a day. Move the target completion date out, add school days, or cover fewer pages to ease the pace.`
      : "");
  warning.hidden = !(math.is_rigorous || message);
  warning.textContent = message;
  warning.classList.toggle("rigorous", Boolean(math.is_rigorous));

  $("pacing-math").innerHTML = pacingMathRows(data)
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");

  const finishNote = $("pacing-calculated-finish");
  const finishDate = math.target_completion_date
    ? MEDIUM_DATE.format(parseISODate(math.target_completion_date))
    : "";
  finishNote.hidden = !finishDate;
  finishNote.textContent = finishDate ? `Calculated finish date: ${finishDate}` : "";

  $("pacing-course-title").value = data.book_title;
  $("pacing-rows").innerHTML = data.lessons
    .map(
      (lesson) => `
      <tr>
        <td class="preview-seq">${lesson.sequence}</td>
        <td>
          <input class="preview-title" data-sequence="${lesson.sequence}" maxlength="255"
                 aria-label="Title for lesson ${lesson.sequence}" value="${escapeHtml(lesson.title)}">
        </td>
        <td class="preview-pages">${lesson.start_page}–${lesson.end_page}</td>
        <td class="preview-date">${escapeHtml(MEDIUM_DATE.format(parseISODate(lesson.scheduled_date)))}</td>
      </tr>`
    )
    .join("");
}

function editedLessons(data) {
  const titles = new Map(
    [...$("pacing-rows").querySelectorAll(".preview-title")].map((input) => [
      Number(input.dataset.sequence),
      input.value.trim(),
    ])
  );
  // Only the fields the commit schema declares are sent; it forbids extras, and
  // page_count is the API's to compute.
  return data.lessons.map((lesson) => ({
    sequence: lesson.sequence,
    title: titles.get(lesson.sequence) || lesson.title,
    start_page: lesson.start_page,
    end_page: lesson.end_page,
    scheduled_date: lesson.scheduled_date,
  }));
}

async function commitPacing() {
  const data = pacing.preview;
  if (!data || !pacing.resources) return;

  pacingError("");
  const courseTitle = $("pacing-course-title").value.trim();
  if (!courseTitle) {
    pacingError("Name the course before committing.");
    $("pacing-course-title").focus();
    return;
  }

  const studentIds = selectedPacingStudentIds();
  if (!studentIds.length) {
    pacingError("Pick at least one student.");
    return;
  }

  const button = $("pacing-actions").querySelector('[data-action="commit-pacing"]');
  button.disabled = true;
  try {
    const summary = await api("/pacing/commit", {
      method: "POST",
      body: JSON.stringify({
        student_ids: studentIds,
        curriculum_edition_id: pacing.resources.curriculum_edition_id,
        book_id: data.book_id,
        course_title: courseTitle,
        start_page: numberOrNull(pacingField("start_page").value),
        end_page: numberOrNull(pacingField("end_page").value),
        lessons: editedLessons(data),
      }),
    });
    closeAutoSchedule();
    if (isOfflineQueued(summary)) return;
    await showGeneratedSchedule(summary);
  } catch (error) {
    pacingError(error.message);
  } finally {
    button.disabled = false;
  }
}

/** Land on the calendar showing the work that was just written. */
async function showGeneratedSchedule(summary) {
  const scheduledIds = summary.student_ids || [summary.student_id];
  state.calendarStudentId = scheduledIds.length > 1 ? ALL_STUDENTS : scheduledIds[0];
  // A syllabus usually runs for weeks, so the month view shows more of it than
  // whichever week the parent happened to be looking at.
  state.currentPeriod = "month";
  state.currentAnchorDate = summary.first_scheduled_date;

  // replaceState rather than assigning to the hash: hashchange clears the flash,
  // and the confirmation is the whole reason for coming here.
  if (routeName() !== "assignments") {
    history.replaceState(null, "", "#/assignments");
  }
  try {
    await refresh();
  } catch (error) {
    flash(error.message, true);
  }
  render();
  const from = MEDIUM_DATE.format(parseISODate(summary.first_scheduled_date));
  const to = MEDIUM_DATE.format(parseISODate(summary.last_scheduled_date));
  flash(`${summary.assignments_created} lessons scheduled, ${from} to ${to}.`);
}

function handlePacingClick(event) {
  const control = event.target.closest("[data-action]");
  if (!control) return;

  switch (control.dataset.action) {
    case "close-pacing":
      closeAutoSchedule();
      break;
    case "pacing-back":
      pacingError("");
      showPacingStep("form");
      break;
    case "commit-pacing":
      commitPacing();
      break;
    case "pacing-method":
      updatePacingMethodUI(control.dataset.method);
      break;
    default:
      break;
  }
}

function handlePacingChange(event) {
  const field = event.target;
  if (field.name === "curriculum_id") {
    loadPacingBooks(Number(field.value));
  } else if (field.name === "book_id") {
    applyBookPages();
  }
}

function detailRows(item) {
  const curriculum = [item.resource_title, item.unit_title].filter(Boolean).join(" · ");
  const rows = [
    ["Status", humanize(item.status)],
    ["Scheduled", MEDIUM_DATE.format(parseISODate(item.scheduled_date))],
    [
      "Completed",
      item.completion_date ? MEDIUM_DATE.format(parseISODate(item.completion_date)) : "Not yet",
    ],
    ["Subject", item.subject_taxonomy ? item.subject_taxonomy.full_name : "Unfiled"],
    ["Curriculum", curriculum || "Not linked to the catalog"],
    [
      "Grade",
      item.grade ? `${item.grade.score_value} (${humanize(item.grade.score_type)})` : "Not graded",
    ],
  ];
  if (item.grade && item.grade.graded_on) {
    rows.push(["Graded on", MEDIUM_DATE.format(parseISODate(item.grade.graded_on))]);
  }
  return `<dl class="detail-grid">${rows
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("")}</dl>`;
}

const evidenceBlobUrls = new Map();

function evidenceRelativePath(filePath) {
  const normalized = String(filePath || "").replace(/\\/g, "/");
  let relative = normalized.replace(/^\/+/, "");
  if (relative.startsWith("data/evidence/")) {
    relative = relative.slice("data/evidence/".length);
  }
  const parts = relative.split("/").filter(Boolean);
  if (parts.length !== 2 || parts.some((part) => part === "." || part === "..")) {
    return "";
  }
  return parts.join("/");
}

function evidenceFileRequestPath(filePath) {
  const relative = evidenceRelativePath(filePath);
  if (!relative) return "";
  return `/api/evidence/files/${relative
    .split("/")
    .map(encodeURIComponent)
    .join("/")}`;
}

async function evidenceObjectUrl(filePath) {
  const relative = evidenceRelativePath(filePath);
  if (!relative) return "";
  if (evidenceBlobUrls.has(relative)) return evidenceBlobUrls.get(relative);
  const token = getAuthToken();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(evidenceFileRequestPath(relative), { headers });
  if (!response.ok) return "";
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  evidenceBlobUrls.set(relative, url);
  return url;
}

function clearEvidenceBlobs() {
  for (const url of evidenceBlobUrls.values()) {
    URL.revokeObjectURL(url);
  }
  evidenceBlobUrls.clear();
}

async function hydrateEvidenceImages(root = document) {
  if (!root || typeof root.querySelectorAll !== "function") return;
  const nodes = [...root.querySelectorAll("[data-evidence-file]")];
  await Promise.all(
    nodes.map(async (el) => {
      const current = el.getAttribute("src") || el.getAttribute("href") || "";
      if (current.startsWith("blob:")) return;
      const url = await evidenceObjectUrl(el.getAttribute("data-evidence-file"));
      if (!url) return;
      if (el.tagName === "IMG") el.src = url;
      if (el.tagName === "A") el.href = url;
    })
  );
}

function isImagePath(filePath) {
  return /\.(png|jpe?g|gif|webp|heic|bmp|svg|avif)$/i.test(filePath || "");
}

function evidenceThumb(record) {
  if (record.file_path) {
    const alt = record.notes || "Work sample";
    const fileAttr = `data-evidence-file="${escapeHtml(record.file_path)}"`;
    if (isImagePath(record.file_path)) {
      return `<a ${fileAttr} target="_blank" rel="noopener">
        <img ${fileAttr} alt="${escapeHtml(alt)}">
      </a>`;
    }
    const name = String(record.file_path).split("/").pop() || "File";
    return `<a class="evidence-file" ${fileAttr} target="_blank" rel="noopener">${escapeHtml(name)}</a>`;
  }
  if (record.url) {
    return `<a class="evidence-file" href="${escapeHtml(record.url)}" target="_blank" rel="noopener">${escapeHtml(
      record.url
    )}</a>`;
  }
  return "";
}

function evidenceGallery(item) {
  const records = item.evidence || [];
  if (!records.length) {
    return `<p class="empty">No work samples attached.</p>`;
  }
  return records.map(evidenceThumb).join("");
}

function detailBody(item) {
  const notes = [
    item.notes ? ["Notes", item.notes] : null,
    item.grade && item.grade.notes ? ["Grade notes", item.grade.notes] : null,
  ].filter(Boolean);

  return `
    ${detailRows(item)}
    ${notes
      .map(
        ([label, text]) =>
          `<section class="detail-section"><h3>${label}</h3><p>${escapeHtml(text)}</p></section>`
      )
      .join("")}
    <section class="detail-section">
      <div class="evidence-head">
        <h3>Evidence (${item.evidence_count})</h3>
        <button type="button" class="ghost" data-action="upload-evidence">Upload</button>
      </div>
      <div id="evidence-gallery" class="evidence-gallery">${evidenceGallery(item)}</div>
    </section>
    ${renderHomeworkHelpHistory(item)}`;
}

const detail = { item: null, editing: false, helpSessions: [] };

function detailForm(item) {
  const grade = item.grade || {};
  return `
    <form id="assignment-edit" data-form="assignment-edit">
      <div class="field-row">
        <label>Status<select name="status">${enumOptions(STATUSES, item.status)}</select></label>
        <label>Scheduled<input type="date" name="scheduled_date" required value="${item.scheduled_date}"></label>
        <label>Completed<input type="date" name="completion_date" value="${item.completion_date || ""}"></label>
      </div>
      <fieldset class="detail-fieldset">
        <legend>Grade</legend>
        <div class="field-row">
          <label>Score<input name="score_value" maxlength="64" placeholder="A+, 18/20, 92"
                             value="${escapeHtml(grade.score_value || "")}"></label>
          <label>Type<select name="score_type">${enumOptions(SCORE_TYPES, grade.score_type || "percentage")}</select></label>
          <label>Graded on<input type="date" name="graded_on" value="${grade.graded_on || ""}"></label>
        </div>
        <label>Grade notes<textarea name="grade_notes">${escapeHtml(grade.notes || "")}</textarea></label>
        <p class="muted">An empty score leaves any recorded grade untouched. Saving a score
          replaces the whole grade, so blank fields here are stored as blank.</p>
      </fieldset>
    </form>`;
}

function detailActions() {
  if (detail.editing) {
    // The buttons sit outside the form, so the submit button names its owner.
    return `
      <button type="submit" form="assignment-edit">Save changes</button>
      <button type="button" class="ghost" data-action="cancel-edit">Cancel</button>`;
  }
  return `
    <button type="button" data-action="edit-assignment">Edit</button>
    <button type="button" class="danger" data-action="delete-assignment">Delete assignment</button>`;
}

function renderDetail() {
  const item = detail.item;
  if (!item) return;
  $("detail-eyebrow").textContent = FULL_DATE.format(parseISODate(item.scheduled_date));
  $("detail-title").textContent = item.title;
  $("detail-body").innerHTML = detail.editing ? detailForm(item) : detailBody(item);
  $("detail-actions").innerHTML = detailActions();
  $("detail-actions").hidden = false;
  if (!detail.editing) hydrateEvidenceImages($("detail-body"));
}

function openModal() {
  lastFocused = document.activeElement;
  $("detail-modal").hidden = false;
  document.body.classList.add("modal-open");
  $("detail-modal").querySelector(".icon-button").focus();
}

function closeModal() {
  const modal = $("detail-modal");
  if (modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  detail.item = null;
  detail.editing = false;
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus();
  }
}

function renderHomeworkHelpHistory(item) {
  const sessions = detail.helpSessions || [];
  const locked = sessions.some((session) => session.status === "redirected");
  const latest = sessions[0];
  let body = `<p class="empty">This child has not used homework help on this assignment.</p>`;
  if (latest) {
    const when = latest.messages.length
      ? latest.messages[latest.messages.length - 1]
      : null;
    body = `<p>${escapeHtml(humanize(latest.status))}${
      when ? ` · last activity in this session` : ""
    }</p>
      <div class="homework-thread">${(latest.messages || [])
        .map(
          (message) =>
            `<div class="homework-bubble is-${escapeHtml(message.role)}">${escapeHtml(message.content)}</div>`
        )
        .join("")}</div>`;
  }
  return `
    <section class="detail-section">
      <h3>Homework help</h3>
      ${body}
      ${
        locked
          ? `<button type="button" data-action="unlock-homework-help" data-id="${item.id}">Allow homework help again</button>`
          : ""
      }
    </section>`;
}

async function openAssignment(assignmentId) {
  detail.item = null;
  detail.editing = false;
  detail.helpSessions = [];
  $("detail-eyebrow").textContent = "";
  $("detail-title").textContent = "Loading…";
  $("detail-body").innerHTML = `<p class="empty">Loading assignment…</p>`;
  $("detail-actions").hidden = true;
  openModal();
  try {
    detail.item = await api(`/assignments/${assignmentId}`);
    try {
      detail.helpSessions = await api(`/homework-help/sessions?assignment_id=${assignmentId}`);
    } catch {
      detail.helpSessions = [];
    }
    renderDetail();
  } catch (error) {
    $("detail-title").textContent = "Could not load assignment";
    $("detail-body").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

async function saveAssignment() {
  const form = $("assignment-edit");
  const previous = detail.item;
  if (!form || !previous) return;
  const data = formValues(form);
  flash("");
  try {
    let item = await api(`/assignments/${previous.id}`, {
      method: "PUT",
      body: JSON.stringify({
        status: data.status,
        scheduled_date: data.scheduled_date,
        completion_date: emptyToNull(data.completion_date),
      }),
    });
    // The grade is a separate record with its own upsert, and an empty score
    // means "no opinion", not "wipe the grade".
    const score = emptyToNull(data.score_value);
    const queued = isOfflineQueued(item);
    let gradeQueued = false;
    if (score) {
      const graded = await api(`/assignments/${previous.id}/grade`, {
        method: "PUT",
        body: JSON.stringify({
          score_type: data.score_type,
          score_value: score,
          graded_on: emptyToNull(data.graded_on),
          notes: emptyToNull(data.grade_notes),
        }),
      });
      gradeQueued = isOfflineQueued(graded);
      if (!gradeQueued) item = graded;
    }
    if (queued || gradeQueued) {
      detail.item = {
        ...previous,
        status: data.status,
        scheduled_date: data.scheduled_date,
        completion_date: emptyToNull(data.completion_date),
      };
      if (score) {
        detail.item.grade = {
          ...(previous.grade || {}),
          score_type: data.score_type,
          score_value: score,
          graded_on: emptyToNull(data.graded_on),
          notes: emptyToNull(data.grade_notes),
        };
      }
      detail.editing = false;
      renderDetail();
      return;
    }
    detail.item = item;
    detail.editing = false;
    renderDetail();
    await syncCalendarTile(previous, item);
    flash("Assignment saved.");
  } catch (error) {
    flash(error.message, true);
  }
}

function uploadEvidence(event) {
  const input = event.target;
  const file = input.files && input.files[0];
  const item = detail.item;
  if (!file || !item || detail.editing) {
    input.value = "";
    return;
  }

  const payload = new FormData();
  payload.append("file", file);
  const assignmentId = item.id;
  const previous = item;
  const query = item.shared_group_uuid ? "?apply_to_group=true" : "";
  input.value = "";
  closeModal();
  queueEvidenceUpload({ assignmentId, previous, payload, query });
}

function importCurriculumCsv(event) {
  const input = event.target;
  const file = input.files && input.files[0];
  input.value = "";
  if (!file || catalogKind() !== "plans") return;

  const payload = new FormData();
  payload.append("file", file);
  beginBackgroundJob("upload");
  api("/curriculum/import-csv", { method: "POST", body: payload })
    .then(async (result) => {
      settleUploadQueue(true, "upload");
      if (isOfflineQueued(result)) return;
      state.curriculumPlans = await api("/curriculum/plans");
      render();
      flash("Pacing guide imported.");
    })
    .catch((error) => {
      lastUploadError = error.message || "Upload Failed";
      settleUploadQueue(false, "upload");
      flash(error.message || "Upload Failed", true);
    });
}

function importCurriculumPdf(event) {
  const input = event.target;
  const file = input.files && input.files[0];
  input.value = "";
  if (!file || catalogKind() !== "plans") return;

  const payload = new FormData();
  payload.append("file", file);
  pdfImportBusy = true;
  if (catalogKind() === "plans") render();
  api("/curriculum/import-pdf", { method: "POST", body: payload, skipOutbox: true })
    .then(async (result) => {
      if (isOfflineQueued(result)) return;
      showToast("success", "PDF accepted for background AI processing.");
      try {
        state.curriculumPlans = await api("/curriculum/plans");
        syncPlanStatusPolling();
      } catch {
        // The PDF is already accepted; refreshing the catalog is best-effort.
      }
    })
    .catch((error) => {
      flash(error.message || "Upload Failed", true);
    })
    .finally(() => {
      pdfImportBusy = false;
      if (catalogKind() === "plans") render();
    });
}

function stopPaperImportPolling() {
  if (paperImportPollTimer) {
    window.clearTimeout(paperImportPollTimer);
    paperImportPollTimer = 0;
  }
}

function finishPaperImportUi() {
  stopPaperImportPolling();
  paperImportBusy = false;
  paperImportPhase = "";
  paperImportPlanId = 0;
}

function pollPaperImportPlan(planId) {
  stopPaperImportPolling();
  paperImportPollTimer = window.setTimeout(async () => {
    paperImportPollTimer = 0;
    if (paperImportPlanId !== planId) return;
    try {
      const plan = await api(`/curriculum/plans/${planId}`);
      if (plan.status === "ready") {
        finishPaperImportUi();
        flash("");
        try {
          state.curriculumPlans = await api("/curriculum/plans");
        } catch {
          /* catalog refresh is best-effort */
        }
        if (catalogKind() === "plans") render();
        showToast("success", "Paper import is ready", "Review the lessons before applying them.");
        await openLessonBuilderEdit(planId);
        return;
      }
      if (plan.status === "failed") {
        finishPaperImportUi();
        flash("Handwriting extraction failed. You can edit the plan by hand or try another photo.", true);
        try {
          state.curriculumPlans = await api("/curriculum/plans");
        } catch {
          /* catalog refresh is best-effort */
        }
        if (catalogKind() === "plans") render();
        showToast("error", "Handwriting extraction failed");
        return;
      }
    } catch {
      // Keep polling; the plan may still be processing.
    }
    if (paperImportPlanId === planId) pollPaperImportPlan(planId);
  }, PAPER_IMPORT_POLL_MS);
}

async function downloadPaperTemplate() {
  if (paperTemplateBusy) return;
  paperTemplateBusy = true;
  if (catalogKind() === "plans") render();
  const token = getAuthToken();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    const res = await fetch("/api/curriculum/paper-template", { headers });
    if (!res.ok) {
      if (res.status === 401) handleUnauthorized();
      let message = `Request failed (${res.status})`;
      try {
        const body = await res.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch {
        /* not JSON */
      }
      throw new Error(message);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "curiculy_template.pdf";
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (error) {
    flash(error.message || "Could not download the paper template.", true);
  } finally {
    paperTemplateBusy = false;
    if (catalogKind() === "plans") render();
  }
}

function importPaperSheet(event) {
  const input = event.target;
  const file = input.files && input.files[0];
  input.value = "";
  if (!file) return;

  const payload = new FormData();
  payload.append("file", file);
  paperImportBusy = true;
  paperImportPhase = "scanning";
  flash("Scanning page geometry...");
  if (catalogKind() === "plans") render();
  api("/curriculum/import-paper", { method: "POST", body: payload, skipOutbox: true })
    .then(async (result) => {
      if (isOfflineQueued(result)) {
        finishPaperImportUi();
        flash("");
        return;
      }
      const planId = Number(result && result.id);
      paperImportPhase = "transcribing";
      paperImportPlanId = planId;
      flash("Transcribing handwriting with Ollama...");
      try {
        state.curriculumPlans = await api("/curriculum/plans");
      } catch {
        /* the photo is already accepted */
      }
      if (catalogKind() === "plans") render();
      pollPaperImportPlan(planId);
    })
    .catch((error) => {
      finishPaperImportUi();
      flash(error.message || "Could not scan the page. Check that all four corners are visible.", true);
      if (catalogKind() === "plans") render();
    });
}

function queueEvidenceUpload({ assignmentId, previous, payload, query }) {
  beginBackgroundJob("upload");

  api(`/assignments/${assignmentId}/evidence${query}`, { method: "POST", body: payload })
    .then((result) => {
      settleUploadQueue(true, "upload");
      if (isOfflineQueued(result)) return;
      return api(`/assignments/${assignmentId}`)
        .then(async (item) => {
          await syncCalendarTile(previous, item);
          if (detail.item && detail.item.id === assignmentId && !detail.editing) {
            detail.item = item;
            renderDetail();
          }
        })
        .catch(() => {
          // The file is already saved; refreshing the tile is best-effort.
        });
    })
    .catch((error) => {
      lastUploadError = error.message || "Upload Failed";
      settleUploadQueue(false, "upload");
    });
}

function settleUploadQueue(ok, kind = "upload") {
  if (!ok) uploadFailures += 1;
  uploadQueue = Math.max(0, uploadQueue - 1);
  if (kind === "email") {
    queueEmails = Math.max(0, queueEmails - 1);
  } else {
    queueUploads = Math.max(0, queueUploads - 1);
  }
  if (uploadQueue > 0) {
    showUploadProgressToast();
    return;
  }
  const succeeded = uploadFailures === 0;
  uploadFailures = 0;
  finishUploadToast(succeeded);
}

async function deleteAssignment() {
  const item = detail.item;
  if (!item) return;
  if (!window.confirm(`Delete “${item.title}”? Its grade and work samples go too.`)) return;
  try {
    const result = await api(`/assignments/${item.id}`, { method: "DELETE" });
    closeModal();
    if (isOfflineQueued(result)) return;
    await refreshVisibleAssignmentBoard();
    flash("Assignment deleted.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function unscheduleCurriculum(curriculumId) {
  const item = state.curricula.find((entry) => entry.id === curriculumId);
  const title = item ? item.title : "this book";
  if (
    !window.confirm(
      `Remove all scheduled lessons for “${title}” from the calendar?`
    )
  ) {
    return;
  }
  try {
    const result = await api(`/curricula/${curriculumId}/schedule`, { method: "DELETE" });
    if (isOfflineQueued(result)) return;
    await refresh();
    render();
    flash("Removed from the calendar.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function deleteStudent(studentId) {
  if (!studentId) return;
  const student = state.students.find((item) => item.id === studentId);
  const name = student ? student.name : "this student";
  if (
    !window.confirm(
      `Delete “${name}”? Their assignments and work samples will be removed too.`
    )
  ) {
    return;
  }
  try {
    const result = await api(`/students/${studentId}`, { method: "DELETE" });
    studentEditor.id = null;
    if (state.calendarStudentId === studentId) {
      state.calendarStudentId = null;
    }
    if (isOfflineQueued(result)) return;
    await refresh();
    render();
    flash("Student deleted.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function deleteCurriculum(curriculumId) {
  const item = state.curricula.find((entry) => entry.id === curriculumId);
  const title = item ? item.title : "this curriculum";
  if (!window.confirm(`Delete “${title}” from the catalog? This cannot be undone.`)) {
    return;
  }
  try {
    const result = await api(`/curricula/${curriculumId}`, { method: "DELETE" });
    if (isOfflineQueued(result)) return;
    await refresh();
    render();
    flash("Curriculum deleted.");
  } catch (error) {
    flash(error.message, true);
  }
}

function handleModalClick(event) {
  const control = event.target.closest("[data-action]");
  if (!control) return;

  switch (control.dataset.action) {
    case "close-modal":
      closeModal();
      break;
    case "edit-assignment":
      detail.editing = true;
      renderDetail();
      $("detail-body").querySelector("select, input").focus();
      break;
    case "cancel-edit":
      detail.editing = false;
      renderDetail();
      break;
    case "delete-assignment":
      deleteAssignment();
      break;
    case "upload-evidence":
      $("evidence-upload-input").click();
      break;
    default:
      break;
  }
}

function reportTypeLabel(value) {
  const match = REPORT_TYPES.find(([id]) => id === value);
  return match ? match[1] : humanize(value);
}

function isCustomPortfolio() {
  return state.portfolio.reportType === "custom";
}

function currentSchoolYearForPortfolio() {
  const today = todayISO();
  const containing = state.years.find(
    (year) => year.start_date <= today && today <= year.end_date
  );
  if (containing) return containing;
  const selected = state.years.find((year) => year.id === state.portfolio.schoolYearId);
  return selected || state.years[0] || null;
}

function ensurePortfolioCustomDefaults() {
  const custom = state.portfolio.custom;
  const year = currentSchoolYearForPortfolio();
  if (!custom.startDate || !custom.endDate) {
    if (year) {
      custom.startDate = year.start_date;
      custom.endDate = year.end_date;
    } else {
      const today = todayISO();
      custom.startDate = today;
      custom.endDate = today;
    }
  }
  if (!custom.studentIds.length) {
    const selected = selectedPortfolioStudentId();
    custom.studentIds = selected ? [selected] : state.students.map((student) => student.id);
  }
  custom.allStudents =
    state.students.length > 0 &&
    custom.studentIds.length === state.students.length &&
    state.students.every((student) => custom.studentIds.includes(student.id));
}

function customPortfolioStudentIds() {
  if (state.portfolio.custom.allStudents) {
    return state.students.map((student) => student.id);
  }
  return state.portfolio.custom.studentIds.filter((id) =>
    state.students.some((student) => student.id === id)
  );
}

function portfolioGeneratePayload() {
  if (!isCustomPortfolio()) {
    return {
      report_type: state.portfolio.reportType,
      student_id: selectedPortfolioStudentId(),
      student_ids: [selectedPortfolioStudentId()],
      school_year_id: selectedPortfolioYearId(),
    };
  }
  const custom = state.portfolio.custom;
  const books = custom.includeBooks;
  return {
    report_type: "custom",
    student_ids: customPortfolioStudentIds(),
    start_date: custom.startDate,
    end_date: custom.endDate,
    include_attendance: custom.includeAttendance,
    include_lessons: custom.includeLessons,
    include_assignments: custom.includeAssignments,
    include_books_completed: Boolean(books && custom.includeBooksCompleted),
    include_books_in_progress: Boolean(books && custom.includeBooksInProgress),
    include_books_incomplete: Boolean(books && custom.includeBooksIncomplete),
    include_attachments: custom.includeAttachments,
    include_notes: custom.includeNotes,
  };
}

function portfolioReady() {
  if (isCustomPortfolio()) {
    ensurePortfolioCustomDefaults();
    return (
      customPortfolioStudentIds().length > 0 &&
      Boolean(state.portfolio.custom.startDate && state.portfolio.custom.endDate)
    );
  }
  return Boolean(selectedPortfolioStudentId() && selectedPortfolioYearId());
}

function portfolioCustomPanel() {
  const custom = state.portfolio.custom;
  const studentBoxes = state.students
    .map(
      (student) => `
        <label class="weekday-toggle">
          <input type="checkbox" data-control="portfolio-custom-student" value="${student.id}"
                 ${custom.studentIds.includes(student.id) || custom.allStudents ? "checked" : ""}>
          ${escapeHtml(student.name)}
        </label>`
    )
    .join("");
  const booksOpen = custom.includeBooks;
  return `
    <div class="portfolio-custom-panel">
      <div class="field-row">
        <fieldset class="portfolio-students">
          <legend>Students</legend>
          <label class="weekday-toggle">
            <input type="checkbox" data-control="portfolio-all-students" ${custom.allStudents ? "checked" : ""}>
            All Students
          </label>
          ${studentBoxes || `<p class="empty">Add a student in Settings first.</p>`}
        </fieldset>
        <div class="field-row">
          <label class="inline-field">Start Date
            <input type="date" data-control="portfolio-start-date" value="${escapeHtml(custom.startDate)}">
          </label>
          <label class="inline-field">End Date
            <input type="date" data-control="portfolio-end-date" value="${escapeHtml(custom.endDate)}">
          </label>
        </div>
      </div>
      <fieldset class="portfolio-modules">
        <legend>Include in report</legend>
        <label><input type="checkbox" data-control="portfolio-module" data-module="includeAttendance" ${custom.includeAttendance ? "checked" : ""}> Attendance (Presents, Absences, Sick, Vacation)</label>
        <label><input type="checkbox" data-control="portfolio-module" data-module="includeLessons" ${custom.includeLessons ? "checked" : ""}> Lessons &amp; Completed Activity Log</label>
        <label><input type="checkbox" data-control="portfolio-module" data-module="includeAssignments" ${custom.includeAssignments ? "checked" : ""}> Assignments (with completion status)</label>
        <label><input type="checkbox" data-control="portfolio-module" data-module="includeBooks" ${booksOpen ? "checked" : ""}> Books / Reading Log</label>
        <div class="portfolio-books-sub"${booksOpen ? "" : " hidden"}>
          <label><input type="checkbox" data-control="portfolio-module" data-module="includeBooksCompleted" ${custom.includeBooksCompleted ? "checked" : ""}> Completed</label>
          <label><input type="checkbox" data-control="portfolio-module" data-module="includeBooksInProgress" ${custom.includeBooksInProgress ? "checked" : ""}> In Progress</label>
          <label><input type="checkbox" data-control="portfolio-module" data-module="includeBooksIncomplete" ${custom.includeBooksIncomplete ? "checked" : ""}> Incomplete</label>
        </div>
        <label><input type="checkbox" data-control="portfolio-module" data-module="includeAttachments" ${custom.includeAttachments ? "checked" : ""}> Photos / Attachments</label>
        <label><input type="checkbox" data-control="portfolio-module" data-module="includeNotes" ${custom.includeNotes ? "checked" : ""}> Lesson &amp; Assignment Notes</label>
      </fieldset>
    </div>`;
}

function renderPortfolios() {
  const studentId = selectedPortfolioStudentId();
  const yearId = selectedPortfolioYearId();
  const reportType = state.portfolio.reportType;
  const custom = isCustomPortfolio();
  if (custom) ensurePortfolioCustomDefaults();
  const studentOptions = state.students.length
    ? state.students
        .map(
          (student) =>
            `<option value="${student.id}"${student.id === studentId ? " selected" : ""}>${escapeHtml(student.name)}</option>`
        )
        .join("")
    : `<option value="">No students yet</option>`;
  const yearOptions = state.years.length
    ? state.years
        .map(
          (year) =>
            `<option value="${year.id}"${year.id === yearId ? " selected" : ""}>${escapeHtml(year.name)}</option>`
        )
        .join("")
    : `<option value="">No school years yet</option>`;
  const ready = portfolioReady();
  const enrollmentsForPreview = custom
    ? state.enrollments || []
    : (state.enrollments || []).filter(
        (row) => row.student_id === studentId && row.school_year_id === yearId
      );
  const emptyReadingList = ready && !enrollmentsForPreview.length;
  return `
    <section id="portfolio-view">
      <div class="portfolio-toolbar">
        ${
          custom
            ? ""
            : `<label class="inline-field">Student
          <select data-control="portfolio-student"${state.students.length ? "" : " disabled"}>${studentOptions}</select>
        </label>
        <label class="inline-field">School Year
          <select data-control="portfolio-year"${state.years.length ? "" : " disabled"}>${yearOptions}</select>
        </label>`
        }
        <label class="inline-field">Report Type
          <select data-control="portfolio-type">
            ${REPORT_TYPES.map(
              ([value, label]) =>
                `<option value="${value}"${value === reportType ? " selected" : ""}>${escapeHtml(label)}</option>`
            ).join("")}
          </select>
        </label>
        <div class="portfolio-toolbar-actions">
          <button type="button" class="ghost" data-action="email-evaluator"${
            ready ? "" : " disabled"
          }>Email Evaluator</button>
          <button type="button" data-action="print-portfolio"${ready ? "" : " disabled"}>Print / Save PDF</button>
        </div>
      </div>
      ${custom ? portfolioCustomPanel() : ""}
      ${
        emptyReadingList
          ? `<p class="text-gray-500 italic">Reading list is empty. <br><span class="text-xs">Note: Book auto-schedule from before auto-enrollment can be reconstructed with the operator backfill script (see README). Week/day plan lessons are not stored with a library link; add those books in Settings → Enrollments.</span></p>`
          : ""
      }
      <div class="a4-preview">
        <div id="portfolio-canvas" class="a4-canvas">
          <p class="empty">${
            custom
              ? "Select students, a date range, and modules to preview a portfolio."
              : "Select a student and school year to preview a portfolio."
          }</p>
        </div>
      </div>
    </section>`;
}

let portfolioRequest = 0;

async function loadPortfolioReport() {
  const canvas = $("portfolio-canvas");
  if (!canvas) return;
  if (!portfolioReady()) {
    canvas.innerHTML = isCustomPortfolio()
      ? `<p class="empty">Select at least one student and a date range.</p>`
      : `<p class="empty">Select a student and school year to preview a portfolio.</p>`;
    return;
  }
  const token = (portfolioRequest += 1);
  try {
    const preview = await api("/portfolios/preview", {
      method: "POST",
      body: JSON.stringify(portfolioGeneratePayload()),
    });
    if (token !== portfolioRequest || !$("portfolio-canvas")) return;
    $("portfolio-canvas").innerHTML = preview.html || `<p class="empty">Nothing to preview.</p>`;
    hydrateEvidenceImages($("portfolio-canvas"));
  } catch (error) {
    if (token !== portfolioRequest || !$("portfolio-canvas")) return;
    $("portfolio-canvas").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    flash(error.message, true);
  }
}

function isEmailEvaluatorOpen() {
  const modal = $("email-evaluator-modal");
  return Boolean(modal && !modal.hidden);
}

function openEmailEvaluator() {
  if (!portfolioReady()) {
    flash(
      isCustomPortfolio()
        ? "Select at least one student and a date range first."
        : "Select a student and school year first.",
      true
    );
    return;
  }
  const form = $("email-evaluator-form");
  if (!form) return;
  lastFocused = document.activeElement;
  const names = isCustomPortfolio()
    ? customPortfolioStudentIds().map(studentName).join(", ")
    : studentName(selectedPortfolioStudentId());
  form.elements.subject.value = `${names} Portfolio Log`;
  $("email-evaluator-modal").hidden = false;
  document.body.classList.add("modal-open");
  form.elements.evaluator_email.focus();
}

function closeEmailEvaluator() {
  const modal = $("email-evaluator-modal");
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  if (
    $("detail-modal").hidden &&
    $("pacing-modal").hidden &&
    (!$("onboarding-wizard") || $("onboarding-wizard").hidden)
  ) {
    document.body.classList.remove("modal-open");
  }
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus();
  }
}

function submitEvaluatorEmail(event) {
  event.preventDefault();
  const form = event.target.closest("form[data-form='email-evaluator']");
  if (!form) return;
  if (!portfolioReady()) {
    flash(
      isCustomPortfolio()
        ? "Select at least one student and a date range first."
        : "Select a student and school year first.",
      true
    );
    return;
  }
  const data = formValues(form);
  const payload = {
    ...portfolioGeneratePayload(),
    evaluator_email: (data.evaluator_email || "").trim(),
    subject: (data.subject || "").trim(),
    message: (data.message || "").trim(),
  };
  closeEmailEvaluator();
  queueEvaluatorEmail(payload);
}

function queueEvaluatorEmail(payload) {
  beginBackgroundJob("email");
  api("/portfolios/email", {
    method: "POST",
    body: JSON.stringify(payload),
  })
    .then(() => settleUploadQueue(true, "email"))
    .catch((error) => {
      lastUploadError = error.message || "Email Failed";
      settleUploadQueue(false, "email");
    });
}

function handleEmailEvaluatorClick(event) {
  if (event.target.closest("[data-action='close-email-evaluator']")) {
    closeEmailEvaluator();
  }
}

/* ---- School year & vacations ---- */

const SY_CHECK =
  '<svg class="sy-icon" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M6.3 11.5 2.8 8l1.1-1.1 2.4 2.4 5.8-5.8 1.1 1.1z"/></svg>';
const SY_CROSS =
  '<svg class="sy-icon" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="m4.2 3.1 3.8 3.8 3.8-3.8 1.1 1.1-3.8 3.8 3.8 3.8-1.1 1.1-3.8-3.8-3.8 3.8-1.1-1.1 3.8-3.8-3.8-3.8z"/></svg>';

const US_HOLIDAY_REGIONS = [
  { country: "US", subdiv: "", label: "Holidays in United States (Federal)" },
  ["AL", "Alabama"],
  ["AK", "Alaska"],
  ["AZ", "Arizona"],
  ["AR", "Arkansas"],
  ["CA", "California"],
  ["CO", "Colorado"],
  ["CT", "Connecticut"],
  ["DE", "Delaware"],
  ["DC", "District of Columbia"],
  ["FL", "Florida"],
  ["GA", "Georgia"],
  ["HI", "Hawaii"],
  ["ID", "Idaho"],
  ["IL", "Illinois"],
  ["IN", "Indiana"],
  ["IA", "Iowa"],
  ["KS", "Kansas"],
  ["KY", "Kentucky"],
  ["LA", "Louisiana"],
  ["ME", "Maine"],
  ["MD", "Maryland"],
  ["MA", "Massachusetts"],
  ["MI", "Michigan"],
  ["MN", "Minnesota"],
  ["MS", "Mississippi"],
  ["MO", "Missouri"],
  ["MT", "Montana"],
  ["NE", "Nebraska"],
  ["NV", "Nevada"],
  ["NH", "New Hampshire"],
  ["NJ", "New Jersey"],
  ["NM", "New Mexico"],
  ["NY", "New York"],
  ["NC", "North Carolina"],
  ["ND", "North Dakota"],
  ["OH", "Ohio"],
  ["OK", "Oklahoma"],
  ["OR", "Oregon"],
  ["PA", "Pennsylvania"],
  ["RI", "Rhode Island"],
  ["SC", "South Carolina"],
  ["SD", "South Dakota"],
  ["TN", "Tennessee"],
  ["TX", "Texas"],
  ["UT", "Utah"],
  ["VT", "Vermont"],
  ["VA", "Virginia"],
  ["WA", "Washington"],
  ["WV", "West Virginia"],
  ["WI", "Wisconsin"],
  ["WY", "Wyoming"],
].map((item) =>
  Array.isArray(item)
    ? { country: "US", subdiv: item[0], label: `Holidays in ${item[1]}` }
    : item
);

const schoolYearEditor = {
  start_date: "",
  end_date: "",
  weekdays: [0, 1, 2, 3, 4],
  exceptionDates: new Set(),
  pending: new Set(),
};

let schoolYearSaveTimer = null;

function isSchoolYearOpen() {
  const modal = $("school-year-modal");
  return Boolean(modal) && !modal.hidden;
}

function schoolYearError(message) {
  const el = $("school-year-error");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function schoolYearStatus(message) {
  const el = $("school-year-status");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function fillHolidayRegions() {
  const select = $("school-year-holiday-region");
  if (!select || select.options.length) return;
  select.innerHTML = US_HOLIDAY_REGIONS.map(
    (item) =>
      `<option value="${item.country}:${item.subdiv}">${escapeHtml(item.label)}</option>`
  ).join("");
}

function readSchoolYearForm() {
  schoolYearEditor.start_date = $("school-year-start")?.value || "";
  schoolYearEditor.end_date = $("school-year-end")?.value || "";
  schoolYearEditor.weekdays = [...document.querySelectorAll("#school-year-weekdays input:checked")].map(
    (box) => Number(box.value)
  );
}

function isEditorSchoolDay(iso) {
  if (!schoolYearEditor.start_date || !schoolYearEditor.end_date) return false;
  if (iso < schoolYearEditor.start_date || iso > schoolYearEditor.end_date) return false;
  const classDay = schoolYearEditor.weekdays.includes(mondayIndex(parseISODate(iso)));
  return classDay && !schoolYearEditor.exceptionDates.has(iso);
}

function updateSchoolYearTotal() {
  const el = $("school-year-total");
  if (!el) return;
  let total = 0;
  if (
    schoolYearEditor.start_date &&
    schoolYearEditor.end_date &&
    schoolYearEditor.end_date >= schoolYearEditor.start_date
  ) {
    for (const iso of dayRange(schoolYearEditor.start_date, schoolYearEditor.end_date)) {
      if (isEditorSchoolDay(iso)) total += 1;
    }
  }
  el.textContent = String(total);
}

function schoolYearMonthCells(year, month) {
  const first = new Date(Date.UTC(year, month, 1));
  const lastDate = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const cells = [];
  for (let blank = 0; blank < mondayIndex(first); blank += 1) {
    cells.push('<span class="sy-day is-pad" aria-hidden="true"></span>');
  }
  const today = todayISO();
  for (let day = 1; day <= lastDate; day += 1) {
    const iso = toISODate(new Date(Date.UTC(year, month, day)));
    const inRange =
      iso >= schoolYearEditor.start_date && iso <= schoolYearEditor.end_date;
    if (!inRange) {
      cells.push(
        `<span class="sy-day is-out"><span class="sy-num">${day}</span></span>`
      );
      continue;
    }
    const school = isEditorSchoolDay(iso);
    cells.push(`
      <button type="button" class="sy-day ${school ? "is-school" : "is-off"}${
        iso === today ? " is-today" : ""
      }" data-action="toggle-school-day" data-date="${iso}"
              aria-pressed="${school}"
              aria-label="${iso}: ${school ? "school day" : "no school"}">
        <span class="sy-num">${day}</span>
        <span class="sy-mark">${school ? SY_CHECK : SY_CROSS}</span>
      </button>`);
  }
  return cells.join("");
}

function renderSchoolYearGrid() {
  const grid = $("school-year-grid");
  if (!grid) return;
  if (!schoolYearEditor.start_date || !schoolYearEditor.end_date) {
    grid.innerHTML = `<p class="empty">Set a first and last day to see the year.</p>`;
    updateSchoolYearTotal();
    return;
  }
  if (schoolYearEditor.end_date < schoolYearEditor.start_date) {
    grid.innerHTML = `<p class="empty">Last day must be on or after the first day.</p>`;
    updateSchoolYearTotal();
    return;
  }
  const months = [];
  const cursor = parseISODate(schoolYearEditor.start_date);
  cursor.setUTCDate(1);
  const last = parseISODate(schoolYearEditor.end_date);
  while (cursor <= last) {
    const year = cursor.getUTCFullYear();
    const month = cursor.getUTCMonth();
    const label = MONTH_YEAR.format(new Date(Date.UTC(year, month, 1)));
    months.push(`
      <section class="sy-month">
        <h3>${escapeHtml(label)}</h3>
        <div class="sy-weekdays">${WEEKDAYS.map((day) => `<span>${day}</span>`).join("")}</div>
        <div class="sy-days">${schoolYearMonthCells(year, month)}</div>
      </section>`);
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }
  grid.innerHTML = months.join("");
  updateSchoolYearTotal();
}

function paintSchoolYearDay(iso) {
  const button = document.querySelector(`#school-year-grid [data-date="${iso}"]`);
  if (!button) {
    updateSchoolYearTotal();
    return;
  }
  const school = isEditorSchoolDay(iso);
  button.classList.toggle("is-school", school);
  button.classList.toggle("is-off", !school);
  button.setAttribute("aria-pressed", String(school));
  button.setAttribute("aria-label", `${iso}: ${school ? "school day" : "no school"}`);
  const mark = button.querySelector(".sy-mark");
  if (mark) mark.innerHTML = school ? SY_CHECK : SY_CROSS;
  updateSchoolYearTotal();
}

async function persistSchoolYearSettings() {
  const start = schoolYearEditor.start_date;
  const end = schoolYearEditor.end_date;
  const weekdays = schoolYearEditor.weekdays;
  if (!start || !end) return;
  if (end < start) {
    schoolYearError("Last day must be on or after the first day.");
    return;
  }
  if (!weekdays.length) {
    schoolYearError("Pick at least one class day.");
    return;
  }
  schoolYearError("");
  try {
    const saved = await api("/settings/school-year", {
      method: "PUT",
      body: JSON.stringify({ start_date: start, end_date: end, weekdays }),
    });
    state.schoolYear = saved;
    await loadYears();
  } catch (error) {
    schoolYearError(error.message);
  }
}

function scheduleSchoolYearSave() {
  readSchoolYearForm();
  renderSchoolYearGrid();
  window.clearTimeout(schoolYearSaveTimer);
  schoolYearSaveTimer = window.setTimeout(() => {
    persistSchoolYearSettings();
  }, 350);
}

async function openSchoolYearSettings() {
  closeUserMenu();
  closeModal();
  closeAutoSchedule();
  closeEmailEvaluator();
  if (typeof closeLessonBuilder === "function") closeLessonBuilder();
  if (typeof closeApplyPlan === "function") closeApplyPlan();
  fillHolidayRegions();
  const modal = $("school-year-modal");
  if (!modal) return;
  lastFocused = document.activeElement;
  modal.hidden = false;
  document.body.classList.add("modal-open");
  schoolYearError("");
  schoolYearStatus("");
  $("school-year-grid").innerHTML = `<p class="empty">Loading…</p>`;
  try {
    const [year, exceptions] = await Promise.all([
      api("/settings/school-year"),
      api("/exceptions/dates"),
    ]);
    state.schoolYear = year;
    schoolYearEditor.start_date = year.start_date;
    schoolYearEditor.end_date = year.end_date;
    schoolYearEditor.weekdays = year.weekdays;
    schoolYearEditor.exceptionDates = new Set(exceptions.dates || []);
    $("school-year-start").value = year.start_date;
    $("school-year-end").value = year.end_date;
    for (const box of $("school-year-weekdays").querySelectorAll("input")) {
      box.checked = year.weekdays.includes(Number(box.value));
    }
    renderSchoolYearGrid();
    $("school-year-start").focus();
  } catch (error) {
    schoolYearError(error.message);
  }
}

function closeSchoolYearSettings() {
  const modal = $("school-year-modal");
  if (!modal || modal.hidden) return;
  window.clearTimeout(schoolYearSaveTimer);
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  Promise.all([loadExceptions(), loadYears(), loadSchoolYearSettings()])
    .then(() => {
      if (routeName() === "settings") render();
    })
    .catch(() => {});
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus();
  }
}

async function toggleSchoolYearDay(iso) {
  if (schoolYearEditor.pending.has(iso)) return;
  const wasExcepted = schoolYearEditor.exceptionDates.has(iso);
  if (wasExcepted) schoolYearEditor.exceptionDates.delete(iso);
  else schoolYearEditor.exceptionDates.add(iso);
  paintSchoolYearDay(iso);
  schoolYearEditor.pending.add(iso);
  schoolYearError("");
  try {
    const result = await api("/exceptions/toggle", {
      method: "POST",
      body: JSON.stringify({ date: iso }),
    });
    schoolYearEditor.exceptionDates = new Set(result.dates || []);
    paintSchoolYearDay(iso);
  } catch (error) {
    if (wasExcepted) schoolYearEditor.exceptionDates.add(iso);
    else schoolYearEditor.exceptionDates.delete(iso);
    paintSchoolYearDay(iso);
    schoolYearError(error.message);
  } finally {
    schoolYearEditor.pending.delete(iso);
  }
}

async function applyHolidays() {
  const select = $("school-year-holiday-region");
  if (!select || !schoolYearEditor.start_date || !schoolYearEditor.end_date) return;
  const [country, subdiv] = select.value.split(":");
  const startYear = parseISODate(schoolYearEditor.start_date).getUTCFullYear();
  const endYear = parseISODate(schoolYearEditor.end_date).getUTCFullYear();
  const button = document.querySelector("[data-action='apply-holidays']");
  if (button) button.disabled = true;
  schoolYearError("");
  schoolYearStatus("Applying holidays…");
  let imported = 0;
  let skipped = 0;
  let dates = [...schoolYearEditor.exceptionDates];
  try {
    for (let year = startYear; year <= endYear; year += 1) {
      const result = await api("/exceptions/import-holidays", {
        method: "POST",
        body: JSON.stringify({
          country,
          subdiv: subdiv || null,
          year,
        }),
      });
      imported += result.imported;
      skipped += result.skipped;
      dates = result.dates || dates;
    }
    schoolYearEditor.exceptionDates = new Set(dates);
    renderSchoolYearGrid();
    const added = imported === 1 ? "1 holiday" : `${imported} holidays`;
    const extra = skipped ? ` (${skipped} already on the calendar)` : "";
    schoolYearStatus(`Added ${added}${extra}.`);
  } catch (error) {
    schoolYearError(error.message);
    schoolYearStatus("");
  } finally {
    if (button) button.disabled = false;
  }
}

function handleSchoolYearClick(event) {
  if (event.target.closest("[data-action='close-school-year']")) {
    closeSchoolYearSettings();
    return;
  }
  if (event.target.closest("[data-action='apply-holidays']")) {
    applyHolidays();
    return;
  }
  const day = event.target.closest("[data-action='toggle-school-day']");
  if (day?.dataset.date) {
    toggleSchoolYearDay(day.dataset.date);
  }
}

function handleSchoolYearChange(event) {
  if (
    event.target.closest("#school-year-start") ||
    event.target.closest("#school-year-end") ||
    event.target.closest("#school-year-weekdays")
  ) {
    scheduleSchoolYearSave();
  }
}

function kidAssignmentId() {
  const [, id] = routeSegments();
  const number = Number(id);
  return Number.isInteger(number) && number > 0 ? number : null;
}

function addDaysISO(iso, days) {
  return addDays(iso, days);
}

async function loadKidWorkspace() {
  const me = await api("/auth/me");
  state.sessionUser = me;
  const label = me.display_name || "Student";
  $("household-label").textContent = label;
  $("user-avatar").textContent = householdInitial(label);
  const studentId = me.student_id;
  if (!studentId) {
    state.kidWork = [];
    return;
  }
  const start = addDaysISO(todayISO(), -14);
  const end = addDaysISO(todayISO(), 60);
  const calendar = await api(
    `/students/${studentId}/assignments?start_date=${start}&end_date=${end}`
  );
  state.kidWork = calendar.assignments || [];
  const assignmentId = kidAssignmentId();
  if (assignmentId) {
    await loadHomeworkSession(assignmentId);
  }
}

function renderMyWork() {
  const assignmentId = kidAssignmentId();
  if (assignmentId) {
    const item = state.kidWork.find((row) => row.id === assignmentId) || detail.item;
    return renderKidAssignment(item, assignmentId);
  }
  const today = todayISO();
  const upcoming = [...state.kidWork].sort((a, b) =>
    a.scheduled_date < b.scheduled_date ? -1 : a.scheduled_date > b.scheduled_date ? 1 : a.id - b.id
  );
  const todayItems = upcoming.filter((item) => item.scheduled_date === today);
  const later = upcoming.filter((item) => item.scheduled_date > today);
  const earlier = upcoming.filter((item) => item.scheduled_date < today);
  const section = (title, items) =>
    !items.length
      ? ""
      : `<section class="card"><h2>${escapeHtml(title)}</h2><div class="kid-work-list">${items
          .map((item) => kidWorkRow(item))
          .join("")}</div></section>`;
  if (!upcoming.length) {
    return `<section class="card"><h2>My work</h2><p class="empty">Nothing on your list yet. A parent will add assignments here.</p></section>`;
  }
  return `${section("Today", todayItems)}${section("Coming up", later)}${section("Earlier", earlier)}`;
}

function kidWorkRow(item) {
  const done = isCompleteStatus(item.status);
  return `
    <div class="checklist-item${done ? " is-complete" : ""}" data-checklist-id="${item.id}">
      <input type="checkbox" data-action="toggle-complete" data-id="${item.id}"
             ${done ? "checked" : ""} aria-label="Mark ${escapeHtml(item.title)} complete">
      <button type="button" class="checklist-copy" data-action="open-kid-work" data-id="${item.id}">
        <span class="checklist-title">${escapeHtml(item.title)}</span>
        <span class="meta">${escapeHtml(MEDIUM_DATE.format(parseISODate(item.scheduled_date)))} · ${escapeHtml(humanize(item.status))}</span>
      </button>
      <span class="celebrate-burst" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>
    </div>`;
}

function renderKidAssignment(item, assignmentId) {
  if (!item) {
    return `<section class="card"><p class="empty">Loading assignment…</p>
      <p><a href="#/my-work">Back to my work</a></p></section>`;
  }
  const session = state.homework.session;
  const locked = Boolean(session && session.locked);
  const redirected = session && session.status === "redirected";
  const messages = (session && session.messages) || [];
  const notes = item.notes
    ? `<section class="detail-section"><h3>Notes</h3><p>${escapeHtml(item.notes)}</p></section>`
    : "";
  const thread = messages
    .map(
      (message) =>
        `<div class="homework-bubble is-${escapeHtml(message.role)}">${escapeHtml(message.content)}</div>`
    )
    .join("");
  const composer =
    locked || redirected
      ? `<p class="banner">Please ask a parent for help. Homework help is paused on this assignment.</p>`
      : `<form class="login-form homework-chat" data-form="homework-help">
          <label>Ask for a hint or an example
            <textarea name="content" required maxlength="4000" rows="3" placeholder="What part is tricky?"></textarea>
          </label>
          <button type="submit"${state.homework.busy ? " disabled" : ""}>Send</button>
        </form>`;
  const done = isCompleteStatus(item.status);
  const start =
    session
      ? ""
      : `<button type="button" data-action="start-homework-help" data-id="${assignmentId}">Get homework help</button>`;
  return `
    <p><a href="#/my-work">Back to my work</a></p>
    <section class="card">
      <h2>${escapeHtml(item.title)}</h2>
      <p class="meta">${escapeHtml(FULL_DATE.format(parseISODate(item.scheduled_date)))} · ${escapeHtml(humanize(item.status))}</p>
      <div class="checklist-item${done ? " is-complete" : ""}" data-checklist-id="${assignmentId}">
        <input type="checkbox" data-action="toggle-complete" data-id="${assignmentId}"
               ${done ? "checked" : ""} aria-label="Mark ${escapeHtml(item.title)} complete">
        <span class="checklist-title">Done</span>
        <span class="celebrate-burst" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>
      </div>
      ${notes}
    </section>
    <section class="card homework-chat">
      <h2>Homework help</h2>
      <p class="muted">You'll get hints and similar examples — not the complete answer.</p>
      ${start}
      <div class="homework-thread">${thread}</div>
      ${session ? composer : ""}
    </section>`;
}

async function loadHomeworkSession(assignmentId) {
  state.homework.assignmentId = assignmentId;
  try {
    const sessions = await api(`/homework-help/sessions?assignment_id=${assignmentId}`);
    state.homework.session = sessions[0] || null;
  } catch {
    state.homework.session = null;
  }
}

async function startHomeworkHelp(assignmentId) {
  flash("");
  try {
    state.homework.session = await api("/homework-help/sessions", {
      method: "POST",
      body: JSON.stringify({ assignment_id: assignmentId }),
    });
    render();
  } catch (error) {
    flash(error.message, true);
  }
}

async function sendHomeworkHelp(content) {
  const session = state.homework.session;
  if (!session) return;
  state.homework.busy = true;
  render();
  try {
    state.homework.session = await api(`/homework-help/sessions/${session.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  } catch (error) {
    flash(error.message, true);
  } finally {
    state.homework.busy = false;
    render();
  }
}

const VIEWS = {
  dashboard: renderDashboard,
  assignments: renderAssignments,
  students: renderStudents,
  curricula: renderCurricula,
  portfolios: renderPortfolios,
  settings: renderSettings,
  "my-work": renderMyWork,
};

// Views render synchronously from cached state; anything that has to fetch on
// entry hangs its loader here and patches its own container afterwards.
const ACTIVATORS = {
  dashboard: loadDashboardStats,
  assignments: loadAssignmentsPage,
  students: loadStudentDashboard,
  portfolios: loadPortfolioReport,
};

function render() {
  const route = routeName();
  destroyDashboardCharts();
  const student =
    route === "students"
      ? state.students.find((item) => item.id === selectedDashboardStudentId())
      : null;
  const kidItem =
    route === "my-work" && kidAssignmentId()
      ? state.kidWork.find((item) => item.id === kidAssignmentId())
      : null;
  $("page-title").textContent = kidItem
    ? kidItem.title
    : student
    ? `${firstName(student.name)}'s day`
    : TITLES[route];
  document.querySelectorAll(".nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });
  const profile = $("user-profile");
  if (profile) {
    profile.classList.toggle("active", route === "settings");
  }
  $("view").innerHTML = VIEWS[route]();
  ACTIVATORS[route]?.();
  syncSessionChrome();
}

function isUserMenuOpen() {
  const menu = $("user-menu");
  return Boolean(menu) && !menu.hidden;
}

function closeUserMenu() {
  const menu = $("user-menu");
  const button = $("user-profile");
  if (!menu || menu.hidden) return;
  menu.hidden = true;
  button?.setAttribute("aria-expanded", "false");
}

function toggleUserMenu() {
  const menu = $("user-menu");
  const button = $("user-profile");
  if (!menu || !button) return;
  const open = menu.hidden;
  menu.hidden = !open;
  button.setAttribute("aria-expanded", String(open));
}

function handleUserMenuClick(event) {
  if (event.target.closest("[data-action='open-school-year-settings']")) {
    closeUserMenu();
    openSchoolYearSettings();
    return;
  }
  if (event.target.closest("[data-action='toggle-user-menu']")) {
    toggleUserMenu();
    return;
  }
  if (event.target.closest("[data-action='logout']")) {
    closeUserMenu();
    logout();
    return;
  }
  if (event.target.closest("[data-action='switch-user']")) {
    closeUserMenu();
    openSwitchUser();
    return;
  }
  if (event.target.closest("#user-menu a") || !event.target.closest("#user-menu")) {
    closeUserMenu();
  }
}

function showCalendarFor(studentId) {
  state.calendarStudentId = studentId;
  state.currentAnchorDate = todayISO();
  window.location.hash = "#/assignments";
}

async function handleClick(event) {
  if (event.target.closest("[data-action='toggle-complete']")) return;
  if (event.target.closest('[data-control="attendance"]')) return;

  const tile = event.target.closest("[data-assignment-id]");
  if (tile) {
    if (Date.now() < ignoreAssignmentClickUntil) return;
    await openAssignment(Number(tile.dataset.assignmentId));
    return;
  }

  const control = event.target.closest("[data-action]");
  if (!control) return;

  switch (control.dataset.action) {
    case "open-kid-work":
      window.location.hash = `#/my-work/${control.dataset.id}`;
      break;
    case "start-homework-help":
      await startHomeworkHelp(Number(control.dataset.id));
      break;
    case "pick-student-login":
      pickStudentLogin(Number(control.dataset.studentId), control.textContent);
      break;
    case "switch-to-user":
      await chooseSwitchTarget(control.dataset.kind, control.dataset.studentId);
      break;
    case "close-switch-user":
      closeSwitchUser();
      break;
    case "toggle-notifications":
      toggleNotifications();
      break;
    case "mark-notifications-read":
      await markNotificationsRead();
      break;
    case "open-notification":
      await openNotification(Number(control.dataset.id));
      break;
    case "unlock-homework-help":
      await unlockHomeworkHelp(Number(control.dataset.id));
      break;
    case "set-student-pin":
      await setStudentPin(Number(control.dataset.studentId));
      break;
    case "clear-student-pin":
      await clearStudentPin(Number(control.dataset.studentId));
      break;
    case "period":
      state.currentPeriod = control.dataset.period;
      render();
      break;
    case "prev":
    case "next":
      state.currentAnchorDate = shiftAnchor(
        anchorDate(),
        state.currentPeriod,
        control.dataset.action === "next" ? 1 : -1
      );
      loadCalendar();
      break;
    case "today":
      state.currentAnchorDate = todayISO();
      loadCalendar();
      break;
    case "toggle-evidence-inbox":
      toggleEvidenceInbox();
      break;
    case "student-calendar":
      showCalendarFor(Number(control.dataset.studentId));
      break;
    case "spark-choice": {
      const card = control.closest(".spark-card");
      markSparkSolved(card, control.dataset.value === card?.dataset.answer);
      break;
    }
    case "spark-hint": {
      const card = control.closest(".spark-card");
      const hint = card?.querySelector(".spark-hint");
      if (hint) hint.hidden = false;
      control.hidden = true;
      break;
    }
    case "spark-reveal":
      markSparkSolved(control.closest(".spark-card"), true);
      break;
    case "dash-cal-prev":
      shiftDashboardMonth(-1);
      break;
    case "dash-cal-next":
      shiftDashboardMonth(1);
      break;
    case "reset-exception-colors":
      await resetExceptionColors();
      break;
    case "set-household-icon":
      await setHouseholdIcon(control.dataset.icon);
      break;
    case "use-device-timezone":
      await useDeviceTimeZone();
      break;
    case "edit-student":
      studentEditor.id = Number(control.dataset.studentId);
      render();
      break;
    case "cancel-edit-student":
      studentEditor.id = null;
      render();
      break;
    case "delete-student":
      await deleteStudent(Number(control.dataset.studentId));
      break;
    case "toggle-assignment-form":
      toggleAssignmentForm();
      break;
    case "auto-schedule":
      openAutoSchedule(
        control.dataset.curriculumId ? Number(control.dataset.curriculumId) : undefined
      );
      break;
    case "open-recalibrate":
      await openRecalibrate(control.dataset.studentId || selectedStudentId());
      break;
    case "print-weekly-checklist":
      await printWeeklyChecklist(
        control.dataset.studentId || selectedStudentId(),
        control.dataset.startDate
      );
      break;
    case "lookup-isbn": {
      const form = control.closest('form[data-form="curriculum"]');
      if (form) await lookupIsbn(form);
      break;
    }
    case "curriculum-filter":
      state.curriculumFilter = control.dataset.filter || "unscheduled";
      render();
      break;
    case "catalog-kind":
      state.catalogKind = control.dataset.kind === "plans" ? "plans" : "books";
      render();
      break;
    case "create-lesson-plan":
      openLessonBuilderNew();
      break;
    case "edit-lesson-plan":
      await openLessonBuilderEdit(Number(control.dataset.planId));
      break;
    case "apply-lesson-plan":
      openApplyPlan(Number(control.dataset.planId));
      break;
    case "archive-lesson-plan":
      await archiveLessonPlan(Number(control.dataset.planId));
      break;
    case "delete-lesson-plan":
      await deleteLessonPlan(Number(control.dataset.planId));
      break;
    case "import-curriculum-csv":
      if (catalogKind() !== "plans") break;
      $("curriculum-csv-input").click();
      break;
    case "import-curriculum-pdf":
      if (catalogKind() !== "plans") break;
      $("curriculum-pdf-input")?.click();
      break;
    case "download-paper-template":
      await downloadPaperTemplate();
      break;
    case "import-paper":
      $("paper-import-input")?.click();
      break;
    case "settings-panel":
      window.location.hash = `#/settings/${control.dataset.panel}`;
      break;
    case "toggle-theme":
      toggleTheme();
      break;
    case "generate-invite":
      await generateInviteKey();
      break;
    case "generate-capture-token":
      await generateCaptureToken();
      break;
    case "revoke-capture-token":
      await revokeCaptureToken();
      break;
    case "copy-capture-token":
      await copyCaptureToken();
      break;
    case "unschedule-curriculum":
      await unscheduleCurriculum(Number(control.dataset.curriculumId));
      break;
    case "delete-curriculum":
      await deleteCurriculum(Number(control.dataset.curriculumId));
      break;
    case "print-portfolio":
      window.print();
      break;
    case "email-evaluator":
      openEmailEvaluator();
      break;
    case "logout":
      logout();
      break;
    default:
      break;
  }
}

function handleChange(event) {
  const complete = event.target.closest("[data-action='toggle-complete']");
  if (complete) {
    toggleAssignmentComplete(Number(complete.dataset.id), complete.checked);
    return;
  }
  const exceptionColorInput = event.target.closest("[data-action='exception-color']");
  if (exceptionColorInput) {
    saveExceptionColor(exceptionColorInput.dataset.kind, exceptionColorInput.value);
    return;
  }
  const attendance = event.target.closest('[data-control="attendance"]');
  if (attendance) {
    saveAttendance(Number(attendance.dataset.studentId), attendance.dataset.date, attendance.value);
    return;
  }
  const select = event.target.closest('[data-control="student"]');
  if (select) {
    state.calendarStudentId = select.value === ALL_STUDENTS ? ALL_STUDENTS : Number(select.value);
    render();
    return;
  }
  const portfolioStudent = event.target.closest('[data-control="portfolio-student"]');
  if (portfolioStudent) {
    state.portfolio.studentId = Number(portfolioStudent.value);
    render();
    return;
  }
  const portfolioYear = event.target.closest('[data-control="portfolio-year"]');
  if (portfolioYear) {
    state.portfolio.schoolYearId = Number(portfolioYear.value);
    render();
    return;
  }
  const portfolioType = event.target.closest('[data-control="portfolio-type"]');
  if (portfolioType) {
    state.portfolio.reportType = portfolioType.value;
    if (portfolioType.value === "custom") ensurePortfolioCustomDefaults();
    render();
    return;
  }
  const allStudents = event.target.closest('[data-control="portfolio-all-students"]');
  if (allStudents) {
    state.portfolio.custom.allStudents = allStudents.checked;
    state.portfolio.custom.studentIds = allStudents.checked
      ? state.students.map((student) => student.id)
      : [];
    render();
    return;
  }
  const customStudent = event.target.closest('[data-control="portfolio-custom-student"]');
  if (customStudent) {
    const id = Number(customStudent.value);
    const ids = new Set(state.portfolio.custom.studentIds);
    if (customStudent.checked) ids.add(id);
    else ids.delete(id);
    state.portfolio.custom.studentIds = [...ids];
    state.portfolio.custom.allStudents =
      state.students.length > 0 && state.students.every((student) => ids.has(student.id));
    render();
    return;
  }
  const startDate = event.target.closest('[data-control="portfolio-start-date"]');
  if (startDate) {
    state.portfolio.custom.startDate = startDate.value;
    loadPortfolioReport();
    return;
  }
  const endDate = event.target.closest('[data-control="portfolio-end-date"]');
  if (endDate) {
    state.portfolio.custom.endDate = endDate.value;
    loadPortfolioReport();
    return;
  }
  const moduleBox = event.target.closest('[data-control="portfolio-module"]');
  if (moduleBox) {
    const key = moduleBox.dataset.module;
    state.portfolio.custom[key] = moduleBox.checked;
    if (key === "includeBooks") {
      if (moduleBox.checked) {
        state.portfolio.custom.includeBooksCompleted = true;
        state.portfolio.custom.includeBooksInProgress = true;
        state.portfolio.custom.includeBooksIncomplete = true;
      }
    } else if (
      key === "includeBooksCompleted" ||
      key === "includeBooksInProgress" ||
      key === "includeBooksIncomplete"
    ) {
      const custom = state.portfolio.custom;
      custom.includeBooks =
        custom.includeBooksCompleted ||
        custom.includeBooksInProgress ||
        custom.includeBooksIncomplete;
    }
    render();
    return;
  }
  if (event.target.matches('form[data-form="curriculum"] [name="isbn"], form[data-form="curriculum"] [name="sku"]')) {
    syncCurriculumTitleRequired(event.target.form);
  }
}

function syncCurriculumTitleRequired(form) {
  if (!form) return;
  const isbn = (form.elements.isbn?.value || "").trim();
  const sku = (form.elements.sku?.value || "").trim();
  // Title is optional only when a lookup ISBN will be resolved by providers.
  // A custom SKU is saved by hand, so the title still has to be typed.
  form.elements.title.required = Boolean(sku) || !isbn;
}

function setIsbnStatus(form, message) {
  const status = form.querySelector("[data-isbn-status]");
  if (!status) return;
  status.hidden = !message;
  status.textContent = message || "";
}

async function lookupIsbn(form) {
  const isbn = (form.elements.isbn.value || "").trim();
  if (!isbn) {
    flash("Enter an ISBN or scan a barcode first.", true);
    form.elements.isbn.focus();
    return;
  }

  const button = form.querySelector('[data-action="lookup-isbn"]');
  button.disabled = true;
  try {
    const result = await api("/catalog/lookup-isbn", {
      method: "POST",
      skipOutbox: true,
      body: JSON.stringify({ isbn }),
    });
    form.elements.isbn.value = result.isbn13;
    form.elements.title.value = result.title;
    form.elements.publisher.value = result.publisher || "";
    form.elements.description.value = result.description || "";
    form.elements.source_type.value = "barcode";
    if (form.elements.sku) {
      form.elements.sku.value = "";
    }
    syncCurriculumTitleRequired(form);
    const pages =
      result.page_count != null
        ? `${result.page_count} pages · ISBN ${result.isbn13}`
        : `ISBN ${result.isbn13} (page count unknown)`;
    setIsbnStatus(form, pages);
    flash(`Found “${result.title}”.`);
  } catch (error) {
    if (error.status === 404 && form.elements.sku) {
      form.elements.sku.value = isbn;
      form.elements.source_type.value = "barcode";
      syncCurriculumTitleRequired(form);
      setIsbnStatus(
        form,
        "Not found in the catalog. The barcode was copied into ISBN / Custom SKU."
      );
      flash("No match online. Add a title and save to keep this barcode for next time.", true);
      form.elements.title.focus();
      return;
    }
    setIsbnStatus(form, "");
    flash(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadHealth() {
  const pill = $("health-pill");
  if (!pill || (typeof navigator !== "undefined" && navigator.onLine === false)) return;
  try {
    const health = await api("/health", { skipAuth: true });
    state.devMode = Boolean(health.dev_mode);
    pill.textContent = `API ${health.status} · DB ${health.database}`;
    pill.className = "pill ok";
  } catch {
    pill.textContent = "API unavailable";
    pill.className = "pill bad";
  }
}

function offlinePillElement() {
  let el = $("offline-pill");
  if (el) return el;
  el = document.createElement("span");
  el.id = "offline-pill";
  el.className = "pill offline";
  el.setAttribute("role", "status");
  el.hidden = true;
  el.innerHTML = `
    <svg class="offline-pill-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path fill="currentColor" d="M12.4 10.1A3.4 3.4 0 0 0 9.1 5.2 4.1 4.1 0 0 0 1.9 7.4 2.7 2.7 0 0 0 2.9 12.6h8.4a2.5 2.5 0 0 0 1.1-2.5z"/>
      <path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" d="M2.2 13.6 13.8 2.4"/>
    </svg>
    Offline`;
  const health = $("health-pill");
  if (health) {
    let cluster = health.closest(".topbar-status");
    if (!cluster) {
      cluster = document.createElement("div");
      cluster.className = "topbar-status";
      health.replaceWith(cluster);
      cluster.append(el, health);
    } else {
      health.before(el);
    }
  } else {
    document.querySelector(".topbar")?.appendChild(el);
  }
  return el;
}

function syncOfflineIndicator() {
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;
  const pill = offlinePillElement();
  pill.hidden = !offline;
  const health = $("health-pill");
  if (health) health.hidden = offline;
  document.documentElement.toggleAttribute("data-offline", offline);
}

function initOfflineIndicator() {
  window.addEventListener("online", () => {
    syncOfflineIndicator();
    registerOutboxSync();
    loadHealth();
  });
  window.addEventListener("offline", () => {
    syncOfflineIndicator();
  });
  syncOfflineIndicator();
}

function formValues(form) {
  return Object.fromEntries(new FormData(form).entries());
}

async function handleSubmit(event) {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  event.preventDefault();
  flash("");
  const kind = form.dataset.form;
  const data = formValues(form);
  try {
    if (kind === "homework-help") {
      await sendHomeworkHelp(String(data.content || "").trim());
      return;
    }
    if (kind === "switch-user") {
      await submitSwitchUser(form);
      return;
    }
    if (kind === "spark-guess") {
      const card = form.closest(".spark-card");
      const guess = String(data.guess || "").trim();
      const answer = card?.dataset.answer || "";
      markSparkSolved(card, guess.toLowerCase() === answer.toLowerCase());
      return;
    }
    if (kind === "assignment") {
      // Assignments live outside the cached state the other forms refresh, so
      // this one repaints the calendar instead of the whole view.
      await createAssignment(data);
      return;
    }
    let result;
    if (kind === "student") {
      const payload = {
        name: data.name,
        grade: emptyToNull(data.grade),
        notes: emptyToNull(data.notes),
        color_hex: data.color_hex || (data.id ? DEFAULT_STUDENT_COLOR : nextStudentColor()),
      };
      if (data.id) {
        result = await api(`/students/${data.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        result = await api("/students", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      studentEditor.id = null;
    } else if (kind === "household") {
      result = await api("/household", {
        method: "PATCH",
        body: JSON.stringify({ name: String(data.name || "").trim() }),
      });
      if (!isOfflineQueued(result) && result?.name) {
        paintHouseholdChrome(result);
      }
    } else if (kind === "curriculum") {
      const isbn = emptyToNull(data.isbn);
      const sku = emptyToNull(data.sku) || isbn;
      result = await api("/curricula", {
        method: "POST",
        body: JSON.stringify({
          title: emptyToNull(data.title),
          publisher: emptyToNull(data.publisher),
          subject: emptyToNull(data.subject),
          description: emptyToNull(data.description),
          source_type: data.source_type,
          sku,
        }),
      });
    } else if (kind === "year") {
      result = await api("/school-years", {
        method: "POST",
        body: JSON.stringify({
          name: data.name,
          start_date: data.start_date,
          end_date: data.end_date,
        }),
      });
    } else if (kind === "enrollment") {
      result = await api("/enrollments", {
        method: "POST",
        body: JSON.stringify({
          student_id: Number(data.student_id),
          curriculum_id: Number(data.curriculum_id),
          school_year_id: Number(data.school_year_id),
          start_date: emptyToNull(data.start_date),
          end_date: emptyToNull(data.end_date),
        }),
      });
    } else if (kind === "exception") {
      result = await api("/exceptions", {
        method: "POST",
        body: JSON.stringify({
          kind: data.kind,
          title: data.title,
          student_id: data.student_id ? Number(data.student_id) : null,
          start_date: data.start_date,
          end_date: data.end_date,
          notes: emptyToNull(data.notes),
        }),
      });
    }
    if (isOfflineQueued(result)) return;
    await refresh();
    render();
    flash("Saved.");
  } catch (error) {
    flash(error.message, true);
  }
}

/* ---- First-time setup wizard ---- */

const DEFAULT_HOUSEHOLD_NAME = "Default household";
const onboarding = { step: 1, yearPosted: false, householdOnly: false };
const WIZARD_YEAR_STEP = 3;
const WIZARD_STUDENT_STEP = 4;

function needsOnboarding() {
  return state.students.length === 0 && state.years.length === 0;
}

function householdNeedsName(household = state.household) {
  const name = String(household?.name || "").trim();
  return !name || name === DEFAULT_HOUSEHOLD_NAME;
}

function isOnboardingOpen() {
  const wizard = $("onboarding-wizard");
  return Boolean(wizard) && !wizard.hidden;
}

function wizardError(message) {
  const el = $("wizard-error");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function defaultSchoolYearFields() {
  const now = new Date();
  const calendarYear = now.getUTCFullYear();
  const startYear = now.getUTCMonth() >= 6 ? calendarYear : calendarYear - 1;
  return {
    name: `${startYear}-${startYear + 1}`,
    start_date: `${startYear}-08-01`,
    end_date: `${startYear + 1}-06-30`,
  };
}

function prefillWizardYear() {
  const form = $("wizard-year-form");
  if (!form) return;
  const defaults = defaultSchoolYearFields();
  if (!form.elements.name.value) form.elements.name.value = defaults.name;
  if (!form.elements.start_date.value) form.elements.start_date.value = defaults.start_date;
  if (!form.elements.end_date.value) form.elements.end_date.value = defaults.end_date;
}

function prefillWizardHousehold() {
  const form = $("wizard-household-form");
  if (!form || form.elements.name.value) return;
  const current = String(state.household?.name || "").trim();
  if (current && current !== DEFAULT_HOUSEHOLD_NAME) {
    form.elements.name.value = current;
  }
}

function showWizardStep(step) {
  const wizard = $("onboarding-wizard");
  if (!wizard) return;
  onboarding.step = step;
  wizard.querySelectorAll(".wizard-step").forEach((panel) => {
    panel.classList.toggle("is-active", Number(panel.dataset.wizardStep) === step);
  });
  wizard.querySelectorAll(".wizard-dot").forEach((dot) => {
    const n = Number(dot.dataset.wizardDot);
    dot.classList.toggle("is-active", n === step);
  });
  const title = wizard.querySelector(`.wizard-step.is-active h2`);
  const card = wizard.querySelector(".wizard-card");
  if (title && card) card.setAttribute("aria-labelledby", title.id);
  wizardError("");
  syncWizardHouseholdMode();
  const focusTarget = wizard.querySelector(
    ".wizard-step.is-active input, .wizard-step.is-active button"
  );
  focusTarget?.focus();
}

function syncWizardHouseholdMode() {
  const wizard = $("onboarding-wizard");
  const form = $("wizard-household-form");
  if (!wizard || !form) return;
  const only = onboarding.householdOnly;
  wizard.classList.toggle("household-only", only);
  const meta = form.querySelector(".wizard-head .meta");
  const submit = form.querySelector('button[type="submit"]');
  const back = form.querySelector('[data-action="wizard-back"]');
  if (meta) meta.textContent = only ? "Getting started" : "Step 2 of 4";
  if (submit) submit.textContent = only ? "Save" : "Next";
  if (back) back.hidden = only;
}

function setOnboardingLock(locked) {
  const shell = document.querySelector(".app-shell");
  if (shell) {
    if (locked) shell.setAttribute("inert", "");
    else shell.removeAttribute("inert");
  }
  document.body.classList.toggle("modal-open", locked);
}

function openOnboardingWizard() {
  const wizard = $("onboarding-wizard");
  if (!wizard) return;
  onboarding.householdOnly = false;
  wizard.classList.remove("is-fading");
  wizard.hidden = false;
  setOnboardingLock(true);
  prefillWizardHousehold();
  prefillWizardYear();
  showWizardStep(1);
}

function openHouseholdNameWizard() {
  const wizard = $("onboarding-wizard");
  if (!wizard) return;
  onboarding.householdOnly = true;
  wizard.classList.remove("is-fading");
  wizard.hidden = false;
  setOnboardingLock(true);
  prefillWizardHousehold();
  showWizardStep(2);
}

function fadeOutOnboardingWizard() {
  return new Promise((resolve) => {
    const wizard = $("onboarding-wizard");
    if (!wizard || wizard.hidden) {
      resolve();
      return;
    }
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      wizard.hidden = true;
      wizard.classList.remove("is-fading", "household-only");
      setOnboardingLock(false);
      resolve();
    };
    const onEnd = (event) => {
      if (event.target !== wizard) return;
      wizard.removeEventListener("transitionend", onEnd);
      finish();
    };
    wizard.addEventListener("transitionend", onEnd);
    wizard.classList.add("is-fading");
    window.setTimeout(finish, 450);
  });
}

async function submitWizardHousehold(form) {
  wizardError("");
  const name = String(formValues(form).name || "").trim();
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const zone = deviceTimeZone();
    const result = await api("/household", {
      method: "PATCH",
      body: JSON.stringify(zone ? { name, timezone: zone } : { name }),
    });
    if (!isOfflineQueued(result) && result?.name) {
      paintHouseholdChrome(result);
    } else {
      paintHouseholdChrome({ ...(state.household || {}), name });
    }
    if (onboarding.householdOnly) {
      onboarding.householdOnly = false;
      await fadeOutOnboardingWizard();
      render();
      return;
    }
    showWizardStep(WIZARD_YEAR_STEP);
  } catch (error) {
    wizardError(error.message);
  } finally {
    button.disabled = false;
  }
}

async function submitWizardYear(form) {
  wizardError("");
  const data = formValues(form);
  if (onboarding.yearPosted) {
    showWizardStep(WIZARD_STUDENT_STEP);
    return;
  }
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await api("/school-years", {
      method: "POST",
      body: JSON.stringify({
        name: data.name,
        start_date: data.start_date,
        end_date: data.end_date,
      }),
    });
    onboarding.yearPosted = true;
    showWizardStep(WIZARD_STUDENT_STEP);
  } catch (error) {
    wizardError(error.message);
  } finally {
    button.disabled = false;
  }
}

async function finishOnboarding(form) {
  wizardError("");
  const data = formValues(form);
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const created = await api("/students", {
      method: "POST",
      body: JSON.stringify({
        name: data.name,
        grade: emptyToNull(data.grade),
      }),
    });
    if (isOfflineQueued(created)) {
      button.disabled = false;
      await fadeOutOnboardingWizard();
      if (routeName() === "curricula") {
        render();
      } else {
        window.location.hash = "#/curricula";
      }
      return;
    }
  } catch (error) {
    wizardError(error.message);
    button.disabled = false;
    return;
  }
  try {
    await Promise.all([fadeOutOnboardingWizard(), refresh()]);
  } catch (error) {
    flash(error.message, true);
  }
  if (routeName() === "curricula") {
    render();
  } else {
    window.location.hash = "#/curricula";
  }
}

function handleWizardClick(event) {
  const control = event.target.closest("[data-action]");
  if (!control) return;
  if (control.dataset.action === "wizard-next" && onboarding.step === 1) {
    showWizardStep(2);
  } else if (control.dataset.action === "wizard-back") {
    showWizardStep(Math.max(1, onboarding.step - 1));
  }
}

function handleWizardSubmit(event) {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  event.preventDefault();
  if (form.dataset.form === "wizard-household") {
    submitWizardHousehold(form);
  } else if (form.dataset.form === "wizard-year") {
    submitWizardYear(form);
  } else if (form.dataset.form === "wizard-student") {
    finishOnboarding(form);
  }
}

/* ---- Authentication ---- */

function getAuthToken() {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
}

function setAuthToken(token) {
  try {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  } catch {
    /* private mode */
  }
}

function clearAuthToken() {
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch {
    /* private mode */
  }
}

function decodeJwtPayload(token) {
  try {
    const parts = String(token || "").split(".");
    if (parts.length < 2) return null;
    const padded = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = "=".repeat((4 - (padded.length % 4)) % 4);
    return JSON.parse(atob(padded + pad));
  } catch {
    return null;
  }
}

function hasValidToken() {
  const token = getAuthToken();
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  if (!payload) {
    clearAuthToken();
    return false;
  }
  if (payload.exp && payload.exp * 1000 <= Date.now()) {
    clearAuthToken();
    return false;
  }
  return true;
}

function tokenIsDemo() {
  const payload = decodeJwtPayload(getAuthToken() || "");
  if (!payload) return false;
  return payload.tenant_uuid === "DEMO" || payload.demo === true;
}

function currentUserIsChild() {
  const payload = decodeJwtPayload(getAuthToken() || "");
  return Boolean(payload && payload.role === "child");
}

function currentUserIsAdmin() {
  if (tokenIsDemo()) return false;
  if (state.devMode) return true;
  const payload = decodeJwtPayload(getAuthToken() || "");
  return Boolean(payload && payload.is_admin === true);
}

function syncSessionChrome() {
  const badge = $("demo-badge");
  if (badge) {
    const isDemo = tokenIsDemo();
    badge.hidden = !isDemo;
    badge.style.display = isDemo ? "inline-block" : "none";
  }
  const adminLink = $("admin-menu-item");
  if (adminLink) adminLink.hidden = !currentUserIsAdmin() || currentUserIsChild();
  document.documentElement.setAttribute(
    "data-role",
    currentUserIsChild() ? "child" : "parent"
  );
  const kidLink = document.querySelector(".nav-kid");
  if (kidLink) kidLink.hidden = !currentUserIsChild();
}

function canUseApp() {
  return state.devMode || hasValidToken();
}

function isLoginOpen() {
  return document.documentElement.getAttribute("data-auth") === "required";
}

function loginError(message) {
  const el = $("login-error");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function setAuthLayout(required) {
  const shell = document.querySelector(".app-shell");
  if (required) {
    document.documentElement.setAttribute("data-auth", "required");
    shell?.setAttribute("inert", "");
  } else {
    document.documentElement.removeAttribute("data-auth");
    shell?.removeAttribute("inert");
  }
}

function setLoginMode(mode) {
  const register = mode === "register";
  const student = mode === "student";
  const loginView = $("login-view");
  const registerView = $("register-view");
  const studentView = $("student-view");
  if (loginView) loginView.style.display = register || student ? "none" : "grid";
  if (registerView) registerView.style.display = register ? "grid" : "none";
  if (studentView) studentView.style.display = student ? "grid" : "none";
  const card = document.querySelector("#auth-page .auth-card");
  const labelled = register
    ? "auth-title-register"
    : student
      ? "auth-title-student"
      : "auth-title-signin";
  card?.setAttribute("aria-labelledby", labelled);
  loginError("");
  if (mode !== "student") resetStudentLoginForms();
  const form = register
    ? $("register-form")
    : student
      ? $("student-household-form")
      : $("login-form");
  form?.querySelector("input")?.focus();
}

function resetStudentLoginForms() {
  const household = $("student-household-form");
  const pin = $("student-pin-form");
  if (household) household.hidden = false;
  if (pin) {
    pin.hidden = true;
    pin.reset();
  }
  const chips = $("student-name-chips");
  if (chips) chips.innerHTML = "";
  state.studentLoginEmail = "";
}

function openLoginModal() {
  closeModal();
  closeAutoSchedule();
  closeLessonBuilder();
  closeApplyPlan();
  closeRecalibrate();
  closeEmailEvaluator();
  closeUserMenu();
  const wizard = $("onboarding-wizard");
  if (wizard && !wizard.hidden) {
    wizard.hidden = true;
    setOnboardingLock(false);
  }
  setAuthLayout(true);
  setLoginMode("signin");
}

function closeLoginModal() {
  setAuthLayout(false);
  loginError("");
}

function handleUnauthorized() {
  clearEvidenceBlobs();
  clearAuthToken();
  syncSessionChrome();
  if (state.devMode) return;
  openLoginModal();
}

function resetWorkspaceState() {
  stopPlanStatusPolling();
  state.household = null;
  state.students = [];
  state.curricula = [];
  state.curriculumPlans = [];
  state.catalogKind = "books";
  state.years = [];
  state.enrollments = [];
  state.exceptions = [];
  state.attendance = [];
  state.calendar = null;
  state.evidenceStaging = [];
  state.dashboardAssignments = [];
  state.dashboardCourses = [];
  dashboardChartStats = null;
  destroyDashboardCharts();
  state.inviteKeys = [];
  state.captureTokenStatus = { active: false, created_at: null, expires_at: null };
  state.captureTokenSecret = "";
  state.schoolYear = null;
  state.exceptionColors = null;
  state.dashboardMonth = null;
  state.portfolio = {
    studentId: null,
    schoolYearId: null,
    reportType: "state_evaluation_log",
    custom: emptyPortfolioCustom(),
  };
  state.sessionUser = null;
  state.notifications = { unread_count: 0, notifications: [] };
  state.kidWork = [];
  state.homework = { session: null, assignmentId: null, busy: false };
  state.switchUsers = [];
  onboarding.step = 1;
  onboarding.yearPosted = false;
  onboarding.householdOnly = false;
}

async function loadWorkspace() {
  try {
    if (currentUserIsChild()) {
      if (!window.location.hash.startsWith("#/my-work")) {
        history.replaceState(null, "", "#/my-work");
      }
      await loadKidWorkspace();
      return;
    }
    await loadHousehold();
    await Promise.all([loadStudents(), loadYears()]);
    if (needsOnboarding()) {
      openOnboardingWizard();
    } else if (householdNeedsName()) {
      openHouseholdNameWizard();
    }
    await Promise.all([
      loadCurricula(),
      loadEnrollments(),
      loadExceptions(),
      loadSchoolYearSettings(),
      loadExceptionColors(),
      loadEvidenceStaging(),
    ]);
    loadNotifications();
  } catch (error) {
    if (error.status === 401) return;
    flash(error.message, true);
  }
}

async function enterApp() {
  closeLoginModal();
  syncSessionChrome();
  flash("");
  resetWorkspaceState();
  await loadWorkspace();
  if (currentUserIsChild() && !window.location.hash.startsWith("#/my-work")) {
    window.location.hash = "#/my-work";
    return;
  }
  render();
  if (!currentUserIsChild() && !window.__notifyTimer) {
    window.__notifyTimer = window.setInterval(() => {
      if (!isLoginOpen() && !currentUserIsChild()) loadNotifications();
    }, 30000);
  }
}

async function loginWithPassword(email, password) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  const result = await api("/auth/token", { method: "POST", body, skipAuth: true });
  setAuthToken(result.access_token);
  await enterApp();
}

async function submitLogin(form) {
  loginError("");
  const data = formValues(form);
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await loginWithPassword(data.username, data.password);
  } catch (error) {
    loginError(error.message);
  } finally {
    button.disabled = false;
  }
}

async function submitRegister(form) {
  loginError("");
  const data = formValues(form);
  if (data.password !== data.password_verify) {
    loginError("Passwords do not match.");
    form.elements.password_verify?.focus();
    return;
  }
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await api("/auth/register", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({
        email: data.email,
        password: data.password,
        invite_key: data.invite_key,
      }),
    });
    setAuthToken(result.access_token);
    window.location.hash = "#/dashboard";
    await enterApp();
  } catch (error) {
    loginError(error.message);
  } finally {
    button.disabled = false;
  }
}

async function generateInviteKey() {
  flash("");
  try {
    const invite = await api("/admin/invite", { method: "POST" });
    if (isOfflineQueued(invite)) return;
    await loadInviteKeys();
    render();
    flash(`Invite key ${invite.key} created.`);
  } catch (error) {
    flash(error.message, true);
  }
}

async function generateCaptureToken() {
  flash("");
  const status = state.captureTokenStatus || {};
  if (status.active && !window.confirm(
    "Generate a new capture token? The old one on the student’s computer will stop working."
  )) {
    return;
  }
  try {
    const issued = await api("/auth/capture-token", { method: "POST" });
    if (isOfflineQueued(issued)) return;
    state.captureTokenSecret = issued && issued.access_token ? issued.access_token : "";
    await loadCaptureTokenStatus();
    render();
    flash("Copy this token now and paste it into the Chrome extension. It will not be shown again.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function revokeCaptureToken() {
  flash("");
  if (!window.confirm(
    "Revoke the capture token? The Chrome extension will stop uploading until you generate a new one."
  )) {
    return;
  }
  try {
    const result = await api("/auth/capture-token", { method: "DELETE" });
    if (isOfflineQueued(result)) return;
    state.captureTokenSecret = "";
    await loadCaptureTokenStatus();
    render();
    flash("Capture token revoked.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function copyCaptureToken() {
  const token = state.captureTokenSecret || "";
  if (!token) return;
  try {
    await navigator.clipboard.writeText(token);
    flash("Capture token copied. Paste it into the Chrome extension.");
  } catch {
    flash("Select the token and copy it. It will not be shown again after you leave this page.", true);
  }
}

async function startDemo() {
  loginError("");
  const button = $("try-demo");
  if (button) button.disabled = true;
  try {
    const result = await api("/auth/demo", { method: "POST", skipAuth: true });
    setAuthToken(result.access_token);
    await enterApp();
  } catch (error) {
    loginError(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}

function handleLoginClick(event) {
  const mode = event.target.closest("[data-action='login-mode']");
  if (mode) {
    setLoginMode(mode.dataset.mode);
    return;
  }
  const demo = event.target.closest("[data-action='try-demo']");
  if (demo) startDemo();
  const pick = event.target.closest("[data-action='pick-student-login']");
  if (pick) {
    pickStudentLogin(Number(pick.dataset.studentId), pick.textContent);
  }
}

function handleLoginSubmit(event) {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  if (form.dataset.form === "login") {
    event.preventDefault();
    submitLogin(form);
  } else if (form.dataset.form === "register") {
    event.preventDefault();
    submitRegister(form);
  } else if (form.dataset.form === "student-household") {
    event.preventDefault();
    submitStudentHousehold(form);
  } else if (form.dataset.form === "student-pin") {
    event.preventDefault();
    submitStudentPin(form);
  }
}

async function submitStudentHousehold(form) {
  loginError("");
  const data = formValues(form);
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await api("/auth/student-household", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ email: data.email }),
    });
    const students = result.students || [];
    if (!students.length) {
      loginError("No student logins for that household yet.");
      return;
    }
    state.studentLoginEmail = data.email;
    form.hidden = true;
    const pinForm = $("student-pin-form");
    pinForm.hidden = false;
    $("student-name-chips").innerHTML = students
      .map(
        (student) =>
          `<button type="button" class="student-name-chip" data-action="pick-student-login"
                   data-student-id="${student.student_id}">${escapeHtml(student.name)}</button>`
      )
      .join("");
  } catch (error) {
    loginError(error.message);
  } finally {
    button.disabled = false;
  }
}

function pickStudentLogin(studentId, name) {
  $("student-pick-id").value = String(studentId);
  document.querySelectorAll(".student-name-chip").forEach((chip) => {
    const selected = Number(chip.dataset.studentId) === studentId;
    chip.classList.toggle("is-selected", selected);
    chip.setAttribute("aria-pressed", String(selected));
  });
  $("student-pin-form")?.querySelector('input[name="pin"]')?.focus();
}

async function submitStudentPin(form) {
  loginError("");
  const data = formValues(form);
  if (!data.student_id) {
    loginError("Tap your name first.");
    return;
  }
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await api("/auth/student-token", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({
        email: state.studentLoginEmail,
        student_id: Number(data.student_id),
        pin: data.pin,
      }),
    });
    setAuthToken(result.access_token);
    await enterApp();
  } catch (error) {
    loginError(error.message);
  } finally {
    button.disabled = false;
  }
}

let switchTarget = { studentId: null };

function switchUserError(message) {
  const el = $("switch-user-error");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function closeSwitchUser() {
  const modal = $("switch-user-modal");
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  switchUserError("");
  const form = $("switch-user-form");
  if (form) {
    form.hidden = true;
    form.reset();
  }
}

async function openSwitchUser() {
  switchUserError("");
  closeUserMenu();
  try {
    state.switchUsers = await api("/auth/switchable-users");
  } catch (error) {
    flash(error.message, true);
    return;
  }
  const hint = $("switch-user-hint");
  if (hint) {
    hint.textContent = currentUserIsChild()
      ? "A parent password is required to leave this student."
      : "Choose who should use the app on this screen.";
  }
  $("switch-user-list").innerHTML = state.switchUsers
    .map((item) => {
      const studentId = item.student_id == null ? "" : String(item.student_id);
      return `<button type="button" class="switch-user-option${item.is_current ? " is-current" : ""}"
                 data-action="switch-to-user" data-kind="${escapeHtml(item.kind)}"
                 data-student-id="${escapeHtml(studentId)}">
        ${escapeHtml(item.display_name)}${item.is_current ? " (current)" : ""}
      </button>`;
    })
    .join("");
  const form = $("switch-user-form");
  if (form) form.hidden = true;
  $("switch-user-modal").hidden = false;
  document.body.classList.add("modal-open");
}

async function chooseSwitchTarget(kind, studentIdValue) {
  const studentId = studentIdValue ? Number(studentIdValue) : null;
  switchTarget.studentId = kind === "parent" ? null : studentId;
  if (currentUserIsChild()) {
    const form = $("switch-user-form");
    if (form) {
      form.hidden = false;
      form.elements.parent_password?.focus();
    }
    return;
  }
  await performSwitch(switchTarget.studentId, null);
}

async function submitSwitchUser(form) {
  switchUserError("");
  const data = formValues(form);
  try {
    await performSwitch(switchTarget.studentId, data.parent_password);
  } catch (error) {
    switchUserError(error.message);
  }
}

async function performSwitch(studentId, parentPassword) {
  const result = await api("/auth/switch", {
    method: "POST",
    body: JSON.stringify({
      student_id: studentId,
      parent_password: parentPassword || null,
    }),
  });
  setAuthToken(result.access_token);
  closeSwitchUser();
  await enterApp();
}

async function loadNotifications() {
  if (currentUserIsChild()) return;
  try {
    state.notifications = await api("/notifications");
  } catch {
    state.notifications = { unread_count: 0, notifications: [] };
  }
  paintNotifications();
}

function paintNotifications() {
  const count = $("notify-count");
  const unread = Number(state.notifications?.unread_count || 0);
  if (count) {
    count.hidden = unread < 1;
    count.textContent = unread > 9 ? "9+" : String(unread);
  }
  const list = $("notify-list");
  if (!list) return;
  const rows = state.notifications?.notifications || [];
  if (!rows.length) {
    list.innerHTML = `<p class="empty" style="padding:0.75rem">No notifications yet.</p>`;
    return;
  }
  list.innerHTML = rows
    .map(
      (item) => `
      <button type="button" class="notify-item${item.read_at ? "" : " is-unread"}"
              data-action="open-notification" data-id="${item.id}"
              data-assignment-id="${item.assignment_id || ""}">
        <strong>${escapeHtml(item.title)}</strong>
        <p class="meta">${escapeHtml(item.body)}</p>
      </button>`
    )
    .join("");
}

function toggleNotifications() {
  const panel = $("notify-panel");
  const button = $("notify-bell");
  if (!panel || !button) return;
  const open = panel.hidden;
  panel.hidden = !open;
  button.setAttribute("aria-expanded", String(open));
  if (open) loadNotifications();
}

function closeNotifications() {
  const panel = $("notify-panel");
  const button = $("notify-bell");
  if (panel) panel.hidden = true;
  button?.setAttribute("aria-expanded", "false");
}

async function markNotificationsRead() {
  try {
    state.notifications = await api("/notifications/read-all", { method: "POST" });
    paintNotifications();
  } catch (error) {
    flash(error.message, true);
  }
}

async function openNotification(id) {
  const item = (state.notifications?.notifications || []).find((row) => row.id === id);
  try {
    await api(`/notifications/${id}/read`, { method: "POST" });
  } catch {
    /* still open the assignment */
  }
  closeNotifications();
  if (item?.assignment_id) {
    await openAssignment(item.assignment_id);
  } else if (
    item?.type === "curriculum_plan_ready" ||
    item?.type === "curriculum_plan_failed"
  ) {
    state.catalogKind = "plans";
    if (routeName() === "curricula") {
      render();
    } else {
      window.location.hash = "#/curricula";
    }
  }
  loadNotifications();
}

async function setStudentPin(studentId) {
  const input = $("student-pin-input");
  const pin = (input?.value || "").trim();
  flash("");
  try {
    const student = await api(`/students/${studentId}/pin`, {
      method: "POST",
      body: JSON.stringify({ pin }),
    });
    const index = state.students.findIndex((row) => row.id === studentId);
    if (index !== -1) state.students[index] = student;
    if (input) input.value = "";
    render();
    flash("Student PIN saved.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function clearStudentPin(studentId) {
  flash("");
  try {
    const student = await api(`/students/${studentId}/pin`, { method: "DELETE" });
    const index = state.students.findIndex((row) => row.id === studentId);
    if (index !== -1) state.students[index] = student;
    render();
    flash("Student login removed.");
  } catch (error) {
    flash(error.message, true);
  }
}

async function unlockHomeworkHelp(assignmentId) {
  flash("");
  try {
    detail.helpSessions = await api(`/homework-help/assignments/${assignmentId}/unlock`, {
      method: "POST",
    });
    if (detail.item) {
      detail.item = await api(`/assignments/${assignmentId}`);
    }
    renderDetail();
    flash("Homework help is available again.");
  } catch (error) {
    flash(error.message, true);
  }
}

function logout() {
  clearEvidenceBlobs();
  clearAuthToken();
  syncSessionChrome();
  closeModal();
  closeAutoSchedule();
  closeLessonBuilder();
  closeApplyPlan();
  closeRecalibrate();
  closeEmailEvaluator();
  closeSchoolYearSettings();
  const wizard = $("onboarding-wizard");
  if (wizard) wizard.hidden = true;
  setOnboardingLock(false);
  resetWorkspaceState();
  if (state.devMode) {
    enterApp();
    return;
  }
  $("view").innerHTML = "";
  $("household-label").textContent = "Household";
  const avatar = $("user-avatar");
  if (avatar) {
    avatar.textContent = "C";
    avatar.classList.remove("is-emoji");
  }
  openLoginModal();
}

async function boot() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  initOfflineIndicator();
  $("view").addEventListener("submit", handleSubmit);
  $("view").addEventListener("click", handleClick);
  $("view").addEventListener("change", handleChange);
  $("view").addEventListener("dragstart", handleEvidenceDragStart);
  $("view").addEventListener("dragend", handleEvidenceDragEnd);
  $("view").addEventListener("dragenter", handleAssignmentDragEnter);
  $("view").addEventListener("dragover", handleAssignmentDragOver);
  $("view").addEventListener("dragleave", handleAssignmentDragLeave);
  $("view").addEventListener("drop", handleAssignmentDrop);
  $("detail-modal").addEventListener("click", handleModalClick);
  $("evidence-upload-input").addEventListener("change", uploadEvidence);
  $("curriculum-csv-input").addEventListener("change", importCurriculumCsv);
  $("curriculum-pdf-input")?.addEventListener("change", importCurriculumPdf);
  $("paper-import-input")?.addEventListener("change", importPaperSheet);
  $("detail-modal").addEventListener("submit", (event) => {
    if (!event.target.closest('form[data-form="assignment-edit"]')) return;
    event.preventDefault();
    saveAssignment();
  });
  $("pacing-modal").addEventListener("click", handlePacingClick);
  $("pacing-modal").addEventListener("change", handlePacingChange);
  $("pacing-modal").addEventListener("submit", (event) => {
    if (!event.target.closest('form[data-form="pacing-preview"]')) return;
    event.preventDefault();
    generatePacingPreview();
  });
  $("lesson-plan-modal").addEventListener("click", handleLessonBuilderClick);
  $("lesson-plan-modal").addEventListener("change", handleLessonBuilderChange);
  $("lesson-plan-modal").addEventListener("input", handleLessonBuilderInput);
  $("lesson-plan-modal").addEventListener("keydown", handleLessonBuilderKeydown);
  $("lesson-builder-form").addEventListener("submit", (event) => {
    event.preventDefault();
  });
  $("apply-plan-modal").addEventListener("click", handleApplyPlanClick);
  $("apply-plan-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitApplyPlan();
  });
  $("recalibrate-modal").addEventListener("click", handleRecalibrateClick);
  $("recalibrate-modal").addEventListener("change", handleRecalibrateChange);
  $("email-evaluator-modal").addEventListener("click", handleEmailEvaluatorClick);
  $("email-evaluator-form").addEventListener("submit", submitEvaluatorEmail);
  $("school-year-modal").addEventListener("click", handleSchoolYearClick);
  $("school-year-modal").addEventListener("change", handleSchoolYearChange);
  $("onboarding-wizard").addEventListener("click", handleWizardClick);
  $("onboarding-wizard").addEventListener("submit", handleWizardSubmit);
  $("auth-page").addEventListener("click", handleLoginClick);
  $("auth-page").addEventListener("submit", handleLoginSubmit);
  $("switch-user-modal")?.addEventListener("click", handleClick);
  $("switch-user-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitSwitchUser(event.currentTarget);
  });
  $("notify-bell")?.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleNotifications();
  });
  $("notify-panel")?.addEventListener("click", handleClick);
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#notify-wrap")) closeNotifications();
  });
  document.addEventListener("click", handleUserMenuClick);
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (isLoginOpen()) {
      event.preventDefault();
      return;
    }
    if (isOnboardingOpen()) {
      event.preventDefault();
      return;
    }
    if (isUserMenuOpen()) {
      closeUserMenu();
      $("user-profile")?.focus();
    } else if ($("switch-user-modal") && !$("switch-user-modal").hidden) {
      closeSwitchUser();
    } else if ($("notify-panel") && !$("notify-panel").hidden) {
      closeNotifications();
    } else if (isSchoolYearOpen()) {
      closeSchoolYearSettings();
    } else if (!$("pacing-modal").hidden) {
      closeAutoSchedule();
    } else if (isLessonBuilderOpen()) {
      closeLessonBuilder();
    } else if (isApplyPlanOpen()) {
      closeApplyPlan();
    } else if (isRecalibrateOpen()) {
      closeRecalibrate();
    } else if (isEmailEvaluatorOpen()) {
      closeEmailEvaluator();
    } else if (!$("detail-modal").hidden) {
      closeModal();
    }
  });
  window.addEventListener("hashchange", () => {
    if (isLoginOpen()) return;
    flash("");
    closeModal();
    closeAutoSchedule();
    closeLessonBuilder();
    closeApplyPlan();
    closeRecalibrate();
    closeEmailEvaluator();
    closeSchoolYearSettings();
    closeUserMenu();
    showRoute();
  });
  await loadHealth();
  syncSessionChrome();
  if (!canUseApp()) {
    openLoginModal();
    return;
  }
  closeLoginModal();
  await loadWorkspace();
  render();
  if (!currentUserIsChild()) {
    loadNotifications();
    window.setInterval(() => {
      if (!isLoginOpen() && !currentUserIsChild()) loadNotifications();
    }, 30000);
  }
}

boot();
