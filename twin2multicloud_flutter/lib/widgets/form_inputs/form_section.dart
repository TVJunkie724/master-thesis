// lib/widgets/form_inputs/form_section.dart
// Reusable form section container with title and optional help

import 'package:flutter/material.dart';

/// A styled container for grouping related form inputs.
/// 
/// Features:
/// - Title with optional icon
/// - Collapsible support
/// - Consistent spacing
/// - Optional help button
/// - Card-like styling
class FormSection extends StatelessWidget {
  final String title;
  final IconData? icon;
  final List<Widget> children;
  final VoidCallback? onHelpPressed;
  final bool initiallyExpanded;
  final EdgeInsetsGeometry padding;
  final bool showDivider;
  
  const FormSection({
    super.key,
    required this.title,
    required this.children,
    this.icon,
    this.onHelpPressed,
    this.initiallyExpanded = true,
    this.padding = const EdgeInsets.all(16),
    this.showDivider = true,
  });
  
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(
              children: [
                if (icon != null) ...[
                  Icon(
                    icon,
                    color: theme.colorScheme.primary,
                    size: 22,
                  ),
                  const SizedBox(width: 12),
                ],
                Expanded(
                  child: Text(
                    title,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                if (onHelpPressed != null)
                  IconButton(
                    icon: Icon(
                      Icons.help_outline,
                      color: theme.colorScheme.outline,
                      size: 20,
                    ),
                    onPressed: onHelpPressed,
                    tooltip: 'Help',
                  ),
              ],
            ),
          ),
          
          // Divider
          if (showDivider)
            Divider(
              height: 1,
              color: theme.colorScheme.outlineVariant,
            ),
          
          // Content
          Padding(
            padding: padding,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: _buildChildrenWithSpacing(),
            ),
          ),
        ],
      ),
    );
  }
  
  List<Widget> _buildChildrenWithSpacing() {
    if (children.isEmpty) return [];
    
    final result = <Widget>[];
    for (int i = 0; i < children.length; i++) {
      result.add(children[i]);
      if (i < children.length - 1) {
        result.add(const SizedBox(height: 16));
      }
    }
    return result;
  }
}

/// A collapsible version of FormSection
class CollapsibleFormSection extends StatefulWidget {
  final String title;
  final IconData? icon;
  final List<Widget> children;
  final VoidCallback? onHelpPressed;
  final bool initiallyExpanded;
  final EdgeInsetsGeometry padding;
  
  const CollapsibleFormSection({
    super.key,
    required this.title,
    required this.children,
    this.icon,
    this.onHelpPressed,
    this.initiallyExpanded = true,
    this.padding = const EdgeInsets.all(16),
  });
  
  @override
  State<CollapsibleFormSection> createState() => _CollapsibleFormSectionState();
}

class _CollapsibleFormSectionState extends State<CollapsibleFormSection> {
  late bool _isExpanded;
  
  @override
  void initState() {
    super.initState();
    _isExpanded = widget.initiallyExpanded;
  }
  
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Clickable Header
          InkWell(
            onTap: () => setState(() => _isExpanded = !_isExpanded),
            borderRadius: BorderRadius.vertical(
              top: const Radius.circular(12),
              bottom: _isExpanded ? Radius.zero : const Radius.circular(12),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  if (widget.icon != null) ...[
                    Icon(
                      widget.icon,
                      color: theme.colorScheme.primary,
                      size: 22,
                    ),
                    const SizedBox(width: 12),
                  ],
                  Expanded(
                    child: Text(
                      widget.title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  if (widget.onHelpPressed != null)
                    IconButton(
                      icon: Icon(
                        Icons.help_outline,
                        color: theme.colorScheme.outline,
                        size: 20,
                      ),
                      onPressed: widget.onHelpPressed,
                      tooltip: 'Help',
                    ),
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    color: theme.colorScheme.outline,
                  ),
                ],
              ),
            ),
          ),
          
          // Content (animated)
          AnimatedCrossFade(
            firstChild: Column(
              children: [
                Divider(
                  height: 1,
                  color: theme.colorScheme.outlineVariant,
                ),
                Padding(
                  padding: widget.padding,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: _buildChildrenWithSpacing(),
                  ),
                ),
              ],
            ),
            secondChild: const SizedBox.shrink(),
            crossFadeState: _isExpanded 
                ? CrossFadeState.showFirst 
                : CrossFadeState.showSecond,
            duration: const Duration(milliseconds: 200),
          ),
        ],
      ),
    );
  }
  
  List<Widget> _buildChildrenWithSpacing() {
    if (widget.children.isEmpty) return [];
    
    final result = <Widget>[];
    for (int i = 0; i < widget.children.length; i++) {
      result.add(widget.children[i]);
      if (i < widget.children.length - 1) {
        result.add(const SizedBox(height: 16));
      }
    }
    return result;
  }
}
