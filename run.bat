@echo off
cd /d "%~dp0"
if not exist .venv (
  py -3.12 -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python headscreen.py %*
