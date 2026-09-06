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
