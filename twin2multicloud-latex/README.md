# Master Thesis LaTeX Project

## Quick Start

### Using Batch Files (Recommended)
| Action | File |
|--------|------|
| **Watch mode** (auto-compile + opens PDF viewer) | Double-click `start-watch.bat` |
| **Compile once** | Double-click `compile.bat` |

> **Note:** `start-watch.bat` automatically opens the PDF in SumatraPDF or Adobe Reader if installed.

### Using Docker Commands
```bash
# Watch mode - auto-compiles when you save
docker compose run --rm thesis-latex

# Compile once
docker compose run --rm thesis-latex latexmk -pdf -cd /thesis/main.tex

# Clean build files
docker compose run --rm thesis-latex latexmk -C -cd /thesis/main.tex
```

---

## Project Structure

```
twin2multicloud-latex/
├── main.tex              # Main document - edit this
├── chapters/             # Chapter files
│   ├── abstract.tex
│   ├── introduction.tex
│   ├── background.tex
│   └── ...
├── frontmatter/          # Title page elements
│   ├── affidavit.tex
│   └── acknowledgements.tex
├── styles/               # LaTeX styles and config
│   ├── QEmaster.cls      # University template
│   ├── codeKeywords.tex  # Code highlighting
│   └── glossary.tex      # Acronyms/glossary
├── figures/              # Images
├── bibliography/         # References
│   └── biblio.bib
└── build/                # Output (git-ignored)
    └── main.pdf          # Generated PDF
```

---

## Viewing PDF

**Recommended:** [SumatraPDF](https://www.sumatrapdfreader.org/)
- Lightweight and fast
- Auto-refreshes when PDF changes
- Perfect for watch mode workflow

---

## Code Highlighting

Supported languages: `Python`, `JSON`, `YAML`, `Terraform`, `Dockerfile`, `Bash`

```latex
\begin{lstlisting}[language=Python]
def hello():
    print("Hello World")
\end{lstlisting}
```

---

## Acronyms

Use `\gls{acronym}` for automatic expansion:

```latex
\gls{dt}     % First use: "Digital Twin (DT)"
\gls{dt}     % Later uses: "DT"
\Gls{aws}    % Capitalized: "AWS"
```

Pre-defined: DT, IoT, AAS, API, REST, JSON, YAML, AWS, GCP, CLI, UI, VM, IaC

Add more in `styles/glossary.tex`.

---

## Requirements

- Docker Desktop
- Docker Compose
