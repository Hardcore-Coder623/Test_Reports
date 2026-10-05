"""Trim calculator results must equal the cached values in Trim_Calculator.xlsx (sheet Data Input)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from calc import trim  # noqa: E402

BHP1 = [9.91555368499813, 12.187542849307555, 12.392441860465116, 11.720707070707071,
        11.407269813519813, 26.269640852974188, 8.390663040663041, 0]                   # C19:J19
Q2 = [900.1923076923076, 861.0164835164835, 815.0274725274725, 685.5769230769231,
      634.478021978022, 455.6318681318681, 292.1153846153846, 0]                         # C21:J21
H2 = [7.274808296099504, 15.303933703658979, 19.191568047337277, 21.954979772974276,
      22.868863965704627, 25.385672020287405, 27.40201968361309, 30.24521494988528]      # K21:R21
BHP2 = [6.124884463229477, 7.528302928318164, 7.65487001774543, 7.239936257321687,
        7.0463245793729286, 16.226881546557863, 5.182952291580534, 0]                    # C22:J22


def close(a, b):
    assert abs(a - b) <= 1e-9 * max(1, abs(b)), f"{a} != {b}"


def test_matches_excel():
    r = trim.calculate(trim.DEFAULTS)
    raw = r["_raw"]
    close(raw["ratio"], 0.8516483516483516); close(raw["ratio2"], 0.7253049148653544)   # B23 B24
    for row, b1, q2, h2, b2 in zip(raw["rows"], BHP1, Q2, H2, BHP2):
        close(row["p1"], b1); close(row["q2"], q2); close(row["h2"], h2); close(row["p2"], b2)
    assert r["checks"][0]["status"] == "Fail"                      # 14.8 % trim > 10 %


def test_fix_and_units():
    r = trim.calculate({**trim.DEFAULTS, "d2": 163.8})
    assert r["checks"][0]["status"] == "Pass"                      # exactly 10 %
    fix = trim.calculate(trim.DEFAULTS)["checks"][0]["fixes"][0]["apply"]["d2"]
    assert trim.calculate({**trim.DEFAULTS, "d2": fix})["checks"][0]["status"] == "Pass"
    kw = trim.calculate({**trim.DEFAULTS, "units": "metric_kw"})["_raw"]["rows"][0]["p1"]
    close(kw, 1057 * 10.03 * 100 / (6120 * 27))


if __name__ == "__main__":
    test_matches_excel()
    test_fix_and_units()
    print("Trim calculator results match the Excel workbook.")
