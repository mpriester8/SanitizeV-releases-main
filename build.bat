@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE="
set "PYTHON_ARGS="

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
	set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else (
	where py >nul 2>nul
	if not errorlevel 1 (
		set "PYTHON_EXE=py"
		set "PYTHON_ARGS=-3"
	) else (
		where python >nul 2>nul
		if not errorlevel 1 set "PYTHON_EXE=python"
	)
)

if not defined PYTHON_EXE (
	echo Error: Python 3.12+ was not found.
	echo The build script looks for a local .venv, then the Windows py launcher, then python on PATH.
	exit /b 1
)

echo Using Python command: %PYTHON_EXE% %PYTHON_ARGS%
echo Installing Dependencies...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r requirements.txt
if errorlevel 1 (
	echo.
	echo Build failed during: Installing Dependencies...
	exit /b 1
)

echo Installing PyInstaller...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install pyinstaller
if errorlevel 1 (
	echo.
	echo Build failed during: Installing PyInstaller...
	exit /b 1
)

echo Building EXE...
"%PYTHON_EXE%" %PYTHON_ARGS% -m PyInstaller --onefile --noconsole --name "Sanitize V" --icon=assets/app_icon.ico --add-data "assets/sidebar_logo.png;assets" --add-data "assets/app_icon.ico;assets" --add-data "assets/app_icon.png;assets" --hidden-import=PIL --hidden-import=PIL.ImageTk --hidden-import=update_manager src/main.py
if errorlevel 1 (
	echo.
	echo Build failed during: Building EXE...
	exit /b 1
)

echo.
echo Build Complete!
echo You can find your executable in the 'dist' folder.
echo.
echo Remember to:
echo 1. Update version.json with new version and download URL
echo 2. Upload the new EXE to your release URL
echo 3. Commit version.json to your GitHub repository
pause
exit /b 0
