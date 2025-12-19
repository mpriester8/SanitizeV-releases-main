@echo off
echo Installing Dependencies...
python -m pip install -r requirements.txt
echo Installing PyInstaller...
python -m pip install pyinstaller

echo Building EXE...
rem Note: On Windows, use a semicolon (;) separator for --add-data.
python -m PyInstaller --onefile --noconsole --name "Sanitize V" --icon=assets/app_icon.ico --add-data "assets/banner.png;assets" --hidden-import=PIL --hidden-import=PIL.ImageTk --hidden-import=update_manager src/main.py

echo.
echo Build Complete!
echo You can find your executable in the 'dist' folder.
echo.
echo Remember to:
echo 1. Update version.json with new version and download URL
echo 2. Upload the new EXE to your release URL
echo 3. Commit version.json to your GitHub repository
pause
