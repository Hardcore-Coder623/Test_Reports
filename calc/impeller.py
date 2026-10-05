"""Impeller & volute design (server side only).

Port of "Impeller_Design_of_7.5_HP_65x50.xls":
  sheet "IMP Design"  - impeller main dimensions, vane development, blade arcs,
                         point-by-point blade layout (2 tables), pipe friction / system head
  sheet "Vol Design"  - volute throat and cross sections
  sheet "Sheet1"      - Kc1 / Kc2 chart vs specific speed
Cell references are given next to each formula.
"""
import json
import math
from pathlib import Path

from calc.bearing import HP_LIST

# design checks (tolerances shown on the page with each check)
D2_TOL_UNDER, D2_TOL_OVER = 0.02, 0.05      # D2 chosen may be 2 % below / 5 % above calculated
ETA_H_MAX = 0.95                            # hydraulic efficiency must stay below this

# ---------------------------------------------------------------- input schema
# (key, label, unit, default)   default = value typed in the original sheet
INPUT_GROUPS = [
    ("Pump duty", [
        ("pump_type", "Pump type", "", "7.5 HP 65mm"),                    # B2
        ("hp", "Motor power", "HP", 7.5),                                  # B3
        ("q_lpm", "Discharge Q", "lpm", 870),                              # B4
        ("head", "Head H", "m", 39),                                       # B5
        ("rpm", "Speed", "RPM", 2850),                                     # B6
    ]),
    ("Efficiencies", [
        ("eff", "Overall efficiency", "–", 0.7),                           # B8
        ("eff_mech", "Mechanical efficiency", "–", 0.91),                  # B10
        ("eff_vol", "Volumetric efficiency", "–", 0.95),                   # B11
    ]),
    ("Impeller selection", [
        ("d_inlet", "Inlet (eye) dia chosen", "mm", 65),                   # C15
        ("d2", "Outer dia D2 chosen", "mm", 197),                          # C27
        ("z", "No. of vanes Z", "nos", 4),                                 # B28
        ("beta1", "Inlet angle β1", "deg", 23),                            # B21
        ("beta2", "Outlet angle β2", "deg", 21.1),                         # B22
        ("kcm1", "Kcm1 (blank = from chart)", "–", 0.15),                    # B17
        ("kcm2", "Kcm2 (blank = from chart)", "–", 0.1077),                    # B18
    ]),
    ("Vane development - manual adjust factors", [                         # H8:L8
        ("adj1", "Station 2", "×", 0.975),
        ("adj2", "Station 3", "×", 0.945),
        ("adj3", "Station 4", "×", 0.92),
        ("adj4", "Station 5", "×", 0.915),
        ("adj5", "Station 6", "×", 0.9555),
    ]),
    ("Blade arcs (two-arc method)", [
        # D1 (F32) = calculated inlet dia B15 and Dm (G32) = (D1 + D2) / 2 - calculated, not typed
        ("arc_beta_m", "β at middle Dm", "deg", 23),                              # G34
        ("arc_beta_2", "β at outer D2", "deg", 22),                              # H34
    ]),
    ("Blade layout (point-by-point)", [
        ("pp_r0", "Start radius r1", "m", 0.036),                          # B44
        ("pp_step", "Radius step", "m", 0.005),                            # B45
        ("pp_cm_in", "Cm at inlet", "m/s", 3.42),                          # D44
        ("pp_cm_out", "Cm at outlet", "m/s", 2.6),                         # D52
        ("pp_w1", "w point 1", "m/s", 9.54), ("pp_w2", "w point 2", "m/s", 9.1),
        ("pp_w3", "w point 3", "m/s", 8.7), ("pp_w4", "w point 4", "m/s", 8.25),
        ("pp_w5", "w point 5", "m/s", 7.9), ("pp_w6", "w point 6", "m/s", 7.55),
        ("pp_w7", "w point 7", "m/s", 7.3), ("pp_w8", "w point 8", "m/s", 7.1),
        ("pp_w9", "w point 9", "m/s", 6.94),                               # F44:F52
        ("pp_beta_in", "Table 2: β at inlet", "deg", 21),                  # H55
        ("pp_beta_out", "Table 2: β at outlet", "deg", 22),                # H63
    ]),
    ("Volute", [
        # base circle dia B20 = D2 chosen + 7 (calculated, not typed)
        ("vol_width", "Width of volute", "mm", 20),                        # C21
        ("vol_angle", "Diffusion angle", "deg", 22),                       # B22
        ("vol_throat", "Throat dia chosen", "mm", 42.72),                  # C19
    ]),
    ("Fillet radius per cross section (pink row)", [
        ("vol_f1", "Section 1", "mm", 2), ("vol_f2", "Section 2", "mm", 3),
        ("vol_f3", "Section 3", "mm", 3.5), ("vol_f4", "Section 4", "mm", 4),
        ("vol_f5", "Section 5", "mm", 4.5), ("vol_f6", "Section 6", "mm", 5),
        ("vol_f7", "Section 7", "mm", 5.5), ("vol_f8", "Section 8", "mm", 6),   # C31:J31
    ]),
    ("Volute - measured areas", [
        ("vol_m1", "Actual area sec 1", "mm²", 193), ("vol_m2", "Actual area sec 2", "mm²", 381),
        ("vol_m3", "Actual area sec 3", "mm²", 578), ("vol_m4", "Actual area sec 4", "mm²", 780),
        ("vol_m5", "Actual area sec 5", "mm²", 957), ("vol_m6", "Actual area sec 6", "mm²", 1162),
        ("vol_m7", "Actual area sec 7", "mm²", 1342), ("vol_m8", "Actual area sec 8", "mm²", ""),  # C36:J36
    ]),
    ("Pipe friction / system head", [
        ("sys_pipe", "Pipe inside dia", "mm", 41.85),                      # Q10
        ("sys_static", "Static head", "m", 10),                            # S8
        ("sys_len", "Pipe length", "m", 100),                              # S10
        ("sys_f", "Friction factor f", "–", 0.007),
        ("sys_q", "Flows (comma separated)", "lpm", "25, 50, 75, 100, 120, 225, 250, 270"),  # P12:P19
    ]),
]
TEXT_KEYS = {"pump_type", "sys_q"}
OPTIONAL_KEYS = {"kcm1", "kcm2", "vol_m1", "vol_m2", "vol_m3", "vol_m4",
                 "vol_m5", "vol_m6", "vol_m7", "vol_m8"}
DEFAULTS = {k: d for _, fields in INPUT_GROUPS for k, _, _, d in fields}

# Vol Design E3:J5 - Nsq vs Kccv (row 4) and second coefficient (row 5), plotted in the sheet's chart
VOL_CHART_NSQ = [10, 20, 30, 40, 50, 60]
VOL_CHART_ROW4 = [0.52, 0.43, 0.375, 0.333, 0.305, 0.28]     # log trend = Kccv formula (B17)
VOL_CHART_ROW5 = [0.05, 0.099, 0.14, 0.181, 0.22, 0.26]      # power trend


def _linfit(X, Y):
    n = len(X); mx = sum(X) / n; my = sum(Y) / n
    m = sum((a - mx) * (b - my) for a, b in zip(X, Y)) / sum((a - mx) ** 2 for a in X)
    return m, my - m * mx


# Sheet1 A15:C33 - specific speed vs Kc2 / Kc1 (data/kc_chart.json, editable on the Masters tab)
KC_CHART = []


def reload():
    """(Re)load the Kc chart table (called after a Masters save)."""
    global KC_CHART
    rows = json.loads((Path(__file__).resolve().parent.parent / "data" / "kc_chart.json").read_text(encoding="utf-8"))
    KC_CHART = sorted((r["ns"], r["kc2"], r["kc1"]) for r in rows)




# Inputs shown on the page. Every other input keeps its sheet value on the server.
REQUIRED_KEYS = {
    "impeller": ["pump_type", "hp", "q_lpm", "head", "rpm", "eff", "eff_mech", "eff_vol",
                 "d_inlet", "d2", "z", "beta1", "beta2", "kcm1", "kcm2",
                 "arc_beta_m", "arc_beta_2"],
    "volute": ["vol_width", "vol_angle", "vol_throat"] + [f"vol_f{k}" for k in range(1, 9)],
}


def schema():
    """Input fields per page section; every other input keeps its sheet value."""
    out = {}
    for section, keys in REQUIRED_KEYS.items():
        groups = []
        for g, fields in INPUT_GROUPS:
            shown = [{"key": k, "label": l, "unit": u, "default": d, "text": k in TEXT_KEYS,
                      "optional": k in OPTIONAL_KEYS}
                     for k, l, u, d in fields if k in keys]
            if shown:
                groups.append({"group": g, "fields": shown})
        out[section] = groups
    return out


# ---------------------------------------------------------------- helpers
def _rad(deg):
    return math.pi / 180 * deg


def _deg(rad):
    return rad * 180 / math.pi


def _excel_round(x, digits=0):
    m = 10 ** digits
    return math.copysign(math.floor(abs(x) * m + 0.5) / m, x)


def _kc_from_chart(ns):
    pts = KC_CHART
    if ns <= pts[0][0]:
        return pts[0][2], pts[0][1]
    if ns >= pts[-1][0]:
        return pts[-1][2], pts[-1][1]
    for (n0, k20, k10), (n1, k21, k11) in zip(pts, pts[1:]):
        if n0 <= ns <= n1:
            t = (ns - n0) / (n1 - n0)
            return k10 + t * (k11 - k10), k20 + t * (k21 - k20)


def _r(x, n=3):
    return None if x is None else round(x, n)


def _linear(a, b, steps):
    """a .. b in `steps` equal intervals (steps + 1 values), like G6 + (M6 - G6)/6."""
    return [a + (b - a) * i / steps for i in range(steps + 1)]


def parse(data):
    p = {}
    for k, d in DEFAULTS.items():
        v = data.get(k, d)
        if k in TEXT_KEYS:
            p[k] = str(v)
            continue
        if v in ("", None):
            if k in OPTIONAL_KEYS:
                p[k] = None
                continue
            raise ValueError(f"Missing value: {k}")
        try:
            p[k] = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid number for {k}")
    return p


# ---------------------------------------------------------------- calculation
def calculate(p, _checks=True):
    for k in ("q_lpm", "head", "rpm", "eff", "eff_mech", "eff_vol", "d_inlet", "d2", "z"):
        if p[k] <= 0:
            raise ValueError(f"{k} must be greater than zero")

    Q, H, n = p["q_lpm"], p["head"], p["rpm"]
    q = Q / 60000                                            # m³/s
    z, b1d, b2d = p["z"], p["beta1"], p["beta2"]

    # ---- duty
    lps, m3h, gpm, h_ft = Q / 60, Q * 60 / 1000, Q / 3.7854, H / 0.3048     # C4 D4 E4 C5
    nsq = _excel_round(n * q ** 0.5 / H ** 0.75, 1)                          # B7
    ns_us = n * gpm ** 0.5 / h_ft ** 0.75                                    # C7
    pin = Q * H / 4500 / p["eff"]                                            # B9
    eta_h = p["eff"] / p["eff_mech"] / p["eff_vol"]                          # B12
    eta_h_est = 1 - 0.071 / q ** 0.25                                        # B13
    eta_v_est = 1 / (1 + 0.68 * (nsq * 3.65) ** (-2 / 3))                    # C11

    # ---- Kcm1 / Kcm2 (Sheet1 chart, or typed value)
    kc1_chart, kc2_chart = _kc_from_chart(nsq)
    kcm1 = p["kcm1"] if p["kcm1"] is not None else kc1_chart                # B17
    kcm2 = p["kcm2"] if p["kcm2"] is not None else kc2_chart                # B18
    cm1 = kcm1 * (19.62 * H) ** 0.5                                          # B19
    cm2 = kcm2 * (19.62 * H) ** 0.5                                          # B20

    # ---- inlet
    d_in_calc = (q / 0.95 / 0.786 / cm1 / 0.8 + 0.0786 * 0.02 ** 2) ** 0.5 * 1000   # B15
    d_eye_nom = 4.2e3 * (q / n) ** 0.3333                                    # D15
    d_in = p["d_inlet"]
    v_in = q / (math.pi / 4 * (d_in / 1000) ** 2)                            # C16
    u1 = math.pi * (d_in / 1000) * n / 60                                    # C17
    beta1_calc = _deg(math.atan(cm1 / u1))                                   # C21

    # ---- slip factor (F37, F38) uses blade-arc D1 and chosen D2
    d2c = p["d2"]
    arc_d1 = d_in_calc                                                       # F32 = B15
    arc_dm = (arc_d1 + d2c) / 2                                              # G32
    y = 1.25 * (1 + math.sin(_rad(b2d))) * arc_d1 / d2c                      # F37
    cp_slip = 2 * y / z / (1 - (arc_d1 / d2c) ** 2)                          # F38
    cp = 1 + cp_slip                                                         # B23

    # ---- outlet
    g_hth = cp * H / eta_h * 9.81                                            # B24
    cm2_cot = cm2 / math.tan(_rad(b2d))                                      # B25
    u2 = (cm2_cot + (cm2_cot ** 2 + 4 * g_hth) ** 0.5) / 2                   # B26
    d2_calc = 60 * u2 / math.pi / n                                          # B27 (m)
    h_shut = u2 ** 2 / 9.81 * 0.565                                          # B29
    b2 = Q / p["eff_vol"] / 60000 / (math.pi * d2_calc - z * 0.0045 / math.sin(_rad(b2d))) / cm2   # B30
    b1 = Q / p["eff_vol"] / 60000 / (math.pi * d_in / 1000 - z * 0.004 / math.sin(_rad(b1d))) / cm1  # B32
    gap_top, gap_bot = 1000 * b2, 0.9 * b1 * 1000                            # B31 B33

    main = [
        ("Discharge", f"{_r(lps, 2)} lps · {_r(m3h, 2)} m³/h · {_r(gpm, 1)} gpm", ""),
        ("Head", _r(h_ft, 2), "ft"),
        ("Specific speed Nsq (metric)", nsq, ""),
        ("Specific speed Ns (US units)", _r(ns_us, 1), ""),
        ("Power input required Pin", _r(pin, 3), "HP"),
        ("Motor HP / Pin", _r(p["hp"] / pin, 3), ""),
        ("Hydraulic efficiency", _r(eta_h, 4), ""),
        ("Hydraulic efficiency (estimate)", _r(eta_h_est, 4), ""),
        ("Volumetric efficiency (estimate)", _r(eta_v_est, 4), ""),
        ("Kcm1" + ("" if p["kcm1"] is not None else " (chart)"), _r(kcm1, 4), ""),
        ("Kcm2" + ("" if p["kcm2"] is not None else " (chart)"), _r(kcm2, 4), ""),
        ("Cm1 (inlet meridional velocity)", _r(cm1, 3), "m/s"),
        ("Cm2 (outlet meridional velocity)", _r(cm2, 3), "m/s"),
    ]
    inlet = [
        ("Inlet dia (calculated)", _r(d_in_calc, 2), "mm"),
        ("Eye dia D1 nominal", _r(d_eye_nom, 2), "mm"),
        ("Inlet velocity at chosen dia", _r(v_in, 3), "m/s"),
        ("Peripheral velocity U1", _r(u1, 3), "m/s"),
        ("β1 (calculated)", _r(beta1_calc, 2), "deg"),
        ("b1", _r(b1 * 1000, 3), "mm"),
        ("Vane gap @ bottom", _r(gap_bot, 3), "mm"),
    ]
    outlet = [
        ("Slip y", _r(y, 4), ""),
        ("Slip factor Cp", _r(cp, 4), ""),
        ("g·Hth∞", _r(g_hth, 2), "m²/s²"),
        ("Cm2·cot β2", _r(cm2_cot, 3), "m/s"),
        ("Peripheral velocity U2", _r(u2, 3), "m/s"),
        ("D2 outer dia (calculated)", _r(d2_calc * 1000, 2), "mm"),
        ("Shut-off head", _r(h_shut, 2), "m"),
        ("b2", _r(b2 * 1000, 3), "mm"),
        ("Vane gap @ top", _r(gap_top, 3), "mm"),
        ("Vane gap @ average", _r((gap_bot + gap_top) / 2, 3), "mm"),
    ]
    warnings = []          # pass / fail now reported by the checks below

    # ---- vane development (G5:M12) - 7 stations
    D = _linear(d_in, d2c, 6)                                                # row 6
    vf = _linear(cm1, cm2, 6)                                                # row 7
    adj = [1, p["adj1"], p["adj2"], p["adj3"], p["adj4"], p["adj5"], 1]
    vf_adj = [vf[i] * adj[i] for i in range(7)]                              # row 8
    beta = _linear(beta1_calc + 3, b2d, 6)                                   # row 9
    vane_rows, vane_b = [], []
    for i in range(7):
        b = Q / 60000 / p["eff_vol"] / vf_adj[i] / (
            math.pi * D[i] / 1000 - z * 0.0045 / math.sin(_rad(beta[i])))   # row 10
        vane_b.append(b)
        vane_rows.append([i + 1, _r(D[i], 2), _r(D[i] / 2, 2), _r(vf[i], 3), adj[i],
                          _r(vf_adj[i], 3), _r(beta[i], 2), _r(b * 1000, 3)])

    # ---- blade arcs (F30:H38)
    r_1, r_m, r_2 = arc_d1 / 2, arc_dm / 2, d2c / 2
    bf, bm, bo = _rad(b1d), _rad(p["arc_beta_m"]), _rad(p["arc_beta_2"])
    arc_r2 = (r_2 ** 2 - r_m ** 2) / (r_2 * math.cos(bo) - r_m * math.cos(bm)) / 2   # F35
    arc_r1 = (r_m ** 2 - r_1 ** 2) / (r_m * math.cos(bm) - r_1 * math.cos(bf)) / 2   # F36
    arcs = [
        ("Arc radius r1 (D1 → Dm)", _r(arc_r1, 3), "mm"),
        ("Arc radius r2 (Dm → D2)", _r(arc_r2, 3), "mm"),
        ("Radii used D1/2 · Dm/2 · D2/2", f"{r_1:g} · {r_m:g} · {r_2:g}", "mm"),
    ]

    # ---- point-by-point blade layout (rows 44-52 and 55-63)
    npts = 9
    rr = [p["pp_r0"] + i * p["pp_step"] for i in range(npts)]
    cm_in, cm_out = p["pp_cm_in"], p["pp_cm_out"]
    cm = [cm_in] + [(cm_out - cm_in) / (rr[-1] - rr[0]) * (rr[i] - rr[0]) + cm_in
                    for i in range(1, npts - 1)] + [cm_out]
    w_in = cm_in / math.sin(_rad(b1d))                                       # E44
    w_out = cm_out / math.sin(_rad(b2d))                                     # E52
    w_th = [w_in] + [(w_out - w_in) / (cm_out - cm_in) * (cm[i] - cm_in) + w_in
                     for i in range(1, npts - 1)] + [w_out]

    def layout(w_used):
        rows, J = [], []
        for i in range(npts):
            s = cm[i] / w_used[i]
            if not -1 <= s <= 1:
                raise ValueError(f"Blade layout point {i + 1}: Cm / w = {s:.3f} is outside -1..1")
            bt = math.asin(s)
            J.append(1 / (rr[i] * math.tan(bt)))
            rows.append([i + 1, rr[i], cm[i], w_th[i], w_used[i], s, _deg(bt), rr[i] * math.tan(bt)])
        total = 0
        out = []
        for i in range(npts):
            dr = 0 if i == 0 else rr[i] - rr[i - 1]
            j_next = J[i + 1] if i + 1 < npts else 0     # last row: next cell is empty in sheet
            da = dr * (j_next + J[i]) / 2
            total += da
            r = rows[i]
            out.append([r[0], _r(r[1], 4), _r(dr, 4), _r(r[2], 4), _r(r[3], 3), _r(r[4], 3),
                        _r(r[5], 4), _r(r[6], 2), _r(r[7], 5), _r(J[i], 3), _r(da, 4),
                        _r(total, 4), _r(_deg(total), 2), _r(90 - _deg(total), 2)])
        return out, _deg(total)

    w1 = [p[f"pp_w{i}"] for i in range(1, 10)]
    w_a, w_b = cm_in / math.sin(_rad(p["pp_beta_in"])), cm_out / math.sin(_rad(p["pp_beta_out"]))
    w2 = _linear(w_a, w_b, npts - 1)                                         # F55:F63
    t1, wrap1 = layout(w1)
    t2, wrap2 = layout(w2)

    # ---- volute (Vol Design)
    kccv = -0.1345 * math.log(nsq) + 0.831                                   # B17
    vth = kccv * (19.62 * H) ** 0.5                                          # B18
    throat = (q / vth / math.pi * 4) ** 0.5 * 1000                           # B19
    base_dia = p["d2"] + 7                                                   # B20 = C20 + 7, C20 = D2
    width = p["vol_width"]
    c22 = 8.7266 * 0.001 * p["vol_angle"]                                    # C22
    d22 = 0.25 * width ** 2 / math.tan(_rad(p["vol_angle"]) / 2)             # D22
    a1 = 45 / 360 * q / vth * 1e6                                            # C29
    vol_rows = []
    for k in range(1, 9):
        area = a1 * k                                                        # row 29
        R = ((area + d22) / c22) ** 0.5                                      # row 30
        fr = p[f"vol_f{k}"]
        fa = 0.55 * fr ** 2                                                  # row 32
        dr = fa / width                                                      # row 33
        meas = p[f"vol_m{k}"]
        vol_rows.append([k, k * 45, _r(area, 2), _r(R, 3), fr, _r(fa, 3), _r(dr, 4),
                         _r(R + dr, 3), meas, _r(meas / area, 4) if meas else None])
    vol_raw = []
    for k in range(1, 9):
        area = a1 * k
        R = ((area + d22) / c22) ** 0.5
        fa = 0.55 * p[f"vol_f{k}"] ** 2
        vol_raw.append([k, k * 45, area, R, p[f"vol_f{k}"], fa, fa / width, R + fa / width])

    # sheet chart: Nsq vs row 4 (log trend) and row 5 (power trend), with this pump's point on Kccv
    a4, b4 = _linfit([math.log(x) for x in VOL_CHART_NSQ], VOL_CHART_ROW4)
    m5, c5 = _linfit([math.log(x) for x in VOL_CHART_NSQ], [math.log(y) for y in VOL_CHART_ROW5])
    c5 = math.exp(c5)
    xs_fit = [8 + i * 0.5 for i in range(int((max(70, nsq + 5) - 8) / 0.5) + 1)]
    vol_chart = {
        "title": "Volute coefficients vs specific speed Nsq", "x": "Specific speed Nsq", "dual": True,
        "x_max": max(80, math.ceil((nsq + 5) / 20) * 20),
        "series": [
            {"name": "Kccv", "axis": "left", "marker": "diamond",
             "trend": f"y = {a4:.3f} ln(x) + {b4:.3f}",
             "points": [[x, y] for x, y in zip(VOL_CHART_NSQ, VOL_CHART_ROW4)],
             "fit": [[x, _r(a4 * math.log(x) + b4, 4)] for x in xs_fit if x <= 70]},
            {"name": "Row 5 coefficient", "axis": "right", "marker": "square",
             "trend": f"y = {c5:.4f} x^{m5:.4f}",
             "points": [[x, y] for x, y in zip(VOL_CHART_NSQ, VOL_CHART_ROW5)],
             "fit": [[x, _r(c5 * x ** m5, 4)] for x in xs_fit if x <= 70]},
        ],
        "mark": {"x": nsq, "y": _r(kccv, 4), "axis": "left",
                 "label": f"This pump: Nsq {nsq:g}, Kccv {kccv:.3f}"},
    }

    volute = [
        ("Kccv", _r(kccv, 4), ""),
        ("Velocity in volute Vth", _r(vth, 3), "m/s"),
        ("Throat dia (calculated)", _r(throat, 2), "mm"),
        ("Throat dia chosen", p["vol_throat"], "mm"),
        ("Throat area (calculated dia)", _r(throat ** 2 * 0.786, 2), "mm²"),
        ("Base circle dia", base_dia, "mm"),
        ("tan(θ/2) term C22 · D22", f"{_r(c22, 5)} · {_r(d22, 2)}", ""),
    ]

    # ---- pipe friction / system head (P12:S19)
    try:
        flows = [float(x) for x in p["sys_q"].replace(";", ",").split(",") if x.strip()]
    except ValueError:
        raise ValueError("Flows must be numbers separated by commas")
    dp = p["sys_pipe"] / 1000
    sys_rows = []
    for fq in flows:
        v = fq / 60000 / 0.786 / dp ** 2                                     # Q12
        hf = 4 * p["sys_f"] * v ** 2 / 19.62 / dp                            # R12
        sys_rows.append([fq, _r(v, 3), _r(hf, 5), _r(p["sys_static"] + p["sys_len"] * hf, 3)])  # S12

    # ---- compact output for the page: key results, plan view and graphs
    imp_key = [
        ("Specific speed Nsq", nsq, ""),
        ("Power input required", _r(pin, 2), "HP"),
        ("Hydraulic efficiency", _r(eta_h * 100, 1), "%"),
        ("Inlet (eye) dia - calculated", _r(d_in_calc, 1), "mm"),
        ("Inlet width b1", _r(b1 * 1000, 2), "mm"),
        ("β1 - calculated", _r(beta1_calc, 1), "deg"),
        ("Outer dia D2 - calculated", _r(d2_calc * 1000, 1), "mm"),
        ("Outlet width b2", _r(b2 * 1000, 2), "mm"),
        ("Tip speed U2", _r(u2, 2), "m/s"),
        ("Shut-off head", _r(h_shut, 1), "m"),
        ("Slip factor Cp", _r(cp, 3), ""),
    ]
    vol_key = [
        ("Volute coefficient Kccv", _r(kccv, 4), ""),
        ("Velocity in volute Vth", _r(vth, 2), "m/s"),
        ("Throat dia - calculated", _r(throat, 2), "mm"),
        ("Throat dia - chosen", p["vol_throat"], "mm"),
        ("Throat area - calculated", _r(throat ** 2 * 0.786, 1), "mm²"),
        ("Base circle dia (D2 + 7)", base_dia, "mm"),
        ("Volute width", width, "mm"),
        ("Diffusion angle", p["vol_angle"], "deg"),
    ]
    compact = {
        "duty": [("Pump", p["pump_type"], ""), ("Q", Q, "lpm"), ("H", H, "m"),
                 ("Speed", n, "RPM"), ("Nsq", nsq, "")],
        "impeller": {
            "key": imp_key,
            # vane development, laid out like rows 5-11 of IMP Design (7 stations across)
            # rows as in the sheet: D, Vf, Vf (adjusted), β, b (m), b FINAL (mm), radius
            "vane_table": {
                "rows": [
                    {"label": "D", "values": [f"{d:.1f}" if 0 < i < 6 else f"{d:g}" for i, d in enumerate(D)]},
                    {"label": "Vf", "values": [f"{v:.6f}" for v in vf]},
                    {"label": "Vf", "values": [f"{v:.6f}" for v in vf_adj], "adjusted": [1, 2, 3, 4, 5]},
                    {"label": "β", "values": [f"{b:.5f}" for b in beta]},
                    {"label": "b", "values": [f"{b:.6f}" for b in vane_b]},
                    {"label": "b FINAL", "values": [f"{b * 1000:.1f}" for b in vane_b], "bold": True},
                    {"label": "", "values": [f"{d / 2:.1f}" for d in D]},
                ],
            },
            # blade arcs, laid out like F30:H38
            "arc_table": {
                "columns": ["", "Inlet D1", "Middle Dm", "Outer D2"],
                "rows": [
                    ["In Diameter", _r(arc_d1, 2), _r(arc_dm, 2), d2c],
                    ["in Radius", _r(r_1, 2), _r(r_m, 2), r_2],
                    ["β", b1d, p["arc_beta_m"], p["arc_beta_2"]],
                    ["ρ2  (Radius-2)", _r(arc_r2, 5), None, None],
                    ["ρ1  (Radius-1)", _r(arc_r1, 5), None, None],
                    ["ψ", _r(y, 6), None, None],
                    ["Cp", _r(cp_slip, 6), None, None],
                ],
            },
            "charts": [
                {"title": "Vane development - β and Vf along impeller", "x": "Diameter D (mm)",
                 "dual": True,
                 "series": [
                     {"name": "β (deg)", "axis": "left", "marker": "square",
                      "points": [[_r(D[i], 1), _r(beta[i], 2)] for i in range(7)]},
                     {"name": "Vf (m/s)", "axis": "right", "marker": "diamond",
                      "points": [[_r(D[i], 1), _r(vf_adj[i], 3)] for i in range(7)]},
                 ]},
            ],
        },
        "volute": {
            "key": vol_key,
            # cross sections laid out like Vol Design C28:K34 (labels on the right as in the sheet)
            "xs_table": {
                "header": [str(k) for k in range(1, 9)] + ["crossection"],
                "rows": [
                    {"label": "Crosection area", "values": [f"{r[2]:.4f}" for r in vol_raw]},
                    {"label": "R", "values": [f"{r[3]:.5f}" for r in vol_raw]},
                    {"label": "FILLET", "values": [f"{r[4]:.1f}" for r in vol_raw], "input": True},
                    {"label": "∆area", "values": [f"{r[5]:g}" for r in vol_raw]},
                    {"label": "∆r", "values": [f"{r[6]:g}" for r in vol_raw]},
                    {"label": "Act R", "values": [f"{_excel_round(r[7]):.0f}" for r in vol_raw], "bold": True},
                ],
            },
            "charts": [vol_chart],
        },
    }

    # ---- Sheet1: velocity coefficients Kc1 / Kc2 vs specific speed (chart with linear trendlines)
    ns_list = [r[0] for r in KC_CHART]
    m1, c1 = _linfit(ns_list, [r[2] for r in KC_CHART])
    m2, c2 = _linfit(ns_list, [r[1] for r in KC_CHART])
    x_hi = max(ns_list)
    compact["impeller"]["kc"] = {
        "values": [
            ("Nsq of this pump", nsq, ""),
            ("Kcm1 used" + (" (typed)" if p["kcm1"] is not None else " (chart)"), _r(kcm1, 4), ""),
            ("Kcm2 used" + (" (typed)" if p["kcm2"] is not None else " (chart)"), _r(kcm2, 4), ""),
            ("Kc1 / Kc2 from chart (interpolated)", f"{kc1_chart:.4f} / {kc2_chart:.4f}", ""),
            ("Kc1 / Kc2 from trendlines", f"{m1 * nsq + c1:.4f} / {m2 * nsq + c2:.4f}", ""),
        ],
        "chart": {
            "title": "Velocity coefficients vs specific speed (Sheet1)", "x": "Specific speed Nsq", "y": "Kc",
            "dual": True,
            "x_max": max(300, math.ceil((nsq + 10) / 50) * 50),
            "series": [
                {"name": "Kc1", "axis": "left", "marker": "square", "trend": f"y = {m1:.5f}x + {c1:.4f}",
                 "points": [[r[0], r[2]] for r in KC_CHART],
                 "fit": [[x, _r(m1 * x + c1, 4)] for x in (0, x_hi)]},
                {"name": "Kc2", "axis": "left", "marker": "diamond", "trend": f"y = {m2:.5f}x + {c2:.4f}",
                 "points": [[r[0], r[1]] for r in KC_CHART],
                 "fit": [[x, _r(m2 * x + c2, 4)] for x in (0, x_hi)]},
            ],
            "mark": {"x": nsq, "y": _r(kcm1, 4), "axis": "left",
                     "label": f"This pump: Nsq {nsq:g} → Kcm1 {kcm1:.3f}, Kcm2 {kcm2:.4f}"},
        },
    }

    if _checks:
        compact["impeller"]["checks"] = _impeller_checks(p, pin, eta_h, eta_h_est, d2_calc * 1000)
        compact["volute"]["checks"] = _volute_checks(p, throat)
    return {
        "compact": compact,
        "title": p["pump_type"],
        "warnings": warnings,
        "highlights": [
            ("Nsq", nsq, ""), ("D2 calculated", _r(d2_calc * 1000, 1), "mm"),
            ("b2 (vane gap top)", _r(gap_top, 2), "mm"), ("Shut-off head", _r(h_shut, 1), "m"),
            ("Throat dia", _r(throat, 2), "mm"), ("Power input", _r(pin, 2), "HP"),
        ],
        "sections": [
            {"title": "Impeller - duty & velocities", "kv": main},
            {"title": "Impeller - inlet", "kv": inlet},
            {"title": "Impeller - outlet", "kv": outlet},
            {"title": "Vane development (7 stations)", "table": {
                "columns": ["Stn", "D mm", "R mm", "Vf m/s", "Adjust", "Vf adj m/s", "β deg", "b mm"],
                "rows": vane_rows}},
            {"title": "Blade arcs (two-arc method)", "kv": arcs},
            {"title": f"Blade layout - table 1 (typed w) · wrap angle {wrap1:.2f}°", "table": {
                "columns": ["Pt", "r m", "Δr", "Cm", "w theory", "w used", "sin β", "β deg",
                            "r tan β", "B", "Δa", "Σa", "θ deg", "90-θ"], "rows": t1}},
            {"title": f"Blade layout - table 2 (β {p['pp_beta_in']:g}° → {p['pp_beta_out']:g}°) · "
                      f"wrap angle {wrap2:.2f}°", "table": {
                "columns": ["Pt", "r m", "Δr", "Cm", "w theory", "w used", "sin β", "β deg",
                            "r tan β", "B", "Δa", "Σa", "θ deg", "90-θ"], "rows": t2}},
            {"title": "Volute", "kv": volute},
            {"title": "Volute cross sections", "table": {
                "columns": ["Sec", "Angle °", "Area mm²", "R mm", "Fillet R", "Fillet area",
                            "Δr", "Actual R mm", "Actual area", "Actual / theory"],
                "rows": vol_rows}},
            {"title": "Pipe friction / system head", "table": {
                "columns": ["Q lpm", "Velocity m/s", "Hf per m", "System head m"],
                "rows": sys_rows}},
        ],
        # raw values for tests
        "_raw": {"nsq": nsq, "ns_us": ns_us, "pin": pin, "eta_h": eta_h, "cm1": cm1, "cm2": cm2,
                 "d_in_calc": d_in_calc, "d_eye_nom": d_eye_nom, "v_in": v_in, "u1": u1,
                 "beta1_calc": beta1_calc, "y": y, "cp": cp, "g_hth": g_hth, "u2": u2,
                 "d2_calc": d2_calc, "h_shut": h_shut, "b2": b2, "b1": b1,
                 "vane_b": [r[7] for r in vane_rows], "arc_r1": arc_r1, "arc_r2": arc_r2,
                 "wrap1": wrap1, "wrap2": wrap2, "kccv": kccv, "vth": vth, "throat": throat,
                 "vol_R": [r[3] for r in vol_rows], "sys_head": [r[3] for r in sys_rows],
                 "eta_v_est": eta_v_est, "eta_h_est": eta_h_est},
    }


# ---------------------------------------------------------------- pass / fail checks
def _check(name, ok, detail, fixes):
    return {"name": name, "status": "Pass" if ok else "Fail", "detail": detail,
            "fixes": [] if ok else fixes}


def _d2_calc_mm(p, d2):
    """Calculated D2 when D2 chosen = d2 (slip factor depends on the chosen D2)."""
    return calculate({**p, "d2": float(d2)}, _checks=False)["_raw"]["d2_calc"] * 1000


def _d2_ok(chosen, calc):
    dev = (chosen - calc) / calc
    return -D2_TOL_UNDER <= dev <= D2_TOL_OVER, dev


def _impeller_checks(p, pin, eta_h, eta_h_est, d2_calc):
    out = []

    # 1. motor power
    ok = p["hp"] >= pin
    nxt = next((h for h in HP_LIST if h >= pin), None)
    out.append(_check(
        "Motor power", ok,
        f"Motor {p['hp']:g} HP vs power input required {pin:.2f} HP",
        [{"text": f"Use a {nxt:g} HP motor (next standard size above {pin:.2f} HP).", "apply": {"hp": nxt}}]
        if nxt else [{"text": "Required power is above 200 HP - check duty or efficiency.", "apply": None}]))

    # 2. D2 chosen vs calculated
    ok, dev = _d2_ok(p["d2"], d2_calc)
    fix = []
    if not ok:
        # whole-mm D2 closest to its own calculated D2 (slip factor is recalculated with each candidate)
        best = None
        for cand in range(int(math.floor(d2_calc * 0.85)), int(math.ceil(d2_calc * 1.2)) + 1):
            c_calc = _d2_calc_mm(p, cand)
            good, d = _d2_ok(cand, c_calc)
            if good and (best is None or abs(d) < best[2]):
                best = (cand, c_calc, abs(d))
        if best:
            fix = [{"text": f"Change D2 chosen to {best[0]} mm "
                            f"(calculated D2 becomes {best[1]:.1f} mm).", "apply": {"d2": best[0]}}]
    out.append(_check(
        "Outer dia D2", ok,
        f"Chosen {p['d2']:g} mm vs calculated {d2_calc:.1f} mm ({dev * 100:+.1f} %, "
        f"allowed {-D2_TOL_UNDER * 100:g} % to +{D2_TOL_OVER * 100:g} %)", fix))

    # 3. hydraulic efficiency = overall / (mech x vol)
    ok = eta_h < ETA_H_MAX
    new_eff = math.floor(eta_h_est * p["eff_mech"] * p["eff_vol"] * 1000) / 1000
    out.append(_check(
        "Hydraulic efficiency", ok,
        f"η / (ηm × ηv) = {eta_h * 100:.1f} % (must be below {ETA_H_MAX * 100:g} %)",
        [{"text": f"Set overall efficiency to {new_eff:g} "
                  f"(hydraulic efficiency estimate {eta_h_est * 100:.1f} % × ηm × ηv).", "apply": {"eff": new_eff}}]))
    return out


def _volute_checks(p, throat):
    ok = p["vol_throat"] >= throat
    new = math.ceil(throat * 2) / 2
    return [_check(
        "Throat dia", ok,
        f"Chosen {p['vol_throat']:g} mm vs calculated {throat:.2f} mm (chosen must not be smaller)",
        [{"text": f"Change throat dia chosen to {new:g} mm.", "apply": {"vol_throat": new}}])]


reload()
