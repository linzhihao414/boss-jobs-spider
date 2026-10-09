@echo off
chcp 65001 >nul
cd /d %~dp0
pip install -r requirements.txt
python boss_spider.py
pause
