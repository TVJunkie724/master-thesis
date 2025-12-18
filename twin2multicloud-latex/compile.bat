@echo off
echo Compiling thesis...
cd /d "%~dp0.."
docker compose run --rm thesis-latex latexmk -pdf -cd /thesis/main.tex
echo.
echo Done! PDF at: build\main.pdf
pause
