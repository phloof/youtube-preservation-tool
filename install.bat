@echo off
echo =====================================
echo   YouTube Channel Video Archiver
echo   Installation Script for Windows
echo =====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [INFO] Python found:
python --version
echo.

REM Check if pip is available
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip is not available
    echo Please reinstall Python with pip included
    pause
    exit /b 1
)

echo [INFO] pip found:
python -m pip --version
echo.

REM Upgrade pip
echo [STEP 1/4] Upgrading pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [WARNING] Could not upgrade pip, continuing anyway...
)
echo.

REM Install required packages
echo [STEP 2/4] Installing required packages...
echo Installing: requests, beautifulsoup4, lxml, yt-dlp
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install required packages
    echo Please check your internet connection and try again
    pause
    exit /b 1
)
echo [SUCCESS] Required packages installed successfully!
echo.

REM Install yt-dlp separately (in case it's not in requirements.txt)
echo [STEP 3/4] Installing yt-dlp for enhanced video downloading...
python -m pip install yt-dlp
if %errorlevel% neq 0 (
    echo [WARNING] Could not install yt-dlp, but script will still work
    echo You can install it manually later with: pip install yt-dlp
) else (
    echo [SUCCESS] yt-dlp installed successfully!
)
echo.

REM Test import of main modules
echo [STEP 4/4] Testing installation...
python -c "import requests; import bs4; print('[SUCCESS] All modules can be imported')"
if %errorlevel% neq 0 (
    echo [ERROR] Some modules failed to import
    echo Please check the error messages above
    pause
    exit /b 1
)

REM Create a shortcut batch file for easy running
echo [BONUS] Creating easy-run shortcut...
echo @echo off > run_video_archiver.bat
echo echo Starting YouTube Channel Video Archiver... >> run_video_archiver.bat
echo python run_archiver.py >> run_video_archiver.bat
echo pause >> run_video_archiver.bat
echo [SUCCESS] Created run_video_archiver.bat for easy execution
echo.

echo =====================================
echo   INSTALLATION COMPLETE! 
echo =====================================
echo.
echo You can now run the video archiver in three ways:
echo.
echo 1. Double-click: run_video_archiver.bat
echo 2. Command line: python run_archiver.py
echo 3. Direct script: python video_archiver.py
echo.
echo The script will save videos to a 'saved_videos' folder
echo Check video_archiver.log for detailed progress information
echo.
echo Press any key to close this window...
pause >nul 