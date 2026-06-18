// popup.js — handles UI logic, communicates with FastAPI backend
const API_BASE = "http://localhost:8000";

const summaryBox = document.getElementById("summary-box");
const wordCount = document.getElementById("word-count");
const pageUrl = document.getElementById("page-url");
const questionInput = document.getElementById("question-input");
const askBtn = document.getElementById("ask-btn");
const chatHistory = document.getElementById("chat-history");
const errorContainer = document.getElementById("error-container");

let currentHtml = "";
let currentUrl = "";

// ── Helpers ──────────────────────────────────────────────────────────────────
function showError(msg) {
  errorContainer.innerHTML = `<div class="error-box">⚠️ ${msg}</div>`;
}

function clearError() {
  errorContainer.innerHTML = "";
}

function addMessage(text, role, badge = null) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  if (badge) {
    div.innerHTML = `<span class="tool-badge">${badge}</span><br>${text}`;
  } else {
    div.textContent = text;
  }
  chatHistory.appendChild(div);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function setInputEnabled(enabled) {
  questionInput.disabled = !enabled;
  askBtn.disabled = !enabled;
}

// ── Get page content from content script ─────────────────────────────────────
async function getPageContent() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return reject("No active tab.");
      currentUrl = tabs[0].url || "";
      pageUrl.textContent = currentUrl.length > 45
        ? currentUrl.substring(0, 45) + "..."
        : currentUrl;

      chrome.scripting.executeScript(
        {
          target: { tabId: tabs[0].id },
          func: () => document.documentElement.outerHTML,
        },
        (results) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError.message);
          } else {
            resolve(results[0].result);
          }
        }
      );
    });
  });
}

// ── Summarise page on popup open ─────────────────────────────────────────────
async function summarisePage() {
  try {
    currentHtml = await getPageContent();
  } catch (err) {
    summaryBox.textContent = "Could not access page content.";
    showError(`Page access error: ${err}`);
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ html: currentHtml, url: currentUrl }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    summaryBox.textContent = data.summary;
    if (data.word_count > 0) {
      wordCount.textContent = `~${data.word_count.toLocaleString()} words on this page`;
    }

    // Enable Q&A now that we have page content
    setInputEnabled(true);
    clearError();

  } catch (err) {
    summaryBox.textContent = "Could not summarise this page.";
    showError(`Backend error: ${err.message}. Is the server running on port 8000?`);
  }
}

// ── Ask a question ────────────────────────────────────────────────────────────
async function askQuestion() {
  const question = questionInput.value.trim();
  if (!question || !currentHtml) return;

  addMessage(question, "user");
  questionInput.value = "";
  setInputEnabled(false);

  // Thinking indicator
  const thinking = document.createElement("div");
  thinking.className = "message agent";
  thinking.innerHTML = '<div class="loading"><div class="spinner"></div> Thinking...</div>';
  chatHistory.appendChild(thinking);
  chatHistory.scrollTop = chatHistory.scrollHeight;

  try {
    const res = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        html: currentHtml,
        question: question,
        url: currentUrl,
      }),
    });

    chatHistory.removeChild(thinking);

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    addMessage(data.answer, "agent", `RAG · ${data.source_chunks} chunks`);
    clearError();

  } catch (err) {
    chatHistory.removeChild(thinking);
    addMessage(`Error: ${err.message}`, "agent", "error");
  }

  setInputEnabled(true);
  questionInput.focus();
}

// ── Event listeners ───────────────────────────────────────────────────────────
askBtn.addEventListener("click", askQuestion);
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    askQuestion();
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────
summarisePage();
