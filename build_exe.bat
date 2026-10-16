@echo off
REM Build VERDA_Risk_Lab.exe on Windows.
REM Needs Python 3.10+ from python.org (tkinter is included by default).

python -m pip install --upgrade pyinstaller
python -m PyInstaller --onefile --windowed --name VERDA_Risk_Lab --add-data "models;models" verda_app.py

echo.
echo Done. The program is in the dist folder: dist\VERDA_Risk_Lab.exe
echo The VERDA model is built in. Copy the models folder next to the .exe so users can open the other models.
pause
