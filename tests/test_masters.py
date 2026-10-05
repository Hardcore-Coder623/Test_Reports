"""Master data sheets load, validate and keep every value (non-destructive: nothing is written)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from calc import masters as M  # noqa: E402


def test_masters():
    expected = {"bearings": 100, "bush_models": 6, "bush_materials": 3, "kc_chart": 19, "nameplates": 107,
                "company": 4}
    for name, n in expected.items():
        rows = M.rows(name)
        assert len(rows) >= n, name
        assert len(M._clean(name, rows)) == len(rows), name          # every row passes validation
    assert len(M.rows("test_records")) >= 1900
    for bad, msg in (([{"designation": "X", "d": "abc", "D": 1, "B": 1, "Co": 1}], "not a number"),
                     ([{"designation": "", "d": 1, "D": 1, "B": 1, "Co": 1}], "required"),
                     ([{"designation": "A", "d": 1, "D": 2, "B": 1, "Co": 1}] * 2, "duplicate")):
        try:
            M._clean("bearings", bad)
            raise AssertionError("should be rejected: " + msg)
        except ValueError as e:
            assert msg in str(e), e


if __name__ == "__main__":
    test_masters()
    print("Master data sheets load and validate.")
