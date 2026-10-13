// PaperMind frontend — talks to the FastAPI endpoints in server.py.
// Served by the same server, so an empty base means "same origin".
const API_BASE = "";

const $ = (selector) => document.querySelector(selector);
const fileInput = $("#fileInput");
const dropzone = $("#dropzone");
const questionInput = $("#questionInput");
const chatForm = $("#chatForm");
const sendBtn = $("#sendBtn");
const conversation = $("#conversation");
const welcomeCard = $("#welcomeCard");

const state = {
  documents: [],
  isUploading: false,
  isAsking: false,
  apiOnline: false,
};

function showToast(message, type = "") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`.trim();
  toast.textContent = message;
  $("#toastRegion").appendChild(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

function setConnection(online, label) {
  state.apiOnline = online;
  $("#connectionDot").className =
    `connection-dot ${online ? "online" : "offline"}`;
  $("#connectionLabel").textContent = label;
  updateComposerState();
}

async function checkHealth(showMessage = false) {
  $("#connectionLabel").textContent = "Checking API…";
  $("#connectionDot").className = "connection-dot";
  try {
    const response = await fetch(`${API_BASE}/health`, { method: "GET" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    setConnection(true, "API Connected");
    if (showMessage) showToast("Connected to your FastAPI server.", "success");
    if (Number.isFinite(data.indexed_chunks)) {
      $("#summaryChunkCount").textContent = `${data.indexed_chunks} chunks`;
    }
  } catch (error) {
    setConnection(false, "API Offline");
    if (showMessage) {
      showToast(
        `Cannot reach the server at ${window.location.origin}. Make sure it is running.`,
        "error",
      );
    }
  }
}

function updateComposerState() {
  const hasDocs = state.documents.length > 0;
  questionInput.disabled = !state.apiOnline || !hasDocs || state.isAsking;
  sendBtn.disabled = questionInput.disabled || !questionInput.value.trim();
}

function updateCounts(totalChunks = null) {
  const count = state.documents.length;
  $("#docCount").textContent = count;
  $("#panelDocCount").textContent =
    `${count} ${count === 1 ? "file" : "files"}`;
  $("#summaryDocCount").textContent =
    `${count} ${count === 1 ? "file" : "files"}`;
  $("#allDocsLabel").textContent =
    `${count} ${count === 1 ? "document" : "documents"}`;
  if (totalChunks !== null)
    $("#summaryChunkCount").textContent = `${totalChunks} chunks`;
  renderDocuments();
  updateComposerState();
}

function createDocumentItem(doc, detailed = false) {
  const item = document.createElement("div");
  item.className = "document-item";

  const icon = document.createElement("div");
  icon.className = "pdf-icon";
  icon.textContent = "PDF";

  const info = document.createElement("div");
  info.className = "document-info";
  const name = document.createElement("strong");
  name.textContent = doc.filename;
  name.title = doc.filename;
  const meta = document.createElement("span");
  const parts = [];
  if (Number.isFinite(doc.pages)) parts.push(`${doc.pages} pages`);
  if (Number.isFinite(doc.chunks)) parts.push(`${doc.chunks} chunks indexed`);
  parts.push(doc.status || "Indexed");
  meta.textContent = parts.join(" · ") || "Indexed";
  info.append(name, meta);

  const check = document.createElement("span");
  check.className = "document-check";
  check.textContent = "✓";
  item.append(icon, info, check);
  if (detailed) item.classList.add("detailed-document");
  return item;
}

function renderDocuments() {
  const sideList = $("#documentList");
  const libraryList = $("#libraryList");
  const allList = $("#allDocumentsList");
  sideList.replaceChildren();
  libraryList.replaceChildren();
  allList.replaceChildren();

  if (!state.documents.length) {
    sideList.appendChild(
      makeEmptyDocuments(
        "No documents yet",
        "Upload a PDF to build your knowledge base.",
      ),
    );
    allList.appendChild(
      makeEmptyDocuments(
        "Your library is ready",
        "Uploaded PDFs will be listed here.",
        true,
      ),
    );
    const empty = document.createElement("div");
    empty.className = "library-empty";
    const icon = document.createElement("span");
    icon.className = "tiny-file";
    icon.textContent = "▧";
    const label = document.createElement("span");
    label.textContent = "Your PDFs will appear here";
    empty.append(icon, label);
    libraryList.appendChild(empty);
    return;
  }

  state.documents.forEach((doc) => {
    sideList.appendChild(createDocumentItem(doc));
    allList.appendChild(createDocumentItem(doc, true));
    const row = document.createElement("div");
    row.className = "library-file";
    const icon = document.createElement("span");
    icon.className = "library-pdf";
    icon.textContent = "▤";
    const label = document.createElement("span");
    label.textContent = doc.filename;
    label.title = doc.filename;
    row.append(icon, label);
    libraryList.appendChild(row);
  });
}

function makeEmptyDocuments(title, description, large = false) {
  const empty = document.createElement("div");
  empty.className = `empty-docs${large ? " large-empty" : ""}`;
  const icon = document.createElement("div");
  icon.className = "empty-doc-icon";
  icon.textContent = "▤";
  const heading = document.createElement("strong");
  heading.textContent = title;
  const detail = document.createElement("span");
  detail.textContent = description;
  empty.append(icon, heading, detail);
  return empty;
}

function showUploadProgress(filename, message = "Processing PDF…") {
  $("#uploadProgressWrap").hidden = false;
  $("#uploadProgressName").textContent = filename;
  $("#uploadProgressPercent").textContent = message;
  $("#uploadProgressBar").style.width = "65%";
}

function hideUploadProgress() {
  $("#uploadProgressWrap").hidden = true;
  $("#uploadProgressBar").style.width = "0%";
}

async function uploadOnePdf(file) {
  if (
    !file.name.toLowerCase().endsWith(".pdf") &&
    file.type !== "application/pdf"
  ) {
    showToast(`${file.name}: only PDF files are supported.`, "error");
    return;
  }

  state.isUploading = true;
  showUploadProgress(file.name, "Uploading & indexing");
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: formData,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `Upload failed (HTTP ${response.status})`);
    }

    // If a filename was uploaded before, update its entry rather than duplicating it in the UI.
    const doc = {
      filename: data.filename || file.name,
      pages: data.pages_processed,
      chunks: data.chunks_indexed,
      status: "Indexed",
    };
    const existingIndex = state.documents.findIndex(
      (item) => item.filename === doc.filename,
    );
    if (existingIndex >= 0) state.documents[existingIndex] = doc;
    else state.documents.push(doc);

    updateCounts(data.total_indexed_chunks);
    $("#uploadProgressBar").style.width = "100%";
    $("#uploadProgressPercent").textContent = "Complete";
    showToast(
      `${doc.filename} indexed successfully. You can ask questions now.`,
      "success",
    );
  } catch (error) {
    showToast(error.message || "Unable to upload this PDF.", "error");
  } finally {
    state.isUploading = false;
    window.setTimeout(hideUploadProgress, 700);
    updateComposerState();
    fileInput.value = "";
  }
}

async function uploadFiles(files) {
  const pdfs = Array.from(files || []);
  if (!pdfs.length) return;
  for (const file of pdfs) {
    // Sequential uploads prevent concurrent indexing requests from overloading the API.
    await uploadOnePdf(file);
  }
}

function appendMessage(role, text, sources = []) {
  const currentWelcome = $("#welcomeCard");
  if (currentWelcome) currentWelcome.remove();

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "assistant" ? "✦" : "You";

  const content = document.createElement("div");
  content.className = "message-content";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "assistant" ? "PaperMind AI" : "You";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  // textContent (not innerHTML) so model responses cannot inject markup or scripts.
  bubble.textContent = text;

  content.append(meta, bubble);

  if (role === "assistant" && Array.isArray(sources) && sources.length) {
    const sourceArea = document.createElement("div");
    sourceArea.className = "source-area";
    const label = document.createElement("div");
    label.className = "message-meta";
    label.textContent = "Sources";
    content.appendChild(label);

    sources.forEach((source) => {
      const chip = document.createElement("div");
      chip.className = "source-chip";
      const icon = document.createElement("span");
      icon.textContent = "▤";
      const sourceText = document.createElement("span");
      const pageText = Number.isInteger(source.page)
        ? ` · p. ${source.page}`
        : "";
      sourceText.textContent = `${source.filename || "PDF"}${pageText}`;
      chip.append(icon, sourceText);
      sourceArea.appendChild(chip);
    });
    content.appendChild(sourceArea);
  }

  if (role === "user") row.append(content, avatar);
  else row.append(avatar, content);
  conversation.appendChild(row);
  conversation.scrollTop = conversation.scrollHeight;
  return row;
}

function addTypingIndicator() {
  const currentWelcome = $("#welcomeCard");
  if (currentWelcome) currentWelcome.remove();
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.id = "typingIndicator";
  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = "✦";
  const content = document.createElement("div");
  content.className = "message-content";
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = "PaperMind AI is thinking";
  const bubble = document.createElement("div");
  bubble.className = "message-bubble typing-bubble";
  for (let i = 0; i < 3; i++) bubble.appendChild(document.createElement("i"));
  content.append(meta, bubble);
  row.append(avatar, content);
  conversation.appendChild(row);
  conversation.scrollTop = conversation.scrollHeight;
  return row;
}

// Always return plain text, even if the API sends Gemini-style content blocks.
function extractText(answer) {
  if (typeof answer === "string") return answer.trim();
  if (Array.isArray(answer)) {
    return answer
      .map((block) =>
        typeof block === "string"
          ? block
          : block && block.type === "text"
            ? block.text || ""
            : "",
      )
      .join("")
      .trim();
  }
  if (answer && typeof answer === "object" && typeof answer.text === "string")
    return answer.text.trim();
  return "";
}

async function askQuestion(question) {
  const cleanQuestion = question.trim();
  if (!cleanQuestion || state.isAsking) return;

  if (!state.documents.length) {
    showToast("Upload at least one PDF before asking a question.", "error");
    return;
  }
  if (!state.apiOnline) {
    showToast("Your API is offline. Start FastAPI and retry.", "error");
    await checkHealth();
    return;
  }

  appendMessage("user", cleanQuestion);
  questionInput.value = "";
  resizeTextarea();
  state.isAsking = true;
  updateComposerState();
  const typing = addTypingIndicator();

  try {
    const response = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: cleanQuestion }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok)
      throw new Error(
        data.detail || `Request failed (HTTP ${response.status})`,
      );

    typing.remove();
    appendMessage(
      "assistant",
      extractText(data.answer) || "No answer was returned.",
      Array.isArray(data.sources) ? data.sources : [],
    );
  } catch (error) {
    typing.remove();
    appendMessage(
      "assistant",
      `I couldn't get an answer from the API.\n\n${error.message || "Please check that the FastAPI server is running."}`,
    );
    showToast("Question request failed. Check the API connection.", "error");
  } finally {
    state.isAsking = false;
    updateComposerState();
    questionInput.focus();
  }
}

function resizeTextarea() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 130)}px`;
  updateComposerState();
}

function showView(viewName) {
  const isChat = viewName === "chat";
  $("#chatView").classList.toggle("active-view", isChat);
  $("#documentsView").classList.toggle("active-view", !isChat);
  $("#chatNav").classList.toggle("active", isChat);
  $("#documentsNav").classList.toggle("active", !isChat);
  $("#topbarSection").textContent = isChat ? "AI Chat" : "Documents";
  closeMobileSidebar();
}

function openMobileSidebar() {
  $("#sidebar").classList.add("open");
  $("#mobileOverlay").classList.add("show");
}

function closeMobileSidebar() {
  $("#sidebar").classList.remove("open");
  $("#mobileOverlay").classList.remove("show");
}

function startNewConversation() {
  conversation.replaceChildren();
  const card = document.createElement("div");
  card.className = "welcome-card";
  card.id = "welcomeCard";
  const iconWrap = document.createElement("div");
  iconWrap.className = "welcome-icon";
  iconWrap.textContent = "✦";
  const heading = document.createElement("h2");
  heading.textContent = "Ready for a new conversation?";
  const description = document.createElement("p");
  description.textContent = state.documents.length
    ? "Your indexed PDFs are ready. Ask a new question whenever you like."
    : "Upload a PDF to get started, then ask a question about its contents.";
  card.append(iconWrap, heading, description);
  conversation.appendChild(card);
  showView("chat");
  questionInput.focus();
}

$("#browseBtn").addEventListener("click", (event) => {
  event.stopPropagation();
  fileInput.click();
});
dropzone.addEventListener("click", (event) => {
  if (event.target.closest(".text-button")) return;
  fileInput.click();
});
dropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => uploadFiles(fileInput.files));

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragover");
  });
});
dropzone.addEventListener("drop", (event) =>
  uploadFiles(event.dataTransfer.files),
);

$("#uploadTopBtn").addEventListener("click", () => fileInput.click());
$("#uploadDocumentsBtn").addEventListener("click", () => fileInput.click());
$("#healthRefreshBtn").addEventListener("click", () => checkHealth(true));
$("#newChatBtn").addEventListener("click", startNewConversation);
$("#chatNav").addEventListener("click", () => showView("chat"));
$("#documentsNav").addEventListener("click", () => showView("documents"));
$("#mobileMenuBtn").addEventListener("click", openMobileSidebar);
$("#mobileOverlay").addEventListener("click", closeMobileSidebar);

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  askQuestion(questionInput.value);
});
questionInput.addEventListener("input", resizeTextarea);
questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!sendBtn.disabled) chatForm.requestSubmit();
  }
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    if (!state.documents.length) {
      showToast(
        "Upload a PDF first, then try one of these suggested questions.",
        "error",
      );
      fileInput.click();
      return;
    }
    questionInput.value = button.dataset.question || "";
    resizeTextarea();
    questionInput.focus();
  });
});

// The UI tracks uploads made during this browser session only.
// ChromaDB itself stays persistent on the server.
renderDocuments();
checkHealth();
window.setInterval(() => {
  if (!state.apiOnline) checkHealth();
}, 15000);
