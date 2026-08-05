import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });

let renderCounter = 0;

async function renderInto(container, source) {
  if (!source || !source.trim()) {
    container.innerHTML = "";
    return;
  }
  const id = `mermaid-diagram-${renderCounter++}`;
  try {
    const { svg } = await mermaid.render(id, source);
    container.innerHTML = svg;
  } catch (err) {
    // Il messaggio di Mermaid rimanda pezzi del sorgente scritto dall'utente:
    // va inserito come testo, mai come HTML.
    container.textContent = "";
    const box = document.createElement("div");
    box.className = "diagram-error";
    box.textContent = `Errore nel diagramma: ${String((err && err.message) || err)}`;
    container.appendChild(box);
  }
}

window.LedgerMermaid = { renderInto };
