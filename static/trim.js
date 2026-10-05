// Impeller Trim tab: diameters + test curve points in, trimmed curve / power / check out.
// Calculations are on the server (calc/trim.py); this file only collects inputs and draws.
(() => {
  const $ = s => document.querySelector(s);
  const form = $("#trim-form"), out = $("#trim-results");
  const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const fmt = (v, d = 2) => v === null || v === undefined || v === "" ? "–" :
    typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: d }) : esc(v);
  const COLORS = ["#2a78d6", "#eb6834"];                // validated pair: test curve blue, new diameter orange
  let defaults = null, MAXP = 8;

  // ---------- form ----------
  function buildTable() {
    $("#trim-points").innerHTML = `<thead><tr><th>Pt</th><th>Flow Q</th><th>Head H</th><th>Efficiency (%)</th></tr></thead>
      <tbody>${Array.from({ length: MAXP }, (_, i) => `<tr><td>${i + 1}</td>${["q", "h", "eff"].map(f =>
        `<td><input data-row="${i}" data-f="${f}" type="number" step="any"></td>`).join("")}</tr>`).join("")}</tbody>`;
  }
  const points = () => Array.from({ length: MAXP }, (_, i) => Object.fromEntries(["q", "h", "eff"].map(f =>
    [f, document.querySelector(`#trim-points input[data-row="${i}"][data-f="${f}"]`).value])));
  const setPoints = pts => document.querySelectorAll("#trim-points input").forEach(inp => {
    const p = pts[+inp.dataset.row]; inp.value = p ? (p[inp.dataset.f] ?? "") : "";
  });
  function reset() {
    form.elements.d1.value = defaults.d1; form.elements.d2.value = defaults.d2;
    form.elements.units.value = defaults.units; setPoints(defaults.points);
  }
  const say = (t, ok = true) => { const m = $("#trim-msg"); m.textContent = t; m.className = "rep-msg " + (ok ? "ok" : "bad"); };

  // ---------- chart (two smooth curves, own scale) ----------
  function chartSVG(ch, u) {
    const W = 760, H = 380, m = { l: 56, r: 16, t: 12, b: 42 };
    const all = ch.series.flatMap(s => s.points);
    const nice = hi => { const raw = (hi || 1) / 6, mag = 10 ** Math.floor(Math.log10(raw));
      const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(s => s >= raw);
      return Array.from({ length: Math.ceil(hi / step) + 1 }, (_, i) => +(i * step).toFixed(6)); };
    const xt = nice(Math.max(...all.map(p => p[0])) * 1.05), yt = nice(Math.max(...all.map(p => p[1])) * 1.08);
    const X = v => m.l + v / xt.at(-1) * (W - m.l - m.r), Y = v => H - m.b - v / yt.at(-1) * (H - m.t - m.b);
    const path = pts => pts.map(([x, y], i) => `${i ? "L" : "M"}${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join("");
    const mk = (kind, x, y, c, r = 4.5) => kind === "square"
      ? `<rect x="${x - r}" y="${y - r}" width="${2 * r}" height="${2 * r}" fill="${c}" class="mk"/>`
      : `<path d="M${x},${y - r * 1.3}L${x + r * 1.3},${y}L${x},${y + r * 1.3}L${x - r * 1.3},${y}Z" fill="${c}" class="mk"/>`;
    return `<figure class="chart trim-chart"><figcaption>${esc(ch.title)}</figcaption>
      <div class="legend">${ch.series.map((s, i) => `<span><svg width="26" height="12" aria-hidden="true">
        <line x1="0" x2="26" y1="6" y2="6" stroke="${COLORS[i]}" stroke-width="2"/>${mk(s.marker, 13, 6, COLORS[i], 4)}</svg>
        D = ${esc(s.name)}</span>`).join("")}</div>
      <div class="chart-box"><svg class="plot" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(ch.title)}">
        ${yt.map(v => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" class="grid"/>
          <text x="${m.l - 6}" y="${Y(v) + 4}" class="tick" text-anchor="end">${v}</text>`).join("")}
        ${xt.map(v => `<text x="${X(v)}" y="${H - m.b + 18}" class="tick" text-anchor="middle">${v}</text>`).join("")}
        <line x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}" class="axis"/>
        <text x="${(m.l + W - m.r) / 2}" y="${H - 4}" class="ax-t" text-anchor="middle">${esc(ch.x)}</text>
        <text x="14" y="${(m.t + H - m.b) / 2}" class="ax-t" text-anchor="middle" transform="rotate(-90 14 ${(m.t + H - m.b) / 2})">${esc(ch.y)}</text>
        ${ch.series.map((s, i) => `<path d="${path(s.line)}" class="ln" stroke="${COLORS[i]}"/>
          ${s.points.map(([x, y]) => mk(s.marker, X(x), Y(y), COLORS[i])).join("")}`).join("")}
        <g class="hl"></g><line class="xhair" y1="${m.t}" y2="${H - m.b}" x1="-10" x2="-10"/>
        <rect class="hit" x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}"/>
      </svg><div class="tip" hidden></div></div>
      <details class="tbl-view"><summary>Table</summary><table class="tbl"><thead><tr>${ch.series.map(s =>
        `<th>Q · ${esc(s.name)}</th><th>H · ${esc(s.name)}</th>`).join("")}</tr></thead>
        <tbody>${ch.series[0].points.map((_, i) => `<tr>${ch.series.map(s =>
          `<td>${fmt(s.points[i][0], 1)}</td><td>${fmt(s.points[i][1], 2)}</td>`).join("")}</tr>`).join("")}</tbody></table></details>
    </figure>`;
    // hover wiring is done in render()
  }
  function wireHover(fig, ch, u) {
    const svg = fig.querySelector("svg.plot"), tip = fig.querySelector(".tip"), hl = fig.querySelector(".hl"),
      xh = fig.querySelector(".xhair");
    const W = 760;
    svg.addEventListener("pointermove", e => {
      const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      const p = pt.matrixTransform(svg.getScreenCTM().inverse());
      let best = null;
      fig.querySelectorAll("svg.plot .mk").forEach((el, k) => {
        const bb = el.getBBox(), cx = bb.x + bb.width / 2, cy = bb.y + bb.height / 2;
        const d = Math.hypot(cx - p.x, (cy - p.y) * 0.5);
        if (!best || d < best.d) best = { d, cx, cy, k };
      });
      if (!best) return;
      const n = ch.series[0].points.length, si = Math.floor(best.k / n), pi = best.k % n;
      const [q, h] = ch.series[si].points[pi];
      xh.setAttribute("x1", best.cx); xh.setAttribute("x2", best.cx);
      hl.innerHTML = `<circle cx="${best.cx}" cy="${best.cy}" r="8" fill="none" stroke="${COLORS[si]}" stroke-width="2"/>`;
      tip.innerHTML = `<b>D = ${esc(ch.series[si].name)}</b><br>Q ${fmt(q, 1)} ${esc(u.q)} · H ${fmt(h, 2)} ${esc(u.h)}`;
      tip.hidden = false;
      const r = svg.getBoundingClientRect(), sx = r.width / W;
      tip.style.left = Math.min(best.cx * sx + 12, r.width - 170) + "px";
      tip.style.top = Math.max(best.cy * sx - 50, 0) + "px";
    });
    svg.addEventListener("pointerleave", () => { tip.hidden = true; hl.innerHTML = ""; xh.setAttribute("x1", -10); xh.setAttribute("x2", -10); });
  }

  // ---------- results ----------
  function render(r) {
    const u = r.units, bad = r.checks.filter(c => c.status !== "Pass");
    out.innerHTML = `<h2>Results <span class="muted">· ${esc(u.label)}</span></h2>
      <div class="verdict ${bad.length ? "fail" : "pass"}">TRIM ${bad.length ? "CHECK FAILS" : "OK"}
        <span>${bad.length ? bad.map(c => esc(c.name)).join(", ") + " - see below" : "Within 10 % of the test diameter"}</span></div>
      <div class="checks">${r.checks.map(c => `<div class="chk ${c.status === "Pass" ? "" : "bad"}">
        <div class="chk-head"><b>${esc(c.name)}</b><span class="badge ${c.status === "Pass" ? "pass" : "fail"}">${c.status}</span></div>
        <div class="chk-detail">${esc(c.detail)}</div>
        ${c.fixes.length ? `<div class="fix"><div class="fix-head">How to pass</div>${c.fixes.map(f => `<div class="fix-row">
          <span>${esc(f.text)}</span>${f.apply ? `<button type="button" class="btn small apply" data-apply="${esc(JSON.stringify(f.apply))}">Apply</button>` : ""}</div>`).join("")}</div>` : ""}
      </div>`).join("")}</div>
      <div class="key-grid">${r.summary.map(([k, v, un]) => `<div><span>${esc(k)}</span><b>${fmt(v, 4)}<small> ${esc(un)}</small></b></div>`).join("")}</div>
      <div class="sub sec"><h3>Test curve and new diameter</h3>
        <div class="tbl-wrap"><table class="tbl rep-tbl">
          <thead><tr><th rowspan="2">Pt</th><th colspan="4">Test curve · D1 ${fmt(r.summary[0][1])} mm</th>
            <th colspan="3">New diameter · D2 ${fmt(r.summary[1][1])} mm</th></tr>
            <tr><th>Q (${esc(u.q)})</th><th>H (${esc(u.h)})</th><th>Eff (%)</th><th>${esc(u.power)}</th>
              <th>Q (${esc(u.q)})</th><th>H (${esc(u.h)})</th><th>${esc(u.power)}</th></tr></thead>
          <tbody>${r.rows.map(x => `<tr><td>${x.pt}</td><td>${fmt(x.q1, 1)}</td><td>${fmt(x.h1)}</td><td>${fmt(x.eff, 1)}</td>
            <td>${fmt(x.p1)}</td><td class="new">${fmt(x.q2, 1)}</td><td class="new">${fmt(x.h2)}</td><td class="new">${fmt(x.p2)}</td></tr>`).join("")}</tbody>
        </table></div>
        <p class="foot">Affinity laws: Q₂ = Q₁·(D₂/D₁), H₂ = H₁·(D₂/D₁)², efficiency assumed unchanged.
          Power = Q·H / (${u.key === "us" ? "3960" : u.key === "metric_kw" ? "6120" : "4500"} · η).
          Trims greater than 10 % can reduce hydraulic efficiency.</p>
      </div>
      <div class="sub sec">${chartSVG(r.chart, u)}</div>`;
    wireHover(out.querySelector("figure.trim-chart"), r.chart, u);
  }

  async function calc() {
    const body = { d1: form.elements.d1.value, d2: form.elements.d2.value, units: form.elements.units.value, points: points() };
    try {
      const res = await fetch("/api/trim", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || "Server error");
      render(r);
    } catch (e) { out.innerHTML = `<h2>Results</h2><div class="error">${esc(e.message)}</div>`; }
  }

  out.addEventListener("click", e => {
    const b = e.target.closest(".apply"); if (!b) return;
    Object.entries(JSON.parse(b.dataset.apply)).forEach(([k, v]) => { if (form.elements[k]) form.elements[k].value = v; });
    calc();
  });
  let t;
  form.addEventListener("input", () => { clearTimeout(t); t = setTimeout(calc, 300); });
  form.addEventListener("change", e => { if (e.target.name === "units") calc(); });
  $("#trim-reset").onclick = () => { reset(); say(""); calc(); };
  $("#trim-load").onclick = () => {
    const r = window.lastTestReport;
    if (!r) return say("Open a test on the Test Report tab first.", false);
    let pts = r.calculated.map(k => ({ q: k.Qc, h: k.Hc, eff: k.eff })).sort((a, b) => a.q - b.q);
    if (pts.length > MAXP) pts = Array.from({ length: MAXP }, (_, i) => pts[Math.round(i * (pts.length - 1) / (MAXP - 1))]);
    setPoints(pts);
    form.elements.units.value = (r.nameplate.q_unit || "LPM").toUpperCase() === "LPM" ? "metric_kw" : form.elements.units.value;
    say(`Loaded ${pts.length} corrected points of ${r.nameplate.sr_no || "the test"} (${r.nameplate.model || ""}). Enter its impeller diameter as D1.`);
    calc();
  };

  fetch("/api/trim/defaults").then(r => r.json()).then(d => {
    defaults = d; MAXP = d.max_points;
    $("#trim-units").innerHTML = d.options.map(o => `<option value="${o.key}">${esc(o.label)}</option>`).join("");
    buildTable(); reset(); calc();
  });
})();
