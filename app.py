"""Pump Design Calculator - web server.

All engineering formulas live in calc/ and run only on the server.
The browser sends selections/inputs and receives finished results.

Run:  python app.py      then open http://localhost:5000
"""
import os

import re

from flask import Flask, Response, jsonify, render_template, request

from calc import bearing, bush, impeller, masters, test_report, trim

app = Flask(__name__)


def _num(data, key, default=None):
    val = data.get(key, default)
    if val in (None, ""):
        raise ValueError(f"Missing value: {key.replace('_', ' ')}")
    try:
        return float(val)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid number for {key.replace('_', ' ')}")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/options")
def options():
    return jsonify({"bearing": bearing.options(), "bush": bush.options()})


@app.post("/api/bearing")
def api_bearing():
    data = request.get_json(silent=True) or {}
    try:
        params = {k: _num(data, k) for k in
                  ("hp", "rpm", "d", "k", "a", "b", "c", "shaft_dia")}
        params["bearing_a"] = str(data.get("bearing_a", ""))
        params["bearing_b"] = str(data.get("bearing_b", ""))
        params["qty_a"] = int(_num(data, "qty_a", 1))
        params["qty_b"] = int(_num(data, "qty_b", 1))
        return jsonify(bearing.calculate(params))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/bush")
def api_bush():
    data = request.get_json(silent=True) or {}
    try:
        model = str(data.get("model", ""))
        material = str(data.get("material", ""))
        pv_limit = _num(data, "pv_limit")
        params = {k: _num(data, k) for k in bush.INPUT_FIELDS}
        return jsonify(bush.calculate(model, material, pv_limit, params))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/impeller/schema")
def api_impeller_schema():
    return jsonify(impeller.schema())


@app.post("/api/impeller")
def api_impeller():
    data = request.get_json(silent=True) or {}
    try:
        r = impeller.calculate(impeller.parse(data))
        # only the important results go to the page; all intermediate values stay on the server
        return jsonify({"title": r["title"], "warnings": r["warnings"], **r["compact"]})
    except (ValueError, ZeroDivisionError) as e:
        msg = str(e) if isinstance(e, ValueError) else "Inputs give a division by zero - check values"
        return jsonify({"error": msg}), 400


# ---------------------------------------------------------------- impeller trim calculator
@app.get("/api/trim/defaults")
def trim_defaults():
    return jsonify({**trim.DEFAULTS, "options": [{"key": k, "label": v[0]} for k, v in trim.UNITS.items()],
                    "max_points": trim.MAX_POINTS})


@app.post("/api/trim")
def trim_calc():
    try:
        r = trim.calculate(request.get_json(silent=True) or {})
        r.pop("_raw", None)
        return jsonify(r)
    except (ValueError, ZeroDivisionError) as e:
        return jsonify({"error": str(e) if isinstance(e, ValueError) else "Check inputs (division by zero)"}), 400


# ---------------------------------------------------------------- master data sheets
@app.get("/api/masters")
def masters_list():
    return jsonify(masters.catalogue())


@app.get("/api/masters/<name>")
def masters_rows(name):
    try:
        return jsonify(masters.rows(name, request.args.get("q", ""), int(request.args.get("limit", 0)) or None))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.post("/api/masters/<name>")
def masters_save(name):
    try:
        n = masters.save(name, (request.get_json(silent=True) or {}).get("rows", []))
        return jsonify({"saved": n})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.delete("/api/masters/test_records/<path:sr_no>")
def masters_delete_test(sr_no):
    try:
        return jsonify({"deleted": masters.delete_test(sr_no)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ---------------------------------------------------------------- pump test report
@app.get("/api/report/meta")
def report_meta():
    return jsonify({"models": test_report.models(),
                    "nameplate_fields": [{"key": k, "label": l, "unit": u}
                                         for k, l, u in test_report.NAMEPLATE_FIELDS],
                    "reading_fields": test_report.READING_FIELDS, "max_readings": test_report.MAX_READINGS})


@app.get("/api/report/nameplate")                       # "Download Nameplate"
def report_nameplate():
    np = test_report.nameplate(request.args.get("model", ""))
    return jsonify(np) if np else (jsonify({"error": "Model not found in the nameplate master"}), 404)


@app.post("/api/report/nameplate")                      # "Upload Nameplate"
def report_nameplate_save():
    try:
        return jsonify({"saved": test_report.save_nameplate(request.get_json(silent=True) or {})})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/report/serials")
def report_serials():
    return jsonify(test_report.serial_numbers(request.args.get("q", "")))


@app.get("/api/report/record")                          # "Download Readings"
def report_record():
    rec = test_report.test_record(request.args.get("sr_no", ""))
    return jsonify(rec) if rec else (jsonify({"error": "Sr. No. not found in saved test data"}), 404)


@app.post("/api/report/record")                         # "Upload Readings"
def report_record_save():
    d = request.get_json(silent=True) or {}
    try:
        np = d.get("nameplate", {})
        rows = [r for r in d.get("readings", []) if any(str(v).strip() for v in r.values())]
        return jsonify({"saved": test_report.save_test_record(np.get("sr_no", ""), np.get("date", ""),
                                                              np.get("model", ""), rows)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/report")                                # calculated / corrected values, conclusion, graphs
def report_calc():
    try:
        r = test_report.run(request.get_json(silent=True) or {})
        r.pop("_raw", None)
        return jsonify(r)
    except (ValueError, ZeroDivisionError) as e:
        return jsonify({"error": str(e) if isinstance(e, ValueError) else "Check readings (division by zero)"}), 400


@app.post("/api/report/pdf")                            # "Export Report" - A4 landscape PDF
def report_pdf():
    try:
        r = test_report.run(request.get_json(silent=True) or {})
    except (ValueError, ZeroDivisionError) as e:
        return jsonify({"error": str(e)}), 400
    try:
        from calc.report_pdf import build_pdf      # needs reportlab; imported here so the rest of the app runs without it
    except ImportError:
        return jsonify({"error": "PDF export needs the reportlab package. In the pump_calc folder run:  "
                                 "pip install -r requirements.txt   then restart the app."}), 500
    np = r["nameplate"]
    name = re.sub(r"[^\w.()-]+", "_", f"{np.get('sr_no') or 'report'}_({np.get('model') or 'pump'})") + ".pdf"
    return Response(build_pdf(r), mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    try:
        from waitress import serve
        print(f"Pump Design Calculator running on http://localhost:{port}")
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        app.run(host="0.0.0.0", port=port)
