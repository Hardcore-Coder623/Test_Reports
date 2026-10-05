@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
rem installs anything new in requirements.txt (e.g. reportlab for the PDF report)
pip install -q -r requirements.txt
start "" http://localhost:5000
python app.py
