// ── SinkWave Channel JS (updated with Axios + new features) ───────────────────────────

const REACTIONS = ["👍", "❤️", "🔥", "⭐", "👏"];

document.addEventListener("DOMContentLoaded", () => {
  loadDocuments();
  if (USER_ROLE === "admin" && !IS_PUBLIC) {
    loadRequestCount();
  }
  setupDragDrop();
});

// ── TAB SWITCHING ─────────────────────────────────
function switchChTab(name, btn) {
  document
    .querySelectorAll(".ch-pane")
    .forEach((p) => p.classList.remove("active"));
  document
    .querySelectorAll(".ch-nav-item")
    .forEach((b) => b.classList.remove("active"));
  const panel = document.getElementById("ch-tab-" + name);
  if (panel) panel.classList.add("active");
  btn.classList.add("active");

  if (name === "members") loadMembers();
  if (name === "requests") loadRequests();
}

// ── DOCUMENTS ─────────────────────────────────────
async function loadDocuments() {
  const list = document.getElementById("doc-list");
  list.innerHTML = '<div class="loading-state">Loading documents…</div>';

  try {
    const res = await axios.get(`/api/channel/${CHANNEL_ID}/documents`);
    const docs = res.data;

    if (!docs.length) {
      list.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          <div class="es-icon">📄</div>
          <h3>No documents yet</h3>
          ${USER_ROLE === "admin" ? "<p>Upload the first document using the button above.</p>" : "<p>No documents have been shared in this channel yet.</p>"}
        </div>`;
      return;
    }

    list.innerHTML = docs.map((doc) => renderDocCard(doc)).join("");
  } catch (e) {
    list.innerHTML =
      '<div class="loading-state">Failed to load documents.</div>';
  }
}

function renderDocCard(doc) {
  const icon = fileIcon(doc.filetype);
  const ftCls = fileTypeClass(doc.filetype);

  const reactionBar = REACTIONS.map((emoji) => {
    const active = doc.user_reaction === emoji ? "active" : "";
    return `<button class="reaction-btn ${active}" onclick="react(${doc.id}, '${emoji}', this)">${emoji}</button>`;
  }).join("");

  // NEW: Delete button for admins
  const deleteBtn =
    USER_ROLE === "admin"
      ? `<button onclick="deleteDoc(${doc.id});" class="doc-download" style="background:var(--danger-lt);color:var(--danger);border-color:#F4A4A4;">🗑️ Delete</button>`
      : "";

  return `
    <div class="doc-card" id="doc-${doc.id}">
      <div class="doc-icon">${icon}</div>
      <div class="doc-body">
        <div style="display:flex;align-items:center;gap:.6rem;">
          <span class="doc-filename">${escHtml(doc.filename)}</span>
          <span class="filetype-tag ${ftCls}">${escHtml(doc.filetype)}</span>
        </div>
        ${doc.description ? `<div class="doc-desc">${escHtml(doc.description)}</div>` : ""}
        <div class="doc-meta">
          <span>📤 ${escHtml(doc.uploader_name)}</span>
          <span>🕒 ${escHtml(doc.uploaded_at)}</span>
          ${doc.reaction_count > 0 ? `<span>✨ ${doc.reaction_count} reaction${doc.reaction_count !== 1 ? "s" : ""}</span>` : ""}
        </div>
        <div class="doc-actions">
          ${reactionBar}
          <a class="doc-download" href="/static/${escHtml(doc.filepath)}" download="${escHtml(doc.filename)}">
            ⬇️ Download
          </a>
          ${deleteBtn}
        </div>
      </div>
    </div>`;
}

async function react(docId, emoji, btn) {
  try {
    const res = await axios.post(`/api/document/${docId}/react`, {
      reaction: emoji,
    });
    const data = res.data;
    if (data.success) {
      const card = document.getElementById("doc-" + docId);
      card.querySelectorAll(".reaction-btn").forEach((b) => {
        const e = b.textContent.trim();
        b.classList.toggle("active", data.user_reaction === e);
        const cnt = data.counts[e] || 0;
        b.innerHTML = e;
        if (cnt > 0)
          b.innerHTML += ` <span class="reaction-count">${cnt}</span>`;
      });
    }
  } catch (e) {
    showToast("Failed to react.", "error");
  }
}

// ── NEW: DELETE DOCUMENT ──────────────────────────────────
async function deleteDoc(docId) {
  if (!confirm("Delete this document permanently?")) return;
  try {
    const res = await axios.post(`/api/document/${docId}/delete`);
    if (res.data.success) {
      showToast("Document deleted!", "success");
      loadDocuments();
    }
  } catch (e) {
    const msg = e.response?.data?.error || "Failed to delete.";
    showToast(msg, "error");
  }
}

// ── UPLOAD ─────────────────────────────────────────
let _selectedFile = null;

function openUploadModal() {
  _selectedFile = null;
  document.getElementById("file-preview").style.display = "none";
  document.getElementById("upload-alert").innerHTML = "";
  document.getElementById("upload-desc").value = "";
  document.getElementById("file-input").value = "";
  document.getElementById("upload-modal").style.display = "flex";
}

function closeUploadModal() {
  document.getElementById("upload-modal").style.display = "none";
}

function fileSelected(input) {
  const file = input.files[0];
  if (!file) return;
  _selectedFile = file;
  const preview = document.getElementById("file-preview");
  preview.style.display = "flex";
  preview.innerHTML = `${fileIcon(file.name.split(".").pop())} <span>${escHtml(file.name)}</span> <span style="color:var(--text-muted);font-size:.8rem;">(${formatBytes(file.size)})</span>`;
}

function setupDragDrop() {
  const dz = document.getElementById("drop-zone");
  if (!dz) return;
  dz.addEventListener("dragover", (e) => {
    e.preventDefault();
    dz.classList.add("dragover");
  });
  dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) {
      _selectedFile = file;
      const preview = document.getElementById("file-preview");
      preview.style.display = "flex";
      preview.innerHTML = `${fileIcon(file.name.split(".").pop())} <span>${escHtml(file.name)}</span>`;
    }
  });
}

async function uploadFile() {
  const alertEl = document.getElementById("upload-alert");
  alertEl.innerHTML = "";
  if (!_selectedFile) {
    alertEl.innerHTML =
      '<div class="alert alert-error">Please select a file first.</div>';
    return;
  }
  const desc = document.getElementById("upload-desc").value.trim();
  const btn = document.getElementById("upload-btn");
  btn.textContent = "Uploading…";
  btn.disabled = true;

  const form = new FormData();
  form.append("file", _selectedFile);
  form.append("description", desc);

  try {
    const res = await axios.post(`/api/channel/${CHANNEL_ID}/upload`, form);
    const data = res.data;
    if (data.success) {
      closeUploadModal();
      showToast("File uploaded!", "success");
      loadDocuments();
    } else {
      alertEl.innerHTML = `<div class="alert alert-error">${escHtml(data.error)}</div>`;
    }
  } catch (e) {
    alertEl.innerHTML =
      '<div class="alert alert-error">Upload failed. Please try again.</div>';
  } finally {
    btn.textContent = "Upload";
    btn.disabled = false;
  }
}

// ── MEMBERS ────────────────────────────────────────
async function loadMembers() {
  const list = document.getElementById("members-list");
  if (!list) return;
  list.innerHTML = '<div class="loading-state">Loading members…</div>';

  try {
    const res = await axios.get(`/api/channel/${CHANNEL_ID}/members`);
    const members = res.data;
    if (members.error) {
      list.innerHTML = "";
      return;
    }

    list.innerHTML = members
      .map(
        (m) => `
      <div class="member-card" id="member-${m.id}">
        <div class="member-info">
          <div class="member-avatar">${m.username[0].toUpperCase()}</div>
          <div>
            <div class="member-name">
              ${escHtml(m.username)}
              <span class="member-badge mb-${m.role}">${m.role === "admin" ? "★ Admin" : "Member"}</span>
            </div>
            <div class="member-email">${escHtml(m.email)}</div>
            <div class="member-joined">Joined ${escHtml(m.joined_at)}</div>
          </div>
        </div>
        <div class="member-actions">
          ${
            m.id !== USER_ID
              ? `
            ${
              m.role === "admin"
                ? `<button class="btn btn-outline btn-sm" onclick="demoteAdmin(${m.id})">Remove Admin Perm</button>`
                : `<button class="btn btn-outline btn-sm" onclick="makeAdmin(${m.id})">Make Admin</button>`
            }
            <button class="btn btn-danger btn-sm" onclick="removeMember(${m.id})">Remove Member</button>
          `
              : `<span style="color:var(--text-muted);font-size:.85rem;">(You)</span>`
          }
        </div>
      </div>
    `,
      )
      .join("");
  } catch (e) {
    list.innerHTML = '<div class="loading-state">Failed to load members.</div>';
  }
}

// ── NEW: DEMOTE ADMIN ─────────────────────────────────────
async function demoteAdmin(userId) {
  if (!confirm("Remove admin permission for this user?")) return;
  try {
    const res = await axios.post(`/api/channel/${CHANNEL_ID}/demote-admin`, {
      user_id: userId,
    });
    if (res.data.success) {
      showToast("Admin permission removed!", "success");
      loadMembers();
    }
  } catch (e) {
    const msg = e.response?.data?.error || "Failed.";
    showToast(msg, "error");
  }
}

// ── NEW: REMOVE MEMBER ────────────────────────────────────
async function removeMember(userId) {
  if (!confirm("Remove this member from the channel?")) return;
  try {
    const res = await axios.post(`/api/channel/${CHANNEL_ID}/remove-member`, {
      user_id: userId,
    });
    if (res.data.success) {
      showToast("Member removed!", "success");
      loadMembers();
    }
  } catch (e) {
    const msg = e.response?.data?.error || "Failed.";
    showToast(msg, "error");
  }
}

// ── NEW: LEAVE CHANNEL ────────────────────────────────────
async function leaveChannel() {
  if (!confirm("Leave this channel? You will lose all access.")) return;
  try {
    const res = await axios.post(`/api/channel/${CHANNEL_ID}/leave`);
    if (res.data.success) {
      showToast(res.data.message || "You left the channel.", "success");
      window.location.href = "/dashboard";
    }
  } catch (e) {
    const msg = e.response?.data?.error || "Failed to leave.";
    showToast(msg, "error");
  }
}

// ── JOIN REQUESTS ──────────────────────────────────
async function loadRequestCount() {
  try {
    const res = await axios.get(`/api/channel/${CHANNEL_ID}/requests`);
    const data = res.data;
    const badge = document.getElementById("req-badge");
    if (badge && Array.isArray(data) && data.length > 0) {
      badge.textContent = data.length;
    }
  } catch (e) {}
}

async function loadRequests() {
  const list = document.getElementById("requests-list");
  if (!list) return;
  list.innerHTML = '<div class="loading-state">Loading requests…</div>';

  try {
    const res = await axios.get(`/api/channel/${CHANNEL_ID}/requests`);
    const requests = res.data;
    if (!requests.length) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="es-icon">📥</div>
          <h3>No pending requests</h3>
          <p>All join requests have been handled.</p>
        </div>`;
      return;
    }
    list.innerHTML = requests
      .map(
        (r) => `
      <div class="request-card" id="req-${r.id}">
        <div class="member-info">
          <div class="member-avatar">${r.username[0].toUpperCase()}</div>
          <div>
            <div class="member-name">${escHtml(r.username)}</div>
            <div class="member-email">${escHtml(r.email)}</div>
            <div class="member-joined">Requested ${escHtml(r.created_at)}</div>
          </div>
        </div>
        <div class="request-actions">
          <button class="btn btn-success btn-sm" onclick="handleRequest(${r.id}, 'approve')">✓ Approve</button>
          <button class="btn btn-danger btn-sm"  onclick="handleRequest(${r.id}, 'reject')">✕ Reject</button>
        </div>
      </div>
    `,
      )
      .join("");
  } catch (e) {
    list.innerHTML =
      '<div class="loading-state">Failed to load requests.</div>';
  }
}

async function handleRequest(reqId, action) {
  try {
    const res = await axios.post(`/api/channel/${CHANNEL_ID}/handle-request`, {
      request_id: reqId,
      action,
    });
    if (res.data.success) {
      showToast(
        action === "approve" ? "User approved!" : "Request rejected.",
        "success",
      );
      document.getElementById("req-" + reqId)?.remove();
      loadRequestCount();
    }
  } catch (e) {
    showToast("Failed.", "error");
  }
}

// ── COPY CODE ──────────────────────────────────────
function copyChannelCode() {
  const code = document.getElementById("ch-code-val")?.textContent;
  if (code)
    navigator.clipboard
      .writeText(code)
      .then(() => showToast("Code copied!", "success"));
}

// ── HELPERS ────────────────────────────────────────
function fileIcon(ext) {
  if (!ext) return "📄";
  const e = ext.toLowerCase();
  if (e === "pdf") return "📕";
  if (["doc", "docx"].includes(e)) return "📝";
  if (["xls", "xlsx", "csv"].includes(e)) return "📊";
  if (["ppt", "pptx"].includes(e)) return "📋";
  if (e === "txt") return "📃";
  if (["png", "jpg", "jpeg", "gif", "webp"].includes(e)) return "🖼️";
  if (e === "zip") return "🗜️";
  return "📄";
}

function fileTypeClass(ext) {
  if (!ext) return "ft-other";
  const e = ext.toLowerCase();
  if (e === "pdf") return "ft-pdf";
  if (["doc", "docx"].includes(e)) return "ft-doc";
  if (["xls", "xlsx", "csv"].includes(e)) return "ft-xls";
  if (["ppt", "pptx"].includes(e)) return "ft-ppt";
  if (e === "txt") return "ft-txt";
  if (["png", "jpg", "jpeg", "gif", "webp"].includes(e)) return "ft-img";
  if (e === "zip") return "ft-zip";
  return "ft-other";
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

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
