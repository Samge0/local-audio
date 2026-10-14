@echo off
cd /d %~dp0
title Audio Player
if exist .venv\Scripts\python.exe (
  set PYTHON=.venv\Scripts\python.exe
) else (
  set PYTHON=python
)
echo Starting Audio Player...
start "" http://127.0.0.1:8792
%PYTHON% server.py
pause
