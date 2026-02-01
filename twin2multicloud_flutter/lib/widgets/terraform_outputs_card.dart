import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:convert';
import 'package:twin2multicloud_flutter/theme/colors.dart';

/// Card that displays terraform outputs from a successful deployment.
///
/// Features:
/// - Grouped by provider (AWS, Azure, GCP, Cross-Cloud)
/// - Collapsible sections with output counts
/// - Compact table layout with monospace values
/// - Copy individual values on tap
/// - Copy All as JSON button
class TerraformOutputsCard extends StatefulWidget {
  final Map<String, dynamic> outputs;
  final DateTime? deployedAt;
  final void Function(String message) onCopyFeedback;

  const TerraformOutputsCard({
    super.key,
    required this.outputs,
    this.deployedAt,
    required this.onCopyFeedback,
  });

  @override
  State<TerraformOutputsCard> createState() => _TerraformOutputsCardState();
}

class _TerraformOutputsCardState extends State<TerraformOutputsCard> {
  // Track which groups are expanded (first group expanded by default)
  final Map<String, bool> _expandedGroups = {};

  // Toggle for showing/hiding sensitive values
  bool _showSensitive = false;

  // Patterns that indicate sensitive output keys
  static const sensitivePatterns = [
    'connection_string',
    'primary_key',
    'secondary_key',
    'access_key',
    'secret',
    'password',
    'token',
    'certificate',
    'private',
  ];

  bool _isSensitiveKey(String key) {
    final keyLower = key.toLowerCase();
    return sensitivePatterns.any((p) => keyLower.contains(p));
  }

  String _maskValue(String value) {
    if (value.length <= 8) return '••••••••';
    return '${value.substring(0, 4)}••••${value.substring(value.length - 4)}';
  }

  /// Group outputs by provider prefix
  Map<String, Map<String, dynamic>> _groupOutputs() {
    final groups = <String, Map<String, dynamic>>{
      'AWS': <String, dynamic>{},
      'Azure': <String, dynamic>{},
      'GCP': <String, dynamic>{},
      'Cross-Cloud': <String, dynamic>{},
    };

    for (final entry in widget.outputs.entries) {
      final key = entry.key;
      if (key.startsWith('aws_')) {
        groups['AWS']![key.substring(4)] = entry.value; // Strip prefix
      } else if (key.startsWith('azure_')) {
        groups['Azure']![key.substring(6)] = entry.value;
      } else if (key.startsWith('gcp_')) {
        groups['GCP']![key.substring(4)] = entry.value;
      } else {
        groups['Cross-Cloud']![key] = entry.value;
      }
    }

    // Remove empty groups
    groups.removeWhere((key, value) => value.isEmpty);

    return groups;
  }

  String _formatRelativeTime(DateTime? time) {
    if (time == null) return '';

    final now = DateTime.now();
    final difference = now.difference(time);

    if (difference.inMinutes < 1) {
      return 'just now';
    } else if (difference.inHours < 1) {
      return '${difference.inMinutes} min ago';
    } else if (difference.inDays < 1) {
      return '${difference.inHours} hours ago';
    } else {
      return '${time.day}/${time.month}/${time.year}';
    }
  }

  void _copyToClipboard(String value, {String? keyName}) async {
    await Clipboard.setData(ClipboardData(text: value));
    widget.onCopyFeedback(
      keyName != null ? 'Copied $keyName' : 'Copied to clipboard',
    );
  }

  void _copyAllOutputs() async {
    final jsonStr = const JsonEncoder.withIndent('  ').convert(widget.outputs);
    await Clipboard.setData(ClipboardData(text: jsonStr));
    widget.onCopyFeedback('Copied all outputs as JSON');
  }

  IconData _getProviderIcon(String provider) {
    switch (provider) {
      case 'AWS':
        return Icons.cloud_outlined;
      case 'Azure':
        return Icons.cloud;
      case 'GCP':
        return Icons.cloud_circle_outlined;
      default:
        return Icons.sync_alt;
    }
  }

  Color _getProviderColor(String provider, ThemeData theme) {
    if (provider == 'Cross-Cloud') {
      return AppColors.glueCode;
    }
    return AppColors.getProviderColor(provider);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final groups = _groupOutputs();

    // Initialize expanded state for first group
    if (_expandedGroups.isEmpty && groups.isNotEmpty) {
      _expandedGroups[groups.keys.first] = true;
    }

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header (not collapsible - always visible)
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Icon(
                  Icons.terminal,
                  color: theme.colorScheme.primary,
                  size: 20,
                ),
                const SizedBox(width: 12),
                Text(
                  'Terraform Outputs',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (widget.deployedAt != null) ...[
                  const SizedBox(width: 8),
                  Text(
                    '• ${_formatRelativeTime(widget.deployedAt)}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                const Spacer(),
                // Show/Hide sensitive toggle
                TextButton.icon(
                  onPressed: () =>
                      setState(() => _showSensitive = !_showSensitive),
                  icon: Icon(
                    _showSensitive ? Icons.visibility_off : Icons.visibility,
                    size: 16,
                  ),
                  label: Text(_showSensitive ? 'Hide' : 'Show'),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                  ),
                ),
                const SizedBox(width: 8),
                // Copy All JSON button
                TextButton.icon(
                  onPressed: _copyAllOutputs,
                  icon: const Icon(Icons.copy_all, size: 16),
                  label: const Text('Copy All'),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                  ),
                ),
              ],
            ),
          ),

          // Content (provider groups - always visible, but individual groups are collapsible)
          const Divider(height: 1),
          // Provider groups
          ...groups.entries.map((groupEntry) {
            final provider = groupEntry.key;
            final outputs = groupEntry.value;
            final isGroupExpanded = _expandedGroups[provider] ?? false;

            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Group header
                InkWell(
                  onTap: () {
                    setState(() {
                      _expandedGroups[provider] = !isGroupExpanded;
                    });
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 10,
                    ),
                    color: theme.colorScheme.surfaceContainerHighest.withValues(
                      alpha: 0.3,
                    ),
                    child: Row(
                      children: [
                        Icon(
                          isGroupExpanded
                              ? Icons.keyboard_arrow_down
                              : Icons.keyboard_arrow_right,
                          size: 20,
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: 8),
                        Icon(
                          _getProviderIcon(provider),
                          size: 18,
                          color: _getProviderColor(provider, theme),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          provider,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: _getProviderColor(provider, theme),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '(${outputs.length})',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                // Group content (compact table)
                if (isGroupExpanded) _buildCompactTable(outputs, theme),
              ],
            );
          }),
        ],
      ),
    );
  }

  Widget _buildCompactTable(Map<String, dynamic> outputs, ThemeData theme) {
    return Container(
      color: theme.colorScheme.surface,
      child: Column(
        children: outputs.entries.map((entry) {
          final value = entry.value?.toString() ?? '';

          return InkWell(
            onTap: () => _copyToClipboard(value, keyName: entry.key),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              decoration: BoxDecoration(
                border: Border(
                  bottom: BorderSide(
                    color: theme.dividerColor.withValues(alpha: 0.3),
                    width: 0.5,
                  ),
                ),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Key (narrower than before)
                  SizedBox(
                    width: 180,
                    child: Text(
                      entry.key,
                      style: theme.textTheme.bodySmall?.copyWith(
                        fontFamily: 'monospace',
                        fontWeight: FontWeight.w500,
                        color: theme.colorScheme.onSurface.withValues(
                          alpha: 0.8,
                        ),
                      ),
                    ),
                  ),
                  // Value (truncated, masked if sensitive)
                  Expanded(
                    child: Builder(
                      builder: (context) {
                        final isSensitive = _isSensitiveKey(entry.key);
                        final displayValue = (isSensitive && !_showSensitive)
                            ? _maskValue(value)
                            : (value.length > 50
                                  ? '${value.substring(0, 50)}...'
                                  : value);
                        return Row(
                          children: [
                            if (isSensitive && !_showSensitive)
                              Padding(
                                padding: const EdgeInsets.only(right: 4),
                                child: Icon(
                                  Icons.lock_outline,
                                  size: 12,
                                  color: theme.colorScheme.tertiary.withValues(
                                    alpha: 0.7,
                                  ),
                                ),
                              ),
                            Expanded(
                              child: Text(
                                displayValue,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  fontFamily: 'monospace',
                                  color: theme.colorScheme.onSurface.withValues(
                                    alpha: isSensitive && !_showSensitive
                                        ? 0.5
                                        : 0.7,
                                  ),
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        );
                      },
                    ),
                  ),
                  // Copy icon (subtle)
                  const SizedBox(width: 4),
                  Icon(
                    Icons.copy_outlined,
                    size: 12,
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
