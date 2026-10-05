"""Ball bearing load calculation (server side only).

Faithful port of sheet "Ball" in Bearing_Calculation.xlsx.
"""
import json
import math
from pathlib import Path

_DATA, BEARINGS = [], {}


def reload():
    """(Re)load the bearing master (called after a Masters save)."""
    global _DATA, BEARINGS
    _DATA = json.loads((Path(__file__).resolve().parent.parent / "data" / "bearings.json").read_text(encoding="utf-8"))
    BEARINGS = {b["designation"]: b for b in _DATA}


reload()

DEFAULTS = {
    "hp": 7.5, "rpm": 2700, "d": 1, "k": 3,
    "a": 155, "b": 155, "c": 50, "shaft_dia": 28,   # a = b = CL/2 + ext (170/2 + 70)
    "bearing_a": "6004", "qty_a": 1,
    "bearing_b": "6205", "qty_b": 2,
}


# Standard motor ratings, 1 to 200 HP (HP field still accepts any value)
HP_LIST = [1, 1.5, 2, 3, 4, 5, 5.5, 7.5, 10, 12.5, 15, 20, 25, 30, 40, 50, 60, 75,
           100, 125, 150, 175, 200]


def _excel_round(x, digits=0):
    """Excel ROUND (half away from zero)."""
    m = 10 ** digits
    return math.copysign(math.floor(abs(x) * m + 0.5) / m, x)


def options():
    """Only what the front page needs to build its dropdowns (no ratings)."""
    bores = sorted({b["d"] for b in _DATA})
    return {
        "bores": bores,
        "bearings": [{"designation": b["designation"], "d": b["d"]} for b in _DATA],
        "defaults": DEFAULTS,
        "hp_list": HP_LIST,
    }


def _fixes(side, b, radial_n, same_bore_pick):
    """How to turn an overloaded bearing into a passing one."""
    key = f"bearing_{side}"
    if same_bore_pick:
        x = BEARINGS[same_bore_pick]
        return [{
            "text": f'Change to {x["designation"]} ({x["d"]}x{x["D"]}x{x["B"]}, Co {x["Co"]:,} N) '
                    f'on the same {b["d"]} mm bore.',
            "apply": {key: x["designation"]},
        }]
    bigger = [x for x in _DATA if x["d"] > b["d"] and x["Co"] >= radial_n]
    if bigger:
        x = min(bigger, key=lambda x: (x["d"], x["Co"]))
        return [{
            "text": f'No bearing on {b["d"]} mm bore carries {radial_n:,.0f} N. '
                    f'Use {x["designation"]} ({x["d"]}x{x["D"]}x{x["B"]}, Co {x["Co"]:,} N) - '
                    f'shaft at this bearing must be {x["d"]} mm.',
            "apply": {key: x["designation"]},
        }]
    return [{
        "text": "No bearing in the table carries this load. Reduce the load "
                "(shorter overhang c, longer span a + b) or add larger bearings to data/bearings.json.",
        "apply": None,
    }]


def _bearing_out(side, designation, qty, radial_n, axial_n):
    b = BEARINGS.get(str(designation))
    if b is None:
        raise ValueError(f"Unknown bearing designation: {designation}")
    ok = b["Co"] >= radial_n
    # lightest bearing on the same bore that carries the load
    same_bore = [x for x in _DATA if x["d"] == b["d"] and x["Co"] >= radial_n]
    suggestion = min(same_bore, key=lambda x: x["Co"])["designation"] if same_bore else None
    return {
        "fixes": [] if ok else _fixes(side, b, radial_n, suggestion),
        "designation": b["designation"],
        "size": f'{b["d"]}x{b["D"]}x{b["B"]}',
        "co": b["Co"],
        "c_dyn": b.get("C"),
        "qty": qty,
        "radial_n": radial_n,
        "axial_n": axial_n,
        "load_ratio": round(radial_n / b["Co"] * 100, 1),
        "status": "OK" if ok else "Overloaded",
        "suggested": suggestion,
    }


def calculate(p):
    hp, rpm, d, k = p["hp"], p["rpm"], p["d"], p["k"]
    c_mm, shaft = p["c"], p["shaft_dia"]
    if rpm <= 0 or d == 0 or shaft <= 0:
        raise ValueError("RPM, d and shaft diameter must be greater than zero")

    p1_lb = 126000 * hp / rpm / d * k            # E10
    p1_kg = p1_lb * 0.454                        # E11
    torque = hp / 4                              # F12
    p2_kg = torque / shaft * 1000                # F11
    p2_lb = p2_kg / 0.454                        # F10

    # Layout (see diagram):  Brg A --a-- P1 --b-- Brg B --c-- P2 ;  span L = a + b
    a_mm, b_mm = p["a"], p["b"]
    if a_mm < 0 or b_mm < 0 or c_mm < 0:
        raise ValueError("Distances a, b and c cannot be negative")
    a_in, b_in, c_in = a_mm / 25, b_mm / 25, c_mm / 25
    span_in = a_in + b_in                        # D11
    if span_in == 0:
        raise ValueError("Bearing span (a + b) cannot be zero")

    # moments about Brg B / Brg A
    ra_lb = ((p1_lb * b_in) - (p2_lb * c_in)) / span_in                 # B18
    rb_lb = ((p1_lb * a_in) + (c_in + span_in) * p2_lb) / span_in       # B19 (k = span)

    out = {}
    for key, r_lb, des, qty in (("A", ra_lb, p["bearing_a"], p["qty_a"]),
                                ("B", rb_lb, p["bearing_b"], p["qty_b"])):
        r_kg = r_lb * 0.454
        radial_n = _excel_round(r_kg * 9.81 / 10) * 10
        axial_n = radial_n / 2
        res = _bearing_out(key.lower(), des, qty, radial_n, axial_n)
        res["load_lb"] = round(r_lb, 2)
        res["load_kg"] = round(r_kg, 2)
        out[key] = res

    return {
        "summary": {
            "p1_lb": round(p1_lb, 2), "p1_kg": round(p1_kg, 2),
            "p2_lb": round(p2_lb, 2), "p2_kg": round(p2_kg, 2),
            "torque": round(torque, 3),
            "a_mm": a_mm, "b_mm": b_mm, "c_mm": c_mm,
            "span_mm": a_mm + b_mm, "span_in": round(span_in, 2),
        },
        "bearing_a": out["A"],
        "bearing_b": out["B"],
    }
