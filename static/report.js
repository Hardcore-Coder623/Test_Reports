// Pump Test Report tab: nameplate + observed readings in, results / graphs / PDF out.
// All calculations are on the server (calc/test_report.py); this file only collects inputs and draws.
(() => {
  const $ = s => document.querySelector(s);
  const form = $("#rep-form"), out = $("#rep-results");
  const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const fmt = (v, d = 2) => v === null || v === undefined || v === "" ? "" :
    typeof v === "number" ? v.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }) : esc(v);
  let meta = null;

  // ---------- build form ----------
  const TEXT = new Set(["sr_no", "date", "model", "q_unit", "duty_type", "rated_speed", "category", "winding",
    "motor_type", "brand", "isi"]);
  function buildForm() {
    $("#rep-np").innerHTML = `
      <datalist id="rep-models">${meta.models.map(m => `<option value="${esc(m)}">`).join("")}</datalist>
      <datalist id="rep-serials"></datalist>
      <div class="fields rep-fields">${meta.nameplate_fields.map(f => {
        let input;
        if (f.key === "q_unit") input = `<select name="q_unit"><option>LPM</option><option>LPS</option><option>m3/h</option></select>`;
        else if (f.key === "date") input = `<input name="date" type="date">`;
        else input = `<input name="${f.key}" ${TEXT.has(f.key) ? 'type="text"' : 'type="number" step="any"'}
          ${f.key === "model" ? 'list="rep-models"' : f.key === "sr_no" ? 'list="rep-serials"' : ""}>`;
        return `<label class="${["sr_no", "model"].includes(f.key) ? "key" : ""}">${esc(f.label)}<span class="u">${esc(f.unit)}</span>${input}</label>`;
      }).join("")}</div>`;
    const cols = ["Sr.", "Z (m)", "h (m)", "Discharge", "Voltage (V)", "R / I main (A)", "Y / I aux (A)",
      "B / I com (A)", "Motor input (W)", "Freq. (Hz)", "Speed (RPM)"];
    $("#rep-readings").innerHTML = `<thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
      <tbody>${Array.from({ length: meta.max_readings }, (_, i) => `<tr><td>${i + 1}</td>${meta.reading_fields.map(f =>
        `<td><input data-row="${i}" data-f="${f}" type="number" step="any"></td>`).join("")}</tr>`).join("")}</tbody>`;
  }

  // ---------- read / write form ----------
  const npVal = () => Object.fromEntries(meta.nameplate_fields.map(f => [f.key, form.elements[f.key].value]));
  const setNp = np => Object.entries(np).forEach(([k, v]) => {
    const el = form.elements[k]; if (!el) return;
    if (k === "q_unit") v = String(v || "LPM").toLowerCase() === "m3/h" ? "m3/h" : String(v || "LPM").toUpperCase();
    el.value = v ?? "";
  });
  const readings = () => Array.from({ length: meta.max_readings }, (_, i) => Object.fromEntries(meta.reading_fields.map(f =>
    [f, document.querySelector(`#rep-readings input[data-row="${i}"][data-f="${f}"]`).value])));
  const setReadings = rows => document.querySelectorAll("#rep-readings input").forEach(inp => {
    const r = rows[+inp.dataset.row]; inp.value = r ? (r[inp.dataset.f] ?? "") : "";
  });
  const body = () => ({ nameplate: npVal(), readings: readings() });
  const msg = (id, text, ok = true) => { const m = $(id); m.textContent = text; m.className = "rep-msg " + (ok ? "ok" : "bad"); };

  async function api(url, opts) {
    const r = await fetch(url, opts);
    if (r.headers.get("content-type")?.includes("application/pdf")) return r;
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Server error");
    return j;
  }
  const post = (url, data) => api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

  // ---------- buttons (same as the workbook's) ----------
  async function downloadNameplate(model) {
    try {
      const np = await api("/api/report/nameplate?model=" + encodeURIComponent(model));
      const keep = { sr_no: form.elements.sr_no.value, date: form.elements.date.value };
      setNp({ ...np, ...keep });
      msg("#rep-np-msg", `Nameplate loaded for ${np.model}.`);
    } catch (e) { msg("#rep-np-msg", e.message, false); }
  }
  $("#rep-dl-np").onclick = async () => {
    const m = form.elements.model.value.trim();
    if (!m) return msg("#rep-np-msg", "Enter model", false);
    await downloadNameplate(m); calc();
  };
  $("#rep-up-np").onclick = async () => {
    try { const r = await post("/api/report/nameplate", npVal()); msg("#rep-np-msg", `Nameplate saved for ${r.saved.model}.`); }
    catch (e) { msg("#rep-np-msg", e.message, false); }
  };
  async function downloadReadings(sr) {
    const rec = await api("/api/report/record?sr_no=" + encodeURIComponent(sr));
    form.elements.sr_no.value = rec.sr_no;
    form.elements.date.value = rec.date || "";
    if (rec.model) { form.elements.model.value = rec.model; await downloadNameplate(rec.model); }
    setReadings(rec.readings);
    msg("#rep-rd-msg", `${rec.readings.length} readings loaded for Sr. No. ${rec.sr_no}.`);
  }
  $("#rep-dl-rd").onclick = async () => {
    const sr = form.elements.sr_no.value.trim();
    if (!sr) return msg("#rep-rd-msg", "Enter Sr. No.", false);
    try { await downloadReadings(sr); calc(); } catch (e) { msg("#rep-rd-msg", e.message, false); }
  };
  $("#rep-up-rd").onclick = async () => {
    try { const r = await post("/api/report/record", body()); msg("#rep-rd-msg", `${r.saved.readings.length} readings saved for Sr. No. ${r.saved.sr_no}.`); }
    catch (e) { msg("#rep-rd-msg", e.message, false); }
  };
  $("#rep-clear").onclick = () => { setReadings([]); calc(); };

  // Sr. No. suggestions
  let st;
  form.addEventListener("input", e => {
    if (e.target.name === "sr_no") {
      clearTimeout(st);
      st = setTimeout(async () => {
        const list = await api("/api/report/serials?q=" + encodeURIComponent(e.target.value));
        $("#rep-serials").innerHTML = list.map(s => `<option value="${esc(s)}">`).join("");
      }, 250);
    }
  });

  // ---------- results ----------
  function chartSVG(ch, idx) {
    const W = 520, H = 230, m = { l: 56, r: 14, t: 10, b: 40 };
    const all = [...ch.curve, ...(ch.dashed || []).flat(), ...(ch.red || []).flat(), ...(ch.solid || []).flat()];
    const nice = (hi, n = 6) => {
      const raw = (hi || 1) / n, mag = 10 ** Math.floor(Math.log10(raw));
      const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(s => s >= raw);
      return Array.from({ length: Math.ceil(hi / step) + 1 }, (_, i) => +(i * step).toFixed(6));
    };
    const xt = nice(Math.max(...all.map(p => p[0])) * 1.05), yt = nice(Math.max(...all.map(p => p[1])) * 1.08);
    const X = v => m.l + v / xt.at(-1) * (W - m.l - m.r), Y = v => H - m.b - v / yt.at(-1) * (H - m.t - m.b);
    const path = pts => pts.map(([x, y], i) => `${i ? "L" : "M"}${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join("");
    const pct = ch.percent ? "%" : "";
    return `<figure class="chart rep-chart" data-idx="${idx}"><figcaption>${esc(ch.y)}</figcaption>
      <div class="chart-box"><svg class="plot" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(ch.y)} vs discharge">
        ${yt.map(v => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" class="grid"/>
          <text x="${m.l - 6}" y="${Y(v) + 4}" class="tick" text-anchor="end">${v}${pct}</text>`).join("")}
        ${xt.map(v => `<line x1="${X(v)}" x2="${X(v)}" y1="${m.t}" y2="${H - m.b}" class="grid"/>
          <text x="${X(v)}" y="${H - m.b + 17}" class="tick" text-anchor="middle">${v}</text>`).join("")}
        <rect x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}" class="frame"/>
        <text x="${(m.l + W - m.r) / 2}" y="${H - 5}" class="ax-t" text-anchor="middle">${esc(ch.x)}</text>
        ${(ch.dashed || []).map(s => `<path d="${path(s)}" class="r-dash"/>`).join("")}
        ${(ch.solid || []).map((s, i) => `<path d="${path(s)}" class="r-solid s${i}"/>`).join("")}
        ${(ch.red || []).map(s => `<path d="${path(s)}" class="r-red"/>`).join("")}
        <path d="${path(ch.curve)}" class="r-curve"/>
        <line class="xhair" y1="${m.t}" y2="${H - m.b}" x1="-10" x2="-10"/><circle class="r-dot" r="0"/>
        <rect class="hit" x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}"/>
      </svg><div class="tip" hidden></div></div></figure>`;
  }
  function wire(fig, ch) {
    const svg = fig.querySelector("svg.plot"), tip = fig.querySelector(".tip"), xh = fig.querySelector(".xhair"),
      dot = fig.querySelector(".r-dot");
    const W = 520, H = 230, m = { l: 56, r: 14, t: 10, b: 40 };
    const all = [...ch.curve, ...(ch.dashed || []).flat(), ...(ch.red || []).flat(), ...(ch.solid || []).flat()];
    const nice = hi => { const raw = (hi || 1) / 6, mag = 10 ** Math.floor(Math.log10(raw));
      const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(s => s >= raw); return Math.ceil(hi / step) * step; };
    const xm = nice(Math.max(...all.map(p => p[0])) * 1.05), ym = nice(Math.max(...all.map(p => p[1])) * 1.08);
    const X = v => m.l + v / xm * (W - m.l - m.r), Y = v => H - m.b - v / ym * (H - m.t - m.b);
    svg.addEventListener("pointermove", e => {
      const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      const p = pt.matrixTransform(svg.getScreenCTM().inverse());
      let best = ch.curve[0];
      ch.curve.forEach(c => { if (Math.abs(X(c[0]) - p.x) < Math.abs(X(best[0]) - p.x)) best = c; });
      xh.setAttribute("x1", X(best[0])); xh.setAttribute("x2", X(best[0]));
      dot.setAttribute("cx", X(best[0])); dot.setAttribute("cy", Y(best[1])); dot.setAttribute("r", 4.5);
      tip.innerHTML = `<b>${fmt(best[1], ch.percent ? 1 : 2)}${ch.percent ? "%" : ""}</b> ${esc(ch.y.replace(/\s*\(.*\)/, ""))}<br><span>Q ${fmt(best[0], 0)}</span>`;
      tip.hidden = false;
      const r = svg.getBoundingClientRect(), sx = r.width / W;
      tip.style.left = Math.min(X(best[0]) * sx + 10, r.width - 120) + "px";
      tip.style.top = Math.max(Y(best[1]) * sx - 48, 0) + "px";
    });
    svg.addEventListener("pointerleave", () => { tip.hidden = true; xh.setAttribute("x1", -10); xh.setAttribute("x2", -10); dot.setAttribute("r", 0); });
  }

  const pf = s => `<span class="badge ${s === "Pass" ? "pass" : "fail"}">${s}</span>`;
  function render(r) {
    window.lastTestReport = r;                       // used by the Impeller Trim tab ("Load from Test Report")
    const np = r.nameplate, c = r.conclusion, unit = np.q_unit || "LPM";
    const calcRows = r.calculated.map(k => `<tr><td>${k.sr}</td><td>${fmt(k.vh)}</td><td>${fmt(k.H)}</td><td>${fmt(k.I)}</td>
      <td>${fmt(k.kw, 3)}</td><td>${fmt(k.eff)}%</td><td>${fmt(k.Hc)}</td><td>${fmt(k.Qc)}</td><td>${fmt(k.Pc, 3)}</td>
      <td>${k.Nc}</td><td>${fmt(r.observed[k.sr - 1].slip)}%</td></tr>`).join("");
    out.innerHTML = `
      <div class="rep-res-head">
        <h2>Results <span class="muted">· ${esc(np.sr_no)} · ${esc(np.model)}</span></h2>
        <button type="button" class="btn" id="rep-pdf">Export Report (PDF, A4 landscape)</button>
      </div>
      <div class="verdict ${c.overall === "Pass" ? "pass" : "fail"}">CONCLUSION: ${c.overall.toUpperCase()}
        <span>Head &amp; discharge ${c.hq} · Overall efficiency ${c.eff} · Maximum current ${c.current}</span></div>
      <div class="rep-grid">
        <div>
          <div class="sub sec"><h3>Calculated / corrected parameters</h3>
            <div class="tbl-wrap"><table class="tbl rep-tbl">
              <thead><tr><th rowspan="2">Sr.</th><th colspan="2">Head (m)</th><th rowspan="2">Current (A)</th><th rowspan="2">Input (kW)</th>
                <th rowspan="2">Overall effi.</th><th colspan="4">Corrected @ ${fmt(np.rated_freq, 0)} Hz</th><th rowspan="2">Slip</th></tr>
                <tr><th>V²/2g</th><th>H</th><th>Head (m)</th><th>Disch. (${esc(unit)})</th><th>Input (kW)</th><th>RPM</th></tr></thead>
              <tbody>${calcRows}</tbody></table></div>
            <p class="foot">Z = gauge centre above water level · h = delivery gauge reading · V²/2g = velocity head correction ·
              H = Z + h + V²/2g. Refer IS 14220, latest versions and amendments including relative STI.</p>
          </div>
          <div class="sub sec"><h3>Declared vs observed</h3>
            <div class="tbl-wrap"><table class="tbl rep-tbl rep-con">
              <thead><tr><th></th><th>Declared</th><th>Observed</th><th>Requirement</th><th>Result</th></tr></thead>
              <tbody>
                <tr><th>Discharge</th><td>${fmt(c.declared.q, 0)} ${esc(unit)}</td><td>${fmt(c.observed.q)} ${esc(unit)}</td>
                  <td rowspan="2">Head &amp; discharge (${esc(c.dh)}, ${esc(c.dq)})</td><td rowspan="2">${pf(c.hq)}</td></tr>
                <tr><th>Head</th><td>${fmt(c.declared.h, 1)} m</td><td>${fmt(c.observed.h)} m</td></tr>
                <tr><th>Overall efficiency</th><td>${fmt(c.declared.eff, 1)} %</td><td>${fmt(c.observed.eff)} %</td>
                  <td>&gt; 95.5 % of declared</td><td>${pf(c.eff)}</td></tr>
                <tr><th>Current (max)</th><td>${fmt(c.declared.i_max)} A</td><td>${fmt(c.observed.i_max)} A</td>
                  <td>≤ 1.07 × rated, over H range</td><td>${pf(c.current)}</td></tr>
              </tbody></table></div>
            <p class="foot">Duty point: where the head curve meets the line through the origin and (QG, HG).
              Operating range ${fmt(np.h_min, 0)}–${fmt(np.h_max, 0)} m: Q ${fmt(r.points.hmax.Q, 0)}–${fmt(r.points.hmin.Q, 0)} ${esc(unit)},
              current ${fmt(r.points.hmax.I)}–${fmt(r.points.hmin.I)} A.</p>
          </div>
        </div>
        <div class="rep-charts">${r.charts.map((ch, i) => chartSVG(ch, i)).join("")}</div>
      </div>`;
    out.querySelectorAll("figure.rep-chart").forEach(f => wire(f, r.charts[+f.dataset.idx]));
    $("#rep-pdf").onclick = exportPdf;
  }

  async function exportPdf() {
    try {
      const res = await post("/api/report/pdf", body());
      if (!(res instanceof Response)) throw new Error("PDF could not be created");
      const blob = await res.blob();
      const name = (res.headers.get("content-disposition") || "").match(/filename="([^"]+)"/)?.[1] || "test_report.pdf";
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: name });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } catch (e) { alert(e.message); }
  }

  async function calc() {
    try { render(await post("/api/report", body())); }
    catch (e) { out.innerHTML = `<h2>Results</h2><div class="error">${esc(e.message)}</div>`; }
  }
  let t;
  form.addEventListener("input", e => { if (e.target.name !== "sr_no") { clearTimeout(t); t = setTimeout(calc, 400); } });
  form.addEventListener("change", e => { if (e.target.name === "q_unit") calc(); });

  // "Open" from the Masters tab
  document.addEventListener("open-test", async e => {
    try { await downloadReadings(e.detail); calc(); } catch (err) { msg("#rep-rd-msg", err.message, false); }
  });

  // ---------- init: open with the workbook's example test ----------
  api("/api/report/meta").then(async m => {
    meta = m; buildForm();
    try { await downloadReadings("LSPA1VD000551"); } catch (e) { /* example not in data */ }
    calc();
  });
})();
