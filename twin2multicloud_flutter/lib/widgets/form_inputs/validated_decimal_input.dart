// lib/widgets/form_inputs/validated_decimal_input.dart
// Reusable validated decimal input widget

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A reusable decimal input with validation, theming, and callbacks.
/// 
/// Features:
/// - Decimal number support
/// - Min/max validation
/// - Precision control
/// - Custom error messages
/// - Consistent styling
/// - Disabled state support
class ValidatedDecimalInput extends StatefulWidget {
  final String label;
  final double? value;
  final double? minValue;
  final double? maxValue;
  final int decimalPlaces;
  final ValueChanged<double?> onChanged;
  final String? helperText;
  final String? errorText;
  final bool enabled;
  final String? suffix;
  final bool showClearButton;
  
  const ValidatedDecimalInput({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
    this.minValue,
    this.maxValue,
    this.decimalPlaces = 2,
    this.helperText,
    this.errorText,
    this.enabled = true,
    this.suffix,
    this.showClearButton = false,
  });
  
  @override
  State<ValidatedDecimalInput> createState() => _ValidatedDecimalInputState();
}

class _ValidatedDecimalInputState extends State<ValidatedDecimalInput> {
  late TextEditingController _controller;
  String? _validationError;
  
  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(
      text: widget.value?.toStringAsFixed(widget.decimalPlaces) ?? '',
    );
  }
  
  @override
  void didUpdateWidget(ValidatedDecimalInput oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.value != oldWidget.value) {
      final newText = widget.value?.toStringAsFixed(widget.decimalPlaces) ?? '';
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
    
    final parsed = double.tryParse(value);
    if (parsed == null) {
      setState(() => _validationError = 'Enter a valid decimal');
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
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      inputFormatters: [
        FilteringTextInputFormatter.allow(RegExp(r'^-?\d*\.?\d*')),
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
