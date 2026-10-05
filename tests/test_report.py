"""Test report results must equal the cached values in Test_Report_Program_Tech_Auto_final.xlsm
(sheet Report, Sr. No. LSPA1VD000551, model OWS-15.2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from calc import test_report as T  # noqa: E402

NAMEPLATE = {"sr_no": "LSPA1VD000551", "date": "2022-04-04", "model": "OWS-15.2", "stages": 1,
             "delivery_size": 100, "head_g": 29.5, "q_g": 1710, "q_unit": "LPM", "eff_g": 59, "min_sub": 0.5,
             "duty_type": "S1", "motor_kw": 11, "motor_hp": 15, "rated_speed": "", "rated_current": 29,
             "rated_voltage": 415, "category": "B", "rated_freq": 50, "winding": "DELTA",
             "motor_type": "Induction", "phases": 3, "h_min": 19, "h_max": 36, "brand": "Crompton"}
READINGS = [  # Report C18:L23
    dict(z=1.8, h=38.5, q=0, v=415, b=12.06, w=6808, hz=49.54, n=2913),
    dict(z=1.8, h=36.3, q=789.4, v=415, b=21.5, w=11884, hz=49.58, n=2897),
    dict(z=1.8, h=34.8, q=1184.1, v=415, b=23.41, w=12765, hz=49.63, n=2894),
    dict(z=1.8, h=31.3, q=1667.6, v=415, b=23.41, w=15215, hz=49.63, n=2894),
    dict(z=1.8, h=23.8, q=2033.7, v=415, b=25.06, w=16372, hz=49.75, n=2889),
    dict(z=1.8, h=8, q=2466.9, v=415, b=25.66, w=16692, hz=49.75, n=2886),
]


def close(a, b, tol=1e-6):
    assert abs(a - b) <= max(tol, abs(b) * 1e-9), f"{a} != {b}"


def test_matches_excel():
    r = T.run({"nameplate": NAMEPLATE, "readings": READINGS})
    raw = r["_raw"]
    c = raw["calc"]
    for got, exp in zip([x["Hc"] for x in c], [41.051879960146884, 38.890618264824276, 37.47254161959085,
                                               34.24495000663585, 26.817504608469477, 11.31284563521123]):
        close(got, exp)                                                    # H32:H37
    for got, exp in zip([x["eff"] for x in c], [0, 0.4150504990507366, 0.559600162822669,
                                                0.604245724141338, 0.5388876812635633, 0.2704641885510495]):
        close(got, exp)                                                    # G32:G37
    close(r["observed"][0]["slip"], 2.00)                                  # M18 (rounded %)
    close(raw["hmin"]["Q"], 2307.6935659853016); close(raw["hmin"]["I"], 25.51447119432912)   # R26 S26
    close(raw["hmin"]["E"], 0.39233226123481235)                                              # T26
    close(raw["hmax"]["Q"], 823.5457778806112); close(raw["hmax"]["I"], 18.39035164499767)    # R30 S30
    close(raw["hmax"]["E"], 0.48230225779980995)                                              # T30
    close(raw["hduty"]["Q"], 1922.7103850524607); close(raw["hduty"]["I"], 24.542362327876084)  # R35 S35
    close(raw["Qo"], 1825.3412815314614); close(raw["Ho"], 31.489805734022283)                 # R39 Q39
    close(raw["Io"], 24.103405166611093); close(raw["Eo"], 0.586526697055691)                  # S39 T39
    close(raw["i_max"], 25.51447119432912)                                                     # H47
    con = r["conclusion"]
    assert con["dh"] == ">HG" and con["dq"] == ">QG"
    assert con["hq"] == con["eff"] == con["current"] == con["overall"] == "Pass"
    assert con["declared"]["i_max"] == 31.03                                                   # D47


def test_master_lookups():
    assert T.nameplate("OWS-15.2") is not None
    rec = T.test_record("LSPA1VD000551")
    assert rec and len(rec["readings"]) == 6 and rec["readings"][1]["q"] == 789.4


def test_fail_case():
    weak = [dict(r, h=r["h"] * 0.7) for r in READINGS]          # 30 % low head -> outside tolerance
    con = T.run({"nameplate": NAMEPLATE, "readings": weak})["conclusion"]
    assert con["hq"] == "FAIL" and con["overall"] == "FAIL"


if __name__ == "__main__":
    test_matches_excel()
    test_master_lookups()
    test_fail_case()
    print("Test report results match the Excel workbook.")
