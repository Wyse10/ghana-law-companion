/**
 * Ghana Law Companion - Modern Client Application Logic
 */

// 26 Official Chapters of the 1992 Constitution of Ghana
const CONSTITUTION_CHAPTERS = [
  { num: "1", title: "The Constitution" },
  { num: "2", title: "Territories of Ghana" },
  { num: "3", title: "Citizenship" },
  { num: "4", title: "The Laws of Ghana" },
  { num: "5", title: "Fundamental Human Rights and Freedoms" },
  { num: "6", title: "The Directive Principles of State Policy" },
  { num: "7", title: "Representation of the People" },
  { num: "8", title: "The Executive" },
  { num: "9", title: "The Council of State" },
  { num: "10", title: "The Legislature" },
  { num: "11", title: "The Judiciary" },
  { num: "12", title: "Freedom and Independence of the Media" },
  { num: "13", title: "Finance" },
  { num: "14", title: "The Public Services" },
  { num: "15", title: "The Police Service" },
  { num: "16", title: "The Prisons Service" },
  { num: "17", title: "The Armed Forces of Ghana" },
  { num: "18", title: "Commission on Human Rights and Administrative Justice" },
  { num: "19", title: "National Commission for Civic Education" },
  { num: "20", title: "Decentralization and Local Government" },
  { num: "21", title: "Lands and Natural Resources" },
  { num: "22", title: "Chieftaincy" },
  { num: "23", title: "Commissions of Inquiry" },
  { num: "24", title: "Code of Conduct for Public Officers" },
  { num: "25", title: "Amendment of the Constitution" },
  { num: "26", title: "Miscellaneous" }
];

// State
let selectedChapterFilter = "";
let currentResponseData = null;

// DOM Elements
const queryForm = document.getElementById("queryForm");
const queryInput = document.getElementById("queryInput");
const chapterSelect = document.getElementById("chapterSelect");
const submitBtn = document.getElementById("submitBtn");
const clearBtn = document.getElementById("clearBtn");
const chapterList = document.getElementById("chapterList");
const suggestionsContainer = document.getElementById("suggestionsContainer");

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const activeFilterBadge = document.getElementById("activeFilterBadge");

const errorBanner = document.getElementById("errorBanner");
const errorTitle = document.getElementById("errorTitle");
const errorMessage = document.getElementById("errorMessage");
const dismissErrorBtn = document.getElementById("dismissErrorBtn");

const loadingState = document.getElementById("loadingState");
const loadingStageText = document.getElementById("loadingStageText");
const resultsSection = document.getElementById("resultsSection");
const answerText = document.getElementById("answerText");
const citationsList = document.getElementById("citationsList");

const metricRetrieval = document.getElementById("metricRetrieval");
const metricGeneration = document.getElementById("metricGeneration");
const metricTotal = document.getElementById("metricTotal");
const metricSources = document.getElementById("metricSources");
const metricRequestId = document.getElementById("metricRequestId");

const copyAnswerBtn = document.getElementById("copyAnswerBtn");
const toast = document.getElementById("toast");

const sidebar = document.getElementById("sidebar");
const openSidebarBtn = document.getElementById("openSidebarBtn");
const closeSidebarBtn = document.getElementById("closeSidebarBtn");

const helpModal = document.getElementById("helpModal");
const helpModalBtn = document.getElementById("helpModalBtn");
const closeHelpBtn = document.getElementById("closeHelpBtn");
const confirmHelpBtn = document.getElementById("confirmHelpBtn");

// Initialize application
document.addEventListener("DOMContentLoaded", () => {
  renderChapters();
  populateChapterSelect();
  checkBackendHealth();
  attachEventListeners();
});

// Render Chapter List in Sidebar
function renderChapters() {
  chapterList.innerHTML = "";
  
  // "All Chapters" item
  const allBtn = document.createElement("button");
  allBtn.type = "button";
  allBtn.className = "chapter-item active";
  allBtn.dataset.chapter = "";
  allBtn.innerHTML = `
    <span class="chapter-num">ALL</span>
    <span class="chapter-title">Entire Constitution (1–26)</span>
  `;
  allBtn.addEventListener("click", () => selectChapter(""));
  chapterList.appendChild(allBtn);

  // Individual Chapters
  CONSTITUTION_CHAPTERS.forEach((ch) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chapter-item";
    btn.dataset.chapter = ch.num;
    btn.innerHTML = `
      <span class="chapter-num">CH ${ch.num}</span>
      <span class="chapter-title">${ch.title}</span>
    `;
    btn.addEventListener("click", () => selectChapter(ch.num));
    chapterList.appendChild(btn);
  });
}

// Populate Chapter dropdown in search bar
function populateChapterSelect() {
  CONSTITUTION_CHAPTERS.forEach((ch) => {
    const opt = document.createElement("option");
    opt.value = ch.num;
    opt.textContent = `Chapter ${ch.num}: ${ch.title}`;
    chapterSelect.appendChild(opt);
  });
}

// Select Chapter (syncs sidebar and dropdown)
function selectChapter(chapterNum) {
  selectedChapterFilter = chapterNum;
  chapterSelect.value = chapterNum;
  activeFilterBadge.textContent = chapterNum ? `Ch ${chapterNum}` : "All";

  // Update active class on sidebar items
  document.querySelectorAll(".chapter-item").forEach((item) => {
    if (item.dataset.chapter === chapterNum) {
      item.classList.add("active");
      item.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else {
      item.classList.remove("active");
    }
  });

  // Close mobile sidebar if open
  sidebar.classList.remove("open");
}

// Check Backend Connectivity
async function checkBackendHealth() {
  try {
    statusDot.className = "status-dot status-checking";
    statusText.textContent = "Checking system...";

    const res = await fetch("/api/health/status", { signal: AbortSignal.timeout(4000) });
    if (!res.ok) {
      const liveRes = await fetch("/api/health/live", { signal: AbortSignal.timeout(3000) });
      if (liveRes.ok) {
        setHealthStatus(true, "BFF Online (FastAPI standby)");
        return;
      }
      throw new Error("Health check failed");
    }

    const data = await res.json();
    if (data.bff === "ok" && data.fastApi === "ok") {
      setHealthStatus(true, "BFF & Core RAG Online");
    } else if (data.bff === "ok") {
      setHealthStatus(true, "BFF Online (Waiting for API)");
    } else {
      setHealthStatus(false, "Service Degraded");
    }
  } catch (err) {
    try {
      const live = await fetch("/api/health/live");
      if (live.ok) {
        setHealthStatus(true, "BFF Online");
        return;
      }
    } catch {
      // Offline
    }
    setHealthStatus(false, "Backend Unreachable");
  }
}

function setHealthStatus(isOnline, message) {
  statusDot.className = isOnline ? "status-dot status-online" : "status-dot status-offline";
  statusText.textContent = message;
}

// Event Listeners
function attachEventListeners() {
  // Query submission
  queryForm.addEventListener("submit", handleSubmit);

  // Keyboard shortcut Ctrl+Enter / Cmd+Enter
  queryInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      queryForm.dispatchEvent(new Event("submit"));
    }
  });

  // Chapter dropdown change
  chapterSelect.addEventListener("change", (e) => {
    selectChapter(e.target.value);
  });

  // Clear button
  clearBtn.addEventListener("click", () => {
    queryInput.value = "";
    queryInput.focus();
    hideError();
  });

  // Suggested questions chips
  suggestionsContainer.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip && chip.dataset.query) {
      queryInput.value = chip.dataset.query;
      queryForm.dispatchEvent(new Event("submit"));
    }
  });

  // Dismiss Error
  dismissErrorBtn.addEventListener("click", hideError);

  // Copy Answer
  copyAnswerBtn.addEventListener("click", copyAnswerText);

  // Mobile sidebar controls
  openSidebarBtn.addEventListener("click", () => sidebar.classList.add("open"));
  closeSidebarBtn.addEventListener("click", () => sidebar.classList.remove("open"));

  // Help Modal controls
  helpModalBtn.addEventListener("click", () => helpModal.classList.remove("hidden"));
  closeHelpBtn.addEventListener("click", () => helpModal.classList.add("hidden"));
  confirmHelpBtn.addEventListener("click", () => helpModal.classList.add("hidden"));
  helpModal.addEventListener("click", (e) => {
    if (e.target === helpModal) helpModal.classList.add("hidden");
  });

  // Escape key closes modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      helpModal.classList.add("hidden");
      sidebar.classList.remove("open");
    }
  });
}

// Handle Query Submission
async function handleSubmit(e) {
  e.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;

  hideError();
  setLoading(true);
  resultsSection.classList.add("hidden");

  const payload = {
    query: query,
    top_k: 5,
    chapter: selectedChapterFilter || null
  };

  try {
    updateLoadingStep("Retrieving constitutional context & semantic embeddings...");

    const response = await fetch("/api/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      let detailMsg = "An unexpected error occurred.";
      if (typeof data.detail === "string") {
        detailMsg = data.detail;
      } else if (data.message) {
        detailMsg = Array.isArray(data.message) ? data.message.join(", ") : data.message;
      }
      throw new Error(detailMsg);
    }

    currentResponseData = data;
    renderResults(data);
  } catch (error) {
    showError(
      "Query Execution Error",
      error.message || "Failed to communicate with the constitutional intelligence service."
    );
  } finally {
    setLoading(false);
  }
}

// Loading indicator controller
function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  if (isLoading) {
    loadingState.classList.remove("hidden");
    loadingStageText.textContent = "Searching constitutional clauses...";
  } else {
    loadingState.classList.add("hidden");
  }
}

function updateLoadingStep(stepMsg) {
  loadingStageText.textContent = stepMsg;
}

// Render Results View
function renderResults(data) {
  resultsSection.classList.remove("hidden");

  // Format and render answer in clear, highly readable format
  const answerObj = data.answer || {};
  const rawAnswer = answerObj.answer || "No response generated.";
  answerText.innerHTML = formatLegalText(rawAnswer);

  // Render verified citation chips
  citationsList.innerHTML = "";
  const citations = answerObj.citations || [];
  if (citations.length === 0) {
    citationsList.innerHTML = `<span style="font-size:12px;color:var(--text-dim);">No citations extracted.</span>`;
  } else {
    citations.forEach((cit) => {
      const badge = document.createElement("span");
      badge.className = "citation-badge";
      badge.innerHTML = `<span>📜</span> ${cit}`;
      citationsList.appendChild(badge);
    });
  }

  // Render timing & stats metrics
  const timing = data.timing || {};
  metricRetrieval.textContent = `${timing.retrieval_ms != null ? timing.retrieval_ms : "--"} ms`;
  metricGeneration.textContent = `${timing.generation_ms != null ? timing.generation_ms : "--"} ms`;
  metricTotal.textContent = `${timing.total_ms != null ? timing.total_ms : "--"} ms`;
  metricSources.textContent = `${data.sources ? data.sources.length : 0} clauses`;
  metricRequestId.textContent = data.request_id ? data.request_id.slice(0, 8) : "--";

  // Smooth scroll to results
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * Intelligent Legal Text Formatter
 * Formats legal answers into highly readable, structured layouts:
 * - Direct answers on their own clear lines.
 * - Semicolon-delimited lists (e.g. "namely: A; B; C") transformed into clean bullet points.
 * - Formats inline listings: (a)..., (b)... or (i)..., (ii)... into structured lists.
 * - Highlights statutory citations: "Article X(Y)" and "Chapter Z".
 */
function formatLegalText(text) {
  if (!text) return "";

  // 1. Normalize line endings
  let content = text.replace(/\r\n/g, "\n").trim();

  // 2. Detect semicolon lists following "namely:", "including:", "following public offices:", etc.
  content = formatSemicolonLists(content);

  // 3. Detect inline lettered listings: (a) ... (b) ... (c) ...
  content = formatLetteredListings(content);

  // 4. Parse into blocks (paragraphs, lists, headings)
  const lines = content.split("\n");
  const htmlBlocks = [];
  let currentList = [];

  function flushList() {
    if (currentList.length > 0) {
      htmlBlocks.push(`
        <ul class="legal-bullet-list">
          ${currentList.map(item => `<li><span class="bullet-check">✓</span><span>${item}</span></li>`).join("\n")}
        </ul>
      `);
      currentList = [];
    }
  }

  for (let rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }

    // Check if line is a bullet point (- or * or •)
    const bulletMatch = line.match(/^[-*•]\s+(.*)$/);
    if (bulletMatch) {
      currentList.push(highlightLegalTerms(escapeHtml(bulletMatch[1])));
      continue;
    }

    // Check if line is a numbered list (e.g. 1. or 2.)
    const numberMatch = line.match(/^(\d+)\.\s+(.*)$/);
    if (numberMatch) {
      flushList();
      htmlBlocks.push(`
        <div class="legal-numbered-item">
          <span class="num-badge">${numberMatch[1]}</span>
          <span class="num-text">${highlightLegalTerms(escapeHtml(numberMatch[2]))}</span>
        </div>
      `);
      continue;
    }

    // Regular paragraph
    flushList();
    const formattedParagraph = highlightLegalTerms(escapeHtml(line));
    htmlBlocks.push(`<p class="legal-paragraph">${formattedParagraph}</p>`);
  }

  flushList();
  return htmlBlocks.join("\n");
}

// Transforms "namely: A; B; C; and D." into bullet points
function formatSemicolonLists(text) {
  const triggerRegex = /(namely|including|the following(?: public offices)?|following cases|restricted from|exceptions:?):?\s*([^.\n]+;[^.\n]+)/i;
  let match = text.match(triggerRegex);

  if (match) {
    const trigger = match[1];
    const rawList = match[2];
    
    // Split by semicolons
    const items = rawList
      .split(/;\s*/)
      .map(item => item.replace(/^(?:and|or)\s+/i, "").trim())
      .filter(item => item.length > 0);

    if (items.length > 1) {
      const bulletItems = items.map(item => `- ${item}`).join("\n");
      const replacement = `${trigger}:\n${bulletItems}\n`;
      text = text.replace(match[0], replacement);
    }
  }

  return text;
}

// Transforms "(a) ... (b) ... (c) ..." or "(i) ... (ii) ..." into bullet points
function formatLetteredListings(text) {
  // If text has (a)... (b)... or (i)... (ii)... in one paragraph
  if (/\([a-z0-9]\)/i.test(text) && !text.includes("\n- ")) {
    // Only split if at least 2 occurrences exist
    const matches = text.match(/\([a-z0-9]\)/gi);
    if (matches && matches.length >= 2) {
      text = text.replace(/\s*\(([a-z0-9])\)\s*/gi, "\n- ");
    }
  }
  return text;
}

// Highlights Article and Chapter references with distinct visual tags
function highlightLegalTerms(escapedText) {
  // Bold **markdown**
  escapedText = escapedText.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  // Highlight statutory references like Article 8(1), Article 14, Chapter 3
  escapedText = escapedText.replace(
    /\b(Article\s+\d+(?:\([0-9a-zA-Z]+\))*)/gi,
    '<strong class="statute-ref">$1</strong>'
  );
  escapedText = escapedText.replace(
    /\b(Chapter\s+\d+)/gi,
    '<strong class="chapter-ref">$1</strong>'
  );

  return escapedText;
}

// Helper: Escape HTML
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// Toast notification
function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, 2800);
}

// Error Banner controls
function showError(title, message) {
  errorTitle.textContent = title;
  errorMessage.textContent = message;
  errorBanner.classList.remove("hidden");
}

function hideError() {
  errorBanner.classList.add("hidden");
}

// Copy Answer Action Handler
function copyAnswerText() {
  if (!currentResponseData || !currentResponseData.answer) return;
  const answer = currentResponseData.answer.answer;
  navigator.clipboard.writeText(answer);
  showToast("Constitutional answer copied!");
}
