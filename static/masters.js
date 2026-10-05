// Masters tab: view / edit the supporting data sheets (bearing data, bush models & materials,
// Kc chart, nameplates) and browse saved tests. Validation and saving happen on the server.
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const box = $("#mst-body"), chips = $("#mst-chips"), msg = $("#mst-msg");
  let cat = [], cur = null, dirty = false;

  const say = (t, ok = true) => { msg.textContent = t; msg.className = "rep-msg " + (ok ? "ok" : "bad"); };
  async function api(url, opts) {
    const r = await fetch(url, opts);
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Server error");
    return j;
  }

  function showChips() {
    chips.innerHTML = cat.map(m => `<button type="button" class="chip ${cur && cur.name === m.name ? "on" : ""}"
      data-name="${m.name}">${esc(m.title)}</button>`).join("");
  }
  chips.addEventListener("click", e => {
    const b = e.target.closest(".chip"); if (!b) return;
    if (dirty && !confirm("You have unsaved changes. Leave without saving?")) return;
    open(b.dataset.name);
  });

  async function open(name) {
    cur = cat.find(m => m.name === name); dirty = false; showChips(); say("");
    $("#mst-title").textContent = cur.title;
    $("#mst-source").textContent = "From: " + cur.source;
    if (cur.readonly) return openTests();
    const rows = await api("/api/masters/" + name);
    renderEditor(rows);
  }

  // ---------- editable master ----------
  function rowHTML(r) {
    return `<tr>${cur.columns.map(c => `<td><input data-k="${c.key}" value="${esc(r[c.key])}"
        ${c.type === "num" ? 'inputmode="decimal"' : ""} class="${cur.required.includes(c.key) ? "req" : ""}"></td>`).join("")}
      <td class="act"><button type="button" class="del" title="Delete row" aria-label="Delete row">×</button></td></tr>`;
  }
  function renderEditor(rows) {
    box.innerHTML = `
      <div class="mst-tools">
        <input type="search" id="mst-q" placeholder="Search…">
        <span class="muted" id="mst-count">${rows.length} rows</span>
        <span class="grow"></span>
        <button type="button" class="btn ghost small" id="mst-add">+ Add row</button>
        <button type="button" class="btn ghost small" id="mst-revert">Undo changes</button>
        <button type="button" class="btn small" id="mst-save">Save</button>
      </div>
      <div class="tbl-wrap mst-wrap"><table class="tbl mst">
        <thead><tr>${cur.columns.map(c => `<th>${esc(c.label)}${cur.required.includes(c.key) ? " *" : ""}</th>`).join("")}<th></th></tr></thead>
        <tbody>${rows.map(rowHTML).join("")}</tbody></table></div>
      <p class="foot">* required. Changes are used by the calculations as soon as you save; refresh the page to update drop-down lists on other tabs.</p>`;
    const tb = box.querySelector("tbody");
    box.querySelector("#mst-add").onclick = () => {
      tb.insertAdjacentHTML("beforeend", rowHTML({})); dirty = true;
      tb.lastElementChild.querySelector("input").focus();
      box.querySelector(".mst-wrap").scrollTop = 1e9;
    };
    box.querySelector("#mst-revert").onclick = () => { if (!dirty || confirm("Discard your changes?")) open(cur.name); };
    box.querySelector("#mst-save").onclick = save;
    tb.addEventListener("input", () => { dirty = true; });
    tb.addEventListener("click", e => {
      if (e.target.closest(".del")) { e.target.closest("tr").remove(); dirty = true; count(); }
    });
    box.querySelector("#mst-q").addEventListener("input", e => {
      const q = e.target.value.trim().toLowerCase();
      tb.querySelectorAll("tr").forEach(tr => {
        tr.hidden = q && ![...tr.querySelectorAll("input")].some(i => i.value.toLowerCase().includes(q));
      });
      count();
    });
    const count = () => { box.querySelector("#mst-count").textContent =
      `${[...tb.querySelectorAll("tr")].filter(t => !t.hidden).length} of ${tb.children.length} rows`; };
  }
  async function save() {
    const rows = [...box.querySelectorAll("tbody tr")].map(tr =>
      Object.fromEntries([...tr.querySelectorAll("input")].map(i => [i.dataset.k, i.value])));
    try {
      const r = await api("/api/masters/" + cur.name, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rows }),
      });
      dirty = false; say(`Saved ${r.saved} rows to ${cur.title}.`);
    } catch (e) { say(e.message, false); }
  }

  // ---------- saved tests (TestData) ----------
  function openTests() {
    box.innerHTML = `
      <div class="mst-tools"><input type="search" id="mst-tq" placeholder="Search Sr. No. or model…">
        <span class="muted" id="mst-tcount"></span></div>
      <div class="tbl-wrap mst-wrap"><table class="tbl mst ro">
        <thead><tr>${cur.columns.map(c => `<th>${esc(c.label)}</th>`).join("")}<th></th></tr></thead>
        <tbody id="mst-tbody"></tbody></table></div>
      <p class="foot">Open loads the test into the Test Report tab. Upload Readings there saves changes back here.</p>`;
    let t;
    const load = async () => {
      const q = $("#mst-tq").value;
      const [shown, all] = await Promise.all([api(`/api/masters/test_records?limit=300&q=${encodeURIComponent(q)}`),
        api(`/api/masters/test_records?q=${encodeURIComponent(q)}`)]);
      $("#mst-tcount").textContent = all.length > shown.length ? `showing ${shown.length} of ${all.length}` : `${all.length} tests`;
      $("#mst-tbody").innerHTML = shown.map(r => `<tr><td>${esc(r.sr_no)}</td><td>${esc(r.date)}</td><td>${esc(r.model)}</td>
        <td>${r.n}</td><td class="act"><button type="button" class="btn small ghost op" data-sr="${esc(r.sr_no)}">Open</button>
        <button type="button" class="btn small ghost rm" data-sr="${esc(r.sr_no)}">Delete</button></td></tr>`).join("");
    };
    $("#mst-tq").addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
    $("#mst-tbody").addEventListener("click", async e => {
      const op = e.target.closest(".op"), rm = e.target.closest(".rm");
      if (op) {
        document.querySelector('.tab[data-tab="report"]').click();
        document.dispatchEvent(new CustomEvent("open-test", { detail: op.dataset.sr }));
      }
      if (rm && confirm(`Delete saved test ${rm.dataset.sr}? This cannot be undone.`)) {
        try { await api("/api/masters/test_records/" + encodeURIComponent(rm.dataset.sr), { method: "DELETE" });
          say(`Deleted ${rm.dataset.sr}.`); load(); }
        catch (err) { say(err.message, false); }
      }
    });
    load();
  }

  window.addEventListener("beforeunload", e => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
  api("/api/masters").then(c => { cat = c; showChips(); open(c[0].name); });
})();
