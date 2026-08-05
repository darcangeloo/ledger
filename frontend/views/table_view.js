// Vista tabella per un blocco type='database'. Nessuna dipendenza esterna.

function renderTableView(container, dbBlock, rows) {
  const fields = (dbBlock.schema && dbBlock.schema.campi) || [];
  const table = document.createElement("table");
  table.className = "db-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const f of fields) {
    const th = document.createElement("th");
    th.textContent = f.nome;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    tbody.appendChild(renderRow(row, fields));
  }
  table.appendChild(tbody);

  container.innerHTML = "";
  container.appendChild(table);

  const addBtn = document.createElement("button");
  addBtn.className = "btn-quiet table-add";
  addBtn.textContent = "Nuova riga";
  addBtn.onclick = async () => {
    const properties = {};
    for (const f of fields) properties[f.nome] = null;
    await window.pywebview.api.create_block(
      "database_row",
      dbBlock.id,
      null,
      properties,
      null,
      rows.length
    );
    window.LedgerApp.refreshCurrentView();
  };
  container.appendChild(addBtn);
}

function renderRow(row, fields) {
  const tr = document.createElement("tr");
  for (const f of fields) {
    const td = document.createElement("td");
    td.appendChild(renderFieldInput(row, f));
    tr.appendChild(td);
  }
  return tr;
}

function renderFieldInput(row, field) {
  const value = row.properties ? row.properties[field.nome] : null;

  const commit = async (newValue) => {
    const properties = { ...(row.properties || {}), [field.nome]: newValue };
    row.properties = properties;
    await window.pywebview.api.update_block(row.id, { properties });
  };

  if (field.tipo === "select") {
    const select = document.createElement("select");
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "—";
    select.appendChild(empty);
    for (const opt of field.opzioni || []) {
      const o = document.createElement("option");
      o.value = opt;
      o.textContent = opt;
      if (opt === value) o.selected = true;
      select.appendChild(o);
    }
    select.onchange = () => commit(select.value || null);
    return select;
  }

  if (field.tipo === "checkbox") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = !!value;
    input.onchange = () => commit(input.checked);
    return input;
  }

  const input = document.createElement("input");
  input.type = field.tipo === "number" ? "number" : field.tipo === "date" ? "date" : "text";
  input.value = value ?? "";
  input.onchange = () => commit(field.tipo === "number" ? Number(input.value) : input.value);
  return input;
}
