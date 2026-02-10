// lib/widgets/deployment_verification_card.dart
// Deployment verification UI: infrastructure check + data flow verification

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../config/api_config.dart';
import '../services/api_service.dart';
import '../services/sse_service.dart';
import '../utils/api_error_handler.dart';

/// A card widget for the "Deployment Verification" section.
///
/// Contains:
/// - CHECK INFRASTRUCTURE button with result display
/// - VERIFY DATA FLOW button with payload editor and SSE terminal
class DeploymentVerificationCard extends StatefulWidget {
  final String twinId;
  final ApiService api;
  final String? payloadsJson;
  final String? configEventsJson;

  const DeploymentVerificationCard({
    super.key,
    required this.twinId,
    required this.api,
    this.payloadsJson,
    this.configEventsJson,
  });

  @override
  State<DeploymentVerificationCard> createState() =>
      _DeploymentVerificationCardState();
}

class _DeploymentVerificationCardState
    extends State<DeploymentVerificationCard> {
  // ─── Infrastructure state ───
  bool _isCheckingInfra = false;
  Map<String, dynamic>? _infraResult;
  String? _infraError;

  // ─── Data Flow state ───
  bool _isRunningDataFlow = false;
  String? _dataFlowError;
  final List<_DataFlowLogEntry> _dataFlowLogs = [];
  final Map<int, _PhaseStatus> _phaseStatus = {};
  Map<String, dynamic>? _dataFlowSummary;
  SseService? _sseService;
  StreamSubscription? _sseSubscription;
  final ScrollController _terminalScroll = ScrollController();

  // Payload controller (initialized in initState)
  late final TextEditingController _payloadController;
  String _defaultPayload =
      '{\n  "iotDeviceId": "temperature-sensor-1",\n  "temperature": 42.5,\n  "type": "verification_test"\n}';

  @override
  void initState() {
    super.initState();
    // Pre-fill from payloads_json if available
    if (widget.payloadsJson != null && widget.payloadsJson!.isNotEmpty) {
      try {
        final decoded = json.decode(widget.payloadsJson!);
        if (decoded is List && decoded.isNotEmpty) {
          _defaultPayload = const JsonEncoder.withIndent(
            '  ',
          ).convert(decoded.first);
        } else if (decoded is Map) {
          _defaultPayload = const JsonEncoder.withIndent('  ').convert(decoded);
        }
      } catch (_) {
        // Keep hardcoded default on parse failure
      }
    }
    _payloadController = TextEditingController(text: _defaultPayload);
  }

  @override
  void dispose() {
    _sseSubscription?.cancel();
    _sseService?.cancel();
    _payloadController.dispose();
    _terminalScroll.dispose();
    super.dispose();
  }

  // =====================================================================
  // Infrastructure Check
  // =====================================================================

  Future<void> _runInfraCheck() async {
    setState(() {
      _isCheckingInfra = true;
      _infraError = null;
      _infraResult = null;
    });

    try {
      final result = await widget.api.verifyInfrastructure(widget.twinId);
      if (mounted) {
        setState(() {
          _infraResult = result;
          _isCheckingInfra = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _infraError = ApiErrorHandler.extractMessage(e);
          _isCheckingInfra = false;
        });
      }
    }
  }

  // =====================================================================
  // Data Flow Verification
  // =====================================================================

  Future<void> _runDataFlowVerification() async {
    // Parse payload
    Map<String, dynamic> payload;
    try {
      payload = json.decode(_payloadController.text) as Map<String, dynamic>;
    } catch (e) {
      setState(() {
        _dataFlowError = 'Invalid JSON payload: ${e.toString()}';
      });
      return;
    }

    if (!payload.containsKey('iotDeviceId')) {
      setState(() {
        _dataFlowError = 'Payload must contain "iotDeviceId" field';
      });
      return;
    }

    setState(() {
      _isRunningDataFlow = true;
      _dataFlowError = null;
      _dataFlowLogs.clear();
      _phaseStatus.clear();
      _dataFlowSummary = null;
    });

    try {
      final result = await widget.api.verifyDataFlow(widget.twinId, payload);
      final sseUrl = result['sse_url'] as String?;

      if (sseUrl == null) {
        throw Exception('Backend did not return SSE URL');
      }

      _subscribeToDataFlowSse(sseUrl);
    } catch (e) {
      if (mounted) {
        setState(() {
          _dataFlowError = ApiErrorHandler.extractMessage(e);
          _isRunningDataFlow = false;
        });
      }
    }
  }

  void _subscribeToDataFlowSse(String sseUrl) {
    _sseSubscription?.cancel();
    _sseService?.cancel();

    _sseService = SseService(
      baseUrl: ApiConfig.baseUrl,
      authToken: 'dev-token',
    );

    _sseSubscription = _sseService!
        .streamDeploymentLogs(sseUrl)
        .listen(
          (event) {
            if (event.isHeartbeat) return;

            if (!mounted) return;

            final data = event.data;
            if (data == null) return;

            // The deployer SSE proxy pushes each data line as a raw JSON string.
            // Parse the raw message to determine event type.
            Map<String, dynamic>? parsed;
            try {
              // event.message is the raw data string from SSE
              parsed = json.decode(event.message) as Map<String, dynamic>?;
            } catch (_) {
              // Plain text log
              parsed = null;
            }

            if (parsed != null) {
              _handleParsedEvent(parsed);
            } else {
              // Fallback: treat as plain log
              setState(() {
                _dataFlowLogs.add(
                  _DataFlowLogEntry(timestamp: '', message: event.message),
                );
              });
              _scrollToBottom();
            }

            if (event.isComplete || event.isError) {
              _sseSubscription?.cancel();
              _sseService?.cancel();
              setState(() {
                _isRunningDataFlow = false;
              });
            }
          },
          onError: (e) {
            if (!mounted) return;
            setState(() {
              _dataFlowError =
                  'SSE connection lost: ${ApiErrorHandler.extractMessage(e)}';
              _isRunningDataFlow = false;
            });
          },
        );
  }

  void _handleParsedEvent(Map<String, dynamic> data) {
    // SSE events from the deployer have a structure like:
    // {timestamp, message, status?, detail?, phase?, name?}
    // The proxy pushes all "data:" lines through push_log as raw strings.

    final timestamp = data['timestamp'] as String? ?? '';
    final message = data['message'] as String? ?? '';
    final status = data['status'] as String?;
    final detail = data['detail'] as String?;
    final phase = data['phase'] as int?;
    final name = data['name'] as String?;

    // Phase update
    if (phase != null && name != null && status != null) {
      setState(() {
        _phaseStatus[phase] = _PhaseStatus(
          phase: phase,
          name: name,
          status: status,
          elapsed: (data['elapsed'] as num?)?.toDouble(),
          reason: data['reason'] as String?,
          timeout: data['timeout'] as int?,
        );
      });
    }

    // "done" event — completion summary
    final passCount = data['pass_count'];
    if (passCount != null) {
      setState(() {
        _dataFlowSummary = data;
        _isRunningDataFlow = false;
      });
      _sseSubscription?.cancel();
      _sseService?.cancel();
      return;
    }

    // Log entry
    if (message.isNotEmpty) {
      setState(() {
        _dataFlowLogs.add(
          _DataFlowLogEntry(
            timestamp: timestamp,
            message: message,
            status: status,
            detail: detail,
          ),
        );
      });
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_terminalScroll.hasClients) {
        _terminalScroll.animateTo(
          _terminalScroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // =====================================================================
  // Build
  // =====================================================================

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Section header
            Row(
              children: [
                Icon(Icons.verified_outlined, color: theme.colorScheme.primary),
                const SizedBox(width: 12),
                Text(
                  'DEPLOYMENT VERIFICATION',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: theme.colorScheme.primary,
                    letterSpacing: 1.2,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // ─── Infrastructure Check ───
            _buildInfraSection(context, theme, isDark),

            const SizedBox(height: 24),
            Divider(color: theme.dividerColor.withOpacity(0.5)),
            const SizedBox(height: 16),

            // ─── Data Flow Verification ───
            _buildDataFlowSection(context, theme, isDark),
          ],
        ),
      ),
    );
  }

  // =====================================================================
  // Infrastructure Section (unchanged)
  // =====================================================================

  Widget _buildInfraSection(
    BuildContext context,
    ThemeData theme,
    bool isDark,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Button
        SizedBox(
          width: double.infinity,
          height: 48,
          child: FilledButton.icon(
            onPressed: _isCheckingInfra ? null : _runInfraCheck,
            icon: _isCheckingInfra
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.play_arrow),
            label: Text(
              _isCheckingInfra ? 'Checking...' : 'CHECK INFRASTRUCTURE',
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
            style: FilledButton.styleFrom(
              backgroundColor: theme.colorScheme.primary,
              foregroundColor: theme.colorScheme.onPrimary,
              disabledBackgroundColor: theme.colorScheme.primary.withOpacity(
                0.6,
              ),
              disabledForegroundColor: Colors.white70,
            ),
          ),
        ),
        const SizedBox(height: 8),

        // Description
        Text(
          'Verify all deployed cloud resources (L0–L5): IoT endpoints, functions, '
          'storage, TwinMaker/ADT entities, Grafana. Duration: 5–30s. Cost: none.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),

        // Error display
        if (_infraError != null) ...[
          const SizedBox(height: 12),
          _buildErrorBox(isDark, _infraError!),
        ],

        // Result display
        if (_infraResult != null) ...[
          const SizedBox(height: 12),
          _buildInfraResultCard(theme, isDark),
        ],
      ],
    );
  }

  // =====================================================================
  // Data Flow Section
  // =====================================================================

  Widget _buildDataFlowSection(
    BuildContext context,
    ThemeData theme,
    bool isDark,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Button
        SizedBox(
          width: double.infinity,
          height: 48,
          child: FilledButton.icon(
            onPressed: _isRunningDataFlow ? null : _runDataFlowVerification,
            icon: _isRunningDataFlow
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.send),
            label: Text(
              _isRunningDataFlow ? 'Verifying...' : 'VERIFY DATA FLOW',
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFF4CAF50),
              foregroundColor: Colors.white,
              disabledBackgroundColor: const Color(0xFF4CAF50).withOpacity(0.6),
              disabledForegroundColor: Colors.white70,
            ),
          ),
        ),
        const SizedBox(height: 8),

        // Description
        Text(
          'Send a test IoT message end-to-end: ingestion → processing → hot storage '
          '→ digital twin → event flow. Duration: 1–15 min. Cost: one IoT message. '
          'Prerequisite: infrastructure check should pass first.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 6),

        // Warning about event conditions
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: Colors.orange.withOpacity(0.1),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: Colors.orange.withOpacity(0.3)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(top: 1),
                child: Icon(
                  Icons.warning_amber_rounded,
                  size: 14,
                  color: Colors.orange,
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'If event checking is enabled, payload values must match '
                  'the configured event conditions to trigger full event flow '
                  'verification.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: Colors.orange[800],
                    fontSize: 11,
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // Payload editor
        _buildPayloadEditor(theme, isDark),

        // Error display
        if (_dataFlowError != null) ...[
          const SizedBox(height: 12),
          _buildErrorBox(isDark, _dataFlowError!),
        ],

        // Phase indicators
        if (_phaseStatus.isNotEmpty || _isRunningDataFlow) ...[
          const SizedBox(height: 16),
          _buildPhaseIndicators(theme, isDark),
        ],

        // Terminal log output
        if (_dataFlowLogs.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildTerminalOutput(theme, isDark),
        ],

        // Summary
        if (_dataFlowSummary != null) ...[
          const SizedBox(height: 12),
          _buildDataFlowSummary(theme, isDark),
        ],
      ],
    );
  }

  Widget _buildPayloadEditor(ThemeData theme, bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: isDark
            ? theme.colorScheme.surfaceContainerHighest.withOpacity(0.5)
            : theme.colorScheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: theme.dividerColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
            child: Row(
              children: [
                Icon(
                  Icons.data_object,
                  size: 16,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 6),
                Text(
                  'TEST PAYLOAD',
                  style: theme.textTheme.labelSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.8,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const Spacer(),
                // Reset Payload button
                if (!_isRunningDataFlow)
                  TextButton.icon(
                    onPressed: () {
                      setState(() {
                        _payloadController.text = _defaultPayload;
                      });
                    },
                    icon: const Icon(Icons.restore, size: 14),
                    label: const Text('Reset', style: TextStyle(fontSize: 11)),
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                const SizedBox(width: 4),
                // Show Events button
                if (widget.configEventsJson != null &&
                    widget.configEventsJson!.isNotEmpty)
                  TextButton.icon(
                    onPressed: () => _showEventsDialog(context),
                    icon: const Icon(Icons.event_note, size: 14),
                    label: const Text(
                      'Events ⓘ',
                      style: TextStyle(fontSize: 11),
                    ),
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 6, 12, 12),
            child: TextField(
              controller: _payloadController,
              maxLines: 5,
              minLines: 3,
              enabled: !_isRunningDataFlow,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: theme.colorScheme.onSurface,
              ),
              decoration: InputDecoration(
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(6),
                  borderSide: BorderSide(color: theme.dividerColor),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(6),
                  borderSide: BorderSide(color: theme.dividerColor),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(6),
                  borderSide: BorderSide(
                    color: theme.colorScheme.primary,
                    width: 2,
                  ),
                ),
                filled: true,
                fillColor: isDark ? const Color(0xFF1E1E2E) : Colors.grey[50],
                contentPadding: const EdgeInsets.all(12),
                isDense: true,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showEventsDialog(BuildContext context) {
    final raw = widget.configEventsJson ?? '';
    String formatted;
    try {
      final decoded = json.decode(raw);
      formatted = const JsonEncoder.withIndent('  ').convert(decoded);
    } catch (_) {
      formatted = raw;
    }

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.event_note, size: 20),
            SizedBox(width: 8),
            Text('Configured Event Conditions'),
          ],
        ),
        content: SizedBox(
          width: double.maxFinite,
          child: SingleChildScrollView(
            child: SelectableText(
              formatted,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _buildPhaseIndicators(ThemeData theme, bool isDark) {
    const phases = [
      (1, 'Message Delivery'),
      (2, 'Pipeline → Hot Storage'),
      (3, 'Digital Twin Update'),
      (4, 'Event Flow'),
    ];

    return Row(
      children: [
        for (int i = 0; i < phases.length; i++) ...[
          if (i > 0) _buildPhaseConnector(theme, isDark, phases[i].$1),
          _buildPhaseChip(theme, isDark, phases[i].$1, phases[i].$2),
        ],
      ],
    );
  }

  Widget _buildPhaseChip(ThemeData theme, bool isDark, int phase, String name) {
    final status = _phaseStatus[phase];
    Color bgColor;
    Color textColor;
    IconData? icon;

    if (status == null) {
      // Pending
      bgColor = isDark ? Colors.grey[800]! : Colors.grey[200]!;
      textColor = isDark ? Colors.grey[400]! : Colors.grey[600]!;
    } else {
      switch (status.status) {
        case 'running':
          bgColor = isDark
              ? Colors.blue[900]!.withOpacity(0.5)
              : Colors.blue[50]!;
          textColor = isDark ? Colors.blue[300]! : Colors.blue[800]!;
          icon = null; // will show spinner
          break;
        case 'pass':
          bgColor = isDark
              ? Colors.green[900]!.withOpacity(0.5)
              : Colors.green[50]!;
          textColor = isDark ? Colors.green[300]! : Colors.green[800]!;
          icon = Icons.check;
          break;
        case 'fail':
          bgColor = isDark
              ? Colors.red[900]!.withOpacity(0.5)
              : Colors.red[50]!;
          textColor = isDark ? Colors.red[300]! : Colors.red[800]!;
          icon = Icons.close;
          break;
        case 'skip':
          bgColor = isDark ? Colors.grey[800]! : Colors.grey[100]!;
          textColor = isDark ? Colors.grey[500]! : Colors.grey[500]!;
          icon = Icons.remove;
          break;
        default: // partial
          bgColor = isDark
              ? Colors.orange[900]!.withOpacity(0.5)
              : Colors.orange[50]!;
          textColor = isDark ? Colors.orange[300]! : Colors.orange[800]!;
          icon = Icons.warning_amber;
      }
    }

    return Expanded(
      child: Tooltip(
        message: status?.reason ?? name,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
          decoration: BoxDecoration(
            color: bgColor,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (status?.status == 'running')
                SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    color: textColor,
                  ),
                )
              else if (icon != null)
                Icon(icon, size: 14, color: textColor),
              const SizedBox(width: 3),
              Flexible(
                child: Text(
                  'P$phase',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: textColor,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPhaseConnector(ThemeData theme, bool isDark, int nextPhase) {
    final prevPhase = nextPhase - 1;
    final prevStatus = _phaseStatus[prevPhase]?.status;
    final color = prevStatus == 'pass'
        ? (isDark ? Colors.green[700]! : Colors.green[400]!)
        : (isDark ? Colors.grey[700]! : Colors.grey[300]!);

    return SizedBox(
      width: 12,
      child: Center(child: Container(height: 2, color: color)),
    );
  }

  Widget _buildTerminalOutput(ThemeData theme, bool isDark) {
    return Container(
      height: 200,
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1A1B26) : const Color(0xFF1E1E2E),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isDark ? Colors.grey[800]! : Colors.grey[700]!,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Terminal header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF24253A) : const Color(0xFF2D2D3E),
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(7),
              ),
            ),
            child: Row(
              children: [
                Icon(Icons.terminal, size: 14, color: Colors.grey[400]),
                const SizedBox(width: 6),
                Text(
                  'DATA FLOW LOG',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey[400],
                    letterSpacing: 0.5,
                  ),
                ),
                const Spacer(),
                Text(
                  '${_dataFlowLogs.length} events',
                  style: TextStyle(fontSize: 10, color: Colors.grey[600]),
                ),
              ],
            ),
          ),
          // Log entries
          Expanded(
            child: ListView.builder(
              controller: _terminalScroll,
              padding: const EdgeInsets.all(8),
              itemCount: _dataFlowLogs.length,
              itemBuilder: (context, index) {
                final log = _dataFlowLogs[index];
                return _buildLogLine(log);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLogLine(_DataFlowLogEntry log) {
    Color msgColor;
    switch (log.status) {
      case 'pass':
        msgColor = const Color(0xFF98C379);
        break;
      case 'fail':
        msgColor = const Color(0xFFE06C75);
        break;
      case 'skip':
        msgColor = const Color(0xFF5C6370);
        break;
      default:
        msgColor = const Color(0xFFABB2BF);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: RichText(
        text: TextSpan(
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 11,
            height: 1.4,
          ),
          children: [
            if (log.timestamp.isNotEmpty)
              TextSpan(
                text: '[${log.timestamp}] ',
                style: const TextStyle(color: Color(0xFF5C6370)),
              ),
            TextSpan(
              text: log.message,
              style: TextStyle(color: msgColor),
            ),
            if (log.detail != null && log.detail!.isNotEmpty)
              TextSpan(
                text: ' ${log.detail}',
                style: const TextStyle(
                  color: Color(0xFF5C6370),
                  fontStyle: FontStyle.italic,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildDataFlowSummary(ThemeData theme, bool isDark) {
    final passCount = _dataFlowSummary!['pass_count'] ?? 0;
    final failCount = _dataFlowSummary!['fail_count'] ?? 0;
    final skipCount = _dataFlowSummary!['skip_count'] ?? 0;
    final totalTime = _dataFlowSummary!['total_time'] ?? 0;
    final failedPhase = _dataFlowSummary!['failed_phase'] as String?;
    final hints = (_dataFlowSummary!['hints'] as List?)?.cast<String>() ?? [];
    final allPass = failCount == 0;

    return Container(
      decoration: BoxDecoration(
        color: allPass
            ? (isDark ? Colors.green[900]!.withOpacity(0.3) : Colors.green[50])
            : (isDark ? Colors.red[900]!.withOpacity(0.3) : Colors.red[50]),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: allPass
              ? (isDark ? Colors.green[700]! : Colors.green[300]!)
              : (isDark ? Colors.red[700]! : Colors.red[300]!),
          width: 1.5,
        ),
      ),
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                allPass ? Icons.check_circle : Icons.cancel,
                color: allPass
                    ? (isDark ? Colors.green[400] : Colors.green[700])
                    : (isDark ? Colors.red[400] : Colors.red[700]),
                size: 20,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '$passCount PASSED · $failCount FAILED'
                  '${skipCount > 0 ? ' · $skipCount SKIPPED' : ''}'
                  ' — ${totalTime}s',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: allPass
                        ? (isDark ? Colors.green[300] : Colors.green[800])
                        : (isDark ? Colors.red[300] : Colors.red[800]),
                  ),
                ),
              ),
            ],
          ),
          if (failedPhase != null) ...[
            const SizedBox(height: 6),
            Text(
              'First failure: $failedPhase',
              style: TextStyle(
                fontSize: 12,
                color: isDark ? Colors.red[200] : Colors.red[900],
              ),
            ),
          ],
          if (hints.isNotEmpty) ...[
            const SizedBox(height: 8),
            for (final hint in hints)
              Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Row(
                  children: [
                    Icon(
                      Icons.lightbulb_outline,
                      size: 14,
                      color: isDark ? Colors.orange[300] : Colors.orange[800],
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        hint,
                        style: TextStyle(
                          fontSize: 11,
                          color: isDark
                              ? Colors.orange[200]
                              : Colors.orange[900],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }

  // =====================================================================
  // Shared Widgets
  // =====================================================================

  Widget _buildErrorBox(bool isDark, String error) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark ? Colors.red[900]!.withOpacity(0.3) : Colors.red[50],
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: isDark ? Colors.red[700]! : Colors.red[200]!),
      ),
      child: Row(
        children: [
          Icon(Icons.error, color: Colors.red[isDark ? 300 : 700]),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              error,
              style: TextStyle(color: Colors.red[isDark ? 200 : 900]),
            ),
          ),
        ],
      ),
    );
  }

  // =====================================================================
  // Infrastructure Result Card (unchanged from Phase 1)
  // =====================================================================

  Widget _buildInfraResultCard(ThemeData theme, bool isDark) {
    final checks =
        (_infraResult!['checks'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final summary = _infraResult!['summary'] as Map<String, dynamic>? ?? {};
    final healthy = summary['healthy'] == true;
    final passCount = summary['pass_count'] ?? 0;
    final failCount = summary['fail_count'] ?? 0;
    final skipCount = summary['skip_count'] ?? 0;
    final total = summary['total'] ?? 0;

    // Group checks by layer
    final grouped = <String, List<Map<String, dynamic>>>{};
    for (final check in checks) {
      final layer = check['layer'] as String? ?? 'Unknown';
      grouped.putIfAbsent(layer, () => []).add(check);
    }

    // Order layers
    const layerOrder = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5'];
    final sortedKeys = layerOrder.where(grouped.containsKey).toList();

    return Container(
      decoration: BoxDecoration(
        color: isDark
            ? theme.colorScheme.surfaceContainerHighest.withOpacity(0.5)
            : theme.colorScheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: healthy
              ? (isDark ? Colors.green[700]! : Colors.green[300]!)
              : (isDark ? Colors.red[700]! : Colors.red[300]!),
          width: 1.5,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Summary header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: healthy
                  ? (isDark
                        ? Colors.green[900]!.withOpacity(0.3)
                        : Colors.green[50])
                  : (isDark
                        ? Colors.red[900]!.withOpacity(0.3)
                        : Colors.red[50]),
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(7),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  healthy ? Icons.check_circle : Icons.cancel,
                  color: healthy
                      ? (isDark ? Colors.green[400] : Colors.green[700])
                      : (isDark ? Colors.red[400] : Colors.red[700]),
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '$passCount/$total PASSED'
                    '${skipCount > 0 ? ' ($skipCount skipped)' : ''}'
                    ' ${healthy ? '✓ HEALTHY' : '✗ ISSUES FOUND'}',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: healthy
                          ? (isDark ? Colors.green[300] : Colors.green[800])
                          : (isDark ? Colors.red[300] : Colors.red[800]),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Checks grouped by layer
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final layerKey in sortedKeys) ...[
                  const SizedBox(height: 4),
                  _buildLayerGroup(theme, isDark, layerKey, grouped[layerKey]!),
                ],
              ],
            ),
          ),

          // Failure hint
          if (failCount > 0) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: isDark
                      ? Colors.orange[900]!.withOpacity(0.2)
                      : Colors.orange[50],
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.lightbulb_outline,
                      size: 16,
                      color: isDark ? Colors.orange[300] : Colors.orange[800],
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Check CloudWatch, Azure Log Analytics, or Cloud Logging '
                        'for detailed error information.',
                        style: TextStyle(
                          fontSize: 11,
                          color: isDark
                              ? Colors.orange[200]
                              : Colors.orange[900],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildLayerGroup(
    ThemeData theme,
    bool isDark,
    String layerKey,
    List<Map<String, dynamic>> checks,
  ) {
    const layerLabels = {
      'L0': 'Layer Setup',
      'L1': 'Ingestion',
      'L2': 'Processing',
      'L3': 'Storage',
      'L4': 'Digital Twins',
      'L5': 'Visualization',
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Layer header
        Padding(
          padding: const EdgeInsets.only(bottom: 2),
          child: Text(
            '${layerLabels[layerKey] ?? layerKey} ($layerKey)',
            style: theme.textTheme.labelSmall?.copyWith(
              fontWeight: FontWeight.w600,
              color: theme.colorScheme.onSurfaceVariant,
              letterSpacing: 0.5,
            ),
          ),
        ),
        // Individual checks
        for (final check in checks) _buildCheckRow(theme, isDark, check),
        const SizedBox(height: 4),
      ],
    );
  }

  Widget _buildCheckRow(
    ThemeData theme,
    bool isDark,
    Map<String, dynamic> check,
  ) {
    final status = check['status'] as String? ?? 'fail';
    final name = check['name'] as String? ?? '';
    final provider = check['provider'] as String? ?? '';
    final detail = check['detail'] as String? ?? '';

    IconData icon;
    Color iconColor;

    switch (status) {
      case 'pass':
        icon = Icons.check_circle_outline;
        iconColor = isDark ? Colors.green[400]! : Colors.green[700]!;
        break;
      case 'skip':
        icon = Icons.remove_circle_outline;
        iconColor = isDark ? Colors.grey[500]! : Colors.grey[600]!;
        break;
      default: // fail
        icon = Icons.cancel_outlined;
        iconColor = isDark ? Colors.red[400]! : Colors.red[700]!;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1.5),
      child: Row(
        children: [
          Icon(icon, size: 16, color: iconColor),
          const SizedBox(width: 6),
          // Check name
          Text(
            name,
            style: theme.textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.w500,
            ),
          ),
          // Provider badge
          if (provider.isNotEmpty) ...[
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
              decoration: BoxDecoration(
                color: _getProviderColor(
                  provider,
                ).withOpacity(isDark ? 0.2 : 0.1),
                borderRadius: BorderRadius.circular(3),
              ),
              child: Text(
                provider,
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w600,
                  color: _getProviderColor(provider),
                ),
              ),
            ),
          ],
          const Spacer(),
          // Detail text
          Flexible(
            child: Text(
              status == 'skip' ? '— $detail' : detail,
              style: TextStyle(
                fontSize: 11,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.right,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Color _getProviderColor(String provider) {
    switch (provider.toUpperCase()) {
      case 'AWS':
        return const Color(0xFFFF9900);
      case 'AZURE':
        return const Color(0xFF0078D4);
      case 'GCP':
      case 'GOOGLE':
        return const Color(0xFF34A853);
      default:
        return Colors.grey;
    }
  }
}

// =====================================================================
// Data Models
// =====================================================================

class _DataFlowLogEntry {
  final String timestamp;
  final String message;
  final String? status;
  final String? detail;

  _DataFlowLogEntry({
    required this.timestamp,
    required this.message,
    this.status,
    this.detail,
  });
}

class _PhaseStatus {
  final int phase;
  final String name;
  final String status; // running, pass, fail, skip, partial
  final double? elapsed;
  final String? reason;
  final int? timeout;

  _PhaseStatus({
    required this.phase,
    required this.name,
    required this.status,
    this.elapsed,
    this.reason,
    this.timeout,
  });
}
