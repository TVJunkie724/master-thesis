import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/deployment/user_function_extension_panel.dart';
import 'package:twin2multicloud_flutter/models/user_function_extension.dart';

void main() {
  Widget panel(double width, {ValueChanged<WizardEvent>? onEvent}) {
    return MaterialApp(
      home: Scaffold(
        body: SizedBox(
          width: width,
          height: 900,
          child: SingleChildScrollView(
            child: ExtensionSlotPanel(
              slot: _slot,
              state: _state(),
              onEvent: onEvent ?? (_) {},
            ),
          ),
        ),
      ),
    );
  }

  for (final width in [420.0, 900.0]) {
    testWidgets(
      'renders approved ${width == 420 ? 'compact' : 'wide'} surface',
      (tester) async {
        await tester.pumpWidget(panel(width));

        expect(find.text('Telemetry processor'), findsOneWidget);
        expect(find.text('Slot: processor.telemetry'), findsOneWidget);
        expect(find.textContaining('Python 3.11'), findsWidgets);
        expect(find.textContaining('Lambda'), findsNothing);
        expect(find.textContaining('Terraform'), findsNothing);
        expect(find.textContaining('IAM'), findsNothing);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets('shows field-level validation and collapsed evidence', (
    tester,
  ) async {
    await tester.pumpWidget(panel(700));

    expect(find.text('schema valid'), findsNothing);
    await tester.tap(find.text('Validation details'));
    await tester.pumpAndSettle();
    expect(find.text('schema valid'), findsOneWidget);

    final field = find.byKey(const ValueKey('extension-field-scale_factor'));
    await tester.enterText(field, '2001');
    await tester.pump();
    expect(find.text('Maximum: 1000'), findsOneWidget);
  });

  testWidgets('exposes semantic status and keyboard traversal', (tester) async {
    await tester.pumpWidget(panel(700));

    final semantics = tester.getSemantics(
      find.byKey(const ValueKey('extension-slot-processor.telemetry')),
    );
    expect(semantics.label, contains('Telemetry processor extension slot'));

    final field = find.byKey(const ValueKey('extension-field-scale_factor'));
    await tester.tap(field);
    final before = FocusManager.instance.primaryFocus;
    expect(before, isNotNull);
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    final after = FocusManager.instance.primaryFocus;
    expect(after, isNotNull);
    expect(after, isNot(same(before)));
    expect(after!.canRequestFocus, isTrue);
    expect(tester.takeException(), isNull);
  });
}

WizardState _state() => WizardState(
  twinId: 'twin-1',
  extensionSlots: const [_slot],
  extensionDrafts: {
    _slot.slotId: UserFunctionSourceDraft(
      filename: 'processor.zip',
      bytes: Uint8List.fromList([1, 2, 3]),
      configuration: const {'scale_factor': 1},
    ),
  },
  extensionValidationResults: const {
    'processor.telemetry': UserFunctionValidationResult(
      artifactDigest:
          'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      slotId: 'processor.telemetry',
      slotVersion: '1',
      runtimeId: 'python311',
      sourceFiles: ['process.py', 'requirements.lock'],
      dependencies: [],
      checks: ['schema_valid', 'secret_scan_passed'],
    ),
  },
  extensionPhases: const {
    'processor.telemetry': UserFunctionWorkflowPhase.valid,
  },
);

const _slot = ExtensionSlot(
  slotId: 'processor.telemetry',
  slotVersion: '1',
  displayName: 'Telemetry processor',
  runtimeId: 'python311',
  configurationFields: [
    ExtensionConfigurationField(
      name: 'scale_factor',
      type: 'number',
      title: 'Scale factor',
      required: true,
      minimum: 0,
      maximum: 1000,
    ),
  ],
  resourceLimits: {'timeout_seconds': 30, 'memory_mb': 256},
  permissionCapabilities: ['capability.telemetry.process'],
);
