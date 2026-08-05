// Sezione "Menzionato in" a fondo pagina. Nessuna dipendenza esterna.

function renderBacklinks(container, backlinks) {
  container.innerHTML = "";
  if (backlinks.length === 0) {
    const p = document.createElement("p");
    p.className = "empty-note";
    p.textContent = "Nessuna menzione.";
    container.appendChild(p);
    return;
  }
  for (const b of backlinks) {
    const item = document.createElement("button");
    item.className = "row-link";
    item.textContent = (b.content && (b.content.title || b.content.text)) || "Senza titolo";
    item.onclick = () => window.LedgerApp.openBacklinkTarget(b);
    container.appendChild(item);
  }
}
