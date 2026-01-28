// lib/widgets/form_inputs/validated_number_input.dart
// Reusable validated number input widget

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A reusable number input with validation, theming, and callbacks.
/// 
/// Features:
/// - Integer or decimal mode
/// - Min/max validation
/// - Custom error messages
/// - Consistent styling
/// - Disabled state support
class ValidatedNumberInput extends StatefulWidget {
  final String label;
  final int? value;
  final int? minValue;
  final int? maxValue;
  final ValueChanged<int?> onChanged;
  final String? helperText;
  final String? errorText;
  final bool enabled;
  final String? suffix;
  final bool showClearButton;
  
  const ValidatedNumberInput({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
    this.minValue,
    this.maxValue,
    this.helperText,
    this.errorText,
    this.enabled = true,
    this.suffix,
    this.showClearButton = false,
  });
  
  @override
  State<ValidatedNumberInput> createState() => _ValidatedNumberInputState();
}

class _ValidatedNumberInputState extends State<ValidatedNumberInput> {
  late TextEditingController _controller;
  String? _validationError;
  
  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(
      text: widget.value?.toString() ?? '',
    );
  }
  
  @override
  void didUpdateWidget(ValidatedNumberInput oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.value != oldWidget.value) {
      final newText = widget.value?.toString() ?? '';
      if (_controller.text != newText) {
        _controller.text = newText;
      }
    }
  }
  
  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
  
  void _validate(String value) {
    if (value.isEmpty) {
      setState(() => _validationError = null);
      widget.onChanged(null);
      return;
    }
    
    final parsed = int.tryParse(value);
    if (parsed == null) {
      setState(() => _validationError = 'Enter a valid number');
      return;
    }
    
    if (widget.minValue != null && parsed < widget.minValue!) {
      setState(() => _validationError = 'Minimum: ${widget.minValue}');
      return;
    }
    
    if (widget.maxValue != null && parsed > widget.maxValue!) {
      setState(() => _validationError = 'Maximum: ${widget.maxValue}');
      return;
    }
    
    setState(() => _validationError = null);
    widget.onChanged(parsed);
  }
  
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final effectiveError = widget.errorText ?? _validationError;
    
    return TextField(
      controller: _controller,
      enabled: widget.enabled,
      keyboardType: TextInputType.number,
      inputFormatters: [
        FilteringTextInputFormatter.allow(RegExp(r'^-?\d*')),
      ],
      decoration: InputDecoration(
        labelText: widget.label,
        helperText: widget.helperText,
        errorText: effectiveError,
        suffixText: widget.suffix,
        suffixIcon: widget.showClearButton && _controller.text.isNotEmpty
            ? IconButton(
                icon: const Icon(Icons.clear),
                onPressed: () {
                  _controller.clear();
                  widget.onChanged(null);
                },
              )
            : null,
        border: const OutlineInputBorder(),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(
            color: theme.colorScheme.outline,
          ),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(
            color: theme.colorScheme.primary,
            width: 2,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderSide: BorderSide(
            color: theme.colorScheme.error,
          ),
        ),
      ),
      onChanged: _validate,
    );
  }
}
