import 'package:flutter/material.dart';

/// Branded AppBar with multi-cloud gradient accent.
/// 
/// Use this on all screens for consistent branding with the
/// AWS Orange → Azure Blue → GCP Green gradient bar.
class BrandedAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final List<Widget>? actions;
  final Widget? leading;
  final bool showLogo;
  final bool centerTitle;
  
  const BrandedAppBar({
    super.key,
    required this.title,
    this.actions,
    this.leading,
    this.showLogo = true,
    this.centerTitle = false,
  });
  
  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight + 3);
  
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    // Multi-cloud gradient for both themes (orange -> blue -> green)
    final bgStart = isDark ? const Color(0xFF2a1f1a) : const Color(0xFFFFF5E6);  // Orange tint
    final bgMiddle = isDark ? const Color(0xFF1a2540) : const Color(0xFFE6F0FF); // Blue tint
    final bgEnd = isDark ? const Color(0xFF1a2a20) : const Color(0xFFE6F5EC);    // Green tint
    
    return AppBar(
      leading: leading,
      centerTitle: centerTitle,
      title: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showLogo) ...[
            Image.asset(
              'assets/images/logo_transparent_attempt.png',
              height: 32,
            ),
            const SizedBox(width: 10),
          ],
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ],
      ),
      // Theme-aware gradient background
      flexibleSpace: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [bgStart, bgMiddle, bgEnd],
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
          ),
        ),
      ),
      // Multi-cloud gradient accent bar (same for both themes)
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(3),
        child: Container(
          height: 3,
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [
                Color(0xFFFF9900),  // AWS Orange
                Color(0xFF0078D4),  // Azure Blue
                Color(0xFF34A853),  // GCP Green
              ],
            ),
          ),
        ),
      ),
      actions: actions,
    );
  }
}
