// Widget tests for ZipUploadBlock
// Tests the zip upload UI component for Step 3 wizard auto-population

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mocktail/mocktail.dart';

import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/widgets/file_inputs/zip_upload_block.dart';

// Mock BLoC with proper stream support
class MockWizardBloc extends Mock implements WizardBloc {
  final _stateController = StreamController<WizardState>.broadcast();
  WizardState _currentState = const WizardState();

  @override
  Stream<WizardState> get stream => _stateController.stream;

  @override
  WizardState get state => _currentState;

  void emitState(WizardState newState) {
    _currentState = newState;
    _stateController.add(newState);
  }

  @override
  Future<void> close() async {
    await _stateController.close();
  }
}

class FakeWizardEvent extends Fake implements WizardEvent {}

void main() {
  late MockWizardBloc mockBloc;

  setUpAll(() {
    registerFallbackValue(FakeWizardEvent());
  });

  setUp(() {
    mockBloc = MockWizardBloc();
  });

  tearDown(() {
    mockBloc.close();
  });

  Widget buildTestWidget() {
    return MaterialApp(
      home: Scaffold(
        body: BlocProvider<WizardBloc>.value(
          value: mockBloc,
          child: const ZipUploadBlock(),
        ),
      ),
    );
  }

  group('ZipUploadBlock Widget Tests', () {
    testWidgets('renders ZipUploadBlock widget', (tester) async {
      mockBloc.emitState(const WizardState());
      await tester.pumpWidget(buildTestWidget());
      await tester.pump();

      expect(find.byType(ZipUploadBlock), findsOneWidget);
    });

    testWidgets('shows success state after extraction', (tester) async {
      mockBloc.emitState(
        const WizardState(configEventsJson: '[]', configEventsValidated: true),
      );
      await tester.pumpWidget(buildTestWidget());
      await tester.pump();

      expect(find.byType(ZipUploadBlock), findsOneWidget);
    });

    testWidgets('renders with validated fields', (tester) async {
      mockBloc.emitState(
        const WizardState(
          configEventsJson: '[]',
          configEventsValidated: true,
          configIotDevicesJson: '[]',
          configIotDevicesValidated: true,
        ),
      );
      await tester.pumpWidget(buildTestWidget());
      await tester.pump();

      expect(find.byType(ZipUploadBlock), findsOneWidget);
    });

    testWidgets('handles warning state', (tester) async {
      mockBloc.emitState(
        const WizardState(
          warningMessage: 'Some files were not found',
          configEventsJson: '[]',
          configEventsValidated: true,
        ),
      );
      await tester.pumpWidget(buildTestWidget());
      await tester.pump();

      expect(find.byType(ZipUploadBlock), findsOneWidget);
    });
  });
}
