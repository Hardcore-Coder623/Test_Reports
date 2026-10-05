"""Bush (plain bearing) design check (server side only).

Faithful port of each model sheet in
final_Bush_Design_for_New_Mechanical_Seal_Pumps_08-1-19.xlsx (rows 21-52).
"""
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
MODELS = {}
GLOBAL_PV = {}          # material -> PV limit (lb/in² x ft/min) when a model sheet has no entry


def reload():
    """(Re)load the model sheets and the material master (called after a Masters save)."""
    global MODELS, GLOBAL_PV
    MODELS = json.loads((DATA / "pump_models.json").read_text(encoding="utf-8"))
    GLOBAL_PV = {m["material"]: float(m["pv_imperial"])
                 for m in json.loads((DATA / "bush_materials.json").read_text(encoding="utf-8"))}


reload()

INPUT_FIELDS = [
    "impeller_od", "vane_width", "head", "discharge_m3h", "speed", "kso", "sg",
    "rotor_wt", "impeller_wt", "dim_a", "dim_b",
    "bush_a_dia", "bush_a_len", "bush_b_dia", "bush_b_len",
]

PSI_FPM_TO_KG_MMIN = 14.2233 * 3.28


def pv_limit_for(model_key, material):
    m = MODELS[model_key]
    return m["pv_limits"].get(material, GLOBAL_PV.get(material))


def options():
    out = []
    for key, m in MODELS.items():
        out.append({
            "key": key,
            "label": m["label"],
            "material": m["material"],
            "inputs": {f: m[f] for f in INPUT_FIELDS},
            "pv_limits": {mat: pv_limit_for(key, mat) for mat in GLOBAL_PV},
        })
    return {"models": out, "materials": list(GLOBAL_PV)}


def calculate(model_key, material, pv_limit_imp, p):
    if model_key not in MODELS:
        raise ValueError(f"Unknown pump model: {model_key}")
    m = MODELS[model_key]
    for f in ("head", "dim_b", "bush_a_dia", "bush_a_len", "bush_b_dia", "bush_b_len"):
        if p[f] <= 0:
            raise ValueError(f"{f.replace('_', ' ')} must be greater than zero")

    gpm = p["discharge_m3h"] * 3.67                                               # D27
    ns = p["speed"] * math.sqrt(gpm) / (p["head"] * 3.28) ** 0.75                 # B35
    rso = (p["kso"] * p["head"] * p["sg"] / 2.31 * p["impeller_od"]
           * p["vane_width"] / 100 + p["impeller_wt"])                            # B40
    fra = rso * (p["dim_a"] + p["dim_b"]) / p["dim_b"]                            # B41
    frb = abs(rso - fra) + p["rotor_wt"]                                          # B42

    va = math.pi * p["bush_a_dia"] / 1000 * p["speed"]                            # B47
    pa = fra / (p["bush_a_dia"] * p["bush_a_len"] / 100)                          # B48
    pva = va * pa                                                                 # B49
    vb = math.pi * p["bush_b_dia"] / 1000 * p["speed"]                            # B50
    pb = frb / (p["bush_b_dia"] * p["bush_b_len"] / 100)                          # B51
    pvb = vb * pb                                                                 # B52

    if pv_limit_imp is None or pv_limit_imp <= 0:
        raise ValueError("PV limit must be greater than zero")
    pv_max = pv_limit_imp / PSI_FPM_TO_KG_MMIN                                    # E31

    def fixes(len_field, length, fr, pv):
        """How to turn a failing bush into a passing one.
        PV = (pi*d*N/1000) * Fr/(d*L/100) = pi*N*Fr/(10*L): the diameter cancels,
        so only a longer bush, a better material, or less load helps."""
        if pv_max > pv:
            return []
        out = []
        l_min = math.pi * p["speed"] * fr / (10 * pv_max)
        l_new = (math.floor(l_min / 5) + 1) * 5                      # next 5 mm step, strictly above
        out.append({
            "text": f"Increase length from {length:g} mm to at least {l_new} mm "
                    f"(minimum {l_min:.1f} mm). Changing the diameter does not reduce PV.",
            "apply": {len_field: l_new},
        })
        for mat in GLOBAL_PV:
            if mat == material:
                continue
            lim = pv_limit_for(model_key, mat)
            if lim and lim / PSI_FPM_TO_KG_MMIN > pv:
                out.append({
                    "text": f"Or change material to {mat} (PV limit {lim:,} lb/in²·ft/min) "
                            f"with the present length.",
                    "apply": {"material": mat, "pv_limit": lim},
                })
        return out

    def bush(name, dia, length, v, pr, pv, size, len_field, fr):
        return {
            "fixes": fixes(len_field, length, fr, pv),
            "name": name, "dia": dia, "length": length, "size": size,
            "v_m_min": round(v, 2), "v_m_s": round(v / 60, 3),
            "p_kg_cm2": round(pr, 3), "pv": round(pv, 2),
            "pv_max": round(pv_max, 2),
            "utilisation": round(pv / pv_max * 100, 1),
            "status": "Pass" if pv_max > pv else "Fail",               # F49 / F52
        }

    return {
        "model": m["label"],
        "material": material,
        "pv_limit_imp": pv_limit_imp,
        "pv_limit_metric": round(pv_max, 2),
        "summary": {
            "discharge_gpm": round(gpm, 2),
            "specific_speed": round(ns, 1),
            "rso": round(rso, 2),
            "fra": round(fra, 2),
            "frb": round(frb, 2),
        },
        "bush_a": bush("Bush A (DE)", p["bush_a_dia"], p["bush_a_len"], va, pa, pva,
                       " / ".join(s for s in (m["de_bush_1"], m["de_bush_2"]) if s),
                       "bush_a_len", fra),
        "bush_b": bush("Bush B (NDE)", p["bush_b_dia"], p["bush_b_len"], vb, pb, pvb, m["nde_bush"],
                       "bush_b_len", frb),
    }
