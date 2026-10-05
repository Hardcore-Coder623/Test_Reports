# Pump Design Calculator (web)

A web version of **Bearing_Calculation.xlsx** and **Bush Design for New Mechanical Seal Pumps.xlsx**.

The page only has selection options and input fields. All formulas run on the server
(`calc/` folder). The browser receives just the finished results, so no formulas are
visible in the page or its source.

## Run on Windows
1. Install Python 3.10+ from python.org (tick "Add Python to PATH").
2. Double-click `run_windows.bat`. It installs Flask the first time and opens http://localhost:5000.

## Run on Linux / macOS
```
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000. Other PCs on your network can use http://<server-ip>:5000.

## What is where
| Path | Contents |
|---|---|
| `calc/bearing.py` | Ball bearing formulas (sheet "Ball") |
| `calc/bush.py` | Bush PV formulas (each pump model sheet) |
| `data/bearings.json` | Bearing table (sheet "Bearing_Data"); add rows here to add bearings |
| `data/pump_models.json` | Default inputs and PV limits per pump model; add a block to add a model |
| `tests/test_excel_parity.py` | Checks the web results equal the Excel results |

## Bearing master list (data/bearings.json)
100 deep groove ball bearings, 5 to 130 mm bore:
* the 30 rows from the original Bearing_Data sheet, values unchanged;
* added 6000-6026, 6200-6226, 6300-6326 and 6403-6418 (heavy series).
New rows use the lower (safer) catalogue value where two sources differ
(TFL Bearing and PTI tables). Each row has a `source` field. Dynamic rating `C` is shown where known.
Every standard motor rating 1-200 HP has a passing bearing at the default layout.

Original sheet values that differ from the catalogues (kept as is; please verify):
| Bearing | Sheet Co (N) | Catalogue Co (N) |
|---|---|---|
| 6205 | 9,800 | 7,800 |
| 6005 | 6,550 | 5,850 |
| 6006 | 8,300 | 8,000 |
| 6305 | 11,600 | 11,400 - 11,600 |

## Notes
* The HP field offers the standard motor ratings 1-200 HP and still accepts any value.
* Ball bearing tab has a shaft layout drawing: Brg A —a— P1 —b— Brg B —c— P2, span k = a + b.
  a, b and c (mm) are typed directly on the drawing; P1, P2, span and reactions RA / RB are
  filled in from the server. Defaults a = b = 155 mm (= CL/2 + Bearing ext = 170/2 + 70).
* Bearing B load = (P1·a + P2·(c + k)) / k with k = bearing span, as in the layout sketch.
  The original Excel used k = 3 (the drive factor cell) here, which gave a lower Bearing B load.
* Bearing check: OK when static capacity Co ≥ radial load (N). The sheet listed Co but had
  no pass/fail, so this check is added.
* Bush check: Pass when PV max > PV (same as the sheet's IF formula).
* When a check fails, the results show DESIGN FAILS and a "How to pass" box with an Apply button:
  - Bearing: the lightest bearing on the same bore that carries the load; if none, the
    smallest bearing on the next bore up (shaft at that bearing must be stepped to that bore).
  - Bush: the minimum bush length (rounded up to 5 mm), and any other material that passes
    at the present length. PV = π·N·Fr / (10·L), so changing the bush diameter does not reduce PV.
* PV limits per material come from each model sheet; when a sheet doesn't list one,
  Carbon = 200,000 and Bronze = 75,000 lb/in²·ft/min are used. The limit stays editable.

## Impeller Design, Volute Design and Master tabs (Impeller_Design_of_7.5_HP_65x50.xls)
* Impeller Design - pump duty, efficiencies and impeller inputs; key results, blade arcs, vane development, β + Vf graph.
* Volute Design - volute inputs (base circle, width, diffusion angle, throat chosen); uses the pump duty
  entered on Impeller Design (as the Vol Design sheet links to IMP Design); volute results, graphs, section table.
* Master - both designs together on one page (duty, checks, all results and graphs) for review / printing.

The page shows only the required inputs (pump duty, efficiencies, inlet dia, D2, Z, β1, β2) and the
important results: key dimensions, an impeller plan view (blades drawn by the two-arc method) and
graphs of vane width b, blade angle β and volute section area. All other inputs keep the sheet's
values (`REQUIRED_KEYS` / `DEFAULTS` in `calc/impeller.py`) and every formula runs on the server;
intermediate values are never sent to the browser.
Covers: IMP Design (main dimensions, vane development, blade arcs, both point-by-point blade
layout tables, pipe friction / system head), Vol Design (throat and 8 cross sections) and the
Sheet1 Kc chart. `tests/test_impeller.py` checks the results against the workbook's values.

* Kcm1 / Kcm2: the sheet looks these up in an external workbook that was not supplied.
  They default to the sheet's values (0.15 / 0.1077) so b FINAL etc. match the sheet; clear the box
  to read them from the Ns-Kc chart in Sheet1 instead (Ns 22 gives 0.144 / 0.1048).
* Impeller tab order: key results, blade arcs (D1 / Dm / D2, β, ρ2, ρ1, ψ, Cp), vane development
  (D, Vf, Vf adjusted, β, b, b FINAL, radius - laid out as in the sheet) and the β + Vf graph on two axes.
* Follows the updated workbook: D2 chosen 197 mm, blade inlet D1 = calculated inlet dia (B15),
  Dm = (D1 + D2) / 2. Only β at Dm and β at D2 are typed for the blade arcs.
* Blade layout table 2: its w column was typed in the sheet as a straight line from
  β 21° to 22°; it is now calculated from those two angles (same values).
* Not ported: scratch cells (e.g. F1, F2, J2, O14, K32) and the measured test-data columns
  P1:S6 / P31:S35, which no design formula uses.

### Impeller / volute pass-fail checks (calc/impeller.py)
Each tab starts with a PASS / FAIL banner; a failing check shows "How to pass" with an Apply button.
| Check | Pass when | Fix offered |
|---|---|---|
| Motor power | Motor HP ≥ power input required | next standard motor size (1-200 HP list) |
| Outer dia D2 | D2 chosen within −2 % / +5 % of D2 calculated | whole-mm D2 closest to its own calculated D2 |
| Hydraulic efficiency | η / (ηm × ηv) < 95 % | overall η = hydraulic-efficiency estimate × ηm × ηv |
| Volute throat dia | throat chosen ≥ throat calculated | calculated throat rounded up to 0.5 mm |
Tolerances are constants at the top of calc/impeller.py (D2_TOL_UNDER, D2_TOL_OVER, ETA_H_MAX).
Updated sheet applied: D2 chosen 197, D1 = calculated inlet dia (B15), Dm = (D1 + D2) / 2.

### Volute tab (sheet version with base circle = D2 + 7)
* Base circle dia is calculated as D2 chosen + 7 (Vol Design B20 = C20 + 7, C20 = IMP Design C27).
* Inputs: volute width, diffusion angle, throat dia chosen, and the 8 fillet radii (pink row).
* Cross-section table laid out like Vol Design C28:K34 (sections across, labels on the right, Act R rounded).
* Graph: Vol Design E3:J5 vs Nsq - Kccv (left axis, log trend = B17 formula) and the row-5 coefficient
  (right axis, power trend), trend equations fitted on the server, this pump's Nsq / Kccv marked.

## Test Report tab (Test_Report_Program_Tech_Auto_final.xlsm)
Pump performance test report with the same buttons as the workbook:
* **Download Nameplate** - fills the nameplate from the model master (`data/nameplates.json`, 107 models).
* **Upload Nameplate** - saves the nameplate on screen to that master (adds or replaces the model).
* **Download Readings** - loads up to 10 readings by Sr. No. from saved tests (`data/test_records.json`, 1,950 tests).
* **Upload Readings** - saves the Sr. No., date, model and readings on screen.
* **Export Report** - A4 landscape PDF (`calc/report_pdf.py`, ReportLab), file name `SrNo_(Model).pdf`.

Calculations (`calc/test_report.py`, cell references in comments): V²/2g from delivery size, H = Z + h + V²/2g,
current = average of R/Y/B (3-phase, all three entered) else highest / B, efficiency = H·Q / 6120 / kW,
correction to rated frequency (Q × f, H × f², P × f³, N × f), slip, head curve Q = aH² + c and current /
efficiency quadratics between readings, duty point on the line through the origin and (QG, HG), H-min /
H-max points, and the conclusion: head & discharge tolerance (7 % Q, 4 % H), efficiency > 95.5 % of declared,
maximum current over the H range ≤ 1.07 × rated. `tests/test_report.py` checks against the workbook values.
To refresh the masters from an updated workbook: `python tools/import_test_masters.py "<workbook>.xlsm"`.
Note: the sheet's V²/2g formula assumes LPM; here LPS and m³/h are converted to LPM first (same result for LPM).

## Masters tab (the supporting sheets of each workbook)
| Master | Workbook / sheet | Used by |
|---|---|---|
| Bearing data | Bearing_Calculation · Bearing_Data | Ball Bearing tab |
| Bush pump models | Bush workbook · one sheet per model | Bush Design tab |
| Bush materials (PV limits) | Bush workbook · Table1 I34:K37, J30:K31 (Carbon, Bronze, AMCO) | Bush Design tab |
| Velocity coefficients Kc1/Kc2 | Impeller workbook · Sheet1 A15:C33 | Impeller tab (Kcm from chart, Kc graph) |
| Nameplate data | Test report · NameplateData | Test Report: Download Nameplate |
| Company address | Test report · Report R45 | PDF header |
| Test data (saved tests) | Test report · TestData | Test Report: Download Readings (Open / Delete here) |

Edits are checked on the server (numbers, required fields, no duplicate keys) and used by the
calculations as soon as they are saved (refresh the page to update drop-down lists).

Not implemented: the workbook's "Observed Parameters" macro, which copies a model's reference readings
and applies random factors from VariationMaster to produce "observed" readings. A test report must carry
readings actually measured on the test bench, so the web app only accepts entered or saved readings.
External files referenced by the workbooks (Velocity_Coeff.xls, the Sr. No. → date list, the 5-50X50
label sheet) were not supplied; dates come from TestData and Kcm defaults to the sheet's values.

## Impeller Trim tab (Trim_Calculator.xlsx)
Inputs: test-curve diameter D1, new diameter D2, units and up to 8 flow / head / efficiency points
(blank rows are skipped - no need to repeat the last point). Server (`calc/trim.py`): D2/D1, (D2/D1)²,
Q2 = Q1·D2/D1, H2 = H1·(D2/D1)², power for both curves, and the B26 check (trim > 10 % can reduce
hydraulic efficiency) with an Apply fix. Graph: test and new-diameter head curves together (the workbook's
"Both" chart sheet). "Load from Test Report" copies the corrected points of the test open on the Test Report tab.
Units: "US - gpm, ft" is the sheet's BHP formula Q·H·100/(3960·η%); for LPM and m use the metric options
(kW = Q·H/(6120·η), HP = Q·H/(4500·η)). `tests/test_trim.py` checks against the workbook values.
