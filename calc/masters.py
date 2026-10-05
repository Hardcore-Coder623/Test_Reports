"""Master data sheets (the supporting sheets the main sheets look up), editable from the Masters tab.

  bearings        <- Bearing_Calculation.xlsx  / Bearing_Data
  bush_models     <- Bush design workbook      / one sheet per pump model (inputs rows 21-46)
  bush_materials  <- Bush design workbook      / material PV tables (I34:K37, J30:K31)
  kc_chart        <- Impeller design workbook  / Sheet1 A15:C33 (Kc1, Kc2 vs specific speed)
  nameplates      <- Test report workbook      / NameplateData (Table1)
  test_records    <- Test report workbook      / TestData (Table4)  - list, open, delete
"""
import json
import threading
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
_LOCK = threading.Lock()

N, T = "num", "text"
BUSH_INPUTS = [("impeller_od", "Impeller OD (mm)"), ("vane_width", "Vane width (mm)"), ("head", "Shut-off head (m)"),
               ("discharge_m3h", "Discharge (m³/h)"), ("speed", "Speed (RPM)"), ("kso", "Kso"), ("sg", "Sp. gravity"),
               ("rotor_wt", "Rotor wt (kg)"), ("impeller_wt", "Impeller wt (kg)"), ("dim_a", "A (mm)"),
               ("dim_b", "B (mm)"), ("bush_a_dia", "Bush A dia"), ("bush_a_len", "Bush A length"),
               ("bush_b_dia", "Bush B dia"), ("bush_b_len", "Bush B length")]

MASTERS = {
    "bearings": {
        "title": "Bearing data", "source": "Bearing_Calculation.xlsx · Bearing_Data", "file": "bearings.json",
        "key": "designation",
        "columns": [("designation", "Designation", T), ("d", "Bore d (mm)", N), ("D", "OD D (mm)", N),
                    ("B", "Width B (mm)", N), ("Co", "Static Co (N)", N), ("C", "Dynamic C (N)", N),
                    ("source", "Source", T)],
        "required": ["designation", "d", "D", "B", "Co"],
    },
    "bush_models": {
        "title": "Bush pump models", "source": "Bush design workbook · model sheets (rows 21-46)",
        "file": "pump_models.json", "key": "key",
        "columns": [("key", "Model key", T), ("label", "Model name", T)] +
                   [(k, l, N) for k, l in BUSH_INPUTS] +
                   [("de_bush_1", "DE bush 1 (IDxODxL)", T), ("de_bush_2", "DE bush 2", T),
                    ("nde_bush", "NDE bush", T), ("material", "Default material", T),
                    ("pv_carbon", "PV limit Carbon", N), ("pv_bronze", "PV limit Bronze", N),
                    ("pv_amco", "PV limit AMCO", N)],
        "required": ["key", "label"] + [k for k, _ in BUSH_INPUTS] + ["material"],
    },
    "bush_materials": {
        "title": "Bush materials (PV limits)", "source": "Bush design workbook · Table1 I34:K37 / J30:K31",
        "file": "bush_materials.json", "key": "material",
        "columns": [("material", "Material", T), ("pv_imperial", "PV max (lb/in²·ft/min)", N), ("source", "Source / note", T)],
        "required": ["material", "pv_imperial"],
    },
    "kc_chart": {
        "title": "Velocity coefficients Kc1 / Kc2", "source": "Impeller design workbook · Sheet1 A15:C33",
        "file": "kc_chart.json", "key": "ns",
        "columns": [("ns", "Specific speed Ns", N), ("kc1", "Kc1", N), ("kc2", "Kc2", N)],
        "required": ["ns", "kc1", "kc2"],
    },
    "nameplates": {
        "title": "Nameplate data", "source": "Test report workbook · NameplateData", "file": "nameplates.json",
        "key": "model",
        "columns": [("model", "Model", T), ("stages", "Stages", N), ("delivery_size", "Delivery (mm)", N),
                    ("head_g", "Head HG (m)", N), ("q_g", "Discharge QG", N), ("q_unit", "Unit", T),
                    ("eff_g", "Overall eff (%)", N), ("min_sub", "Min. subm. (m)", N), ("duty_type", "Duty", T),
                    ("motor_kw", "Motor kW", N), ("motor_hp", "Motor HP", N), ("rated_speed", "Rated speed", T),
                    ("rated_current", "Rated current (A)", N), ("rated_voltage", "Rated voltage (V)", N),
                    ("category", "Category", T), ("rated_freq", "Rated freq (Hz)", N), ("winding", "Winding", T),
                    ("motor_type", "Motor type", T), ("phases", "Phases", N), ("h_min", "H min (m)", N),
                    ("h_max", "H max (m)", N), ("brand", "Brand", T), ("isi", "ISI", T)],
        "required": ["model", "delivery_size", "head_g", "q_g", "eff_g", "rated_current", "rated_freq",
                     "phases", "h_min", "h_max"],
    },
    "company": {
        "title": "Company address (report header)", "source": "Test report workbook · Report R45",
        "file": "company.json", "key": "line",
        "columns": [("line", "Address line", T)],
        "required": ["line"],
    },
    "test_records": {
        "title": "Test data (saved tests)", "source": "Test report workbook · TestData", "file": "test_records.json",
        "key": "sr_no", "readonly": True,
        "columns": [("sr_no", "Sr. No.", T), ("date", "Date", T), ("model", "Model", T), ("n", "Readings", N)],
    },
}


def _read(name):
    return json.loads((DATA / MASTERS[name]["file"]).read_text(encoding="utf-8"))


def _write(name, obj):
    f = DATA / MASTERS[name]["file"]
    tmp = f.with_suffix(".tmp")
    compact = name == "test_records"                     # large file: keep it compact
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=None if compact else 1,
                              separators=(",", ":") if compact else None), encoding="utf-8")
    tmp.replace(f)


def catalogue():
    return [{"name": k, "title": m["title"], "source": m["source"], "readonly": m.get("readonly", False),
             "columns": [{"key": c, "label": l, "type": t} for c, l, t in m["columns"]],
             "required": m.get("required", []), "key": m["key"]} for k, m in MASTERS.items()]


def rows(name, q="", limit=None):
    if name not in MASTERS:
        raise ValueError("Unknown master")
    if name == "bush_models":
        out = []
        for key, m in _read(name).items():
            r = {"key": key, **{k: v for k, v in m.items() if k != "pv_limits"}}
            pv = m.get("pv_limits", {})
            r.update(pv_carbon=pv.get("Carbon", ""), pv_bronze=pv.get("Bronze", ""), pv_amco=pv.get("AMCO", ""))
            out.append(r)
        return out
    if name == "test_records":
        q = str(q).strip().lower()
        out = [{"sr_no": r["sr_no"], "date": r.get("date", ""), "model": r.get("model", ""),
                "n": len(r.get("readings", []))}
               for r in _read(name)
               if not q or q in r["sr_no"].lower() or q in str(r.get("model", "")).lower()]
        return out[:limit] if limit else out
    data = _read(name)
    return sorted(data, key=lambda r: (r.get("ns", 0))) if name == "kc_chart" else data


def _clean(name, rows_in):
    m = MASTERS[name]
    cols = {c: t for c, _, t in m["columns"]}
    seen, out = set(), []
    for i, r in enumerate(rows_in, start=1):
        if all(str(r.get(c, "")).strip() == "" for c in cols):
            continue                                               # blank line
        rec = {}
        for c, t in cols.items():
            v = r.get(c, "")
            v = "" if v is None else str(v).strip()
            if t == N and v != "":
                try:
                    f = float(v)
                except ValueError:
                    raise ValueError(f"Row {i}: '{v}' is not a number ({c})")
                f = round(f, 9)                                  # drop Excel float noise
                v = int(f) if f.is_integer() else f
            rec[c] = v
        for c in m.get("required", []):
            if rec.get(c, "") == "":
                raise ValueError(f"Row {i}: {dict((k, l) for k, l, _ in m['columns'])[c]} is required")
        k = str(rec[m["key"]]).lower()
        if k in seen:
            raise ValueError(f"Row {i}: duplicate {m['key']} '{rec[m['key']]}'")
        seen.add(k)
        out.append(rec)
    if not out:
        raise ValueError("The master cannot be empty")
    return out


def save(name, rows_in):
    if name not in MASTERS or MASTERS[name].get("readonly"):
        raise ValueError("This master cannot be edited here")
    recs = _clean(name, rows_in)
    if name == "bush_models":
        obj = {}
        for r in recs:
            pv = {mat: r[k] for mat, k in (("Carbon", "pv_carbon"), ("Bronze", "pv_bronze"), ("AMCO", "pv_amco"))
                  if r.get(k, "") != ""}
            obj[r["key"]] = {k: v for k, v in r.items() if k not in ("key", "pv_carbon", "pv_bronze", "pv_amco")}
            obj[r["key"]]["pv_limits"] = pv
        payload = obj
    elif name == "kc_chart":
        payload = sorted(recs, key=lambda r: r["ns"])
    else:
        payload = recs
    with _LOCK:
        _write(name, payload)
    _reload_calcs()
    return len(recs)


def delete_test(sr_no):
    with _LOCK:
        data = _read("test_records")
        keep = [r for r in data if r["sr_no"].lower() != str(sr_no).strip().lower()]
        if len(keep) == len(data):
            raise ValueError("Sr. No. not found")
        _write("test_records", keep)
    return True


def _reload_calcs():
    from calc import bearing, bush, impeller
    bearing.reload()
    bush.reload()
    impeller.reload()
