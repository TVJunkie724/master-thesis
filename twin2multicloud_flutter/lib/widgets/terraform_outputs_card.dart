import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:twin2multicloud_flutter/theme/colors.dart';
import 'package:twin2multicloud_flutter/theme/spacing.dart';
import 'package:twin2multicloud_flutter/widgets/terraform_output_labels.dart';

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
  final bool embedded;

  const TerraformOutputsCard({
    super.key,
    required this.outputs,
    this.deployedAt,
    required this.onCopyFeedback,
    this.embedded = false,
  });

  @override
  State<TerraformOutputsCard> createState() => _TerraformOutputsCardState();
}

class _TerraformOutputsCardState extends State<TerraformOutputsCard> {
  // Track which groups are expanded (first group expanded by default)
  final Map<String, bool> _expandedGroups = {};

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

  dynamic _redactOutputValue(String key, dynamic value) {
    if (_isSensitiveKey(key)) return '[REDACTED]';
    if (value is Map) {
      return {
        for (final entry in value.entries)
          entry.key.toString(): _redactOutputValue(
            entry.key.toString(),
            entry.value,
          ),
      };
    }
    if (value is List) {
      return [for (final item in value) _redactOutputValue(key, item)];
    }
    return value;
  }

  Map<String, dynamic> _redactedOutputs() {
    return {
      for (final entry in widget.outputs.entries)
        entry.key: _redactOutputValue(entry.key, entry.value),
    };
  }

  /// Group outputs by provider prefix
  Map<String, Map<String, dynamic>> _groupOutputs() {
    final groups = <String, Map<String, dynamic>>{
      'AWS': <String, dynamic>{},
      'Azure': <String, dynamic>{},
      'GCP': <String, dynamic>{},
      'Cross-Cloud': <String, dynamic>{},
    };

    for (final entry in _redactedOutputs().entries) {
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
    final jsonStr = const JsonEncoder.withIndent(
      ' ',
    ).convert(_redactedOutputs());
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

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Header (not collapsible - always visible)
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final title = Row(
                children: [
                  Icon(
                    Icons.terminal,
                    color: theme.colorScheme.primary,
                    size: AppSpacing.iconMd,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Terraform Outputs',
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (widget.deployedAt != null)
                          Text(
                            _formatRelativeTime(widget.deployedAt),
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              );
              final actions = Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  TextButton.icon(
                    onPressed: _copyAllOutputs,
                    icon: const Icon(Icons.copy_all, size: AppSpacing.iconSm),
                    label: const Text('Copy All'),
                    style: TextButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                ],
              );
              if (constraints.maxWidth <
                  AppSpacing.twinOverviewCompactBreakpoint) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    title,
                    const SizedBox(height: AppSpacing.sm),
                    actions,
                  ],
                );
              }
              return Row(
                children: [
                  Expanded(child: title),
                  const SizedBox(width: AppSpacing.md),
                  actions,
                ],
              );
            },
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
              Semantics(
                button: true,
                expanded: isGroupExpanded,
                label: '$provider outputs, ${outputs.length} items',
                child: InkWell(
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
                          size: AppSpacing.iconMd,
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Icon(
                          _getProviderIcon(provider),
                          size: AppSpacing.iconMd,
                          color: _getProviderColor(provider, theme),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Text(
                          provider,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: _getProviderColor(provider, theme),
                          ),
                        ),
                        const SizedBox(width: AppSpacing.sm),
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
              ),
              // Group content (compact table)
              if (isGroupExpanded) _buildCompactTable(outputs, theme),
            ],
          );
        }),
      ],
    );
    if (widget.embedded) return content;
    return Card(
      margin: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: content,
    );
  }

  Widget _buildCompactTable(Map<String, dynamic> outputs, ThemeData theme) {
    // Sort entries by their position in outputLabels (defines UI category order).
    // Keys not in the map go to the end.
    final labelKeys = outputLabels.keys.toList();
    final sortedEntries = outputs.entries.toList()
      ..sort((a, b) {
        final ai = labelKeys.indexOf(a.key);
        final bi = labelKeys.indexOf(b.key);
        // Unknown keys (-1) go to end
        final aIdx = ai == -1 ? labelKeys.length : ai;
        final bIdx = bi == -1 ? labelKeys.length : bi;
        return aIdx.compareTo(bIdx);
      });

    return Container(
      color: theme.colorScheme.surface,
      child: Column(
        children: sortedEntries.map((entry) {
          final value = entry.value?.toString() ?? '';
          final label = getOutputLabel(entry.key);

          return Semantics(
            button: true,
            label: 'Copy $label output',
            child: InkWell(
              onTap: () => _copyToClipboard(value, keyName: entry.key),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.compactRowPadding,
                ),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: theme.dividerColor.withValues(alpha: 0.3),
                      width: AppSpacing.hairlineWidth,
                    ),
                  ),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Label (human-readable, first column)
                    SizedBox(
                      width: AppSpacing.outputTableColumnWidth,
                      child: Text(
                        label,
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w500,
                          color: theme.colorScheme.onSurface.withValues(
                            alpha: 0.85,
                          ),
                        ),
                      ),
                    ),
                    // Key (monospace, subtle, second column)
                    SizedBox(
                      width: AppSpacing.outputTableColumnWidth,
                      child: Text(
                        entry.key,
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontFamily: 'monospace',
                          color: theme.colorScheme.onSurface.withValues(
                            alpha: 0.4,
                          ),
                        ),
                      ),
                    ),
                    // Values are defensively redacted before display or copy.
                    Expanded(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (_isSensitiveKey(entry.key))
                            Padding(
                              padding: const EdgeInsets.only(
                                right: AppSpacing.xs,
                              ),
                              child: Icon(
                                Icons.lock_outline,
                                size: AppSpacing.iconXs,
                                color: theme.colorScheme.tertiary,
                              ),
                            ),
                          Expanded(
                            child: Text(
                              value,
                              softWrap: true,
                              style: theme.textTheme.bodySmall?.copyWith(
                                fontFamily: 'monospace',
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    // Copy icon (subtle)
                    const SizedBox(width: AppSpacing.xs),
                    Icon(
                      Icons.copy_outlined,
                      size: AppSpacing.iconXs,
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                    ),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
