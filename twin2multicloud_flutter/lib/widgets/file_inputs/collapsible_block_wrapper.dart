import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A collapsible wrapper for file blocks in Step 3.
/// 
/// Provides consistent header with:
/// - Title and subtitle
/// - Validation indicator (check/error icon)
/// - EDIT badge for editable blocks
/// - Auto badge for generated blocks
/// - Copy button (optional)
/// - Expand/collapse chevron
/// 
/// Owns outer container styling. Child widgets should NOT render their own
/// outer Container when showHeader: false.
class CollapsibleBlockWrapper extends StatefulWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  
  /// Validation state: true=green check, false=red error, null=no indicator
  final bool? isValid;
  
  /// Show pink "EDIT" badge for editable blocks
  final bool showEditBadge;
  
  /// Show blue auto-generated badge (e.g., "From Step 2")
  final String? autoBadge;
  
  /// Content to copy when copy button pressed
  final String? copyContent;
  
  /// Whether to start expanded (defaults to true)
  /// Set to false for valid blocks in edit mode
  final bool initiallyExpanded;
  
  /// The wrapped content
  final Widget child;
  
  const CollapsibleBlockWrapper({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    this.isValid,
    this.showEditBadge = false,
    this.autoBadge,
    this.copyContent,
    this.initiallyExpanded = true,
    required this.child,
  });
  
  @override
  State<CollapsibleBlockWrapper> createState() => _CollapsibleBlockWrapperState();
}

class _CollapsibleBlockWrapperState extends State<CollapsibleBlockWrapper> {
  late bool _isExpanded;
  
  @override
  void initState() {
    super.initState();
    _isExpanded = widget.initiallyExpanded;
  }
  
  void _toggleExpanded() {
    setState(() => _isExpanded = !_isExpanded);
  }
  
  void _copyToClipboard() {
    if (widget.copyContent == null) return;
    Clipboard.setData(ClipboardData(text: widget.copyContent!));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('${widget.title} copied to clipboard'),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
  
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    // Border color based on validation state
    final borderColor = widget.isValid == true
        ? Colors.green.shade600
        : widget.isValid == false
            ? Colors.red.shade400
            : isDark ? Colors.grey.shade700 : Colors.grey.shade300;
    
    final borderWidth = widget.isValid != null ? 2.0 : 1.0;
    
    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF2D2D2D) : Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor, width: borderWidth),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header - clickable
          Semantics(
            button: true,
            label: '${widget.title}, ${_isExpanded ? "collapse" : "expand"}',
            child: InkWell(
              onTap: _toggleExpanded,
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    // Icon
                    Icon(widget.icon, color: Colors.grey.shade500, size: 22),
                    const SizedBox(width: 12),
                    
                    // Title and subtitle
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.title,
                            style: TextStyle(
                              fontWeight: FontWeight.w600,
                              fontFamily: 'monospace',
                              fontSize: 14,
                              color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                            ),
                          ),
                          Text(
                            widget.subtitle,
                            style: TextStyle(
                              fontSize: 12,
                              color: isDark ? Colors.grey.shade500 : Colors.grey.shade600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    
                    // Auto badge (e.g., "From Step 2")
                    if (widget.autoBadge != null) ...[
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
                              widget.autoBadge!,
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
                    ],
                    
                    // EDIT badge
                    if (widget.showEditBadge) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFFD81B60),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'EDIT',
                          style: TextStyle(
                            color: Colors.white, 
                            fontSize: 10, 
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                    ],
                    
                    // Validation indicator
                    if (widget.isValid == true) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.green.shade100,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: Colors.green.shade300),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.check_circle, size: 14, color: Colors.green.shade700),
                            const SizedBox(width: 4),
                            Text(
                              'Valid',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w500,
                                color: Colors.green.shade700,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                    ] else if (widget.isValid == false) ...[
                      Icon(Icons.error, size: 18, color: Colors.red.shade400),
                      const SizedBox(width: 8),
                    ],
                    
                    // Copy button
                    if (widget.copyContent != null) ...[
                      IconButton(
                        onPressed: _copyToClipboard,
                        icon: Icon(Icons.copy, size: 18, color: Colors.grey.shade500),
                        tooltip: 'Copy to clipboard',
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                      ),
                      const SizedBox(width: 4),
                    ],
                    
                    // Expand/collapse chevron
                    AnimatedRotation(
                      turns: _isExpanded ? 0 : -0.25,
                      duration: const Duration(milliseconds: 200),
                      child: Icon(
                        Icons.expand_more,
                        color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          
          // Content - animated
          ClipRect(
            child: AnimatedSize(
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeInOut,
              child: _isExpanded
                  ? Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      child: widget.child,
                    )
                  : const SizedBox.shrink(),
            ),
          ),
        ],
      ),
    );
  }
}
