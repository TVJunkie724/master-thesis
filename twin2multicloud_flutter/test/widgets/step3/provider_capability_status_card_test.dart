import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/provider_capability.dart';
import 'package:twin2multicloud_flutter/widgets/step3/provider_capability_status_card.dart';

import '../../fixtures/provider_capability_fixture.dart';

void main() {
  PlatformLayerCapability gcpLayer(String layer) =>
      PlatformProviderCapabilities.fromJson(
        platformProviderCapabilitiesJson(),
      ).capability('gcp', layer);

  Widget buildCard({
    PlatformLayerCapability? capability,
    bool loading = false,
    String? error,
    VoidCallback? onRetry,
    ThemeMode themeMode = ThemeMode.light,
  }) => MaterialApp(
    themeMode: themeMode,
    theme: ThemeData.light(),
    darkTheme: ThemeData.dark(),
    home: Scaffold(
      body: SizedBox(
        width: 320,
        child: ProviderCapabilityStatusCard(
          layer: 'l4',
          provider: 'gcp',
          capability: capability,
          isLoading: loading,
          loadError: error,
          onRetry: onRetry ?? () {},
        ),
      ),
    ),
  );

  testWidgets('shows a compact planned unsupported state from the contract', (
    tester,
  ) async {
    await tester.pumpWidget(buildCard(capability: gcpLayer('l4')));

    expect(find.text('GCP L4 unsupported'), findsOneWidget);
    expect(
      find.text('GCP L4 is outside the implemented thesis path.'),
      findsOneWidget,
    );
    expect(find.text(ProviderCapabilityStrings.planned), findsOneWidget);
    expect(find.text(ProviderCapabilityStrings.retry), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('separates loading from unavailable state', (tester) async {
    await tester.pumpWidget(buildCard(loading: true));

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text(ProviderCapabilityStrings.loadingMessage), findsOneWidget);
    expect(
      find.text(ProviderCapabilityStrings.unavailableMessage),
      findsNothing,
    );
  });

  testWidgets('shows a retry action for a failed contract load', (
    tester,
  ) async {
    var retried = false;
    await tester.pumpWidget(
      buildCard(
        error: 'Capability service unavailable',
        onRetry: () {
          retried = true;
        },
        themeMode: ThemeMode.dark,
      ),
    );

    expect(find.text('Capability service unavailable'), findsOneWidget);
    await tester.tap(find.text(ProviderCapabilityStrings.retry));
    expect(retried, true);
    expect(tester.takeException(), isNull);
  });
}
