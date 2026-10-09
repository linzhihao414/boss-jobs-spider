@echo off
chcp 65001 >nul
cd /d %~dp0
set PY=C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe
"%PY%" -m pip install -r requirements.txt
"%PY%" boss_gui.py
