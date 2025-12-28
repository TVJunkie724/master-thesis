import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../utils/file_reader.dart';

/// A file editor block for Step 3 configuration files.
/// 
/// Layout: Code editor (2/3) | Buttons column (1/3)
/// Similar to CredentialSection but for file editing.
class FileEditorBlock extends StatefulWidget {
  final String filename;
  final String description;
  final String? constraints;
  final String? exampleContent;
  final IconData icon;
  final bool isHighlighted;
  final String? initialContent;
  final Function(String)? onContentChanged;
  final Future<Map<String, dynamic>> Function(String)? onValidate;
  
  const FileEditorBlock({
    super.key,
    required this.filename,
    required this.description,
    this.constraints,
    this.exampleContent,
    this.icon = Icons.description,
    this.isHighlighted = false,
    this.initialContent,
    this.onContentChanged,
    this.onValidate,
  });
  
  @override
  State<FileEditorBlock> createState() => _FileEditorBlockState();
}

class _FileEditorBlockState extends State<FileEditorBlock> {
  late TextEditingController _controller;
  bool _isValidating = false;
  bool? _isValid;
  String? _validationMessage;
  double _editorHeight = 200; // Initial height, resizable
  static const double _minEditorHeight = 120;
  
  static const Color editableColor = Color(0xFFD81B60);
  
  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialContent ?? '');
  }
  
  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
  
  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: _getFileExtensions(),
      );
      
      if (result == null || result.files.isEmpty) return;
      
      final file = result.files.single;
      final content = await readPickedFile(file);
      
      setState(() {
        _controller.text = content;
        _isValid = null; // Reset validation
        _validationMessage = null;
      });
      
      widget.onContentChanged?.call(content);
    } catch (e) {
      setState(() {
        _isValid = false;
        _validationMessage = 'Failed to read file: $e';
      });
    }
  }
  
  List<String> _getFileExtensions() {
    if (widget.filename.endsWith('.json')) return ['json'];
    if (widget.filename.endsWith('.yaml') || widget.filename.endsWith('.yml')) return ['yaml', 'yml'];
    return ['json', 'yaml', 'yml', 'py', 'txt'];
  }
  
  void _showExampleDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Example: ${widget.filename}'),
        content: Container(
          constraints: const BoxConstraints(maxWidth: 600, maxHeight: 400),
          child: SingleChildScrollView(
            child: SelectableText(
              widget.exampleContent ?? '// No example available',
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close'),
          ),
          if (widget.exampleContent != null)
            FilledButton(
              onPressed: () {
                setState(() {
                  _controller.text = widget.exampleContent!;
                });
                widget.onContentChanged?.call(widget.exampleContent!);
                Navigator.pop(ctx);
              },
              child: const Text('Use Example'),
            ),
        ],
      ),
    );
  }
  
  Future<void> _validate() async {
    if (widget.onValidate == null) return;
    
    setState(() {
      _isValidating = true;
      _validationMessage = null;
    });
    
    try {
      final result = await widget.onValidate!(_controller.text);
      setState(() {
        _isValid = result['valid'] == true;
        _validationMessage = result['message']?.toString() ?? 
          (_isValid! ? 'Valid ✓' : 'Validation failed');
      });
    } catch (e) {
      setState(() {
        _isValid = false;
        _validationMessage = 'Validation error: $e';
      });
    } finally {
      setState(() => _isValidating = false);
    }
  }
  
  @override
  Widget build(BuildContext context) {
    final color = widget.isHighlighted ? editableColor : Colors.grey.shade600;
    final bgColor = widget.isHighlighted 
        ? editableColor.withAlpha(12) 
        : Theme.of(context).colorScheme.surfaceContainerHighest;
    final borderColor = widget.isHighlighted 
        ? editableColor.withAlpha(120) 
        : Colors.grey.shade300;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: _isValid == true ? Colors.green.shade600 : 
                 _isValid == false ? Colors.red.shade400 : borderColor,
          width: _isValid != null ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Icon(widget.icon, color: color, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.filename, 
                      style: TextStyle(
                        fontWeight: FontWeight.w600, 
                        fontFamily: 'monospace', 
                        fontSize: 14, 
                        color: color,
                      ),
                    ),
                    Text(
                      widget.description, 
                      style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                    ),
                  ],
                ),
              ),
              if (widget.isHighlighted)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                  decoration: BoxDecoration(
                    color: editableColor,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'EDIT',
                    style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ),
            ],
          ),
          
          const SizedBox(height: 16),
          
          // Main content: Code editor (2/3) | Buttons (1/3)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Code editor with resize handle
              Expanded(
                flex: 2,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Container(
                      height: _editorHeight,
                      decoration: BoxDecoration(
                        color: const Color(0xFF1E1E1E),
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
                      ),
                      child: TextField(
                        controller: _controller,
                        maxLines: null,
                        expands: true,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: Colors.white,
                        ),
                        decoration: InputDecoration(
                          contentPadding: const EdgeInsets.all(12),
                          border: InputBorder.none,
                          hintText: 'Paste or upload ${widget.filename}...',
                          hintStyle: TextStyle(color: Colors.grey.shade500),
                        ),
                        onChanged: widget.onContentChanged,
                      ),
                    ),
                    // Resize handle
                    GestureDetector(
                      onVerticalDragUpdate: (details) {
                        final maxHeight = MediaQuery.of(context).size.height * 0.7;
                        setState(() {
                          _editorHeight = (_editorHeight + details.delta.dy)
                              .clamp(_minEditorHeight, maxHeight);
                        });
                      },
                      child: MouseRegion(
                        cursor: SystemMouseCursors.resizeRow,
                        child: Container(
                          height: 16,
                          decoration: BoxDecoration(
                            color: Colors.grey.shade800,
                            borderRadius: const BorderRadius.vertical(bottom: Radius.circular(8)),
                          ),
                          child: Center(
                            child: Container(
                              width: 40,
                              height: 4,
                              decoration: BoxDecoration(
                                color: Colors.grey.shade500,
                                borderRadius: BorderRadius.circular(2),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              
              const SizedBox(width: 16),
              
              // Buttons column
              Expanded(
                flex: 1,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    FilledButton.tonalIcon(
                      onPressed: _pickFile,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Upload'),
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      onPressed: widget.exampleContent != null ? _showExampleDialog : null,
                      icon: const Icon(Icons.description_outlined, size: 16),
                      label: const Text('Example'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                      ),
                    ),
                    
                    if (widget.constraints != null) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Constraints:',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey.shade500,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        widget.constraints!,
                        style: TextStyle(
                          fontSize: 10,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          
          // Validation section
          if (widget.onValidate != null) ...[
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                FilledButton.icon(
                  onPressed: _isValidating || _controller.text.isEmpty ? null : _validate,
                  icon: _isValidating
                      ? const SizedBox(
                          width: 16, height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.check_circle),
                  label: const Text('Validate'),
                  style: FilledButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 20),
                    backgroundColor: color,
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          ],
          
          // Validation result
          if (_validationMessage != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: _isValid == true 
                    ? Colors.green.withAlpha(38)
                    : Colors.red.withAlpha(38),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: _isValid == true ? Colors.green.shade600 : Colors.red.shade400,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    _isValid == true ? Icons.check_circle : Icons.error,
                    color: _isValid == true ? Colors.green.shade400 : Colors.red.shade400,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _validationMessage!,
                      style: TextStyle(
                        color: _isValid == true ? Colors.green.shade300 : Colors.red.shade300,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
