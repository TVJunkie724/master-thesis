import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/wizard_config_requests.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

import '../fixtures/typed_api_fixtures.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';

final class _MockApiService extends Mock implements ApiService {}

void main() {
  setUpAll(() => registerFallbackValue(const TwinConfigUpdateRequest()));

  test('persistence excludes duplicate and competing commands', () async {
    final api = _MockApiService();
    final createTwin = Completer<Twin>();
    when(
      () => api.createTwin('Factory twin'),
    ).thenAnswer((_) => createTwin.future);
    when(
      () => api.updateTwinConfigRequest('twin-1', any()),
    ).thenAnswer((_) async => TypedApiFixtures.twinConfig(twinId: 'twin-1'));
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);

    bloc.add(const WizardTwinNameChanged('Factory twin'));
    await bloc.stream.firstWhere((state) => state.twinName == 'Factory twin');
    bloc.add(const WizardSaveDraft());
    await bloc.stream.firstWhere(
      (state) => state.status == WizardStatus.saving,
    );

    bloc.add(const WizardSaveDraft());
    bloc.add(const WizardFinish());
    bloc.add(const WizardCalculateRequested());
    await Future<void>.delayed(Duration.zero);

    expect(bloc.state.status, WizardStatus.saving);
    expect(bloc.state.errorMessage, isNull);
    verify(() => api.createTwin('Factory twin')).called(1);

    createTwin.complete(
      TypedApiFixtures.twin(id: 'twin-1', name: 'Factory twin'),
    );
    await bloc.stream.firstWhere(
      (state) => state.status == WizardStatus.ready && !state.hasUnsavedChanges,
    );
    expect(bloc.state.successMessage, 'Draft saved!');
    verify(() => api.updateTwinConfigRequest('twin-1', any())).called(1);
    verifyNever(() => api.updateTwin(any(), state: any(named: 'state')));
  });

  test(
    'saving a configured twin reports an actual regression to draft',
    () async {
      final api = _MockApiService();
      when(() => api.updateTwinConfigRequest('twin-1', any())).thenAnswer(
        (_) async =>
            TypedApiFixtures.twinConfig(twinId: 'twin-1', twinState: 'draft'),
      );
      final bloc = WizardBloc(
        api: api,
        initialState: const WizardState(
          mode: WizardMode.edit,
          status: WizardStatus.ready,
          twinId: 'twin-1',
          twinName: 'Factory twin',
          twinState: 'configured',
        ),
      );
      addTearDown(bloc.close);

      bloc.add(const WizardSaveDraft());
      await bloc.stream.firstWhere(
        (state) => state.status == WizardStatus.ready,
      );

      expect(
        bloc.state.successMessage,
        'Saved. Configuration reverted to draft.',
      );
    },
  );
}
