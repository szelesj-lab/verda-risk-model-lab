@echo off
REM Build VERDA_Risk_Lab.exe on Windows.
REM Needs Python 3.10+ from python.org (tkinter is included by default).

python -m pip install --upgrade pyinstaller
python -m PyInstaller --onefile --windowed --name VERDA_Risk_Lab verda_app.py

echo.
echo Done. The program is in the dist folder: dist\VERDA_Risk_Lab.exe
pause
