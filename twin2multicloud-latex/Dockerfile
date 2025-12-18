FROM texlive/texlive:latest

WORKDIR /thesis

# Default: Watch mode - auto-compiles on file save (Ctrl+C to stop)
# Output goes to build/ directory (configured in .latexmkrc)
CMD ["latexmk", "-pvc", "-cd", "/thesis/main.tex"]
