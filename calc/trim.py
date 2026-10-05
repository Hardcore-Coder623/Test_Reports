"""Impeller trim calculator (server side only).

Port of Trim_Calculator.xlsx, sheet "Data Input" (+ chart sheets "Test Curve Trim",
"Larger or Smaller Trim", "Both"): affinity laws for a changed impeller diameter.
  ratio = D2 / D1                      (B23)      Q2 = Q1 x ratio      (C21:J21)
  ratio² (B24)                                     H2 = H1 x ratio²     (K21:R21)
  BHP = Q·H·100 / (3960 · η%)          (C19, C22)  efficiency assumed unchanged
"""
import math

MAX_POINTS = 8
TRIM_WARN = 0.10                       # B26: trims greater than 10 % can reduce hydraulic efficiency

UNITS = {
    # key: (label, flow unit, head unit, power label, power = Q*H/(k*eff))
    "us": ("US - gpm, ft (sheet formula)", "gpm", "ft", "BHP", 3960),
    "metric_kw": ("Metric - LPM, m (kW)", "LPM", "m", "kW", 6120),
    "metric_hp": ("Metric - LPM, m (HP)", "LPM", "m", "HP", 4500),
}

DEFAULTS = {  # Data Input B17, B21, C17:R18
    "d1": 182, "d2": 155, "units": "us",
    "points": [
        {"q": 1057, "h": 10.03, "eff": 27}, {"q": 1011, "h": 21.1, "eff": 44.2},
        {"q": 957, "h": 26.46, "eff": 51.6}, {"q": 805, "h": 30.27, "eff": 52.5},
        {"q": 745, "h": 31.53, "eff": 52}, {"q": 535, "h": 35, "eff": 18},
        {"q": 343, "h": 37.78, "eff": 39}, {"q": 0, "h": 41.7, "eff": 83},
    ],
}


def _num(v):
    if v in ("", None):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _power(q, h, eff, k):
    """C19: (Q*H*100)/(3960*eff); blank when efficiency is 0 or missing (shut-off point)."""
    if eff is None or eff == 0:
        return 0.0 if q == 0 else None
    return q * h * 100 / (k * eff)


def _smooth(points, per_seg=14):
    """Excel 'smoothed line' look (Catmull-Rom through the points, sorted by flow)."""
    pts = sorted(points)
    if len(pts) < 3:
        return [list(p) for p in pts]
    out = []
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else pts[i + 1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        for k in range(per_seg + (1 if i == len(pts) - 2 else 0)):
            t = k / per_seg
            mt = 1 - t
            out.append([round(mt ** 3 * p1[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p2[0], 3),
                        round(mt ** 3 * p1[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p2[1], 4)])
    return out


def calculate(data):
    d1, d2 = _num(data.get("d1")), _num(data.get("d2"))
    if not d1 or d1 <= 0 or not d2 or d2 <= 0:
        raise ValueError("Enter both impeller diameters (greater than zero)")
    units = data.get("units") if data.get("units") in UNITS else "us"
    ulabel, uq, uh, upow, k = UNITS[units]

    pts = []
    for i, p in enumerate((data.get("points") or [])[:MAX_POINTS]):
        q, h, e = _num(p.get("q")), _num(p.get("h")), _num(p.get("eff"))
        if q is None and h is None:
            continue                                            # blank row (sheet: repeat last point)
        if q is None or h is None:
            raise ValueError(f"Point {i + 1}: enter both flow and head")
        if e is not None and not 0 <= e <= 100:
            raise ValueError(f"Point {i + 1}: efficiency must be 0 - 100 %")
        pts.append((q, h, e))
    if len(pts) < 2:
        raise ValueError("Enter at least 2 flow / head points")

    ratio = d2 / d1                                             # B23
    ratio2 = ratio * ratio                                      # B24
    trim = 1 - ratio                                            # + = smaller, - = larger
    rows = []
    for i, (q, h, e) in enumerate(pts):
        q2, h2 = q * ratio, h * ratio2                          # C21, K21
        rows.append({"pt": i + 1, "q1": q, "h1": h, "eff": e, "p1": _power(q, h, e, k),
                     "q2": q2, "h2": h2, "p2": _power(q2, h2, e, k)})

    # check (B26) with the smallest / largest diameter that stays within 10 %
    big = abs(trim) > TRIM_WARN + 1e-12
    if trim > 0:
        lim = math.ceil(d1 * (1 - TRIM_WARN) * 10) / 10
        fix_text = f"Use a diameter of at least {lim:g} mm (10 % trim) - or use a smaller pump / lower speed."
    else:
        lim = math.floor(d1 * (1 + TRIM_WARN) * 10) / 10
        fix_text = f"Keep the diameter at or below {lim:g} mm (10 % larger) - check casing clearance."
    checks = [{
        "name": "Trim amount",
        "status": "Fail" if big else "Pass",
        "detail": f"{'Trim' if trim >= 0 else 'Increase'} {abs(trim) * 100:.1f} % (D2 / D1 = {ratio:.4f}); "
                  f"more than 10 % can reduce hydraulic efficiency",
        "fixes": [{"text": fix_text, "apply": {"d2": lim}}] if big else [],
    }]
    zero_eff = [r["pt"] for r in rows if r["eff"] in (None, 0) and r["q1"] > 0]
    if zero_eff:
        checks.append({"name": "Efficiency data", "status": "Fail",
                       "detail": f"Point(s) {', '.join(map(str, zero_eff))} have flow but no efficiency - "
                                 f"power cannot be calculated", "fixes": []})

    def r(x, n=2):
        return None if x is None else round(x, n)

    tag1, tag2 = f"{d1:g} mm (test)", f"{d2:g} mm ({'trimmed' if trim > 0 else 'larger' if trim < 0 else 'same'})"
    return {
        "units": {"key": units, "label": ulabel, "q": uq, "h": uh, "power": upow},
        "options": [{"key": key, "label": v[0]} for key, v in UNITS.items()],
        "summary": [("Test diameter D1", d1, "mm"), ("New diameter D2", d2, "mm"),
                    ("Diameter ratio D2/D1", r(ratio, 4), ""), ("Head ratio (D2/D1)²", r(ratio2, 4), ""),
                    ("Trim", r(trim * 100, 1), "%"),
                    ("Shut-off head", f"{r(max(p[1] for p in pts), 2)} → {r(max(p[1] for p in pts) * ratio2, 2)}", uh),
                    ("Max flow", f"{r(max(p[0] for p in pts), 1)} → {r(max(p[0] for p in pts) * ratio, 1)}", uq)],
        "rows": [{k: (r(v, 6) if isinstance(v, float) else v) for k, v in row.items()} for row in rows],
        "checks": checks,
        "chart": {
            "title": "Head vs flow - test and trimmed impeller", "x": f"Flow ({uq})", "y": f"Head ({uh})",
            "dual": True,
            "series": [
                {"name": tag1, "axis": "left", "marker": "diamond", "points": [[p[0], p[1]] for p in sorted(pts)],
                 "line": _smooth([(p[0], p[1]) for p in pts])},
                {"name": tag2, "axis": "left", "marker": "square",
                 "points": [[round(p[0] * ratio, 3), round(p[1] * ratio2, 4)] for p in sorted(pts)],
                 "line": _smooth([(p[0] * ratio, p[1] * ratio2) for p in pts])},
            ],
        },
        "_raw": {"ratio": ratio, "ratio2": ratio2, "rows": rows},
    }
