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
let currentSessionId = null;
let sessionTurnCount = 0;
let sessionTurns = [];
let activeTurnIndex = -1;

// DOM Elements
const queryForm = document.getElementById("queryForm");
const queryInput = document.getElementById("queryInput");
const chapterSelect = document.getElementById("chapterSelect");
const submitBtn = document.getElementById("submitBtn");
const clearBtn = document.getElementById("clearBtn");
const sidebarNewChatBtn = document.getElementById("sidebarNewChatBtn");
const sessionTurnBadge = document.getElementById("sessionTurnBadge");
const sessionChatList = document.getElementById("sessionChatList");
const suggestionsContainer = document.getElementById("suggestionsContainer");
const conversationIndicator = document.getElementById("conversationIndicator");
const conversationTurnCount = document.getElementById("conversationTurnCount");
const resetSessionBtn = document.getElementById("resetSessionBtn");

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

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
  renderSessionChat();
  populateChapterSelect();
  checkBackendHealth();
  attachEventListeners();
});

// Render Session Chat in Sidebar
function renderSessionChat() {
  if (!sessionChatList) return;
  sessionChatList.innerHTML = "";

  const turnCount = sessionTurns.length;
  if (sessionTurnBadge) {
    sessionTurnBadge.textContent = `${turnCount} ${turnCount === 1 ? "turn" : "turns"}`;
  }

  if (turnCount === 0) {
    const empty = document.createElement("div");
    empty.className = "session-empty-state";
    empty.innerHTML = `
      <span class="empty-icon">💬</span>
      <p class="empty-title">No conversation turns yet</p>
      <p class="empty-desc">Ask a constitutional question. Follow-ups will reference prior turns automatically.</p>
    `;
    sessionChatList.appendChild(empty);
    return;
  }

  sessionTurns.forEach((item, index) => {
    const card = document.createElement("div");
    card.className = `session-turn-item ${index === activeTurnIndex ? "active" : ""}`;
    card.dataset.index = index;

    // Snippet of the answer
    let cleanAnswer = (item.answer || "").replace(/\s+/g, " ").trim();
    if (cleanAnswer.length > 90) {
      cleanAnswer = cleanAnswer.slice(0, 90) + "...";
    }

    // Citations pills
    const citationsHtml = (item.citations || [])
      .slice(0, 3)
      .map((cit) => `<span class="session-turn-cit-pill">📜 ${escapeHtml(cit)}</span>`)
      .join("");

    card.innerHTML = `
      <div class="session-turn-header">
        <span class="session-turn-badge">Turn ${item.turn}</span>
        <span class="session-turn-time">${escapeHtml(item.time)}</span>
      </div>
      <div class="session-turn-query">
        <span class="turn-icon">👤</span>
        <span>${escapeHtml(item.query)}</span>
      </div>
      <div class="session-turn-answer-snippet">
        <span class="turn-icon">⚖️</span>
        <span>${escapeHtml(cleanAnswer)}</span>
      </div>
      ${citationsHtml ? `<div class="session-turn-citations">${citationsHtml}</div>` : ""}
    `;

    card.addEventListener("click", () => {
      activeTurnIndex = index;
      renderSessionChat();
      if (item.data) {
        renderResults(item.data, item.query, false);
      }
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
      sidebar.classList.remove("open");
    });

    sessionChatList.appendChild(card);
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

// Select Chapter (syncs dropdown filter)
function selectChapter(chapterNum) {
  selectedChapterFilter = chapterNum;
  if (chapterSelect) {
    chapterSelect.value = chapterNum;
  }
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

  // Reset conversation button
  if (resetSessionBtn) {
    resetSessionBtn.addEventListener("click", resetConversation);
  }

  // Sidebar New Chat button
  if (sidebarNewChatBtn) {
    sidebarNewChatBtn.addEventListener("click", resetConversation);
  }

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
    chapter: selectedChapterFilter || null,
    session_id: currentSessionId || null
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
    renderResults(data, query, true);
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
function renderResults(data, query = "", addToHistory = true) {
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

  // Multi-turn conversational session tracking
  if (data.session_id) {
    currentSessionId = data.session_id;
  }
  if (Array.isArray(data.history)) {
    sessionTurnCount = Math.floor(data.history.length / 2);
  } else {
    sessionTurnCount++;
  }
  updateConversationUI();

  // Add turn to session chat list on the left sidebar
  if (addToHistory) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    sessionTurns.push({
      turn: sessionTurnCount || sessionTurns.length + 1,
      query: query || queryInput.value.trim() || "Constitutional Question",
      answer: rawAnswer,
      citations: citations,
      time: timeStr,
      data: data,
    });
    activeTurnIndex = sessionTurns.length - 1;
    renderSessionChat();
  }

  // Smooth scroll to results
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Update UI to reflect multi-turn conversation status
function updateConversationUI() {
  if (sessionTurnCount > 0 && conversationIndicator) {
    conversationIndicator.classList.remove("hidden");
    if (conversationTurnCount) {
      conversationTurnCount.textContent = sessionTurnCount;
    }
    queryInput.placeholder = "Ask a contextual follow-up (e.g. 'Does that exception apply to non-citizens?')...";
  } else if (conversationIndicator) {
    conversationIndicator.classList.add("hidden");
    queryInput.placeholder = "E.g., What are the valid grounds for restricting personal liberty under Article 14?";
  }
}

// Reset conversational memory session
async function resetConversation() {
  if (currentSessionId) {
    try {
      await fetch(`/api/session/${encodeURIComponent(currentSessionId)}`, {
        method: "DELETE",
      });
    } catch (_) {}
  }
  currentSessionId = null;
  sessionTurnCount = 0;
  sessionTurns = [];
  activeTurnIndex = -1;
  renderSessionChat();
  updateConversationUI();
  resultsSection.classList.add("hidden");
  queryInput.value = "";
  queryInput.focus();
  showToast("Started fresh conversation.");
}

/**
 * Intelligent Legal Text Formatter
 * Formats legal answers into highly readable, structured layouts:
 * - Direct answers ("Yes.", "No.") highlighted in a dedicated verdict banner with core finding.
 * - Clear paragraph breaks between general rules, provisions, and subsequent restrictions/exceptions.
 * - Semicolon-delimited lists (e.g. "namely: A; B; C") transformed into structured bullet points.
 * - Comma-delimited lists following list triggers transformed into structured bullet points.
 * - Lettered listings: (a)..., (b)... transformed into structured lists.
 * - Highlights statutory citations: "Article X(Y)", "Chapter Z", and "Clause N".
 * - Eliminates stray punctuation artifacts.
 */
function formatLegalText(text) {
  if (!text) return "";

  // 1. Normalize spaces, non-breaking spaces, and non-breaking hyphens
  let content = text
    .replace(/[\u202f\u00a0]/g, " ")
    .replace(/\u2011/g, "-")
    .replace(/\r\n/g, "\n")
    .trim();

  // 2. Extract direct affirmative/negative verdict if present at start
  let directVerdictHtml = "";
  const verdictPrefixMatch = content.match(/^(Yes|No)\.\s*/i);
  if (verdictPrefixMatch) {
    const isAffirmative = verdictPrefixMatch[1].toLowerCase() === "yes";
    const badgeClass = isAffirmative ? "verdict-yes" : "verdict-no";
    const badgeText = isAffirmative ? "YES" : "NO";
    const badgeIcon = isAffirmative ? "✓" : "✕";

    content = content.slice(verdictPrefixMatch[0].length).trim();

    // The first sentence becomes the core constitutional finding
    const firstPeriodIdx = content.indexOf(".");
    if (firstPeriodIdx !== -1 && firstPeriodIdx < 250) {
      const leadSentence = content.slice(0, firstPeriodIdx).trim();
      content = content.slice(firstPeriodIdx + 1).trim();

      directVerdictHtml = `
        <div class="direct-answer-callout ${badgeClass}">
          <div class="callout-header">
            <span class="verdict-pill"><span class="verdict-icon">${badgeIcon}</span> ${badgeText}</span>
            <span class="callout-label">Direct Constitutional Finding</span>
          </div>
          <p class="callout-text">${highlightLegalTerms(escapeHtml(leadSentence))}.</p>
        </div>
      `;
    } else {
      directVerdictHtml = `
        <div class="direct-answer-callout ${badgeClass}">
          <span class="verdict-pill"><span class="verdict-icon">${badgeIcon}</span> ${badgeText}</span>
        </div>
      `;
    }
  }

  // 3. Separate sentence transitions into clear paragraphs
  content = content.replace(/([.!?])\s+(However|Furthermore|Additionally|In addition|Specifically|Under Article|Article\s+\d+|Nevertheless|Subject to)/g, "$1\n\n$2");

  // 4. Transform semicolon lists into bullets
  content = formatSemicolonLists(content);

  // 5. Transform comma lists following list triggers into bullets
  content = formatCommaSeparatedLists(content);

  // 6. Transform lettered listings (a)... (b)... into bullets
  content = formatLetteredListings(content);

  // 7. Parse lines into structured HTML blocks
  const lines = content.split("\n");
  const htmlBlocks = directVerdictHtml ? [directVerdictHtml] : [];
  let currentList = [];

  function flushList() {
    if (currentList.length > 0) {
      htmlBlocks.push(`
        <ul class="legal-bullet-list">
          ${currentList.map(item => `<li><span class="bullet-icon">⚖️</span><span>${item}</span></li>`).join("\n")}
        </ul>
      `);
      currentList = [];
    }
  }

  for (let rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line === ".") {
      flushList();
      continue;
    }

    // Check if line is a bullet point (- or * or •)
    const bulletMatch = line.match(/^[-*•]\s+(.*)$/);
    if (bulletMatch) {
      let itemText = bulletMatch[1].trim();
      itemText = itemText.replace(/^\([a-z0-9]+\)\s*/i, "");
      itemText = itemText.replace(/^(?:and|or)\s+/i, "");
      if (itemText.length > 0) {
        itemText = itemText.charAt(0).toUpperCase() + itemText.slice(1);
      }
      currentList.push(highlightLegalTerms(escapeHtml(itemText)));
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

    flushList();
    const formattedParagraph = highlightLegalTerms(escapeHtml(line));
    htmlBlocks.push(`<p class="legal-paragraph">${formattedParagraph}</p>`);
  }

  flushList();
  return htmlBlocks.join("\n");
}

// Transforms "namely: A; B; C; and D." into bullet points
function formatSemicolonLists(text) {
  const triggerRegex = /(namely|including|the following(?: public offices)?|following cases|restricted from|exceptions):?:?\s*([^.\n]+(?:;[^.\n]+)+)\.?/i;
  let match = text.match(triggerRegex);

  if (match) {
    const trigger = match[1].replace(/:+$/, "");
    const rawList = match[2];

    const items = rawList
      .split(/;\s*/)
      .map(item => item.replace(/^(?:and|or)\s+/i, "").replace(/[.;]+$/, "").trim())
      .filter(item => item.length > 0)
      .map(item => item.charAt(0).toUpperCase() + item.slice(1));

    if (items.length > 1) {
      const bulletItems = items.map(item => `- ${item}`).join("\n");
      const replacement = `${trigger}:\n${bulletItems}\n`;
      text = text.replace(match[0], replacement);
    }
  }

  return text;
}

// Transforms comma lists following explicit list triggers into bullet points
function formatCommaSeparatedLists(text) {
  if (text.includes("\n- ") || text.includes(";")) {
    return text;
  }

  const triggerRegex = /(cannot be appointed as|restricted from being appointed (?:as|to)|disqualified from holding(?: the)? offices? (?:of)?|prohibited from being appointed as|namely|such as|the following(?: public offices)?):?:?\s+([^.]+)/i;
  let match = text.match(triggerRegex);

  if (match && match[2].includes(",")) {
    const trigger = match[1].replace(/:+$/, "");
    const rawList = match[2];

    const items = rawList
      .split(/,\s+(?:and\s+|or\s+)?/)
      .map(item => item.replace(/^(?:an|a|the)\s+/i, "").replace(/^(?:and|or)\s+/i, "").replace(/[.;]+$/, "").trim())
      .filter(item => item.length > 2)
      .map(item => item.charAt(0).toUpperCase() + item.slice(1));

    if (items.length >= 3) {
      const bulletItems = items.map(item => `- ${item}`).join("\n");
      const replacement = `${trigger}:\n${bulletItems}\n`;
      text = text.replace(match[0], replacement);
    }
  }

  return text;
}

// Transforms "(a) ... (b) ... (c) ..." or "(i) ... (ii) ..." into bullet points
function formatLetteredListings(text) {
  if (/\([a-z0-9]\)/i.test(text) && !text.includes("\n- ")) {
    const matches = text.match(/\([a-z0-9]\)/gi);
    if (matches && matches.length >= 2) {
      text = text.replace(/\s*\(([a-z0-9])\)\s*/gi, "\n- ");
    }
  }
  return text;
}

// Highlights Article, Chapter, Clause, and Section references with distinct visual tags
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
  escapedText = escapedText.replace(
    /\b(Clause\s+\d+(?:\([0-9a-zA-Z]+\))*)/gi,
    '<strong class="statute-ref">$1</strong>'
  );
  escapedText = escapedText.replace(
    /\b(Section\s+\d+)/gi,
    '<strong class="statute-ref">$1</strong>'
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
