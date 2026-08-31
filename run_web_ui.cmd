@echo off

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m generator.webui.server %*
) else (
    python -m generator.webui.server %*
)
pause
