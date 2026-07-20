@echo off
REM ============================================================
REM  KAVACH - one-click publish to GitHub
REM  Pushes this folder to: github.com/satyam11081998-lab/slidehustlers_et
REM  Safe to run again later after any change.
REM ============================================================
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] git is not installed. Install from https://git-scm.com/download/win and re-run.
  pause & exit /b 1
)

git config user.name  >nul 2>&1 || git config --global user.name  "Satyam Kumar"
git config user.email >nul 2>&1 || git config --global user.email "satyam.11081998@gmail.com"

if not exist ".git" git init
git checkout -B main
git add -A
git commit -m "KAVACH - AI-powered industrial safety intelligence (ET AI Hackathon 2.0, PS1, Team SlideHustlers)" || echo (nothing new to commit)

git remote remove origin >nul 2>&1
git remote add origin https://github.com/satyam11081998-lab/slidehustlers_et.git

echo.
echo Pushing to GitHub (a browser sign-in window may appear - approve it)...
git push -u origin main --force
if errorlevel 1 (
  echo.
  echo [ERROR] Push failed. Usually this is sign-in: install Git Credential Manager
  echo         (bundled with Git for Windows), then re-run this script.
  pause & exit /b 1
)

echo.
echo ============================================================
echo  DONE. Verify at:
echo  https://github.com/satyam11081998-lab/slidehustlers_et
echo  Then continue with docs\SUBMISSION_CHECKLIST.md
echo ============================================================
pause
