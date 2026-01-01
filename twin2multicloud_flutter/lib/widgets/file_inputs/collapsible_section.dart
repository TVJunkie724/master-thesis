import 'package:flutter/material.dart';

/// A collapsible section with animated expand/collapse.
/// Used to organize Step 3 into logical groups.
/// 
/// Supports a locked state where the section cannot be expanded
/// and displays a hint message explaining what needs to be completed.
class CollapsibleSection extends StatefulWidget {
  final String title;
  final String description;
  final IconData icon;
  final int sectionNumber;
  final bool initiallyExpanded;
  final Widget child;
  /// If set, constrains header width when collapsed (centers the collapsed header)
  final double? collapsedMaxWidth;
  /// If true, the section is locked and cannot be expanded
  final bool isLocked;
  /// Hint text shown when section is locked (e.g., "Complete Section 2 to unlock")
  final String? lockedHint;
  /// Optional info/warning message shown in header (non-blocking, e.g., dependency warning)
  final String? infoHint;
  /// If true, show a check icon indicating the section is complete/valid
  final bool isValid;
  
  const CollapsibleSection({
    super.key,
    required this.title,
    required this.description,
    required this.icon,
    required this.sectionNumber,
    this.initiallyExpanded = true,
    this.collapsedMaxWidth,
    this.isLocked = false,
    this.lockedHint,
    this.infoHint,
    this.isValid = false,
    required this.child,
  });
  
  @override
  State<CollapsibleSection> createState() => _CollapsibleSectionState();
}

class _CollapsibleSectionState extends State<CollapsibleSection> 
    with SingleTickerProviderStateMixin {
  late bool _isExpanded;
  late AnimationController _controller;
  late Animation<double> _iconTurns;
  
  @override
  void initState() {
    super.initState();
    // If locked, start collapsed regardless of initiallyExpanded
    _isExpanded = widget.isLocked ? false : widget.initiallyExpanded;
    _controller = AnimationController(
      duration: const Duration(milliseconds: 200),
      vsync: this,
    );
    _iconTurns = Tween<double>(begin: 0.0, end: 0.5).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    if (_isExpanded) {
      _controller.value = 1.0;
    }
  }
  
  @override
  void didUpdateWidget(CollapsibleSection oldWidget) {
    super.didUpdateWidget(oldWidget);
    // If section becomes locked, collapse it
    if (widget.isLocked && !oldWidget.isLocked && _isExpanded) {
      setState(() {
        _isExpanded = false;
        _controller.reverse();
      });
    }
  }
  
  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
  
  void _toggleExpanded() {
    // Don't allow expanding if locked
    if (widget.isLocked) return;
    
    setState(() {
      _isExpanded = !_isExpanded;
      if (_isExpanded) {
        _controller.forward();
      } else {
        _controller.reverse();
      }
    });
  }
  
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primaryColor = Theme.of(context).colorScheme.primary;
    final isLocked = widget.isLocked;
    
    // Colors for locked state
    final lockedOpacity = isLocked ? 0.5 : 1.0;
    final badgeColor = isLocked 
        ? (isDark ? Colors.grey.shade600 : Colors.grey.shade400)
        : primaryColor;
    final iconColor = isLocked
        ? (isDark ? Colors.grey.shade600 : Colors.grey.shade400)
        : primaryColor;
    final titleColor = isLocked
        ? (isDark ? Colors.grey.shade500 : Colors.grey.shade500)
        : (isDark ? Colors.white : Colors.black87);
    final descColor = isDark ? Colors.grey.shade400 : Colors.grey.shade600;
    
    final section = Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade900 : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.grey.shade700 : Colors.grey.shade300,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(isDark ? 30 : 10),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Opacity(
        opacity: lockedOpacity,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header - clickable to expand/collapse (disabled when locked)
            InkWell(
              onTap: isLocked ? null : _toggleExpanded,
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        // Section number badge
                        Container(
                          width: 28,
                          height: 28,
                          decoration: BoxDecoration(
                            color: badgeColor,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Center(
                            child: Text(
                              '${widget.sectionNumber}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        // Icon - show lock icon when locked
                        Icon(
                          isLocked ? Icons.lock_outline : widget.icon, 
                          color: iconColor, 
                          size: 22,
                        ),
                        const SizedBox(width: 12),
                        // Title and description
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                widget.title,
                                style: TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 16,
                                  color: titleColor,
                                ),
                              ),
                              Text(
                                widget.description,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: descColor,
                                ),
                              ),
                            ],
                          ),
                        ),
                        // Show lock icon, check icon, or expand chevron
                        if (isLocked)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: isDark ? Colors.grey.shade800 : Colors.grey.shade200,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  Icons.lock,
                                  size: 14,
                                  color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  'Locked',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w500,
                                    color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                                  ),
                                ),
                              ],
                            ),
                          )
                        else ...[
                          // Check icon when valid
                          if (widget.isValid)
                            Container(
                              margin: const EdgeInsets.only(right: 12),
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: Colors.green.shade100,
                                borderRadius: BorderRadius.circular(4),
                                border: Border.all(color: Colors.green.shade300),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.check_circle,
                                    size: 14,
                                    color: Colors.green.shade700,
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    'Complete',
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w500,
                                      color: Colors.green.shade700,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          RotationTransition(
                            turns: _iconTurns,
                            child: Icon(
                              Icons.expand_more,
                              color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                            ),
                          ),
                        ],
                      ],
                    ),
                    // Locked hint message
                    if (isLocked && widget.lockedHint != null) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: isDark 
                              ? Colors.orange.shade900.withAlpha(50)
                              : Colors.orange.shade50,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: isDark 
                                ? Colors.orange.shade700.withAlpha(100)
                                : Colors.orange.shade200,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.info_outline,
                              size: 16,
                              color: isDark ? Colors.orange.shade300 : Colors.orange.shade700,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                widget.lockedHint!,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: isDark ? Colors.orange.shade200 : Colors.orange.shade800,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    // Info hint (non-blocking, blue) - shown when not locked but has info
                    if (!isLocked && widget.infoHint != null) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: isDark 
                              ? Colors.blue.shade900.withAlpha(50)
                              : Colors.blue.shade50,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: isDark 
                                ? Colors.blue.shade700.withAlpha(100)
                                : Colors.blue.shade200,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.info_outline,
                              size: 16,
                              color: isDark ? Colors.blue.shade300 : Colors.blue.shade700,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                widget.infoHint!,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: isDark ? Colors.blue.shade200 : Colors.blue.shade800,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            // Content - animated (never shown when locked)
            if (!isLocked)
              AnimatedCrossFade(
                firstChild: const SizedBox.shrink(),
                secondChild: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: widget.child,
                ),
                crossFadeState: _isExpanded 
                    ? CrossFadeState.showSecond 
                    : CrossFadeState.showFirst,
                duration: const Duration(milliseconds: 200),
              ),
          ],
        ),
      ),
    );
    
    // When collapsed/locked and maxWidth set, center and constrain
    if ((!_isExpanded || isLocked) && widget.collapsedMaxWidth != null) {
      return Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: widget.collapsedMaxWidth!),
          child: section,
        ),
      );
    }
    
    return section;
  }
}
