// Vista lista per un blocco type='database'. Nessuna dipendenza esterna.

function renderListView(container, dbBlock, rows) {
  const fields = (dbBlock.schema && dbBlock.schema.campi) || [];
  const titleField = fields[0];
  const subFields = fields.slice(1);

  container.innerHTML = "";
  const list = document.createElement("div");

  for (const row of rows) {
    const rowEl = document.createElement("div");
    rowEl.className = "list-row";

    const label = document.createElement("span");
    label.textContent =
      (titleField && row.properties && row.properties[titleField.nome]) || "Senza titolo";
    rowEl.appendChild(label);

    const sub = document.createElement("span");
    sub.className = "list-row-meta";
    sub.textContent = subFields
      .map((f) => (row.properties ? row.properties[f.nome] : null))
      .filter((v) => v !== null && v !== undefined && v !== "")
      .join(" · ");
    rowEl.appendChild(sub);

    list.appendChild(rowEl);
  }

  container.appendChild(list);
}
