// Front end: builds selectors, posts inputs to the server, renders returned results.
// No engineering formulas are present in this file.
(() => {
  let OPTS = null;
  const $ = (s, r = document) => r.querySelector(s);
  const fmt = (v, unit = "") =>
    v === null || v === undefined ? "–" :
    (typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 3 }) : v) +
    (unit ? ` <span class="u">${unit}</span>` : "");

  // ---------- tabs ----------
  document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === t));
    document.querySelectorAll(".panel").forEach(p =>
      p.classList.toggle("active", p.id === "tab-" + t.dataset.tab));
  }));

  const formData = form => {
    const o = {};
    new FormData(form).forEach((v, k) => (o[k] = v));
    return o;
  };
  const setForm = (form, values) => {
    for (const [k, v] of Object.entries(values)) {
      const el = form.elements[k];
      if (el) el.value = v;
    }
  };
  const debounce = (fn, ms = 250) => { let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; };

  async function post(url, body) {
    const r = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Server error");
    return j;
  }

  const badge = s => {
    const cls = s === "Pass" || s === "OK" ? "pass" : "fail";
    return `<span class="badge ${cls}">${s}</span>`;
  };
  const meter = pct => {
    const w = Math.min(pct, 100);
    const cls = pct >= 100 ? "fail" : pct >= 85 ? "warn" : "pass";
    return `<div class="meter"><div class="bar ${cls}" style="width:${w}%"></div></div>
            <div class="meter-label">${fmt(pct)}% of limit used</div>`;
  };
  const kv = rows => `<dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
  // "How to pass" box: server-provided fixes, each with an Apply button
  const esc = s => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  const fixBox = fixes => !fixes || !fixes.length ? "" :
    `<div class="fix"><div class="fix-head">How to pass</div>${fixes.map(f =>
      `<div class="fix-row"><span>${esc(f.text)}</span>${f.apply
        ? `<button type="button" class="btn small apply" data-apply="${esc(JSON.stringify(f.apply))}">Apply</button>`
        : ""}</div>`).join("")}</div>`;
  const verdict = (items, okWord) => {
    const bad = items.filter(i => i.status !== okWord);
    return bad.length
      ? `<div class="verdict fail">DESIGN FAILS <span>${bad.map(i => i.name).join(", ")} — see “How to pass” below</span></div>`
      : `<div class="verdict pass">DESIGN PASSES <span>All checks within limits</span></div>`;
  };
  const showError = (el, msg) =>
    (el.innerHTML = `<h2>Results</h2><div class="error">${msg}</div>`);

  // ---------- BALL BEARING ----------
  const bForm = $("#bearing-form");

  function fillBearingSelect(side, bore, keep) {
    const sel = $("#bearing_" + side);
    const list = OPTS.bearing.bearings.filter(b => b.d == bore);
    sel.innerHTML = list.map(b => `<option>${b.designation}</option>`).join("");
    if (keep && list.some(b => b.designation === keep)) sel.value = keep;
  }
  function setupBearingPickers(defaults) {
    ["a", "b"].forEach(side => {
      const boreSel = $("#bore_" + side);
      boreSel.innerHTML = OPTS.bearing.bores.map(d => `<option value="${d}">${d}</option>`).join("");
      const des = defaults["bearing_" + side];
      const found = OPTS.bearing.bearings.find(b => b.designation === des);
      boreSel.value = found ? found.d : OPTS.bearing.bores[0];
      fillBearingSelect(side, boreSel.value, des);
      boreSel.onchange = () => { fillBearingSelect(side, boreSel.value); calcBearing(); };
    });
  }

  function bearingCard(title, b) {
    return `<div class="sub ${b.status === "OK" ? "" : "bad"}">
      <div class="sub-head"><h3>${title}</h3>${badge(b.status)}</div>
      <div class="big">${b.designation} <span class="muted">· ${b.size} mm · Qty ${b.qty}</span></div>
      ${kv([
        ["Radial load", fmt(b.radial_n, "N")],
        ["Axial load", fmt(b.axial_n, "N")],
        ["Load", `${fmt(b.load_kg, "kg")} · ${fmt(b.load_lb, "lb")}`],
        ["Static capacity Co", fmt(b.co, "N")],
        ...(b.c_dyn ? [["Dynamic capacity C", fmt(b.c_dyn, "N")]] : []),
      ])}
      ${meter(b.load_ratio)}
      ${b.status === "OK" && b.suggested && b.suggested !== b.designation
        ? `<div class="hint">Lightest bearing on ${b.size.split("x")[0]} mm bore that carries this load: <b>${b.suggested}</b></div>`
        : ""}
      ${fixBox(b.fixes)}
    </div>`;
  }

  async function calcBearing() {
    const el = $("#bearing-results");
    try {
      const r = await post("/api/bearing", formData(bForm));
      const s = r.summary;
      const lb = v => Math.round(v).toLocaleString("en-IN") + " lb";
      $("#dg-p1").textContent = `${lb(s.p1_lb)} · ${fmt(s.p1_kg)} kg`;
      $("#dg-p2").textContent = `${lb(s.p2_lb)} · ${fmt(s.p2_kg)} kg`;
      $("#dg-ra").textContent = `RA ${fmt(r.bearing_a.radial_n)} N · ${r.bearing_a.designation}`;
      $("#dg-rb").textContent = `RB ${fmt(r.bearing_b.radial_n)} N · ${r.bearing_b.designation}`;
      $("#dg-span").textContent = `k = ${fmt(s.span_mm)} mm (${fmt(s.span_in)}")`;
      el.innerHTML = `<h2>Results</h2>
        ${verdict([{ ...r.bearing_a, name: "Bearing A" }, { ...r.bearing_b, name: "Bearing B" }], "OK")}
        <div class="stats">
          <div><span>Radial force P1</span><b>${fmt(s.p1_kg, "kg")}</b><small>${fmt(s.p1_lb, "lb")}</small></div>
          <div><span>Axial force P2</span><b>${fmt(s.p2_kg, "kg")}</b><small>${fmt(s.p2_lb, "lb")}</small></div>
          <div><span>Bearing span k</span><b>${fmt(s.span_mm, "mm")}</b><small>Torque ${fmt(s.torque)}</small></div>
        </div>
        ${bearingCard("Bearing A", r.bearing_a)}
        ${bearingCard("Bearing B", r.bearing_b)}`;
    } catch (e) { showError(el, e.message); }
  }
  const calcBearingD = debounce(calcBearing);
  bForm.addEventListener("input", calcBearingD);
  bForm.addEventListener("change", calcBearingD);
  // diagram boxes and form fields for a, b, c stay in sync (both typed by the user)
  const syncLinks = src => document.querySelectorAll(`[data-link="${src.dataset.link}"]`)
    .forEach(el => { if (el !== src) el.value = src.value; });
  document.querySelectorAll("[data-link]").forEach(el =>
    el.addEventListener("input", () => { syncLinks(el); calcBearingD(); }));
  const syncAll = () => ["a", "b", "c"].forEach(k => syncLinks(bForm.elements[k]));
  $("#bearing-reset").onclick = () => {
    setForm(bForm, OPTS.bearing.defaults);
    syncAll();
    setupBearingPickers(OPTS.bearing.defaults);
    calcBearing();
  };

  // ---------- BUSH ----------
  const sForm = $("#bush-form");
  const modelOf = key => OPTS.bush.models.find(m => m.key === key);

  function loadModel(key) {
    const m = modelOf(key);
    setForm(sForm, m.inputs);
    $("#material").value = m.material;
    sForm.elements.pv_limit.value = m.pv_limits[m.material];
  }

  function bushCard(b) {
    return `<div class="sub ${b.status === "Pass" ? "" : "bad"}">
      <div class="sub-head"><h3>${b.name}</h3>${badge(b.status)}</div>
      <div class="big">Ø${fmt(b.dia)} × ${fmt(b.length)} mm ${b.size ? `<span class="muted">· ${b.size}</span>` : ""}</div>
      ${kv([
        ["Velocity V", `${fmt(b.v_m_min, "m/min")} · ${fmt(b.v_m_s, "m/s")}`],
        ["Pressure P", fmt(b.p_kg_cm2, "kg/cm²")],
        ["PV", fmt(b.pv, "kg/cm²·m/min")],
        ["PV max", fmt(b.pv_max, "kg/cm²·m/min")],
      ])}
      ${meter(b.utilisation)}
      ${fixBox(b.fixes)}
    </div>`;
  }

  async function calcBush() {
    const el = $("#bush-results");
    try {
      const r = await post("/api/bush", formData(sForm));
      const s = r.summary;
      el.innerHTML = `<h2>Results <span class="muted">· ${r.model} · ${r.material}</span></h2>
        ${verdict([r.bush_a, r.bush_b], "Pass")}
        <div class="stats">
          <div><span>Specific speed Ns</span><b>${fmt(s.specific_speed)}</b><small>${fmt(s.discharge_gpm, "gpm")}</small></div>
          <div><span>Radial thrust Rso</span><b>${fmt(s.rso, "kg")}</b><small>Fp</small></div>
          <div><span>FrA / FrB</span><b>${fmt(s.fra)} / ${fmt(s.frb)}</b><small>kg</small></div>
        </div>
        ${bushCard(r.bush_a)}
        ${bushCard(r.bush_b)}
        <div class="hint">PV limit ${fmt(r.pv_limit_imp)} lb/in²·ft/min = ${fmt(r.pv_limit_metric)} kg/cm²·m/min</div>`;
    } catch (e) { showError(el, e.message); }
  }
  const calcBushD = debounce(calcBush);
  sForm.addEventListener("input", calcBushD);
  $("#model").addEventListener("change", () => { loadModel($("#model").value); calcBush(); });
  $("#material").addEventListener("change", () => {
    const m = modelOf($("#model").value);
    sForm.elements.pv_limit.value = m.pv_limits[$("#material").value];
    calcBush();
  });
  $("#bush-reset").onclick = () => { loadModel($("#model").value); calcBush(); };

  // ---------- Apply buttons ----------
  $("#bearing-results").addEventListener("click", e => {
    const btn = e.target.closest(".apply"); if (!btn) return;
    const fix = JSON.parse(btn.dataset.apply);
    for (const [k, v] of Object.entries(fix)) {
      const side = k === "bearing_a" ? "a" : k === "bearing_b" ? "b" : null;
      if (side) {
        const found = OPTS.bearing.bearings.find(x => x.designation === v);
        $("#bore_" + side).value = found.d;
        fillBearingSelect(side, found.d, v);
      } else if (bForm.elements[k]) {
        bForm.elements[k].value = v;
      }
    }
    calcBearing();
  });
  $("#bush-results").addEventListener("click", e => {
    const btn = e.target.closest(".apply"); if (!btn) return;
    setForm(sForm, JSON.parse(btn.dataset.apply));
    calcBush();
  });

  // ---------- init ----------
  fetch("/api/options").then(r => r.json()).then(o => {
    OPTS = o;
    $("#hp-list").innerHTML = o.bearing.hp_list.map(h => `<option value="${h}">${h} HP</option>`).join("");
    setForm(bForm, o.bearing.defaults);
    syncAll();
    setupBearingPickers(o.bearing.defaults);
    $("#model").innerHTML = o.bush.models.map(m => `<option value="${m.key}">${m.label}</option>`).join("");
    $("#material").innerHTML = o.bush.materials.map(m => `<option>${m}</option>`).join("");
    loadModel(o.bush.models[0].key);
    calcBearing();
    calcBush();
  });
})();
