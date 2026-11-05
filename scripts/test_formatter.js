const fs = require('fs');

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function highlightLegalTerms(escapedText) {
  escapedText = escapedText.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
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

function formatSemicolonLists(text) {
  const triggerRegex = /(namely|including|the following(?: public offices)?|following cases|restricted from|exceptions:?):?\s*([^.\n]+;[^.\n]+)/i;
  let match = text.match(triggerRegex);

  if (match) {
    const trigger = match[1];
    const rawList = match[2];
    
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

function formatLetteredListings(text) {
  if (/\([a-z0-9]\)/i.test(text) && !text.includes("\n- ")) {
    const matches = text.match(/\([a-z0-9]\)/gi);
    if (matches && matches.length >= 2) {
      text = text.replace(/\s*\(([a-z0-9])\)\s*/gi, "\n- ");
    }
  }
  return text;
}

function formatCommaSeparatedLists(text) {
  // If text has "cannot be appointed as an X, Y, Z, or any other..." or "namely: X, Y, Z"
  const listTriggers = /(?:cannot be appointed as|restricted from being appointed (?:as|to)|disqualified from holding(?: the)? offices? (?:of)?|prohibited from being appointed as|namely:?|such as|the following:?)\s+([^.]+)/i;
  const match = text.match(listTriggers);
  if (match && match[1].includes(",")) {
    const rawList = match[1];
    const items = rawList
      .split(/,\s+(?:and\s+|or\s+)?/)
      .map(item => item.replace(/^(?:an|a|the)\s+/i, "").replace(/^(?:and|or)\s+/i, "").trim())
      .filter(item => item.length > 3);

    if (items.length >= 3) {
      const prefix = text.slice(0, match.index + match[0].indexOf(match[1]));
      const suffix = text.slice(match.index + match[0].length);
      const bullets = items.map(it => `- ${it.charAt(0).toUpperCase() + it.slice(1)}`).join("\n");
      return `${prefix.trim()}\n${bullets}\n${suffix.trim()}`;
    }
  }
  return text;
}

function formatLegalText(text) {
  if (!text) return "";

  // Replace narrow no-break space \u202f or non-breaking space \u00a0 with normal space
  let content = text.replace(/[\u202f\u00a0]/g, " ").replace(/\r\n/g, "\n").trim();

  // If text begins with "Yes." or "No.", place on its own clear introductory line
  content = content.replace(/^(Yes|No)\.\s+/i, "$1.\n\n");

  // Separate distinct sentences into paragraphs if long
  content = content.replace(/([.!?])\s+(However|Furthermore|Additionally|In addition|Under Article|Article\s+\d+)/g, "$1\n\n$2");

  // Semicolon lists
  content = formatSemicolonLists(content);

  // Comma lists
  content = formatCommaSeparatedLists(content);

  // Lettered listings
  content = formatLetteredListings(content);

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

    const bulletMatch = line.match(/^[-*•]\s+(.*)$/);
    if (bulletMatch) {
      currentList.push(highlightLegalTerms(escapeHtml(bulletMatch[1])));
      continue;
    }

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

const input1 = "Yes. Under Article 8(1) of Chapter 3 a citizen of Ghana may hold the citizenship of any other country. However, Article 8(2) bars a Ghanaian who also holds another citizenship from being appointed to certain public offices, namely: Ambassador or High Commissioner; Secretary to the Cabinet; Chief of Defence Staff or any Service Chief; Inspector-General of Police; Commissioner, Customs, Excise and Preventive Service; Director of Immigration Service; and any office specified by an Act of Parliament.";
console.log("=== FORMATTED OUTPUT 1 (User's Exact Example) ===");
console.log(formatLegalText(input1));

const input2 = "Yes. Article 8(1) of the Constitution confirms that a Ghanaian citizen may hold citizenship of another country in addition to Ghanaian citizenship. However, Article 8(2) imposes restrictions on the appointment of dual citizens to certain public offices. A dual citizen cannot be appointed as an Ambassador or High Commissioner, Secretary to the Cabinet, Chief of Defence Staff or any Service Chief, Inspector-General of Police, Commissioner of Customs, Excise and Preventive Service, Director of the Immigration Service, or to any other office that Parliament may specify by law.";
console.log("\n=== FORMATTED OUTPUT 2 (Comma separated list) ===");
console.log(formatLegalText(input2));
