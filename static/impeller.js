// Impeller Design, Volute Design and Master tabs: required inputs only; the server returns key results,
// results, table rows and graph points. No formulas here - drawing only.
(() => {
  const $ = s => document.querySelector(s);
  const forms = { impeller: $("#imp-form"), volute: $("#vol-form") };
  const boxes = { impeller: $("#imp-fields"), volute: $("#vol-fields") };
  let schema = {};
  const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const num = v => v === null || v === undefined || v === "" ? "–" :
    typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : esc(v);

  // ---------- forms (one per section, fields from the server) ----------
  function buildForm(sec) {
    boxes[sec].innerHTML = schema[sec].map(g => `
      <h2>${esc(g.group)}</h2>
      <div class="fields">${g.fields.map(f => `
        <label class="${f.text ? "span2" : ""}">${esc(f.label)}<span class="u">${esc(f.unit)}</span>
          <input name="${f.key}" ${f.text ? 'type="text"' : 'type="number" step="any"'}
            ${f.optional ? 'placeholder="blank = chart"' : ""}></label>`).join("")}
      </div>`).join("");
    reset(sec);
  }
  const reset = sec => schema[sec].forEach(g => g.fields.forEach(f => (forms[sec].elements[f.key].value = f.default)));

  // ---------- single-series line chart ----------
  const nice = (lo, hi, n = 4) => {
    const span = hi - lo || Math.abs(hi) || 1, raw = span / n;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw);
    const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step;
    const t = []; for (let v = a; v <= b + step / 2; v += step) t.push(+v.toFixed(6));
    return t;
  };
  // series colours follow the quantity (validated pair): β orange, velocities / widths blue
  const COLORS = { left2: "#eb6834", main: "#2a78d6" };
  const seriesOf = c => c.dual
    ? c.series.map((s, i) => ({ ...s, color: i === 0 ? COLORS.left2 : COLORS.main }))
    : [{ name: c.y, axis: "left", marker: "circle", points: c.points, color: COLORS.main }];
  const marker = (m, x, y, color, on = false) => {
    const s = on ? 6 : 4.5;
    if (m === "square") return `<rect x="${x - s}" y="${y - s}" width="${2 * s}" height="${2 * s}" rx="1" fill="${color}" class="mk"/>`;
    if (m === "diamond") return `<path d="M${x},${y - s * 1.3}L${x + s * 1.3},${y}L${x},${y + s * 1.3}L${x - s * 1.3},${y}Z" fill="${color}" class="mk"/>`;
    return `<circle cx="${x}" cy="${y}" r="${s}" fill="${color}" class="mk"/>`;
  };
  const geom = c => {
    const W = c.dual ? 900 : 460, H = c.dual ? 300 : 250, m = { l: 66, r: c.dual ? 66 : 18, t: 14, b: 46 };
    const ser = seriesOf(c);
    const xs = ser.flatMap(s => s.points.map(p => p[0]));
    const xt = c.x_max ? nice(0, c.x_max, 4) : c.dual ? nice(0, Math.max(...xs), 5) : nice(Math.min(...xs), Math.max(...xs));
    const scale = axis => {
      const ys = ser.filter(s => s.axis === axis).flatMap(s => s.points.map(p => p[1]));
      if (!ys.length) return null;
      return c.dual ? nice(0, Math.max(...ys), 6) : nice(Math.min(...ys), Math.max(...ys));
    };
    const yt = { left: scale("left"), right: scale("right") };
    const X = v => m.l + (v - xt[0]) / (xt.at(-1) - xt[0]) * (W - m.l - m.r);
    const Y = (v, axis) => { const t = yt[axis]; return H - m.b - (v - t[0]) / (t.at(-1) - t[0]) * (H - m.t - m.b); };
    return { W, H, m, ser, xt, yt, X, Y };
  };
  function chartSVG(c, idx) {
    const { W, H, m, ser, xt, yt, X, Y } = geom(c);
    const left = ser.find(s => s.axis === "left"), right = ser.find(s => s.axis === "right");
    const midY = (m.t + H - m.b) / 2;
    return `<figure class="chart" data-idx="${idx}">
      <figcaption>${esc(c.title)}</figcaption>
      ${ser.length > 1 ? `<div class="legend">${ser.map(s => `<span><svg width="26" height="12" aria-hidden="true">
          <line x1="0" x2="26" y1="6" y2="6" stroke="${s.color}" stroke-width="2"/>${marker(s.marker, 13, 6, s.color)}</svg>
          ${esc(s.name)} <em>${right ? `(${s.axis} axis)` : ""}${s.trend ? ` · trend ${esc(s.trend)}` : ""}</em></span>`).join("")}</div>` : ""}
      <div class="chart-box">
      <svg class="plot" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(c.title)}">
        ${yt.left.map(v => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v, "left")}" y2="${Y(v, "left")}" class="grid"/>
          <text x="${m.l - 8}" y="${Y(v, "left") + 4}" class="tick" text-anchor="end">${num(v)}</text>`).join("")}
        ${yt.right ? yt.right.map(v => `<text x="${W - m.r + 8}" y="${Y(v, "right") + 4}" class="tick">${num(v)}</text>`).join("") : ""}
        ${c.dual ? xt.map(v => `<line x1="${X(v)}" x2="${X(v)}" y1="${m.t}" y2="${H - m.b}" class="grid"/>`).join("") : ""}
        ${xt.map(v => `<text x="${X(v)}" y="${H - m.b + 20}" class="tick" text-anchor="middle">${num(v)}</text>`).join("")}
        <line x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}" class="axis"/>
        <text x="${(m.l + W - m.r) / 2}" y="${H - 4}" class="ax-t" text-anchor="middle">${esc(c.x)}</text>
        <text x="14" y="${midY}" class="ax-t" text-anchor="middle" transform="rotate(-90 14 ${midY})">${esc(right ? left.name : (c.y || left.name))}</text>
        ${right ? `<text x="${W - 12}" y="${midY}" class="ax-t" text-anchor="middle" transform="rotate(90 ${W - 12} ${midY})">${esc(right.name)}</text>` : ""}
        <line class="xhair" y1="${m.t}" y2="${H - m.b}" x1="-10" x2="-10"/>
        ${ser.map(s => `<path d="${s.points.map(([x, y], i) => `${i ? "L" : "M"}${X(x)},${Y(y, s.axis)}`).join("")}"
            class="ln" stroke="${s.color}"/>
          <g class="mks">${s.points.map(([x, y]) => marker(s.marker, X(x), Y(y, s.axis), s.color)).join("")}</g>`).join("")}
        ${ser.filter(s => s.fit).map(s => `<path d="${s.fit.map(([x, y], i) => `${i ? "L" : "M"}${X(x)},${Y(y, s.axis)}`).join("")}"
            class="fit" stroke="${s.color}"/>`).join("")}
        ${c.mark ? `<g class="mark"><circle cx="${X(c.mark.x)}" cy="${Y(c.mark.y, c.mark.axis)}" r="7"/>
            <text x="${X(c.mark.x) + 11}" y="${Y(c.mark.y, c.mark.axis) - 10}">${esc(c.mark.label)}</text></g>` : ""}
        <g class="hl"></g>
        <rect class="hit" x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}"/>
      </svg>
      <div class="tip" hidden></div>
      </div>
      <details class="tbl-view"><summary>Table</summary>
        <table class="tbl"><thead><tr><th>${esc(c.x)}</th>${ser.map(s => `<th>${esc(s.name)}</th>`).join("")}</tr></thead>
        <tbody>${ser[0].points.map((p, i) => `<tr><td>${num(p[0])}</td>${ser.map(s => `<td>${num(s.points[i][1])}</td>`).join("")}</tr>`).join("")}</tbody></table>
      </details>
    </figure>`;
  }
  function wireHover(fig, c) {
    const { W, ser, X, Y } = geom(c);
    const svg = fig.querySelector("svg.plot"), tip = fig.querySelector(".tip"), xh = fig.querySelector(".xhair"),
      hl = fig.querySelector(".hl");
    const xs = ser[0].points.map(p => X(p[0]));
    const move = e => {
      const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      const p = pt.matrixTransform(svg.getScreenCTM().inverse());
      let i = 0; xs.forEach((x, k) => { if (Math.abs(x - p.x) < Math.abs(xs[i] - p.x)) i = k; });
      xh.setAttribute("x1", xs[i]); xh.setAttribute("x2", xs[i]);
      hl.innerHTML = ser.map(s => marker(s.marker, xs[i], Y(s.points[i][1], s.axis), s.color, true)).join("");
      tip.innerHTML = ser.map(s => `<b>${num(s.points[i][1])}</b> ${esc(s.name)}`).join("<br>") +
        `<br><span>${esc(c.x.replace(/\s*\(.*\)/, ""))} ${num(ser[0].points[i][0])}</span>`;
      tip.hidden = false;
      const r = svg.getBoundingClientRect(), sx = r.width / W;
      const top = Math.min(...ser.map(s => Y(s.points[i][1], s.axis)));
      tip.style.left = Math.min(xs[i] * sx + 12, r.width - 130) + "px";
      tip.style.top = Math.max(top * sx - 50, 0) + "px";
    };
    const leave = () => { tip.hidden = true; xh.setAttribute("x1", -10); xh.setAttribute("x2", -10); hl.innerHTML = ""; };
    svg.addEventListener("pointermove", move); svg.addEventListener("pointerleave", leave);
  }

  // ---------- render helpers ----------
  const tiles = rows => `<div class="key-grid">${rows.map(([k, v, u]) =>
    `<div><span>${esc(k)}</span><b>${num(v)}<small> ${esc(u)}</small></b></div>`).join("")}</div>`;
  // rowHead: first cell of each row is a label (Excel-style horizontal table)
  const tableHTML = (t, rowHead = false) => `<div class="tbl-wrap"><table class="tbl${rowHead ? " rowhead" : ""}">
      <thead><tr>${t.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${t.rows.map((r, i) => `<tr class="${i === t.highlight ? "hi" : ""}">${r.map((c, j) =>
        rowHead && j === 0 ? `<th scope="row">${esc(c)}</th>` : `<td>${c === null ? "" : num4(c)}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
  const warn = r => r.warnings.map(w => `<div class="verdict fail">CHECK <span>${esc(w)}</span></div>`).join("");
  let charts = [];                                   // all charts on screen, for hover lookup
  const chart = c => { charts.push(c);
    return `<div class="sub sec${c.dual ? " wide" : ""}">${chartSVG(c, charts.length - 1)}</div>`; };
  const num4 = v => typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 6 }) : num(v);

  // vane development laid out like the sheet: no header, label column, adjusted Vf cells marked
  const vaneHTML = t => `<div class="tbl-wrap"><table class="tbl xl">
      <tbody>${t.rows.map(r => `<tr class="${r.bold ? "hi" : ""}"><th scope="row">${esc(r.label)}</th>${r.values.map((v, i) =>
        `<td class="${r.adjusted && r.adjusted.includes(i) ? "adj" : ""}">${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;

  // pass / fail checks with "How to pass" fixes (worked out on the server)
  function checksHTML(checks, label) {
    const bad = checks.filter(c => c.status !== "Pass");
    return `<div class="verdict ${bad.length ? "fail" : "pass"}">${label} ${bad.length ? "FAILS" : "PASSES"}
        <span>${bad.length ? bad.map(c => esc(c.name)).join(", ") + " - see “How to pass” below" : "All checks within limits"}</span></div>
      <div class="checks">${checks.map(c => `
        <div class="chk ${c.status === "Pass" ? "" : "bad"}">
          <div class="chk-head"><b>${esc(c.name)}</b><span class="badge ${c.status === "Pass" ? "pass" : "fail"}">${c.status}</span></div>
          <div class="chk-detail">${esc(c.detail)}</div>
          ${c.fixes.length ? `<div class="fix"><div class="fix-head">How to pass</div>${c.fixes.map(f =>
            `<div class="fix-row"><span>${esc(f.text)}</span>${f.apply
              ? `<button type="button" class="btn small apply" data-apply="${esc(JSON.stringify(f.apply))}">Apply</button>` : ""}</div>`).join("")}</div>` : ""}
        </div>`).join("")}</div>`;
  }

  const xsHTML = t => `<div class="tbl-wrap"><table class="tbl xl xs">
      <thead><tr>${t.header.map((h, i) => `<th class="${i === t.header.length - 1 ? "lbl" : ""}">${esc(h)}</th>`).join("")}</tr></thead>
      <tbody>${t.rows.map(r => `<tr class="${r.input ? "pink" : r.bold ? "hi" : ""}">${r.values.map(v =>
        `<td>${esc(v)}</td>`).join("")}<th scope="row" class="lbl">${esc(r.label)}</th></tr>`).join("")}</tbody>
    </table></div>`;

  // order: checks → key results → blade arcs → vane development → graph
  function impellerHTML(r, compact) {
    return `${checksHTML(r.impeller.checks, "IMPELLER DESIGN")}${tiles(r.impeller.key)}
      <div class="sub sec"><h3>Blade arcs (two-arc method)</h3>${tableHTML(r.impeller.arc_table, true)}</div>
      <div class="sub sec"><h3>Vane development</h3>${vaneHTML(r.impeller.vane_table)}</div>
      <div class="viz">${r.impeller.charts.map(chart).join("")}</div>
      <div class="sub sec"><h3>Velocity coefficients Kc1 / Kc2 (Sheet1)</h3>
        <dl class="kv kc-kv">${r.impeller.kc.values.map(([k, v, u]) => `<dt>${esc(k)}</dt><dd>${num(v)} ${esc(u)}</dd>`).join("")}</dl>
        <p class="foot">The sheet takes Kcm1 / Kcm2 from an external table (Velocity_Coeff.xls) that is not available;
          the typed values reproduce it. Clear the Kcm boxes to use the chart below. The table is editable on the Masters tab.</p>
      </div>
      <div class="viz">${chart(r.impeller.kc.chart)}</div>`;
  }
  // order: checks → key results → volute cross sections → graph
  function voluteHTML(r) {
    return `${checksHTML(r.volute.checks, "VOLUTE DESIGN")}${tiles(r.volute.key)}
      <div class="sub sec"><h3>Volute cross sections</h3>${xsHTML(r.volute.xs_table)}</div>
      <div class="viz">${r.volute.charts.map(chart).join("")}</div>`;
  }

  // ---------- calculate: one server call feeds all three tabs ----------
  async function calc() {
    const body = {};
    Object.values(forms).forEach(f => new FormData(f).forEach((v, k) => (body[k] = v)));
    const outs = [$("#imp-results"), $("#vol-results"), $("#master-results")];
    try {
      const res = await fetch("/api/impeller", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || "Server error");
      charts = [];
      $("#vol-duty").innerHTML = r.duty.map(([k, v, u]) =>
        `<span><em>${esc(k)}</em> ${num(v)} ${esc(u)}</span>`).join("");
      outs[0].innerHTML = `<h2>Impeller results <span class="muted">· ${esc(r.title)}</span></h2>${impellerHTML(r)}`;
      outs[1].innerHTML = `<h2>Volute results <span class="muted">· ${esc(r.title)}</span></h2>${voluteHTML(r)}`;
      outs[2].innerHTML = `<div class="master-head"><h2>Master · ${esc(r.title)}</h2>
          <div class="duty-strip">${r.duty.map(([k, v, u]) =>
            `<span><em>${esc(k)}</em> ${num(v)} ${esc(u)}</span>`).join("")}</div></div>
        ${warn(r)}
        <h3 class="master-sec">Impeller design</h3>${impellerHTML(r, true)}
        <h3 class="master-sec">Volute design</h3>${voluteHTML(r)}`;
      outs.forEach(o => o.querySelectorAll("figure.chart[data-idx]").forEach(f => wireHover(f, charts[+f.dataset.idx])));   // only this tab's charts
    } catch (e) {
      outs.forEach(o => (o.innerHTML = `<h2>Results</h2><div class="error">${esc(e.message)}</div>`));
    }
  }
  ["#imp-results", "#vol-results", "#master-results"].forEach(sel => $(sel).addEventListener("click", e => {
    const btn = e.target.closest(".apply"); if (!btn) return;
    for (const [k, v] of Object.entries(JSON.parse(btn.dataset.apply))) {
      const f = Object.values(forms).find(f => f.elements[k]);
      if (f) f.elements[k].value = v;
    }
    calc();
  }));
  let t;
  const later = () => { clearTimeout(t); t = setTimeout(calc, 300); };
  Object.values(forms).forEach(f => f.addEventListener("input", later));
  $("#imp-reset").onclick = () => { reset("impeller"); calc(); };
  $("#vol-reset").onclick = () => { reset("volute"); calc(); };
  fetch("/api/impeller/schema").then(r => r.json()).then(s => {
    schema = s; buildForm("impeller"); buildForm("volute"); calc();
  });
})();
