// Vista kanban per un blocco type='database'. Raggruppa per il primo campo
// tipo 'select' dello schema. Drag&drop nativo HTML5, nessuna libreria.

function renderBoardView(container, dbBlock, rows) {
  const fields = (dbBlock.schema && dbBlock.schema.campi) || [];
  const groupField = fields.find((f) => f.tipo === "select");

  container.innerHTML = "";

  if (!groupField) {
    const msg = document.createElement("p");
    msg.className = "empty-note";
    msg.textContent = "La board raggruppa per un campo select. Aggiungine uno allo schema.";
    container.appendChild(msg);
    return;
  }

  const columnsWrap = document.createElement("div");
  columnsWrap.className = "board-columns";

  // Un campo select puo' essere stato salvato senza opzioni: la board
  // resta valida, con la sola colonna dei non assegnati.
  const columns = [...(groupField.opzioni || []), "(nessuno)"];
  for (const colValue of columns) {
    const col = document.createElement("div");
    col.className = "board-column";
    col.dataset.value = colValue;

    const title = document.createElement("h3");
    title.textContent = colValue;
    col.appendChild(title);

    const colRows = rows.filter((r) => {
      const v = r.properties ? r.properties[groupField.nome] : null;
      return colValue === "(nessuno)" ? !v : v === colValue;
    });

    for (const row of colRows) {
      col.appendChild(renderCard(row, fields, groupField));
    }

    col.addEventListener("dragover", (e) => {
      e.preventDefault();
      col.classList.add("drop-target");
    });
    col.addEventListener("dragleave", () => col.classList.remove("drop-target"));
    col.addEventListener("drop", async (e) => {
      e.preventDefault();
      col.classList.remove("drop-target");
      const rowId = e.dataTransfer.getData("text/plain");
      const row = rows.find((r) => r.id === rowId);
      if (!row) return;
      const newValue = colValue === "(nessuno)" ? null : colValue;
      const properties = { ...(row.properties || {}), [groupField.nome]: newValue };
      row.properties = properties;
      await window.pywebview.api.update_block(rowId, { properties });
      window.LedgerApp.refreshCurrentView();
    });

    columnsWrap.appendChild(col);
  }

  container.appendChild(columnsWrap);
}

function renderCard(row, fields, groupField) {
  const card = document.createElement("div");
  card.className = "board-card";
  card.draggable = true;

  const titleField = fields.find((f) => f !== groupField) || fields[0];
  const label = titleField && row.properties ? row.properties[titleField.nome] : null;
  card.textContent = label || "Senza titolo";

  card.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", row.id);
    card.classList.add("dragging");
  });
  card.addEventListener("dragend", () => card.classList.remove("dragging"));

  return card;
}
