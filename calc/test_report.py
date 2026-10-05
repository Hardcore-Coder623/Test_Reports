"""Pump performance test report (server side only).

Port of sheet "Report" in Test_Report_Program_Tech_Auto_final.xlsm:
observed readings -> calculated / corrected parameters -> duty point, H-min / H-max points
-> declared vs observed conclusion, plus the three graphs.
Cell references are given next to each formula.
"""
import json
import math
import threading
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
_LOCK = threading.Lock()

NAMEPLATE_FIELDS = [
    # (key, label, unit)  - order as on the report (left column, then right column)
    ("sr_no", "Sr. No.", ""), ("date", "Date", ""), ("model", "Type/ Model", ""),
    ("stages", "No. of Stages", ""), ("delivery_size", "Delivery Size", "mm"),
    ("head_g", "Head (HG)", "m"), ("q_g", "Discharge (QG)", ""), ("q_unit", "Discharge unit", ""),
    ("eff_g", "Overall Effi. (%)", "%"), ("min_sub", "Min. Submergence", "m"), ("duty_type", "Type of duty", ""),
    ("motor_kw", "Motor Rating", "kW"), ("motor_hp", "Motor Rating", "HP"), ("rated_speed", "Rated Speed", "RPM"),
    ("rated_current", "Rated Current", "A"), ("rated_voltage", "Rated Voltage", "V AC"),
    ("category", "Category", ""), ("rated_freq", "Rated Freq.", "Hz"), ("winding", "Winding Conn.", ""),
    ("motor_type", "Type of Motor", ""), ("phases", "No. of Phase", ""),
    ("h_min", "Operating H Range from", "m"), ("h_max", "Operating H Range to", "m"),
    ("brand", "Brand", ""), ("isi", "ISI", ""),
]
NUMERIC = {"stages", "delivery_size", "head_g", "q_g", "eff_g", "min_sub", "motor_kw", "motor_hp",
           "rated_current", "rated_voltage", "rated_freq", "phases", "h_min", "h_max"}
REQUIRED = {"delivery_size", "head_g", "q_g", "eff_g", "rated_current", "rated_freq", "phases", "h_min", "h_max"}
READING_FIELDS = ["z", "h", "q", "v", "r", "y", "b", "w", "hz", "n"]     # Z h Q V R Y B W Hz N
MAX_READINGS = 10
Q_TO_LPM = {"LPM": 1, "LPS": 60, "M3/H": 16.667, "M³/H": 16.667}         # G32 unit factor


# ---------------------------------------------------------------- masters (Download / Upload buttons)
def _load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def _save(name, obj):
    tmp = DATA / (name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), default=str)
    tmp.replace(DATA / name)


def models():
    return sorted(n["model"] for n in _load("nameplates.json"))


def nameplate(model):
    for n in _load("nameplates.json"):
        if n["model"].strip().lower() == str(model).strip().lower():
            return n
    return None


def save_nameplate(np):
    keys = [k for k, _, _ in NAMEPLATE_FIELDS if k not in ("sr_no", "date")]
    rec = {k: np.get(k, "") for k in keys}
    if not str(rec["model"]).strip():
        raise ValueError("Enter the model before saving the nameplate")
    with _LOCK:
        all_ = _load("nameplates.json")
        all_ = [n for n in all_ if n["model"].strip().lower() != rec["model"].strip().lower()] + [rec]
        _save("nameplates.json", all_)
    return rec


def serial_numbers(prefix="", limit=50):
    p = str(prefix).strip().lower()
    out = [r["sr_no"] for r in _load("test_records.json") if r["sr_no"].lower().startswith(p)]
    return out[:limit]


def test_record(sr_no):
    for r in _load("test_records.json"):
        if r["sr_no"].strip().lower() == str(sr_no).strip().lower():
            if str(r.get("date", "")).startswith("#"):       # Excel error value (#N/A) -> no date
                r = {**r, "date": ""}
            return r
    return None


def save_test_record(sr_no, date, model, readings):
    if not str(sr_no).strip():
        raise ValueError("Enter the Sr. No. before saving readings")
    rec = {"sr_no": str(sr_no).strip(), "date": date, "model": model,
           "readings": [{f: r.get(f, "") for f in READING_FIELDS} for r in readings]}
    with _LOCK:
        all_ = [r for r in _load("test_records.json") if r["sr_no"].lower() != rec["sr_no"].lower()] + [rec]
        _save("test_records.json", all_)
    return rec


# ---------------------------------------------------------------- helpers
def _num(v):
    if v in ("", None):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _quad3(p1, p2, p3):
    """y = a x² + b x + c through three points (U27/V27/W27 pattern)."""
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    den = (x1 ** 2 - x2 ** 2) * (x2 - x3) - (x2 ** 2 - x3 ** 2) * (x1 - x2)
    if abs(den) < 1e-12 or x2 == x3:
        # points not distinct -> straight line through the first two
        b = (y1 - y2) / (x1 - x2) if x1 != x2 else 0.0
        return 0.0, b, y1 - b * x1
    a = ((y1 - y2) * (x2 - x3) - (y2 - y3) * (x1 - x2)) / den
    b = (y2 - y3 - a * (x2 ** 2 - x3 ** 2)) / (x2 - x3)
    c = y1 - a * x1 ** 2 - b * x1
    return a, b, c


def _qv(coef, x):
    a, b, c = coef
    return a * x * x + b * x + c


def _match_desc(values, x):
    """Excel MATCH(x, descending_array, -1): position of the smallest value >= x (None if none)."""
    idx = None
    for i, v in enumerate(values):
        if v >= x:
            idx = i
    return idx


def _monotone(points, per_seg=16):
    """Fritsch-Carlson monotone cubic: smooth like Excel but never overshoots between close points."""
    pts = sorted(points)
    pts = [p for i, p in enumerate(pts) if i == 0 or p[0] > pts[i - 1][0]]
    n = len(pts)
    if n < 3:
        return [list(p) for p in pts]
    x = [p[0] for p in pts]
    y = [p[1] for p in pts]
    h = [x[i + 1] - x[i] for i in range(n - 1)]
    d = [(y[i + 1] - y[i]) / h[i] for i in range(n - 1)]
    m = [d[0]] + [0.0 if d[i - 1] * d[i] <= 0 else
                  3 * (h[i - 1] + h[i]) / ((2 * h[i] + h[i - 1]) / d[i - 1] + (h[i] + 2 * h[i - 1]) / d[i])
                  for i in range(1, n - 1)] + [d[-1]]
    out = []
    for i in range(n - 1):
        for k in range(per_seg + (1 if i == n - 2 else 0)):
            t = k / per_seg
            h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
            out.append([round(x[i] + t * h[i], 3),
                        round(h00 * y[i] + h10 * h[i] * m[i] + h01 * y[i + 1] + h11 * h[i] * m[i + 1], 4)])
    return out


def _smooth(points, per_seg=16):
    """Excel 'smoothed line' look: Catmull-Rom through the points, sampled as a polyline."""
    pts = sorted(points)
    if len(pts) < 3:
        return [list(p) for p in pts]
    out = []
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else pts[i + 1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        for k in range(per_seg + (1 if i == len(pts) - 2 else 0)):
            t = k / per_seg
            mt = 1 - t
            x = mt ** 3 * p1[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p2[0]
            y = mt ** 3 * p1[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p2[1]
            out.append([round(x, 3), round(y, 4)])
    return out


# ---------------------------------------------------------------- calculation
def parse(data):
    np = {}
    for k, label, _ in NAMEPLATE_FIELDS:
        v = data.get("nameplate", {}).get(k, "")
        if k in NUMERIC:
            n = _num(v)
            if n is None and k in REQUIRED:
                raise ValueError(f"Nameplate: enter {label}")
            np[k] = n
        else:
            np[k] = "" if v is None else str(v).strip()
    np["q_unit"] = np["q_unit"] or "LPM"
    rows = []
    for i, r in enumerate(data.get("readings", [])[:MAX_READINGS]):
        vals = {f: _num(r.get(f)) for f in READING_FIELDS}
        if vals["h"] is None and vals["q"] is None:
            continue                                                   # blank row (B18: IF(D18<>"", ...))
        for f in ("z", "h", "q", "w", "hz", "n"):
            if vals[f] is None:
                raise ValueError(f"Reading {i + 1}: enter {f.upper() if f != 'hz' else 'Frequency'}")
        if vals["hz"] <= 0 or vals["w"] <= 0:
            raise ValueError(f"Reading {i + 1}: frequency and motor input must be greater than zero")
        rows.append(vals)
    if len(rows) < 3:
        raise ValueError("Enter at least 3 readings")
    return np, rows


def calculate(np, rows):
    fr = np["rated_freq"]                                              # H8
    unit = np["q_unit"].upper().replace(" ", "")
    to_lpm = Q_TO_LPM.get(unit, 1)
    d_pipe = np["delivery_size"] / 1000                                # D7
    observed, calc = [], []
    for i, r in enumerate(rows):
        slip = (60 * fr - fr / r["hz"] * r["n"]) / 60 / fr                       # M18
        q_lpm = r["q"] * to_lpm
        vh = round((q_lpm / 60000 / (math.pi / 4 * d_pipe ** 2)) ** 2 / 2 / 9.81, 2)   # C32
        H = r["z"] + r["h"] + vh                                                    # D32
        three = [r[k] for k in ("r", "y", "b") if r[k] is not None]
        if np["phases"] == 3:                                                       # E32
            cur = sum(three) / 3 if len(three) == 3 else (max(three) if three else 0)
        else:
            cur = r["b"] if r["b"] is not None else (max(three) if three else 0)
        kw = r["w"] / 1000                                                          # F32
        eff = H * r["q"] * to_lpm / 6120 / kw                                       # G32
        k = fr / r["hz"]
        observed.append({"sr": i + 1, **r, "slip": slip})
        calc.append({"sr": i + 1, "vh": vh, "H": H, "I": cur, "kw": kw, "eff": eff,
                     "Hc": k ** 2 * H, "Qc": k * r["q"], "Pc": k ** 3 * kw, "Nc": k * r["n"]})  # H32:K32

    # corrected points (Table2 / Table24) - by rising discharge, i.e. falling head
    pts = sorted(({"Q": c["Qc"], "H": c["Hc"], "I": c["I"], "E": c["eff"]} for c in calc), key=lambda p: p["Q"])
    n = len(pts)
    heads = [p["H"] for p in pts]
    p0 = pts[0]                                     # lowest-discharge reading (shut-off point, R29 = 0)

    def bracket(H, plus_one=False):
        i = _match_desc(heads, H)
        if i is None:
            i = 0
        elif plus_one:                              # H-max uses the reading after the match (Q31)
            i += 1
        i = max(0, min(i, n - 2))
        return pts[i], pts[i + 1]

    def point(H, plus_one=False):
        a_, b_ = bracket(H, plus_one)
        # head curve Q = aH² + c: H-min / H-duty through Rdg-1 and Rdg-2 (U26, U35);
        # H-max through Rdg-2 and the shut-off reading (U30 uses rows 32 and 33)
        f1, f2 = (b_, p0) if plus_one else (a_, b_)
        if f1["H"] == f2["H"]:
            raise ValueError("Two readings have the same corrected head - check readings")
        a = (f1["Q"] - f2["Q"]) / (f1["H"] ** 2 - f2["H"] ** 2)                # U26 / U30 / U35
        c = f1["Q"] - a * f1["H"] ** 2                                          # W26 / W30 / W35
        cur = _quad3((a_["Q"], a_["I"]), (b_["Q"], b_["I"]), (p0["Q"], p0["I"]))  # U27..W27
        eff = _quad3((a_["Q"], a_["E"]), (b_["Q"], b_["E"]), (p0["Q"], p0["E"]))  # U28..W28
        return a, c, cur, eff

    # H-min (rows 26-29), H-max (rows 30-33), H-duty (rows 35-38)
    out_pts = {}
    for key, H, plus in (("hmin", np["h_min"], False), ("hmax", np["h_max"], True), ("hduty", np["head_g"], False)):
        a, c, cur, eff = point(H, plus)
        Q = a * H * H + c                                                       # R26 / R30 / R35
        out_pts[key] = {"H": H, "Q": Q, "I": _qv(cur, Q), "E": _qv(eff, Q), "a": a, "c": c,
                        "cur": cur, "eff": eff}

    # observed duty point: curve Q = aH² + c meets the line through origin and (QG, HG)   (rows 39-43)
    d = out_pts["hduty"]
    s = np["q_g"] / np["head_g"]                                                # S41
    disc = s ** 4 - 4 * d["a"] * d["c"] * s ** 2
    if disc < 0 or d["a"] == 0:
        raise ValueError("Pump curve does not reach the duty line - check readings")
    roots = [(s ** 2 + sg * math.sqrt(disc)) / (2 * d["a"]) for sg in (1, -1)]     # U43 / V43
    Qo = max(roots)
    Ho = Qo / s                                                                 # T43
    Io, Eo = _qv(d["cur"], Qo), _qv(d["eff"], Qo)                               # S39, T39

    # conclusion (rows 43-47)
    QG, HG = np["q_g"], np["head_g"]
    dH = HG - Ho if Ho < HG else None                                           # J44 (">HG")
    dQ = QG - Qo if Qo < QG else None                                           # K44 (">QG")
    try:
        L = (QG * 0.07 / dQ) ** 2 + (HG * 0.04 / dH) ** 2 if dQ is not None and dH is not None else None
    except ZeroDivisionError:
        L = None
    hq_pass = L is None or L > 1                                                # M44
    eff_pass = Eo * 100 > 0.955 * np["eff_g"]                                   # M46
    i_limit = np["rated_current"] * 1.07                                        # D47
    i_max = max(out_pts["hmin"]["I"], out_pts["hmax"]["I"], d["I"])             # H47
    i_pass = not i_max > i_limit                                                # M47
    passed = hq_pass and eff_pass and i_pass                                    # J43

    # ---- graphs
    hmin, hmax = out_pts["hmin"], out_pts["hmax"]
    qx, hx = max(Qo, QG), max(Ho, HG)                                           # R40, Q40
    red_h = HG * (1.1 if HG > Ho else 0.9)                                      # V39
    red_q = QG * (1.1 if QG > Qo else 0.9)                                      # V40
    hq = {
        "title": "Head (m)", "x": "Discharge (" + np["q_unit"] + ")", "y": "Head (m)",
        "curve": _smooth([(p["Q"], p["H"]) for p in pts]),
        "dashed": [[[0, 0], [qx, hx]], [[Qo, 0], [Qo, Ho]],
                   [[0, hmin["H"]], [hmin["Q"], hmin["H"]]], [[hmin["Q"], 0], [hmin["Q"], hmin["H"]]],
                   [[0, hmax["H"]], [hmax["Q"], hmax["H"]]], [[hmax["Q"], 0], [hmax["Q"], hmax["H"]]]],
        "red": [[[QG, HG], [QG, red_h]], [[QG, HG], [red_q, HG]]],
    }
    cur_curve = sorted([(pts[-1]["Q"], pts[-1]["I"]), (hmin["Q"], hmin["I"]), (Qo, Io),
                        (hmax["Q"], hmax["I"]), (pts[0]["Q"], pts[0]["I"])])    # U3:W7
    current = {
        "title": "Current (A)", "x": "Discharge", "y": "Current (A)",
        "curve": _monotone(cur_curve),
        "dashed": [[[Qo, 0], [Qo, Io]], [[hmin["Q"], 0], [hmin["Q"], hmin["I"]]],
                   [[hmax["Q"], 0], [hmax["Q"], hmax["I"]]]],
        "red": [],
    }
    effc = {
        "title": "Overall efficiency (%)", "x": "Discharge (" + np["q_unit"] + ")", "y": "Overall efficiency (%)",
        "curve": _smooth([(p["Q"], p["E"] * 100) for p in pts]),
        "dashed": [], "red": [],
        "solid": [[[Qo, 0], [Qo, Eo * 100]], [[hmin["Q"], 0], [hmin["Q"], hmin["E"] * 100]],
                  [[hmax["Q"], 0], [hmax["Q"], hmax["E"] * 100]]],
        "percent": True,
    }

    def r(x, n=2):
        return None if x is None else round(x, n)

    return {
        "nameplate": np,
        "observed": [{"sr": o["sr"], "z": o["z"], "h": o["h"], "q": o["q"], "v": o["v"], "r": o["r"],
                      "y": o["y"], "b": o["b"], "w": o["w"], "hz": o["hz"], "n": o["n"],
                      "slip": r(o["slip"] * 100, 2)} for o in observed],
        "calculated": [{"sr": c["sr"], "vh": r(c["vh"], 2), "H": r(c["H"], 2), "I": r(c["I"], 2),
                        "kw": r(c["kw"], 3), "eff": r(c["eff"] * 100, 2), "Hc": r(c["Hc"], 2),
                        "Qc": r(c["Qc"], 2), "Pc": r(c["Pc"], 3), "Nc": round(c["Nc"])} for c in calc],
        "points": {
            "duty": {"Q": r(Qo), "H": r(Ho), "I": r(Io), "eff": r(Eo * 100)},
            "hmin": {"H": hmin["H"], "Q": r(hmin["Q"]), "I": r(hmin["I"]), "eff": r(hmin["E"] * 100)},
            "hmax": {"H": hmax["H"], "Q": r(hmax["Q"]), "I": r(hmax["I"]), "eff": r(hmax["E"] * 100)},
            "hduty": {"H": d["H"], "Q": r(d["Q"]), "I": r(d["I"])},
        },
        "conclusion": {
            "declared": {"q": QG, "h": HG, "eff": np["eff_g"], "i_max": r(i_limit)},
            "observed": {"q": r(Qo), "h": r(Ho), "eff": r(Eo * 100), "i_max": r(i_max)},
            "dh": r(dH) if dH is not None else ">HG", "dq": r(dQ) if dQ is not None else ">QG",
            "ellipse": r(L, 3),
            "hq": "Pass" if hq_pass else "FAIL",
            "eff": "Pass" if eff_pass else "FAIL",
            "current": "Pass" if i_pass else "FAIL",
            "overall": "Pass" if passed else "FAIL",
        },
        "charts": [hq, current, effc],
        "_raw": {"Qo": Qo, "Ho": Ho, "Io": Io, "Eo": Eo, "hmin": hmin, "hmax": hmax, "hduty": d,
                 "calc": calc, "i_max": i_max},
    }


def run(data):
    np, rows = parse(data)
    return calculate(np, rows)
