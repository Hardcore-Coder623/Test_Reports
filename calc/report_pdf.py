"""A4 landscape PDF of the pump test report (layout of sheet "Report").

Left: name plate data, observed parameters, calculated / corrected parameters, conclusion.
Right: head, current and efficiency graphs, signatures.
All numbers come from calc.test_report - nothing is calculated here except drawing positions.
"""
import io
import json
import math
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

LOGO = Path(__file__).resolve().parent.parent / "static" / "report_logo.jpg"
COMPANY = Path(__file__).resolve().parent.parent / "data" / "company.json"


def _address():
    try:
        return [r["line"] for r in json.loads(COMPANY.read_text(encoding="utf-8")) if r.get("line")]
    except (OSError, ValueError):
        return []
W, H = landscape(A4)                    # 842 x 595 pt
M = 16                                  # page margin
INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#555555")
GRID = colors.HexColor("#c8c8c8")
HEAD_BG = colors.HexColor("#e9eef5")
PASS = colors.HexColor("#1d7a43")
FAIL = colors.HexColor("#c0261c")
BLUE = colors.HexColor("#1f5fa8")


def _fmt(v, nd=2):
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer() and nd <= 2:
            return f"{int(v)}" if abs(v) >= 100 or nd == 0 else f"{v:.{nd}f}"
        return f"{v:.{nd}f}"
    return str(v)


def _text_width(c, txt, font, size):
    parts = txt.split("²")
    w = sum(c.stringWidth(p_, font, size) for p_ in parts)
    return w + (len(parts) - 1) * c.stringWidth("2", font, size * 0.65)


def _draw_text(c, x, y, txt, font, size):
    """drawString that renders '²' as a raised small 2 (the base PDF fonts have no superscript glyph)."""
    parts = txt.split("²")
    for i, part in enumerate(parts):
        c.setFont(font, size)
        c.drawString(x, y, part)
        x += c.stringWidth(part, font, size)
        if i < len(parts) - 1:
            c.setFont(font, size * 0.65)
            c.drawString(x, y + size * 0.4, "2")
            x += c.stringWidth("2", font, size * 0.65)


class _Grid:
    """Simple ruled table: column x-positions, fixed row height."""

    def __init__(self, c, x, y, widths, rh):
        self.c, self.x, self.y, self.w, self.rh = c, x, y, widths, rh
        self.xs = [x]
        for w in widths:
            self.xs.append(self.xs[-1] + w)

    def row(self, cells, bold=False, bg=None, size=7, align=None, color=None, spans=None):
        c = self.c
        top, bot = self.y, self.y - self.rh
        spans = spans or [1] * len(cells)
        col = 0
        for i, txt in enumerate(cells):
            x0, x1 = self.xs[col], self.xs[col + spans[i]]
            if bg:
                c.setFillColor(bg)
                c.rect(x0, bot, x1 - x0, self.rh, stroke=0, fill=1)
            c.setStrokeColor(INK)
            c.setLineWidth(0.4)
            c.rect(x0, bot, x1 - x0, self.rh, stroke=1, fill=0)
            c.setFillColor(color[i] if isinstance(color, list) and color[i] else (color or INK)
                           if not isinstance(color, list) else INK)
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            a = (align[i] if align else "c")
            ty = bot + (self.rh - size) / 2 + 1.2
            font = "Helvetica-Bold" if bold else "Helvetica"
            tw = _text_width(c, str(txt), font, size)
            tx = x0 + 2.5 if a == "l" else (x1 - 2.5 - tw if a == "r" else (x0 + x1 - tw) / 2)
            _draw_text(c, tx, ty, str(txt), font, size)
            col += spans[i]
        self.y = bot
        return self


def _nice(lo, hi, n=5):
    span = (hi - lo) or abs(hi) or 1
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    a, b = math.floor(lo / step) * step, math.ceil(hi / step) * step
    return [round(a + i * step, 6) for i in range(int(round((b - a) / step)) + 1)]


def _chart(c, x, y, w, h, ch):
    """Draw one graph inside the box (x, y) bottom-left, w x h."""
    pad_l, pad_b, pad_t, pad_r = 34, 22, 6, 8
    px, py, pw, ph = x + pad_l, y + pad_b, w - pad_l - pad_r, h - pad_b - pad_t
    xs = [p[0] for p in ch["curve"]] + [pt[0] for seg in ch.get("dashed", []) + ch.get("red", []) for pt in seg]
    ys = [p[1] for p in ch["curve"]] + [pt[1] for seg in ch.get("dashed", []) + ch.get("red", []) +
                                        ch.get("solid", []) for pt in seg]
    xt = _nice(0, max(xs) * 1.05 or 1, 6)
    yt = _nice(0, max(ys) * 1.08 or 1, 6)
    X = lambda v: px + (v - xt[0]) / (xt[-1] - xt[0]) * pw          # noqa: E731
    Y = lambda v: py + (v - yt[0]) / (yt[-1] - yt[0]) * ph          # noqa: E731

    # fine grid (5 minor divisions) like the Excel chart
    c.setStrokeColor(colors.HexColor("#e2e2e2"))
    c.setLineWidth(0.25)
    for i in range(len(xt) - 1):
        for k in range(1, 5):
            gx = X(xt[i] + (xt[i + 1] - xt[i]) * k / 5)
            c.line(gx, py, gx, py + ph)
    for i in range(len(yt) - 1):
        for k in range(1, 5):
            gy = Y(yt[i] + (yt[i + 1] - yt[i]) * k / 5)
            c.line(px, gy, px + pw, gy)
    c.setStrokeColor(GRID)
    c.setLineWidth(0.5)
    for v in xt:
        c.line(X(v), py, X(v), py + ph)
    for v in yt:
        c.line(px, Y(v), px + pw, Y(v))
    c.setStrokeColor(INK)
    c.setLineWidth(0.8)
    c.rect(px, py, pw, ph, stroke=1, fill=0)

    c.setFillColor(INK)
    c.setFont("Helvetica", 6.5)
    for v in xt:
        c.drawCentredString(X(v), py - 8, f"{v:g}")
    for v in yt:
        c.drawRightString(px - 3, Y(v) - 2.2, (f"{v:g}%" if ch.get("percent") else f"{v:g}"))
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(px + pw / 2, y + 3, ch["x"])
    c.saveState()
    c.translate(x + 7, py + ph / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, ch["y"])
    c.restoreState()

    def seg(points, color, width, dash=None):
        c.setStrokeColor(color)
        c.setLineWidth(width)
        c.setDash(*dash) if dash else c.setDash()
        p = c.beginPath()
        p.moveTo(X(points[0][0]), Y(points[0][1]))
        for q in points[1:]:
            p.lineTo(X(q[0]), Y(q[1]))
        c.drawPath(p, stroke=1, fill=0)
        c.setDash()

    for s in ch.get("dashed", []):
        seg(s, INK, 0.7, (3, 2))
    for i, s in enumerate(ch.get("solid", [])):
        seg(s, [colors.HexColor("#2e9b3d"), colors.HexColor("#5b7fd6"), colors.HexColor("#8a8a8a")][i % 3], 0.8)
    for s in ch.get("red", []):
        seg(s, colors.HexColor("#c00000"), 1.1)
    if ch["curve"]:
        seg(ch["curve"], INK, 1.5)


def _date(d):
    """2022-04-04 -> 04-04-2022 (as on the sheet)."""
    d = "" if str(d or "").startswith("#") else str(d or "")      # Excel error value (#N/A)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", d)
    return f"{m[3]}-{m[2]}-{m[1]}" if m else d


def build_pdf(r):
    """r = result of calc.test_report.calculate(); returns PDF bytes."""
    np = dict(r["nameplate"])
    np["date"] = _date(np.get("date"))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Test Report {np.get('sr_no', '')}")
    c.setAuthor(np.get("brand", "") or "Pump Design Calculator")

    LX, LW = M, 492                                  # left block
    RX, RW = LX + LW + 10, W - (LX + LW + 10) - M    # right block (graphs)

    # ---- header
    top = H - M
    if LOGO.exists():
        c.drawImage(ImageReader(str(LOGO)), LX, top - 30, width=90, height=30, mask="auto")
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(INK)
    c.drawString(LX + 100, top - 14, "PUMP PERFORMANCE TEST REPORT")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    c.drawString(LX + 100, top - 25, f"Sr. No. {np.get('sr_no', '')}   ·   Model {np.get('model', '')}   ·   "
                                     f"Date {np.get('date', '')}")
    addr = _address()                                  # Report R45
    for i, line in enumerate(addr[:4]):
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 7.5 if i == 0 else 6.5)
        c.setFillColor(INK if i == 0 else MUTED)
        c.drawRightString(LX + LW, top - 7 - i * 8, line)
    y = top - 36

    # ---- name plate data (2 x 2 columns)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(LX, y - 9, "Name Plate Data:")
    y -= 12
    unit = np.get("q_unit") or "LPM"
    left = [("Sr. No.:", np.get("sr_no", "")), ("Date:", np.get("date", "")), ("Type/ Model:", np.get("model", "")),
            ("No. of Stages:", _fmt(np.get("stages"), 0)), ("Delivery Size:", f"{_fmt(np.get('delivery_size'), 0)} mm"),
            ("--- Duty Point ---", ""), ("Head (HG):", f"{_fmt(np.get('head_g'), 1)} m"),
            ("Discharge (QG):", f"{_fmt(np.get('q_g'), 0)} {unit}"), ("Overall Effi. (%):", f"{_fmt(np.get('eff_g'), 0)} %"),
            ("Min. Submergence:", f"{_fmt(np.get('min_sub'), 1)} m"), ("Type of duty:", np.get("duty_type", ""))]
    right = [("Motor Rating:", f"{_fmt(np.get('motor_kw'), 1)} kW / {_fmt(np.get('motor_hp'), 1)} HP"),
             ("Rated Speed:", f"{np.get('rated_speed') or ''} RPM"), ("Rated Current:", f"{_fmt(np.get('rated_current'), 1)} A"),
             ("Rated Voltage:", f"{_fmt(np.get('rated_voltage'), 0)} V AC"), ("Category:", np.get("category", "")),
             ("Rated Freq.:", f"{_fmt(np.get('rated_freq'), 0)} Hz"), ("Winding Conn.:", np.get("winding", "")),
             ("Type of Motor:", np.get("motor_type", "")), ("No. of Phase:", _fmt(np.get("phases"), 0)),
             ("Operating H Range:", f"{_fmt(np.get('h_min'), 0)}  to  {_fmt(np.get('h_max'), 0)} m"),
             ("Brand:", np.get("brand", ""))]
    g = _Grid(c, LX, y, [78, 112, 96, 206], 11.2)
    for (l1, v1), (l2, v2) in zip(left, right):
        g.row([l1, v1, l2, v2], align=["r", "l", "r", "l"], size=6.8)
    y = g.y - 8

    # ---- observed parameters
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(INK)
    c.drawString(LX, y - 9, "Observed Parameters:")
    y -= 12
    ow = [26, 30, 34, 46, 34, 34, 34, 34, 50, 50, 50, 70]
    g = _Grid(c, LX, y, ow, 11.6)
    g.row(["Sr. No.", "Head (m)", f"Discharge", "Voltage", "Current (A)", "Motor Input", "Frequency",
           "Speed", "Slip (%)"], bold=True, bg=HEAD_BG, size=6.3, spans=[1, 2, 1, 1, 3, 1, 1, 1, 1])
    g.row(["", "Z *", "h *", f"({unit})", "(V)", "R/ I MAIN", "Y/ I AUX", "B/ I COM", "(W)", "(Hz)", "(RPM)", ""],
          bold=True, bg=HEAD_BG, size=6.3)
    obs = r["observed"]
    for i in range(10):
        if i < len(obs):
            o = obs[i]
            g.row([o["sr"], _fmt(o["z"], 1), _fmt(o["h"], 1), _fmt(o["q"], 1), _fmt(o["v"], 0), _fmt(o["r"]),
                   _fmt(o["y"]), _fmt(o["b"]), _fmt(o["w"], 0), _fmt(o["hz"]), _fmt(o["n"], 0),
                   f"{o['slip']:.2f}%"], size=6.6)
        else:
            g.row([""] * 12, size=6.6)
    y = g.y - 8

    # ---- calculated / corrected parameters
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(INK)
    c.drawString(LX, y - 9, "Calculated/ Corrected Parameters:")
    y -= 12
    cw = [26, 40, 40, 46, 46, 56, 52, 60, 56, 70]
    g = _Grid(c, LX, y, cw, 11.6)
    g.row(["Sr. No.", "Head (m)", "Current (A)", "Input", "Overall", f"Corrected @ {_fmt(np.get('rated_freq'), 0)} Hz"],
          bold=True, bg=HEAD_BG, size=6.3, spans=[1, 2, 1, 1, 1, 4])
    g.row(["", "V²/2g *", "H *", "", "(kW)", "Effi. (%)", "Head (m)", f"Disch. ({unit})", "Input (kW)", "RPM"],
          bold=True, bg=HEAD_BG, size=6.3)
    cal = r["calculated"]
    for i in range(10):
        if i < len(cal):
            k = cal[i]
            g.row([k["sr"], _fmt(k["vh"]), _fmt(k["H"]), _fmt(k["I"]), _fmt(k["kw"], 3), f"{k['eff']:.2f}%",
                   _fmt(k["Hc"]), _fmt(k["Qc"]), _fmt(k["Pc"], 3), k["Nc"]], size=6.6)
        else:
            g.row([""] * 10, size=6.6)
    c.setFillColor(MUTED)
    _draw_text(c, LX, g.y - 7, "* Z = distance of gauge centre from water level (m)  ·  h = delivery gauge reading (m)  ·  "
                               "V²/2g = velocity head correction  ·  H = total head = Z + h + V²/2g", "Helvetica", 5.8)
    _draw_text(c, LX, g.y - 14, "  Refer IS 14220, latest versions and amendments including relative STI",
               "Helvetica", 5.8)
    y = g.y - 20

    # ---- declared vs observed + conclusion
    con = r["conclusion"]
    dec, ob = con["declared"], con["observed"]
    g = _Grid(c, LX, y, [96, 70, 96, 70, 110, 50], 12)
    overall = con["overall"]
    g.row(["Declared Values", "Observed Values", f"Conclusion: {overall}"], bold=True, bg=HEAD_BG, size=7,
          spans=[2, 2, 2], color=[None, None, PASS if overall == "Pass" else FAIL])
    g.row(["Discharge (QG):", f"{_fmt(dec['q'], 0)} {unit}", "Discharge:", f"{_fmt(ob['q'])} {unit}",
           f"{con['dh']}   {con['dq']}", con["hq"]], size=6.8, align=["r", "l", "r", "l", "c", "c"],
          color=[None] * 5 + [PASS if con["hq"] == "Pass" else FAIL])
    g.row(["Head (HG):", f"{_fmt(dec['h'], 1)} m", "Head:", f"{_fmt(ob['h'])} m",
           "Head & Discharge Requirements:", con["hq"]], size=6.8, align=["r", "l", "r", "l", "l", "c"],
          color=[None] * 5 + [PASS if con["hq"] == "Pass" else FAIL])
    g.row(["Overall Effi. (%):", f"{_fmt(dec['eff'], 1)} %", "Overall Effi. (%):", f"{_fmt(ob['eff'])} %",
           "Overall Efficiency Requirements:", con["eff"]], size=6.8, align=["r", "l", "r", "l", "l", "c"],
          color=[None] * 5 + [PASS if con["eff"] == "Pass" else FAIL])
    g.row(["Current (A):", f"{_fmt(dec['i_max'])} A, Max", "Current H-Range:", f"{_fmt(ob['i_max'])} A, Max",
           "Maximum Current Requirements:", con["current"]], size=6.8, align=["r", "l", "r", "l", "l", "c"],
          color=[None] * 5 + [PASS if con["current"] == "Pass" else FAIL])

    # ---- graphs (right)
    c.setStrokeColor(INK)
    c.setLineWidth(0.6)
    c.line(RX - 5, M, RX - 5, H - M)
    sig_h = 34
    gh = (H - 2 * M - sig_h - 8) / 3
    titles = r["charts"]
    for i, ch in enumerate(titles):
        _chart(c, RX, H - M - (i + 1) * gh, RW, gh - 4, ch)

    # ---- signatures
    sy = M
    c.setLineWidth(0.6)
    c.rect(RX, sy, RW / 2, sig_h, stroke=1, fill=0)
    c.rect(RX + RW / 2, sy, RW / 2, sig_h, stroke=1, fill=0)
    c.setFont("Helvetica", 7)
    c.setFillColor(INK)
    c.drawCentredString(RX + RW / 4, sy + 4, "Tested By")
    c.drawCentredString(RX + 3 * RW / 4, sy + 4, "Approved By")

    c.showPage()
    c.save()
    return buf.getvalue()
