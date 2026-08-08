import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_operation_dialogs.dart';

void main() {
  testWidgets('destroy confirmation requires acknowledgement before Enter', (
    tester,
  ) async {
    final triggerFocus = FocusNode();
    addTearDown(triggerFocus.dispose);
    bool? result;

    await tester.pumpWidget(
      _DialogHost(
        triggerFocus: triggerFocus,
        dialog: const DestroyTwinConfirmationDialog(),
        onResult: (value) => result = value,
      ),
    );
    expect(triggerFocus.hasFocus, isTrue);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();

    final confirm = find.byKey(const Key('confirm-destroy'));
    expect(tester.widget<FilledButton>(confirm).onPressed, isNull);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    expect(find.text('Destroy Cloud Resources?'), findsOneWidget);

    await tester.tap(find.byKey(const Key('acknowledge-destroy')));
    await tester.pump();
    expect(tester.widget<FilledButton>(confirm).onPressed, isNotNull);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();

    expect(result, isTrue);
    expect(triggerFocus.hasFocus, isTrue);
  });

  testWidgets('simulator confirmation requires acknowledgement before Enter', (
    tester,
  ) async {
    final triggerFocus = FocusNode();
    addTearDown(triggerFocus.dispose);
    bool? result;

    await tester.pumpWidget(
      _DialogHost(
        triggerFocus: triggerFocus,
        dialog: const SimulatorDownloadConfirmationDialog(provider: 'AWS'),
        onResult: (value) => result = value,
      ),
    );
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();

    final confirm = find.byKey(const Key('confirm-simulator-download'));
    expect(tester.widget<FilledButton>(confirm).onPressed, isNull);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    expect(find.text('Download simulator package?'), findsOneWidget);

    await tester.tap(
      find.byKey(const Key('acknowledge-simulator-credentials')),
    );
    await tester.pump();
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();

    expect(result, isTrue);
    expect(triggerFocus.hasFocus, isTrue);
  });

  testWidgets('Escape dismisses a confirmation and restores trigger focus', (
    tester,
  ) async {
    final triggerFocus = FocusNode();
    addTearDown(triggerFocus.dispose);
    bool completed = false;

    await tester.pumpWidget(
      _DialogHost(
        triggerFocus: triggerFocus,
        dialog: const DeployTwinConfirmationDialog(
          resourceName: 'demo-resource',
        ),
        onResult: (_) => completed = true,
      ),
    );
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();

    expect(completed, isTrue);
    expect(find.text('Deploy to Cloud?'), findsNothing);
    expect(triggerFocus.hasFocus, isTrue);
  });

  testWidgets('GCP Viewer rotation confirmation explains invalidation', (
    tester,
  ) async {
    final triggerFocus = FocusNode();
    addTearDown(triggerFocus.dispose);
    bool? result;
    await tester.pumpWidget(
      _DialogHost(
        triggerFocus: triggerFocus,
        dialog: const RotateGcpGrafanaViewerConfirmationDialog(),
        onResult: (value) => result = value,
      ),
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(find.textContaining('becomes invalid'), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirm-gcp-viewer-rotation')));
    await tester.pumpAndSettle();

    expect(result, isTrue);
  });

  testWidgets('Viewer credential starts obscured and copies only explicitly', (
    tester,
  ) async {
    String? clipboardText;
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        clipboardText =
            (call.arguments as Map<Object?, Object?>)['text'] as String?;
      }
      return null;
    });
    addTearDown(
      () => messenger.setMockMethodCallHandler(SystemChannels.platform, null),
    );
    final triggerFocus = FocusNode();
    addTearDown(triggerFocus.dispose);
    await tester.pumpWidget(
      _DialogHost(
        triggerFocus: triggerFocus,
        dialog: const GcpGrafanaCredentialRevealDialog(
          username: 'viewer@example.invalid',
          password: 'one-time-secret',
        ),
        onResult: (_) {},
      ),
    );
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();

    expect(clipboardText, isNull);
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('gcp-viewer-password')))
          .obscureText,
      isTrue,
    );
    expect(find.textContaining('clipboard history'), findsOneWidget);

    await tester.tap(find.byKey(const Key('toggle-gcp-viewer-password')));
    await tester.pump();
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('gcp-viewer-password')))
          .obscureText,
      isFalse,
    );

    await tester.tap(find.byKey(const Key('copy-gcp-viewer-username')));
    await tester.pump();
    expect(clipboardText, 'viewer@example.invalid');
    expect(
      find.text('Username copied by explicit user action.'),
      findsOneWidget,
    );

    await tester.pump(const Duration(seconds: 5));
    await tester.tap(find.byKey(const Key('copy-gcp-viewer-password')));
    await tester.pump();
    expect(clipboardText, 'one-time-secret');
    expect(find.textContaining('one-time-secret copied'), findsNothing);
  });

  testWidgets('Escape discards the one-time credential dialog', (tester) async {
    final triggerFocus = FocusNode();
    addTearDown(triggerFocus.dispose);
    await tester.pumpWidget(
      _DialogHost(
        triggerFocus: triggerFocus,
        dialog: const GcpGrafanaCredentialRevealDialog(
          username: 'viewer@example.invalid',
          password: 'one-time-secret',
        ),
        onResult: (_) {},
      ),
    );
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();

    expect(find.text('GCP Grafana Viewer credential'), findsNothing);
    expect(triggerFocus.hasFocus, isTrue);
  });
}

class _DialogHost extends StatelessWidget {
  final FocusNode triggerFocus;
  final Widget dialog;
  final ValueChanged<bool?> onResult;

  const _DialogHost({
    required this.triggerFocus,
    required this.dialog,
    required this.onResult,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => FilledButton(
            autofocus: true,
            focusNode: triggerFocus,
            onPressed: () async {
              final result = await showDialog<bool>(
                context: context,
                builder: (_) => dialog,
              );
              onResult(result);
            },
            child: const Text('Open confirmation'),
          ),
        ),
      ),
    );
  }
}
