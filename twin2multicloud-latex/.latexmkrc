# Latexmk configuration
# All build output goes to build/ folder
$out_dir = 'build';

# pdflatex preserves the relative path of files loaded through \include. A clean
# checkout therefore needs matching auxiliary directories before the first run.
use File::Path qw(make_path);
make_path('build/chapters', 'build/frontmatter', 'build/styles');

# Use pdflatex
$pdf_mode = 1;
$pdflatex = 'pdflatex -interaction=nonstopmode -file-line-error %O %S';

# Disable PDF previewer (view PDF on Windows, not in container)
$pdf_previewer = 'true';
