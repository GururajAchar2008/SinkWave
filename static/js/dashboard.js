// ── SinkWave Dashboard JS (updated with Axios + search by name) ──────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  loadMyChannels();
});

// ── TAB SWITCHING ─────────────────────────────────
function switchTab(name, btn) {
  document
    .querySelectorAll(".tab-pane")
    .forEach((p) => p.classList.remove("active"));
  document
    .querySelectorAll(".sidebar-item")
    .forEach((b) => b.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  btn.classList.add("active");

  if (name === "my-channels") loadMyChannels();
}

// ── MY CHANNELS ───────────────────────────────────
async function loadMyChannels() {
  const container = document.getElementById("my-channels-list");
  container.innerHTML = '<div class="loading-state">Loading channels…</div>';

  try {
    const res = await axios.get("/api/my-channels");
    const data = res.data;

    if (!data.length) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="es-icon">🗂️</div>
          <h3>No channels yet</h3>
          <p>Create a new channel or search for one to join.</p>
        </div>`;
      return;
    }

    container.innerHTML = data
      .map(
        (ch) => `
      <a class="channel-card" href="/channel/${ch.id}">
        <div class="cc-top">
          <span class="cc-name">${escHtml(ch.name)}</span>
          <span class="cc-role cc-role-${ch.role}">${ch.role === "admin" ? "★ Admin" : "Member"}</span>
        </div>
        <div class="cc-meta">
          <span>👥 ${ch.member_count} member${ch.member_count !== 1 ? "s" : ""}</span>
          <span>📄 ${ch.doc_count} doc${ch.doc_count !== 1 ? "s" : ""}</span>
          <span>${ch.is_public ? "🌐 Public" : "🔒 Private"}</span>
        </div>
        <div class="cc-code">
          <div class="cc-code-label">Channel Code</div>
          <div class="cc-code-val">${escHtml(ch.channel_code)}</div>
        </div>
      </a>
    `,
      )
      .join("");
  } catch (e) {
    container.innerHTML =
      '<div class="loading-state">Failed to load channels.</div>';
  }
}

// ── SEARCH CHANNELS (now supports name + code) ───────────────────────────────
document
  .getElementById("search-code-input")
  ?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchChannel();
  });

async function searchChannel() {
  const q = document.getElementById("search-code-input").value.trim();
  const area = document.getElementById("search-result");
  if (!q) {
    showToast("Please enter a channel code or name.", "error");
    return;
  }

  area.innerHTML = '<div class="loading-state">Searching…</div>';

  try {
    const res = await axios.get(
      `/api/search-channels?q=${encodeURIComponent(q)}`,
    );
    const data = res.data;

    if (!Array.isArray(data) || data.length === 0) {
      area.innerHTML = `<div class="alert alert-error">No channels found matching "${escHtml(q)}".</div>`;
      return;
    }

    // Show results as a grid (same style as My Channels)
    let html = `<div class="channels-grid" style="margin-top:1rem;">`;
    html += data
      .map(
        (ch) => `
      <div class="channel-card">
        <div class="cc-top">
          <span class="cc-name">${escHtml(ch.name)}</span>
          ${ch.is_member ? `<span class="cc-role cc-role-${ch.membership_role}">${ch.membership_role === "admin" ? "★ Admin" : "Member"}</span>` : ""}
        </div>
        <div class="cc-meta">
          <span>👥 ${ch.member_count} member${ch.member_count !== 1 ? "s" : ""}</span>
          <span>${ch.is_public ? "🌐 Public" : "🔒 Private"}</span>
        </div>
        <div class="cc-code">
          <div class="cc-code-label">Channel Code</div>
          <div class="cc-code-val">${escHtml(ch.channel_code)}</div>
        </div>
        <div style="margin-top: 1rem;">
          ${
            ch.is_member
              ? `<a class="btn btn-primary btn-full" href="/channel/${ch.id}">Open Channel →</a>`
              : ch.has_pending_request
                ? `<span class="btn btn-outline btn-full" style="cursor:default;">⏳ Request Pending</span>`
                : `<button class="btn btn-primary btn-full" onclick="joinChannel(${ch.id}, ${ch.is_public})">${ch.is_public ? "🌐 Join Now" : "📥 Request to Join"}</button>`
          }
        </div>
      </div>
    `,
      )
      .join("");
    html += `</div>`;
    area.innerHTML = html;
  } catch (e) {
    area.innerHTML =
      '<div class="alert alert-error">Something went wrong. Please try again.</div>';
  }
}

async function joinChannel(channelId, isPublic) {
  try {
    const res = await axios.post("/api/join-channel", {
      channel_id: channelId,
    });
    const data = res.data;
    if (data.success) {
      showToast(data.message, "success");
      searchChannel(); // refresh results
    } else {
      showToast(data.error || "Something went wrong.", "error");
    }
  } catch (e) {
    showToast("Network error.", "error");
  }
}

// ── CREATE CHANNEL ────────────────────────────────
let _newChannelId = null;

async function createChannel() {
  const name = document.getElementById("ch-name").value.trim();
  const maxRaw = document.getElementById("ch-max").value.trim();
  const maxMembers = maxRaw ? parseInt(maxRaw) : null;
  const visibility = document.querySelector(
    'input[name="visibility"]:checked',
  )?.value;
  const is_public = visibility !== "private";
  const alertEl = document.getElementById("create-alert");

  alertEl.innerHTML = "";
  if (!name) {
    alertEl.innerHTML =
      '<div class="alert alert-error">Channel name is required.</div>';
    return;
  }
  if (maxMembers !== null && (isNaN(maxMembers) || maxMembers < 2)) {
    alertEl.innerHTML =
      '<div class="alert alert-error">Max members must be at least 2.</div>';
    return;
  }

  try {
    const res = await axios.post("/api/create-channel", {
      name,
      is_public,
      max_members: maxMembers,
    });
    const data = res.data;
    if (data.success) {
      _newChannelId = data.channel_id;
      document.getElementById("new-channel-code").textContent =
        data.channel_code;
      document.getElementById("create-success").style.display = "block";
      document.getElementById("go-channel-btn").onclick = () => {
        window.location = "/channel/" + _newChannelId;
      };
      document.getElementById("ch-name").value = "";
      document.getElementById("ch-max").value = "";
      showToast("Channel created!", "success");
    } else {
      alertEl.innerHTML = `<div class="alert alert-error">${escHtml(data.error)}</div>`;
    }
  } catch (e) {
    alertEl.innerHTML =
      '<div class="alert alert-error">Network error. Please try again.</div>';
  }
}

function copyCode() {
  const code = document.getElementById("new-channel-code").textContent;
  navigator.clipboard
    .writeText(code)
    .then(() => showToast("Code copied!", "success"));
}

// ── UTILS ─────────────────────────────────────────
function showToast(msg, type = "") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "toast show" + (type ? " toast-" + type : "");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => {
    t.className = "toast";
  }, 3000);
}

function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
