import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/provider_capability.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

import '../fixtures/provider_capability_fixture.dart';

final class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  late _MockManagementApi api;
  late PlatformProviderCapabilities capabilities;

  setUp(() {
    api = _MockManagementApi();
    capabilities = PlatformProviderCapabilities.fromJson(
      platformProviderCapabilitiesJson(),
    );
  });

  blocTest<WizardBloc, WizardState>(
    'loads the complete provider capability contract',
    setUp: () {
      when(
        () => api.getProviderCapabilities(),
      ).thenAnswer((_) async => capabilities);
    },
    build: () => WizardBloc(api: api),
    act: (bloc) => bloc.add(const WizardProviderCapabilitiesLoadRequested()),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.providerCapabilitiesLoading,
        'loading',
        true,
      ),
      isA<WizardState>()
          .having(
            (state) => state.providerCapabilities,
            'capabilities',
            capabilities,
          )
          .having(
            (state) => state.isLayerSelectable('AWS', 'l4'),
            'AWS L4 selectable',
            true,
          )
          .having(
            (state) => state.isLayerSelectable('GCP', 'l4'),
            'GCP L4 selectable',
            false,
          )
          .having(
            (state) => state.isLayerSelectable('GCP', 'l5'),
            'GCP L5 selectable',
            false,
          ),
    ],
    verify: (_) => verify(() => api.getProviderCapabilities()).called(1),
  );

  blocTest<WizardBloc, WizardState>(
    'fails closed and preserves the last valid contract when reload fails',
    setUp: () {
      when(
        () => api.getProviderCapabilities(),
      ).thenThrow(Exception('credential=must-not-leak'));
    },
    seed: () => WizardState(providerCapabilities: capabilities),
    build: () => WizardBloc(api: api),
    act: (bloc) => bloc.add(const WizardProviderCapabilitiesLoadRequested()),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.providerCapabilitiesLoading,
        'loading',
        true,
      ),
      isA<WizardState>()
          .having(
            (state) => state.providerCapabilities,
            'cached capabilities',
            capabilities,
          )
          .having(
            (state) => state.providerCapabilitiesError,
            'sanitized error',
            allOf(isNotNull, isNot(contains('must-not-leak'))),
          ),
    ],
  );

  test('missing contract never enables a provider layer', () {
    const state = WizardState();

    expect(state.isLayerSelectable('AWS', 'l4'), false);
    expect(state.providerCapability('AWS', 'l4'), isNull);
  });
}
