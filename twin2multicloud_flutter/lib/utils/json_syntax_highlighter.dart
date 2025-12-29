import 'package:flutter/material.dart';

/// Simple JSON syntax highlighter for code editors.
/// Provides colored text spans for keys, strings, numbers, booleans, and punctuation.
class JsonSyntaxHighlighter {
  // VS Code-like dark theme colors
  static const Color keyColor = Color(0xFF9CDCFE);      // Light blue for keys
  static const Color stringColor = Color(0xFFCE9178);   // Orange for strings
  static const Color numberColor = Color(0xFFB5CEA8);   // Light green for numbers
  static const Color boolNullColor = Color(0xFF569CD6);  // Blue for booleans/null
  static const Color punctuationColor = Color(0xFFD4D4D4); // Grey for braces/commas
  static const Color defaultColor = Colors.white;
  
  /// Highlight JSON content and return TextSpans
  static List<TextSpan> highlight(String text) {
    if (text.isEmpty) return [];
    
    final spans = <TextSpan>[];
    final buffer = StringBuffer();
    var currentColor = defaultColor;
    
    bool inString = false;
    bool isKey = true; // After { or , before :
    bool escaped = false;
    
    for (int i = 0; i < text.length; i++) {
      final char = text[i];
      
      if (escaped) {
        buffer.write(char);
        escaped = false;
        continue;
      }
      
      if (char == '\\' && inString) {
        buffer.write(char);
        escaped = true;
        continue;
      }
      
      if (char == '"') {
        if (inString) {
          // End of string
          buffer.write(char);
          spans.add(TextSpan(text: buffer.toString(), style: TextStyle(color: currentColor)));
          buffer.clear();
          inString = false;
        } else {
          // Start of string
          if (buffer.isNotEmpty) {
            spans.add(TextSpan(text: buffer.toString(), style: TextStyle(color: currentColor)));
            buffer.clear();
          }
          inString = true;
          currentColor = isKey ? keyColor : stringColor;
          buffer.write(char);
        }
        continue;
      }
      
      if (inString) {
        buffer.write(char);
        continue;
      }
      
      // Not in string
      if (char == ':') {
        if (buffer.isNotEmpty) {
          spans.add(TextSpan(text: buffer.toString(), style: TextStyle(color: currentColor)));
          buffer.clear();
        }
        spans.add(TextSpan(text: char, style: TextStyle(color: punctuationColor)));
        isKey = false;
        continue;
      }
      
      if (char == ',' || char == '{' || char == '}' || char == '[' || char == ']') {
        if (buffer.isNotEmpty) {
          // Check if buffer contains a keyword
          final word = buffer.toString().trim();
          Color wordColor = currentColor;
          if (word == 'true' || word == 'false' || word == 'null') {
            wordColor = boolNullColor;
          } else if (RegExp(r'^-?\d+\.?\d*$').hasMatch(word)) {
            wordColor = numberColor;
          }
          spans.add(TextSpan(text: buffer.toString(), style: TextStyle(color: wordColor)));
          buffer.clear();
        }
        spans.add(TextSpan(text: char, style: TextStyle(color: punctuationColor)));
        if (char == ',' || char == '{' || char == '[') {
          isKey = (char == '{' || char == ',');
        }
        continue;
      }
      
      // Check for numbers or keywords
      if (RegExp(r'[\d\w.]').hasMatch(char)) {
        buffer.write(char);
        continue;
      }
      
      // Whitespace or other
      buffer.write(char);
    }
    
    // Flush remaining buffer
    if (buffer.isNotEmpty) {
      final word = buffer.toString().trim();
      Color wordColor = defaultColor;
      if (word == 'true' || word == 'false' || word == 'null') {
        wordColor = boolNullColor;
      } else if (RegExp(r'^-?\d+\.?\d*$').hasMatch(word)) {
        wordColor = numberColor;
      }
      spans.add(TextSpan(text: buffer.toString(), style: TextStyle(color: wordColor)));
    }
    
    return spans;
  }
}

/// Text editing controller with JSON syntax highlighting.
class JsonEditingController extends TextEditingController {
  JsonEditingController({String? text}) : super(text: text);
  
  @override
  TextSpan buildTextSpan({
    required BuildContext context,
    TextStyle? style,
    required bool withComposing,
  }) {
    final spans = JsonSyntaxHighlighter.highlight(text);
    
    return TextSpan(
      style: style?.copyWith(fontFamily: 'monospace', fontSize: 12) ?? 
          const TextStyle(fontFamily: 'monospace', fontSize: 12),
      children: spans.isEmpty 
          ? [TextSpan(text: text, style: const TextStyle(color: Colors.white))]
          : spans,
    );
  }
}
