// lib/widgets/form_inputs/validated_switch.dart
// Reusable validated switch widget for boolean inputs

import 'package:flutter/material.dart';

/// A reusable switch widget with label and optional helper text.
/// 
/// Features:
/// - Consistent styling with form inputs
/// - Helper/description text
/// - Disabled state support
/// - Subtitle support
class ValidatedSwitch extends StatelessWidget {
  final String title;
  final String? subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;
  final bool enabled;
  final IconData? leadingIcon;
  final Color? activeColor;
  
  const ValidatedSwitch({
    super.key,
    required this.title,
    required this.value,
    required this.onChanged,
    this.subtitle,
    this.enabled = true,
    this.leadingIcon,
    this.activeColor,
  });
  
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return SwitchListTile(
      title: Row(
        children: [
          if (leadingIcon != null) ...[
            Icon(
              leadingIcon,
              color: enabled 
                  ? theme.colorScheme.primary 
                  : theme.colorScheme.outline,
              size: 20,
            ),
            const SizedBox(width: 12),
          ],
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                color: enabled ? null : theme.colorScheme.outline,
              ),
            ),
          ),
        ],
      ),
      subtitle: subtitle != null
          ? Text(
              subtitle!,
              style: TextStyle(
                color: enabled 
                    ? theme.colorScheme.onSurfaceVariant 
                    : theme.colorScheme.outline,
                fontSize: 12,
              ),
            )
          : null,
      value: value,
      onChanged: enabled ? onChanged : null,
      activeColor: activeColor ?? theme.colorScheme.primary,
      contentPadding: EdgeInsets.zero,
    );
  }
}
