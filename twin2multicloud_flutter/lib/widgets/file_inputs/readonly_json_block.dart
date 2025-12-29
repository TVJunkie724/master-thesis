import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../utils/json_syntax_highlighter.dart';

/// A read-only JSON display block for auto-generated config files.
/// Shows JSON in a dark code editor style with syntax highlighting, selectable but not editable.
class ReadOnlyJsonBlock extends StatelessWidget {
  final String filename;
  final String description;
  final String jsonContent;
  final IconData icon;
  final String? sourceLabel;  // e.g., "Auto-generated from Step 2"
  
  const ReadOnlyJsonBlock({
    super.key,
    required this.filename,
    required this.description,
    required this.jsonContent,
    this.icon = Icons.code,
    this.sourceLabel,
  });
  
  void _copyToClipboard(BuildContext context) {
    Clipboard.setData(ClipboardData(text: jsonContent));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$filename copied to clipboard'),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
  
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800.withAlpha(100) : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.grey.shade700 : Colors.grey.shade300,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row
          Row(
            children: [
              Icon(icon, color: Colors.grey.shade500, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      filename,
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontFamily: 'monospace',
                        fontSize: 14,
                        color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                      ),
                    ),
                    Text(
                      description,
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? Colors.grey.shade500 : Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
              // Auto-generated badge
              if (sourceLabel != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.blue.shade700.withAlpha(isDark ? 80 : 40),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: Colors.blue.shade400.withAlpha(100)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.auto_mode, size: 12, color: Colors.blue.shade400),
                      const SizedBox(width: 4),
                      Text(
                        sourceLabel!,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w500,
                          color: Colors.blue.shade300,
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(width: 8),
              // Copy button
              IconButton(
                onPressed: () => _copyToClipboard(context),
                icon: Icon(Icons.copy, size: 18, color: Colors.grey.shade500),
                tooltip: 'Copy to clipboard',
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              ),
            ],
          ),
          
          const SizedBox(height: 12),
          
          // JSON content display with syntax highlighting
          Container(
            height: 200,
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFF1E1E1E),
              borderRadius: BorderRadius.circular(8),
            ),
            child: SingleChildScrollView(
              child: SelectableText.rich(
                TextSpan(
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    height: 1.5,
                  ),
                  children: jsonContent.isEmpty 
                      ? [const TextSpan(text: '// No content', style: TextStyle(color: Colors.grey))]
                      : JsonSyntaxHighlighter.highlight(jsonContent),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

