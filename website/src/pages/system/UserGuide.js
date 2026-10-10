import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getUserGuide } from "../../services/API";

// Minimal, dependency-free markdown renderer. The content is our own
// USER_GUIDE.md (trusted, shipped in the repo), not user input, so we keep the
// bundle lean rather than pulling in a full markdown library that would need to
// npm-install on every Pi update. HTML is still escaped defensively.
function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Inline formatting: bold, inline code, links. Operates on already-escaped text.
function renderInline(text) {
  let t = text;
  // Links [label](url)
  t = t.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_m, label, url) =>
      `<a href="${encodeURI(url)}" target="_blank" rel="noopener noreferrer" style="color:#4ea1ff">${label}</a>`
  );
  // Bold **text**
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // Inline code `code`
  t = t.replace(
    /`([^`]+)`/g,
    '<code style="background:#1a1a1a;padding:1px 5px;border-radius:4px;font-size:0.9em">$1</code>'
  );
  return t;
}

// Block-level markdown → HTML. Handles headings, hr, tables, ordered/unordered
// lists, fenced code blocks, and paragraphs — the subset USER_GUIDE.md uses.
function markdownToHtml(md) {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;

  const flushParagraph = (buf) => {
    if (buf.length) {
      out.push(`<p style="line-height:1.7;margin:0.6em 0">${renderInline(escapeHtml(buf.join(" ")))}</p>`);
      buf.length = 0;
    }
  };

  let para = [];

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (/^```/.test(line)) {
      flushParagraph(para);
      const code = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) {
        code.push(lines[i]);
        i++;
      }
      i++; // closing fence
      out.push(
        `<pre style="background:#0e0e0e;padding:0.7em;border-radius:6px;overflow:auto"><code style="font-size:0.85em;color:#cfe3cf">${escapeHtml(code.join("\n"))}</code></pre>`
      );
      continue;
    }

    // Horizontal rule
    if (/^---+\s*$/.test(line)) {
      flushParagraph(para);
      out.push('<hr style="border:none;border-top:1px solid #333;margin:1.2em 0" />');
      i++;
      continue;
    }

    // Heading
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushParagraph(para);
      const level = h[1].length;
      const sizes = { 1: "1.6em", 2: "1.3em", 3: "1.1em", 4: "1em", 5: "0.95em", 6: "0.9em" };
      out.push(
        `<h${level} style="font-size:${sizes[level]};margin:1em 0 0.4em;color:#fff">${renderInline(escapeHtml(h[2]))}</h${level}>`
      );
      i++;
      continue;
    }

    // Table (header row | --- | rows)
    if (/^\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      flushParagraph(para);
      const parseRow = (row) =>
        row
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((c) => c.trim());
      const header = parseRow(line);
      i += 2; // skip header + separator
      const rows = [];
      while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) {
        rows.push(parseRow(lines[i]));
        i++;
      }
      let table =
        '<table style="border-collapse:collapse;width:100%;margin:0.6em 0;font-size:0.9em"><thead><tr>';
      header.forEach((c) => {
        table += `<th style="border:1px solid #333;padding:5px 8px;text-align:left;background:#1a1a1a">${renderInline(escapeHtml(c))}</th>`;
      });
      table += "</tr></thead><tbody>";
      rows.forEach((r) => {
        table += "<tr>";
        r.forEach((c) => {
          table += `<td style="border:1px solid #333;padding:5px 8px">${renderInline(escapeHtml(c))}</td>`;
        });
        table += "</tr>";
      });
      table += "</tbody></table>";
      out.push(table);
      continue;
    }

    // Unordered list
    if (/^\s*[-*]\s+/.test(line)) {
      flushParagraph(para);
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      out.push(
        `<ul style="margin:0.5em 0;padding-left:1.3em;line-height:1.7">${items
          .map((it) => `<li>${renderInline(escapeHtml(it))}</li>`)
          .join("")}</ul>`
      );
      continue;
    }

    // Ordered list
    if (/^\s*\d+\.\s+/.test(line)) {
      flushParagraph(para);
      const items = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      out.push(
        `<ol style="margin:0.5em 0;padding-left:1.4em;line-height:1.7">${items
          .map((it) => `<li>${renderInline(escapeHtml(it))}</li>`)
          .join("")}</ol>`
      );
      continue;
    }

    // Blockquote
    if (/^>\s?/.test(line)) {
      flushParagraph(para);
      const quote = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      out.push(
        `<blockquote style="border-left:3px solid #4ea1ff;margin:0.6em 0;padding:0.2em 0 0.2em 0.8em;color:#bbb">${renderInline(
          escapeHtml(quote.join(" "))
        )}</blockquote>`
      );
      continue;
    }

    // Blank line → paragraph break
    if (/^\s*$/.test(line)) {
      flushParagraph(para);
      i++;
      continue;
    }

    // Default: accumulate into a paragraph
    para.push(line.trim());
    i++;
  }
  flushParagraph(para);
  return out.join("\n");
}

export default function UserGuide() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["userGuide"],
    queryFn: getUserGuide,
    staleTime: 3600000,
  });

  const html = React.useMemo(
    () => (data?.markdown ? markdownToHtml(data.markdown) : ""),
    [data]
  );

  return (
    <div>
      <div
        className="m-section-title"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        User Manual
        <button
          className="m-btn m-btn-neutral"
          style={{ fontSize: "0.8rem", padding: "2px 10px" }}
          onClick={() => navigate("/system")}
        >
          ← Back
        </button>
      </div>

      {isLoading && <div style={{ color: "#888" }}>Loading…</div>}
      {isError && <div style={{ color: "#e05050" }}>Could not load the user manual.</div>}
      {!isLoading && !isError && (
        <div
          style={{ color: "#ddd", fontSize: "0.9rem" }}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      )}
    </div>
  );
}
