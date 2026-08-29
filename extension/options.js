const STORAGE_KEYS = ["serverUrl", "deviceToken"];

const form = document.getElementById("options-form");
const serverUrlInput = document.getElementById("server-url");
const deviceTokenInput = document.getElementById("device-token");
const toggleToken = document.getElementById("toggle-token");
const statusEl = document.getElementById("status");

function showStatus(message, kind) {
  statusEl.hidden = false;
  statusEl.className = `banner ${kind}`;
  statusEl.textContent = message;
}

function normalizeServerUrl(raw) {
  const trimmed = (raw || "").trim();
  if (!trimmed) {
    throw new Error("Enter the homeschool web address.");
  }
  const parsed = new URL(trimmed);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("The web address must start with http:// or https://.");
  }
  let path = parsed.pathname.replace(/\/+$/, "");
  if (path === "/api") {
    path = "";
  }
  return `${parsed.origin}${path}`;
}

async function loadOptions() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS);
  serverUrlInput.value = stored.serverUrl || "";
  deviceTokenInput.value = stored.deviceToken || "";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const serverUrl = normalizeServerUrl(serverUrlInput.value);
    const deviceToken = deviceTokenInput.value.trim();
    if (!deviceToken) {
      throw new Error("Enter the device token.");
    }
    serverUrlInput.value = serverUrl;
    await chrome.storage.local.set({ serverUrl, deviceToken });
    showStatus("Saved. Students can click the toolbar icon to send a screenshot.", "ok");
  } catch (error) {
    const message = error instanceof TypeError
      ? "Enter a full web address, such as https://your-family.curiculy.com"
      : error.message;
    showStatus(message, "error");
  }
});

toggleToken.addEventListener("click", () => {
  const hidden = deviceTokenInput.type === "password";
  deviceTokenInput.type = hidden ? "text" : "password";
  toggleToken.textContent = hidden ? "Hide" : "Show";
  toggleToken.setAttribute("aria-pressed", hidden ? "true" : "false");
});

loadOptions();
