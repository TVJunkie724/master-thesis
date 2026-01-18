// lib/widgets/credentials/credential_file_uploader.dart
// Extracted credential file upload widget

import 'package:flutter/material.dart';

/// A widget for uploading credential files (JSON).
/// 
/// Features:
/// - File picker integration
/// - Upload status display
/// - Preview of uploaded content
/// - Clear button
class CredentialFileUploader extends StatelessWidget {
  final String? fileName;
  final DateTime? uploadTime;
  final bool isUploading;
  final VoidCallback onUploadPressed;
  final VoidCallback onClearPressed;
  final VoidCallback? onViewSchemaPressed;
  final String buttonText;
  final String? helperText;
  final bool showSchemaButton;
  
  const CredentialFileUploader({
    super.key,
    this.fileName,
    this.uploadTime,
    required this.isUploading,
    required this.onUploadPressed,
    required this.onClearPressed,
    this.onViewSchemaPressed,
    this.buttonText = 'Upload JSON',
    this.helperText,
    this.showSchemaButton = false,
  });
  
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasFile = fileName != null && fileName!.isNotEmpty;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.3),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: hasFile 
              ? Colors.green.withOpacity(0.5) 
              : theme.colorScheme.outlineVariant,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(
                hasFile ? Icons.check_circle : Icons.upload_file,
                color: hasFile ? Colors.green : theme.colorScheme.outline,
                size: 24,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      hasFile ? fileName! : buttonText,
                      style: TextStyle(
                        fontWeight: FontWeight.w500,
                        color: hasFile 
                            ? theme.colorScheme.onSurface 
                            : theme.colorScheme.outline,
                      ),
                    ),
                    if (uploadTime != null)
                      Text(
                        'Uploaded ${_formatTime(uploadTime!)}',
                        style: TextStyle(
                          fontSize: 12,
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    if (helperText != null && !hasFile)
                      Text(
                        helperText!,
                        style: TextStyle(
                          fontSize: 12,
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                  ],
                ),
              ),
              if (hasFile) ...[
                IconButton(
                  icon: const Icon(Icons.clear),
                  color: theme.colorScheme.outline,
                  tooltip: 'Clear',
                  onPressed: onClearPressed,
                ),
              ] else ...[
                if (showSchemaButton && onViewSchemaPressed != null)
                  TextButton.icon(
                    icon: const Icon(Icons.code, size: 18),
                    label: const Text('Schema'),
                    onPressed: onViewSchemaPressed,
                  ),
                const SizedBox(width: 8),
                if (isUploading)
                  SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: theme.colorScheme.primary,
                    ),
                  )
                else
                  FilledButton.icon(
                    icon: const Icon(Icons.upload, size: 18),
                    label: Text(buttonText),
                    onPressed: onUploadPressed,
                  ),
              ],
            ],
          ),
        ],
      ),
    );
  }
  
  String _formatTime(DateTime time) {
    final now = DateTime.now();
    final diff = now.difference(time);
    
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${time.day}/${time.month}/${time.year}';
  }
}
