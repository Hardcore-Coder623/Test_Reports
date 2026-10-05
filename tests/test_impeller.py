"""Impeller / volute results must equal the cached values in Impeller_Design_of_7.5_HP_65x50.xls
(updated sheet: D2 chosen 197, D1 = B15, Dm = (D1 + D2) / 2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from calc import impeller  # noqa: E402

# with Kcm1 / Kcm2 typed as the sheet's external lookup returned them
EXCEL = {
    "nsq": 22, "ns_us": 1135.69408574817, "pin": 10.7714285714286, "eta_h": 0.809716599190283,
    "cm1": 4.14928307060388, "cm2": 2.97918524469359, "d_in_calc": 76.6908046508472,
    "d_eye_nom": 72.2659063143851, "v_in": 4.36969784583665, "u1": 9.69966731795849,
    "beta1_calc": 23.1600675958557, "y": 0.661797268637758, "cp": 1.3900034047902,
    "g_hth": 656.774732258775, "u2": 29.7771051286895, "d2_calc": 0.199544146197809,
    "h_shut": 51.0674754599837, "b2": 0.00888089844438421, "b1": 0.0225323131537063,
    "arc_r1": 57.9943186001092, "arc_r2": 88.5646322926109,
    "wrap1": 91.6013212501159, "wrap2": 94.7722107784431,
    "kccv": 0.415254790023306, "vth": 11.4867311348725, "throat": 40.0904409025484,
    "eta_v_est": 0.964753585011549, "eta_h_est": 0.795394950222947,
}
VANE_B = [22.5155596245484, 17.1213693909611, 14.3702323354307, 12.6954597267227,
          11.4029218557388, 10.0325811107379, 9.00567069660557]
VOL_R = [59.1739130594626, 65.7528873862185, 71.7309724768919, 77.2478001326673,
         82.3960729537058, 87.241062872069, 91.8307860355349, 96.2017852056815]
SYS = {25: 10.3124022413929, 50: 11.2496089655718, 75: 12.8116201725365, 100: 14.9984358622871,
       225: 35.3045815528283, 250: 41.2402241392942, 270: 46.4385974360728}


def run(**over):
    p = impeller.parse({**impeller.DEFAULTS, **over})
    return impeller.calculate(p)


def test_matches_excel():
    r = run()                      # defaults = sheet values (Kcm1 0.15, Kcm2 0.1077)
    raw = r["_raw"]
    for k, v in EXCEL.items():
        assert abs(raw[k] - v) <= max(1e-6, abs(v) * 1e-9), f"{k}: {raw[k]} != {v}"
    for a, b in zip(raw["vane_b"], VANE_B):
        assert abs(a - b) < 0.001
    for a, b in zip(raw["vol_R"], VOL_R):
        assert abs(a - b) < 0.001
    heads = dict(zip([25, 50, 75, 100, 120, 225, 250, 270], raw["sys_head"]))
    for q, h in SYS.items():
        assert abs(heads[q] - h) < 0.001, q


def test_chart_mode_runs():
    raw = run(kcm1="", kcm2="")["_raw"]
    assert raw["nsq"] == 22
    assert abs(raw["cm1"] / (19.62 * 39) ** 0.5 - 0.144) < 1e-9   # chart Kc1 at Ns 22 (20→0.14, 25→0.15)
    assert 0.18 < raw["d2_calc"] < 0.22


def test_b_final_row():
    rows = run()["compact"]["impeller"]["vane_table"]["rows"]
    assert rows[0]["values"] == ["65", "87.0", "109.0", "131.0", "153.0", "175.0", "197"]
    assert rows[5]["values"] == ["22.5", "17.1", "14.4", "12.7", "11.4", "10.0", "9.0"]     # b FINAL
    assert rows[6]["values"] == ["32.5", "43.5", "54.5", "65.5", "76.5", "87.5", "98.5"]
    a = run()["compact"]["impeller"]["arc_table"]["rows"]
    assert a[0][1:] == [76.69, 136.85, 197]
    assert a[3][1] == 88.56463 and a[4][1] == 57.99432 and a[5][1] == 0.661797 and a[6][1] == 0.390003


def test_volute_cross_section_table():
    v = run()["compact"]["volute"]
    rows = {r["label"]: r["values"] for r in v["xs_table"]["rows"]}
    assert rows["Crosection area"][0] == "157.7908" and rows["R"][7] == "96.20179"
    assert rows["Act R"] == ["59", "66", "72", "78", "83", "88", "93", "97"]
    assert dict((k, val) for k, val, _ in v["key"])["Base circle dia (D2 + 7)"] == 204   # B20 = D2 + 7
    tr = [s["trend"] for s in v["charts"][0]["series"]]
    assert tr == ["y = -0.135 ln(x) + 0.831", "y = 0.0062 x^0.9134"]                    # Excel trendlines


def _apply_first_fix(over, section, name):
    """Make a design fail, apply the suggested fix, and return the check before / after."""
    before = run(**over)["compact"][section]["checks"]
    chk = next(c for c in before if c["name"] == name)
    assert chk["status"] == "Fail" and chk["fixes"][0]["apply"], (name, chk)
    after = run(**{**over, **chk["fixes"][0]["apply"]})["compact"][section]["checks"]
    return next(c for c in after if c["name"] == name)


def test_fixes_turn_fail_into_pass():
    assert _apply_first_fix({}, "impeller", "Motor power")["status"] == "Pass"           # 7.5 HP < 10.77
    assert _apply_first_fix({"d2": 180}, "impeller", "Outer dia D2")["status"] == "Pass"
    assert _apply_first_fix({"d2": 230}, "impeller", "Outer dia D2")["status"] == "Pass"
    assert _apply_first_fix({"hp": 15, "eff": 0.9}, "impeller", "Hydraulic efficiency")["status"] == "Pass"
    assert _apply_first_fix({"vol_throat": 35}, "volute", "Throat dia")["status"] == "Pass"
    ok = run(hp=12.5)["compact"]["impeller"]["checks"]
    assert all(c["status"] == "Pass" for c in ok)


if __name__ == "__main__":
    test_volute_cross_section_table()
    test_fixes_turn_fail_into_pass()
    test_b_final_row()
    test_matches_excel()
    test_chart_mode_runs()
    print("Impeller results match the Excel workbook.")
