// lib/widgets/deployment_terminal.dart
// Dark-themed terminal widget for deployment logs

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Dark-themed terminal widget for displaying deployment/destroy logs
class DeploymentTerminal extends StatefulWidget {
  final List<String> logs;
  final bool isConnected;
  final bool isReconnecting;
  final bool showTimestamps;
  final VoidCallback? onRetryConnection;
  final VoidCallback? onToggleTimestamps;

  const DeploymentTerminal({
    super.key,
    required this.logs,
    this.isConnected = true,
    this.isReconnecting = false,
    this.showTimestamps = false,
    this.onRetryConnection,
    this.onToggleTimestamps,
  });

  @override
  State<DeploymentTerminal> createState() => _DeploymentTerminalState();
}

class _DeploymentTerminalState extends State<DeploymentTerminal> {
  final ScrollController _scrollController = ScrollController();
  bool _autoScroll = true;
  bool _isAtBottom = true;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;

    final maxScroll = _scrollController.position.maxScrollExtent;
    final currentScroll = _scrollController.offset;

    // Consider "at bottom" if within 50 pixels of max
    final atBottom = (maxScroll - currentScroll) < 50;

    if (atBottom != _isAtBottom) {
      setState(() {
        _isAtBottom = atBottom;
        // Re-enable auto-scroll when user scrolls to bottom
        if (atBottom) _autoScroll = true;
      });
    }

    // Disable auto-scroll if user scrolls up
    if (!atBottom && _autoScroll) {
      setState(() => _autoScroll = false);
    }
  }

  @override
  void didUpdateWidget(DeploymentTerminal oldWidget) {
    super.didUpdateWidget(oldWidget);

    // Auto-scroll to bottom when new logs arrive (if enabled)
    if (widget.logs.length != oldWidget.logs.length && _autoScroll) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollController.hasClients) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 100),
            curve: Curves.easeOut,
          );
        }
      });
    }
  }

  void _copyAllLogs() {
    final text = widget.logs.join('\n');
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Logs copied to clipboard'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
      setState(() => _autoScroll = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1E1E1E),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade800),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header bar
          _buildHeader(),
          // Connection status banner
          if (!widget.isConnected || widget.isReconnecting)
            _buildConnectionBanner(),
          // Log content
          Expanded(
            child: Stack(
              children: [
                // Logs
                _buildLogContent(),
                // Scroll to bottom button (when not at bottom)
                if (!_isAtBottom)
                  Positioned(
                    right: 16,
                    bottom: 16,
                    child: FloatingActionButton.small(
                      onPressed: _scrollToBottom,
                      backgroundColor: Colors.blue.shade700,
                      tooltip: 'Scroll to bottom',
                      child: const Icon(Icons.arrow_downward, size: 18),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.grey.shade900,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(8),
          topRight: Radius.circular(8),
        ),
      ),
      child: Row(
        children: [
          // Connection status indicator
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: widget.isReconnecting
                  ? Colors.amber
                  : widget.isConnected
                  ? Colors.green
                  : Colors.red,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            widget.isReconnecting
                ? 'Reconnecting...'
                : widget.isConnected
                ? 'Connected'
                : 'Disconnected',
            style: TextStyle(color: Colors.grey.shade400, fontSize: 12),
          ),
          const Spacer(),
          // Auto-scroll indicator
          if (_autoScroll)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.blue.shade900,
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text(
                'AUTO-SCROLL',
                style: TextStyle(
                  color: Colors.blue,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          const SizedBox(width: 8),
          // Timestamps toggle
          IconButton(
            icon: Icon(
              Icons.schedule,
              size: 18,
              color: widget.showTimestamps
                  ? Colors.blue.shade400
                  : Colors.grey.shade600,
            ),
            onPressed: widget.onToggleTimestamps,
            tooltip: widget.showTimestamps
                ? 'Hide timestamps'
                : 'Show timestamps',
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
          ),
          // Copy all button
          IconButton(
            icon: Icon(Icons.copy, size: 18, color: Colors.grey.shade400),
            onPressed: widget.logs.isEmpty ? null : _copyAllLogs,
            tooltip: 'Copy all logs',
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
          ),
        ],
      ),
    );
  }

  Widget _buildConnectionBanner() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: widget.isReconnecting
          ? Colors.amber.shade900
          : Colors.red.shade900,
      child: Row(
        children: [
          Icon(
            widget.isReconnecting ? Icons.sync : Icons.cloud_off,
            size: 16,
            color: Colors.white,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              widget.isReconnecting
                  ? 'Connection lost. Attempting to reconnect...'
                  : 'Connection lost. Logs may be incomplete.',
              style: const TextStyle(color: Colors.white, fontSize: 12),
            ),
          ),
          if (!widget.isReconnecting && widget.onRetryConnection != null)
            TextButton(
              onPressed: widget.onRetryConnection,
              child: const Text('Retry', style: TextStyle(color: Colors.white)),
            ),
        ],
      ),
    );
  }

  Widget _buildLogContent() {
    if (widget.logs.isEmpty) {
      return Center(
        child: Text(
          'Waiting for logs...',
          style: TextStyle(color: Colors.grey.shade600),
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(12),
      itemCount: widget.logs.length,
      itemBuilder: (context, index) {
        return _buildLogLine(widget.logs[index], index);
      },
    );
  }

  Widget _buildLogLine(String log, int index) {
    // Parse log level from prefix
    Color textColor = Colors.grey.shade300;
    String displayLog = log;

    if (log.startsWith('[ERROR]') || log.startsWith('ERROR:')) {
      textColor = Colors.red.shade400;
    } else if (log.startsWith('[WARN]') || log.startsWith('WARNING:')) {
      textColor = Colors.amber.shade400;
    } else if (log.startsWith('[INFO]') || log.startsWith('>')) {
      textColor = Colors.greenAccent;
    } else if (log.startsWith('[DEBUG]')) {
      textColor = Colors.grey.shade500;
    } else if (log.startsWith('✓') ||
        log.contains('successfully') ||
        log.contains('complete')) {
      textColor = Colors.green.shade400;
    } else if (log.startsWith('✗') ||
        log.contains('failed') ||
        log.contains('error')) {
      textColor = Colors.red.shade400;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: SelectableText(
        displayLog,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 12,
          color: textColor,
          height: 1.4,
        ),
      ),
    );
  }
}
