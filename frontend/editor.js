import EditorJS from "@editorjs/editorjs";
import Header from "@editorjs/header";
import Checklist from "@editorjs/checklist";
import List from "@editorjs/list";
import Quote from "@editorjs/quote";
import CodeTool from "@editorjs/code";
import Delimiter from "@editorjs/delimiter";
import Table from "@editorjs/table";
import Marker from "@editorjs/marker";
import InlineCode from "@editorjs/inline-code";

// Editor.js tool name <-> tipo blocco nella tabella `blocks`.
// Nessuna tabella nuova: solo nuovi valori della colonna `type`.
const TYPE_TO_TOOL = {
  text: "paragraph",
  heading: "header",
  checklist: "checklist",
  diagram: "mermaid",
  list: "list",
  quote: "quote",
  code: "code",
  delimiter: "delimiter",
  table: "table",
};
const TOOL_TO_TYPE = {
  paragraph: "text",
  header: "heading",
  checklist: "checklist",
  mermaid: "diagram",
  list: "list",
  quote: "quote",
  code: "code",
  delimiter: "delimiter",
  table: "table",
};

class MermaidTool {
  static get toolbox() {
    return {
      title: "Diagramma",
      icon: '<svg width="17" height="17" viewBox="0 0 17 17"><rect x="1" y="1" width="6" height="5" fill="none" stroke="currentColor"/><rect x="10" y="1" width="6" height="5" fill="none" stroke="currentColor"/><rect x="5" y="11" width="6" height="5" fill="none" stroke="currentColor"/><path d="M4 6v3h9V6M8.5 9v2" fill="none" stroke="currentColor"/></svg>',
    };
  }

  constructor({ data }) {
    this.data = { source: (data && data.source) || "" };
    this._timer = null;
  }

  render() {
    this.wrapper = document.createElement("div");
    this.wrapper.className = "diagram-block";

    const textarea = document.createElement("textarea");
    textarea.className = "diagram-source-input";
    textarea.placeholder = "graph TD\n  A[Inizio] --> B[Fine]";
    textarea.value = this.data.source;

    const preview = document.createElement("div");
    preview.className = "diagram-preview";

    const update = () => {
      this.data.source = textarea.value;
      if (window.LedgerMermaid) window.LedgerMermaid.renderInto(preview, textarea.value);
    };
    textarea.addEventListener("input", () => {
      clearTimeout(this._timer);
      this._timer = setTimeout(update, 400);
    });

    this.wrapper.appendChild(textarea);
    this.wrapper.appendChild(preview);
    update();
    return this.wrapper;
  }

  save() {
    return { source: this.data.source };
  }
}

let editor = null;
let currentPageId = null;
let knownBlockIds = new Set();
let saveTimer = null;

function debounceSave(pageId) {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => syncPage(pageId), 500);
}

async function syncPage(pageId) {
  if (!editor) return;
  const output = await editor.save();
  const seenIds = new Set();
  let order = 0;
  for (const eb of output.blocks) {
    seenIds.add(eb.id);
    const type = TOOL_TO_TYPE[eb.type] || "text";
    if (knownBlockIds.has(eb.id)) {
      await window.pywebview.api.update_block(eb.id, {
        content: eb.data,
        type,
        order_index: order,
      });
    } else {
      await window.pywebview.api.create_block(type, pageId, eb.data, null, null, order, eb.id);
      knownBlockIds.add(eb.id);
    }
    order++;
  }
  for (const oldId of Array.from(knownBlockIds)) {
    if (!seenIds.has(oldId)) {
      await window.pywebview.api.delete_block(oldId);
      knownBlockIds.delete(oldId);
    }
  }
}

async function init(containerId, pageId) {
  if (editor) {
    await editor.isReady;
    editor.destroy();
    editor = null;
  }
  currentPageId = pageId;

  const existing = await window.pywebview.api.list_blocks(pageId);
  knownBlockIds = new Set(existing.map((b) => b.id));
  const blocks = existing
    .sort((a, b) => a.order_index - b.order_index)
    .map((b) => ({ id: b.id, type: TYPE_TO_TOOL[b.type] || "paragraph", data: b.content || {} }));

  editor = new EditorJS({
    holder: containerId,
    minHeight: 200,
    placeholder: "Scrivi qualcosa...",
    tools: {
      header: { class: Header, inlineToolbar: true },
      list: { class: List, inlineToolbar: true },
      checklist: { class: Checklist, inlineToolbar: true },
      quote: { class: Quote, inlineToolbar: true },
      code: CodeTool,
      table: { class: Table, inlineToolbar: true },
      delimiter: Delimiter,
      mermaid: MermaidTool,
      marker: Marker,
      inlineCode: InlineCode,
    },
    data: { blocks },
    onChange: () => {
      if (currentPageId === pageId) debounceSave(pageId);
    },
  });
  await editor.isReady;
}

async function flush() {
  clearTimeout(saveTimer);
  if (currentPageId) await syncPage(currentPageId);
}

window.LedgerEditor = { init, flush };
