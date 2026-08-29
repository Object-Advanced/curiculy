const STORAGE_KEYS = ["serverUrl", "deviceToken"];
const BADGE_CLEAR_MS = 2200;

let captureInFlight = false;
let badgeTimer = 0;

function delay(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function normalizeServerUrl(raw) {
  const trimmed = (raw || "").trim();
  if (!trimmed) {
    return "";
  }
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "";
    }
    let path = parsed.pathname.replace(/\/+$/, "");
    if (path === "/api") {
      path = "";
    }
    return `${parsed.origin}${path}`;
  } catch {
    return "";
  }
}

function authorizationHeader(token) {
  return `Bearer ${token.trim().replace(/^Bearer\s+/i, "")}`;
}

async function dataUrlToBlob(dataUrl) {
  const response = await fetch(dataUrl);
  return response.blob();
}

async function setBadge(text, color) {
  if (badgeTimer) {
    clearTimeout(badgeTimer);
    badgeTimer = 0;
  }
  await chrome.action.setBadgeBackgroundColor({ color });
  await chrome.action.setBadgeText({ text });
  if (text) {
    badgeTimer = setTimeout(() => {
      chrome.action.setBadgeText({ text: "" });
      badgeTimer = 0;
    }, BADGE_CLEAR_MS);
  }
}

function overlayScript(payload) {
  const id = "curiculy-capture-overlay";
  document.getElementById(id)?.remove();

  const host = document.createElement("div");
  host.id = id;
  host.setAttribute("aria-live", "polite");
  Object.assign(host.style, {
    all: "initial",
    position: "fixed",
    inset: "0",
    zIndex: "2147483647",
    pointerEvents: "none",
  });

  const ok = payload.ok;
  const color = ok ? "#2f6f4e" : "#dc2626";
  const mark = ok
    ? '<polyline points="20 36 32 48 52 24"></polyline>'
    : '<line x1="24" y1="24" x2="48" y2="48"></line><line x1="48" y1="24" x2="24" y2="48"></line>';

  const shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = `
    <style>
      .wrap {
        position: fixed;
        inset: 0;
        display: grid;
        place-items: center;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .toast {
        display: grid;
        justify-items: center;
        gap: 0.65rem;
        animation: curiculy-float 1.65s ease forwards;
      }
      .mark {
        width: 88px;
        height: 88px;
        border-radius: 50%;
        background: ${color};
        display: grid;
        place-items: center;
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.28);
      }
      svg {
        width: 48px;
        height: 48px;
        stroke: #ffffff;
        stroke-width: 5;
        stroke-linecap: round;
        stroke-linejoin: round;
        fill: none;
      }
      .label {
        color: ${color};
        font-size: 0.95rem;
        font-weight: 700;
        text-shadow: 0 1px 0 #ffffff;
      }
      @keyframes curiculy-float {
        0% { transform: translateY(18px) scale(0.7); opacity: 0; }
        16% { transform: translateY(0) scale(1.1); opacity: 1; }
        30% { transform: translateY(0) scale(1); opacity: 1; }
        70% { transform: translateY(0) scale(1); opacity: 1; }
        100% { transform: translateY(-16px) scale(0.96); opacity: 0; }
      }
    </style>
    <div class="wrap">
      <div class="toast">
        <div class="mark">
          <svg viewBox="0 0 72 72" aria-hidden="true">${mark}</svg>
        </div>
        <div class="label"></div>
      </div>
    </div>
  `;
  shadow.querySelector(".label").textContent = payload.message;
  document.documentElement.appendChild(host);
  setTimeout(() => host.remove(), 1750);
}

async function showOverlay(tabId, payload) {
  if (tabId == null) {
    return false;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: overlayScript,
      args: [payload],
      injectImmediately: true,
    });
    return true;
  } catch {
    return false;
  }
}

function errorMessage(error, status) {
  if (status === 401 || status === 403) {
    return "Check the device token in extension settings.";
  }
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  return "Could not send this page to Curiculy.";
}

async function uploadCapture(serverUrl, deviceToken, blob) {
  const body = new FormData();
  const filename = `capture-${new Date().toISOString().replace(/[:.]/g, "-")}.png`;
  body.append("file", blob, filename);
  body.append("source", "chrome_extension");

  const response = await fetch(`${serverUrl}/api/evidence/staging`, {
    method: "POST",
    credentials: "omit",
    headers: {
      Authorization: authorizationHeader(deviceToken),
    },
    body,
  });

  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : "";
    } catch {
      detail = "";
    }
    const error = new Error(errorMessage(detail, response.status));
    error.status = response.status;
    throw error;
  }
}

async function captureAndUpload(tab) {
  const stored = await chrome.storage.local.get(STORAGE_KEYS);
  const serverUrl = normalizeServerUrl(stored.serverUrl);
  const deviceToken = (stored.deviceToken || "").trim();

  if (!serverUrl || !deviceToken) {
    await chrome.runtime.openOptionsPage();
    return;
  }

  await setBadge("…", "#2f6f4e");
  const windowId = tab.windowId ?? chrome.windows.WINDOW_ID_CURRENT;
  const dataUrl = await chrome.tabs.captureVisibleTab(windowId, { format: "png" });
  const blob = await dataUrlToBlob(dataUrl);
  await uploadCapture(serverUrl, deviceToken, blob);

  const overlayed = await showOverlay(tab.id, {
    ok: true,
    message: "Sent to Curiculy",
  });
  await setBadge(overlayed ? "" : "✓", "#2f6f4e");
}

chrome.action.onClicked.addListener(async (tab) => {
  if (captureInFlight) {
    return;
  }
  captureInFlight = true;
  try {
    await captureAndUpload(tab);
  } catch (error) {
    const message = errorMessage(error.message, error.status);
    const overlayed = await showOverlay(tab.id, { ok: false, message: "Not sent" });
    await setBadge("!", "#dc2626");
    if (!overlayed) {
      await chrome.action.setTitle({ title: message });
      delay(BADGE_CLEAR_MS).then(() => {
        chrome.action.setTitle({ title: "Send this page to Curiculy" });
      });
    }
  } finally {
    captureInFlight = false;
  }
});
