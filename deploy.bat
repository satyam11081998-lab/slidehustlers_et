@echo off
REM ============================================================
REM  KAVACH - deploy the control room to Vercel via the CLI
REM
REM  Backend first (30 seconds, one click, no CLI needed):
REM    https://render.com/deploy?repo=https://github.com/satyam11081998-lab/slidehustlers_et
REM    Render reads render.yaml and configures everything itself.
REM    Wait for it to go live, then copy the service URL and run this script.
REM
REM  You can also run this WITHOUT a backend URL - the control room ships
REM  precomputed frames and will play the scenario offline, so the link works
REM  either way.
REM ============================================================
setlocal
cd /d "%~dp0"

where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js is not installed. Get it from https://nodejs.org and re-run.
  pause & exit /b 1
)

echo.
echo === Installing the Vercel CLI (skipped if already present) ===
where vercel >nul 2>&1
if errorlevel 1 (
  call npm install -g vercel --no-audit --no-fund
  if errorlevel 1 (
    echo [ERROR] Could not install the Vercel CLI.
    pause & exit /b 1
  )
)

echo.
echo === Signing in to Vercel ===
echo A browser window will open. Approve it there - your credentials never
echo pass through this script.
call vercel login
if errorlevel 1 (
  echo [ERROR] Vercel login failed.
  pause & exit /b 1
)

cd frontend

echo.
set /p RENDER_URL="Paste your Render backend URL (https://...onrender.com), or press Enter to skip: "
if not "%RENDER_URL%"=="" (
  echo.
  echo === Pointing the frontend at your backend ===
  echo %RENDER_URL%| call vercel env add NEXT_PUBLIC_API_BASE production
  echo %RENDER_URL%| call vercel env add NEXT_PUBLIC_API_BASE preview
)

echo.
echo === Deploying to production ===
echo If asked, accept the defaults. The project root is this frontend folder.
call vercel deploy --prod
if errorlevel 1 (
  echo [ERROR] Deploy failed. Scroll up for the reason.
  pause & exit /b 1
)

echo.
echo ============================================================
echo  DONE. The production URL is printed just above this line.
echo.
echo  Before you attach it to the submission:
echo    1. Open it once and press Play - confirm the clock runs.
echo    2. Jump to 06:30 - Battery 4 Basement should go CRITICAL.
echo    3. If you deployed the backend, open its /api/health first to
echo       wake it (free instances sleep after 15 minutes idle).
echo ============================================================
pause
