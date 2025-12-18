# Latexmk configuration
# All build output goes to build/ folder
$out_dir = 'build';

# Use pdflatex
$pdf_mode = 1;
$pdflatex = 'pdflatex -interaction=nonstopmode -file-line-error %O %S';

# Disable PDF previewer (view PDF on Windows, not in container)
$pdf_previewer = 'true';
