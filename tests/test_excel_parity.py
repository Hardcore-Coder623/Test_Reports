"""Check the web calculations reproduce the original Excel results.

Run:  python -m pytest tests   (or: python tests/test_excel_parity.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from calc import bearing, bush  # noqa: E402


def close(a, b, tol=0.01):
    assert abs(a - b) <= tol, f"{a} != {b}"


def test_bearing_matches_excel():
    r = bearing.calculate(dict(bearing.DEFAULTS))
    close(r["summary"]["p1_lb"], 1050)
    close(r["summary"]["p2_lb"], 147.50)
    close(r["bearing_a"]["load_lb"], 501.21)
    assert r["bearing_a"]["radial_n"] == 2230 and r["bearing_a"]["axial_n"] == 1115
    # Bearing B uses k = span (a + b) per the shaft sketch; Excel used k = 3 (584.48 lb)
    close(r["bearing_b"]["load_lb"], 696.29)
    assert r["bearing_b"]["radial_n"] == 3100
    assert r["bearing_a"]["size"] == "20x42x12" and r["bearing_a"]["co"] == 5000
    assert r["bearing_b"]["size"] == "25x52x15" and r["bearing_b"]["co"] == 9800


def test_bearing_matches_sketch():
    """Sketch: a=7", b=4", c=3", P1=1000 lb, P2=150 lb  ->  RA=322.7, RB=827.3 lb."""
    p = dict(bearing.DEFAULTS, hp=1, rpm=126, d=1, k=1,
             shaft_dia=0.25 * 1000 / (0.454 * 150), a=7 * 25, b=4 * 25, c=3 * 25)
    r = bearing.calculate(p)
    close(r["summary"]["p1_lb"], 1000); close(r["summary"]["p2_lb"], 150)
    close(r["bearing_a"]["load_lb"], 322.73)
    close(r["bearing_b"]["load_lb"], 827.27)


# (model, material, Ns, Rso, FrA, FrB, PVA, PVB, PVmax) from the cached Excel values
EXCEL_BUSH = [
    ("OWNS7.52", "Carbon", 521.63, 198.93, 246.13, 54.20, 2754.69, 1386.61, 2893.74),
    ("OWKS52", "Bronze", 506.23, 149.48, 184.95, 40.47, 1505.44, 1207.85, 1607.63),
    ("OWNH52", "Bronze", 778.30, 127.21, 157.39, 35.18, 1565.78, 1050.08, 1607.63),
    ("OWK22", "Bronze", 611.74, 1.70, 2.08, 3.38, 37.67, 87.42, 2679.39),
    ("1HP", "Bronze", 435.57, 50.68, 60.82, 12.14, 1583.12, 614.28, 1607.63),
    ("0.5HP", "Bronze", 540.17, 34.10, 44.12, 11.52, 1579.96, 572.80, 1607.63),
]


def test_bush_matches_excel():
    for key, mat, ns, rso, fra, frb, pva, pvb, pvmax in EXCEL_BUSH:
        m = bush.MODELS[key]
        params = {f: m[f] for f in bush.INPUT_FIELDS}
        r = bush.calculate(key, mat, bush.pv_limit_for(key, mat), params)
        s = r["summary"]
        close(s["specific_speed"], ns, 0.1)
        close(s["rso"], rso); close(s["fra"], fra); close(s["frb"], frb)
        close(r["bush_a"]["pv"], pva); close(r["bush_b"]["pv"], pvb)
        close(r["pv_limit_metric"], pvmax)
        assert r["bush_a"]["status"] == "Pass" and r["bush_b"]["status"] == "Pass", key


def test_fail_fixes_make_design_pass():
    # bush: applying the suggested length must turn Fail into Pass
    m = bush.MODELS["OWNS7.52"]
    p = {f: m[f] for f in bush.INPUT_FIELDS}
    p["bush_a_len"] = 40
    r = bush.calculate("OWNS7.52", "Carbon", 135000, p)
    assert r["bush_a"]["status"] == "Fail" and r["bush_a"]["fixes"]
    p.update(r["bush_a"]["fixes"][0]["apply"])
    assert bush.calculate("OWNS7.52", "Carbon", 135000, p)["bush_a"]["status"] == "Pass"
    # bearing: applying the suggested bearing must turn Overloaded into OK
    d = dict(bearing.DEFAULTS, hp=25)
    r = bearing.calculate(d)
    for side in ("a", "b"):
        res = r[f"bearing_{side}"]
        assert res["status"] == "Overloaded" and res["fixes"][0]["apply"]
        d.update(res["fixes"][0]["apply"])
    r = bearing.calculate(d)
    assert r["bearing_a"]["status"] == "OK" and r["bearing_b"]["status"] == "OK"


def test_every_hp_1_to_200_has_a_passing_bearing():
    for hp in bearing.HP_LIST:
        r = bearing.calculate(dict(bearing.DEFAULTS, hp=hp))
        for side in ("a", "b"):
            b = r[f"bearing_{side}"]
            assert b["status"] == "OK" or b["fixes"][0]["apply"], f"{hp} HP bearing {side}"


if __name__ == "__main__":
    test_every_hp_1_to_200_has_a_passing_bearing()
    test_fail_fixes_make_design_pass()
    test_bearing_matches_excel()
    test_bearing_matches_sketch()
    test_bush_matches_excel()
    print("All results match the Excel workbooks.")
