@echo off
setlocal

echo Starting LaTeX watch mode...
echo.
echo PDF will be generated at: build\main.pdf
echo Press Ctrl+C to stop watching
echo.

cd /d "%~dp0"

:: Wait for PDF to exist (may need initial compile)
set "PDF_PATH=%~dp0build\main.pdf"

:: Open PDF viewer
set "SUMATRA_PATH=C:\Program Files\SumatraPDF\SumatraPDF.exe"
set "SUMATRA_PATH_X86=C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe"
set "ACROBAT_PATH=C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe"
set "ACROBAT_READER_PATH=C:\Program Files\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe"

:: Check for SumatraPDF (64-bit)
if exist "%SUMATRA_PATH%" (
    echo Opening PDF in SumatraPDF...
    start "" "%SUMATRA_PATH%" "%PDF_PATH%"
    goto :start_docker
)

:: Check for SumatraPDF (32-bit)
if exist "%SUMATRA_PATH_X86%" (
    echo Opening PDF in SumatraPDF...
    start "" "%SUMATRA_PATH_X86%" "%PDF_PATH%"
    goto :start_docker
)

:: Check for Adobe Acrobat
if exist "%ACROBAT_PATH%" (
    echo Opening PDF in Adobe Acrobat...
    start "" "%ACROBAT_PATH%" "%PDF_PATH%"
    goto :start_docker
)

:: Check for Adobe Reader
if exist "%ACROBAT_READER_PATH%" (
    echo Opening PDF in Adobe Reader...
    start "" "%ACROBAT_READER_PATH%" "%PDF_PATH%"
    goto :start_docker
)

:: No PDF viewer found
echo.
echo ============================================================
echo WARNING: No PDF viewer found!
echo.
echo Please install one of the following:
echo   - SumatraPDF (recommended): https://www.sumatrapdfreader.org/
echo   - Adobe Acrobat Reader
echo.
echo After installing, manually open: build\main.pdf
echo ============================================================
echo.

:start_docker
cd /d "%~dp0.."
docker compose run --rm thesis-latex
pause
