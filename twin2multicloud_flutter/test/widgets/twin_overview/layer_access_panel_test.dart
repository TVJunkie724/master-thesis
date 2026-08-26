import 'dart:ui' show SemanticsAction;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_access.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/layer_access_panel.dart';

void main() {
  testWidgets('renders exactly one ready L4 and L5 card with enabled Open', (
    tester,
  ) async {
    final opened = <DeploymentLayer>[];
    await _pumpHost(
      tester,
      state: _state(),
      onOpen: (surface) => opened.add(surface.layer),
    );

    expect(find.byKey(const Key('layer-access-card-l4')), findsOneWidget);
    expect(find.byKey(const Key('layer-access-card-l5')), findsOneWidget);
    expect(find.text('Azure Digital Twins Explorer'), findsOneWidget);
    expect(find.text('Amazon Managed Grafana'), findsOneWidget);
    expect(_filledButton(tester, 'open-layer-l4').onPressed, isNotNull);
    expect(_filledButton(tester, 'open-layer-l5').onPressed, isNotNull);

    await tester.tap(find.byKey(const Key('open-layer-l4')));
    await tester.ensureVisible(find.byKey(const Key('open-layer-l5')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('open-layer-l5')));
    expect(opened, [DeploymentLayer.l4, DeploymentLayer.l5]);
  });

  testWidgets('GCP L5 exposes one rotation action and invokes it once', (
    tester,
  ) async {
    var rotations = 0;
    await _pumpHost(
      tester,
      state: _state(l5: CloudProvider.gcp),
      onRotate: () => rotations += 1,
    );

    expect(find.byKey(const Key('rotate-gcp-viewer')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('rotate-gcp-viewer')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('rotate-gcp-viewer')));
    expect(rotations, 1);
  });

  testWidgets('failed GET shows isolated error and Retry without cards', (
    tester,
  ) async {
    var retries = 0;
    await _pumpHost(
      tester,
      state: const LayerAccessViewState(
        phase: LayerAccessViewPhase.failed,
        errorMessage: 'Safe access failure.',
      ),
      onRetry: () => retries += 1,
    );

    expect(find.text('Safe access failure.'), findsOneWidget);
    expect(find.text('Retry layer access'), findsOneWidget);
    expect(find.byKey(const Key('layer-access-card-l4')), findsNothing);
    await tester.tap(find.text('Retry layer access'));
    expect(retries, 1);
  });

  testWidgets('blocked L4 disables only L4 and expands exact reason', (
    tester,
  ) async {
    await _pumpHost(tester, state: _state(l4Access: 'blocked'));

    expect(_filledButton(tester, 'open-layer-l4').onPressed, isNull);
    expect(_filledButton(tester, 'open-layer-l5').onPressed, isNotNull);
    expect(
      find.text('Open is blocked because the user access binding is blocked.'),
      findsOneWidget,
    );
    expect(find.text('blocked'), findsOneWidget);
  });

  testWidgets('loading and historical unsupported states fabricate no links', (
    tester,
  ) async {
    await _pumpHost(
      tester,
      state: const LayerAccessViewState(phase: LayerAccessViewPhase.loading),
    );
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.text('Open Twin UI'), findsNothing);

    await _pumpHost(
      tester,
      state: LayerAccessViewState.fromSnapshot(_unsupported()),
    );
    expect(find.textContaining('historical six-layer profile'), findsOneWidget);
    expect(find.text('Open Twin UI'), findsNothing);
    expect(find.text('Retry layer access'), findsNothing);
  });

  testWidgets('unverified browser sign-in remains informative and open', (
    tester,
  ) async {
    await _pumpHost(tester, state: _state());

    expect(_filledButton(tester, 'open-layer-l5').onPressed, isNotNull);
    await tester.ensureVisible(find.text('Access details'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Access details'));
    await tester.pumpAndSettle();
    expect(find.text('Browser sign-in'), findsOneWidget);
    expect(find.text('unverified'), findsOneWidget);
  });

  testWidgets('stacks below 900 and renders siblings from 900', (tester) async {
    await _pumpHost(tester, state: _state(), width: 899);
    final compactL4 = tester.getRect(
      find.byKey(const Key('layer-access-card-l4')),
    );
    final compactL5 = tester.getRect(
      find.byKey(const Key('layer-access-card-l5')),
    );
    expect(compactL5.top, greaterThan(compactL4.bottom));

    await _pumpHost(tester, state: _state(), width: 900);
    final wideL4 = tester.getRect(
      find.byKey(const Key('layer-access-card-l4')),
    );
    final wideL5 = tester.getRect(
      find.byKey(const Key('layer-access-card-l5')),
    );
    expect(wideL4.top, wideL5.top);
    expect(wideL5.left, greaterThan(wideL4.right));
  });

  for (final textScale in [1.5, 2.0]) {
    testWidgets(
      '640 px at ${(textScale * 100).toInt()} percent text scale has no overflow',
      (tester) async {
        await _pumpHost(
          tester,
          state: _state(l5: CloudProvider.gcp),
          width: 640,
          textScale: textScale,
        );
        await tester.pumpAndSettle();

        expect(tester.takeException(), isNull);
        expect(find.byKey(const Key('layer-access-card-l4')), findsOneWidget);
        expect(find.byKey(const Key('rotate-gcp-viewer')), findsOneWidget);
      },
    );
  }

  for (final brightness in Brightness.values) {
    testWidgets('${brightness.name} semantics name layer/provider/status', (
      tester,
    ) async {
      await _pumpHost(tester, state: _state(), brightness: brightness);
      final semantics = tester.getSemantics(
        find.byKey(const Key('layer-access-card-l4')),
      );

      expect(semantics.label, contains('L4 Semantic Twin'));
      expect(semantics.label, contains('Azure'));
      expect(semantics.label, contains('Ready'));
    });
  }

  testWidgets('details show bounded capabilities and limitations only', (
    tester,
  ) async {
    await _pumpHost(tester, state: _state());
    await tester.tap(find.text('Authentication details'));
    await tester.pumpAndSettle();

    expect(find.text('Inspect models and relationships.'), findsOneWidget);
    expect(find.text('Browser sign-in is user verified.'), findsWidgets);
    expect(find.textContaining('secret'), findsNothing);
  });

  testWidgets('keyboard focus follows L4 then L5 action hierarchy', (
    tester,
  ) async {
    await _pumpHost(tester, state: _state(l5: CloudProvider.gcp));

    for (final key in const [
      'open-layer-l4',
      'layer-access-details-l4',
      'open-layer-l5',
      'rotate-gcp-viewer',
      'layer-access-details-l5',
    ]) {
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();
      expect(
        _containsPrimaryFocus(tester, find.byKey(Key(key))),
        isTrue,
        reason: 'Expected focus within $key.',
      );
    }
  });

  testWidgets('details remain independent semantic controls', (tester) async {
    final semantics = tester.ensureSemantics();
    await _pumpHost(tester, state: _state());

    for (final label in const ['Authentication details', 'Access details']) {
      final finder = find.bySemanticsLabel(label);
      expect(finder, findsOneWidget);
      final node = tester.getSemantics(finder);
      expect(node.getSemanticsData().hasAction(SemanticsAction.tap), isTrue);
      expect(node.label, label);
    }
    semantics.dispose();
  });
}

bool _containsPrimaryFocus(WidgetTester tester, Finder finder) {
  final focusContext = FocusManager.instance.primaryFocus?.context;
  if (focusContext is! Element) return false;
  var containsFocus = false;

  void inspect(Element element) {
    if (identical(element, focusContext)) {
      containsFocus = true;
      return;
    }
    element.visitChildElements(inspect);
  }

  inspect(tester.element(finder));
  return containsFocus;
}

FilledButton _filledButton(WidgetTester tester, String key) {
  return tester.widget<FilledButton>(find.byKey(Key(key)));
}

Future<void> _pumpHost(
  WidgetTester tester, {
  required LayerAccessViewState state,
  double width = 1000,
  double textScale = 1,
  Brightness brightness = Brightness.light,
  VoidCallback? onRetry,
  ValueChanged<DeploymentAccessSurface>? onOpen,
  VoidCallback? onRotate,
}) async {
  await tester.binding.setSurfaceSize(Size(width, 1200));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      key: ValueKey((width, textScale, brightness)),
      theme: ThemeData(brightness: brightness),
      home: Scaffold(
        body: MediaQuery(
          data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
          child: SingleChildScrollView(
            child: LayerAccessPanel(
              state: state,
              onRetry: onRetry ?? () {},
              onOpenSurface: onOpen ?? (_) {},
              onRotateViewerCredential: onRotate ?? () {},
            ),
          ),
        ),
      ),
    ),
  );
}

LayerAccessViewState _state({
  CloudProvider l4 = CloudProvider.azure,
  CloudProvider l5 = CloudProvider.aws,
  String l4Access = 'ready',
}) {
  return LayerAccessViewState.fromSnapshot(
    DeploymentAccessSnapshot.fromJson({
      'schema_version': 'deployment-access.v1',
      'twin_id': 'twin-1',
      'deployment_id': 'deployment-1',
      'generated_at': '2026-07-31T12:00:00Z',
      'availability': 'available',
      'reason_code': null,
      'surfaces': [
        _surface(DeploymentLayer.l4, l4, access: l4Access),
        _surface(DeploymentLayer.l5, l5),
      ],
    }),
  );
}

DeploymentAccessSnapshot _unsupported() {
  return DeploymentAccessSnapshot.fromJson({
    'schema_version': 'deployment-access.v1',
    'twin_id': 'twin-1',
    'deployment_id': 'deployment-1',
    'generated_at': '2026-07-31T12:00:00Z',
    'availability': 'unsupported',
    'reason_code': 'unsupported_historical_profile',
    'surfaces': <Object>[],
  });
}

Map<String, dynamic> _surface(
  DeploymentLayer layer,
  CloudProvider provider, {
  String access = 'ready',
}) {
  final config = switch ((layer, provider)) {
    (DeploymentLayer.l4, CloudProvider.aws) => (
      'aws_iot_twinmaker',
      'AWS IoT TwinMaker',
      'aws_identity_center',
      'none',
    ),
    (DeploymentLayer.l4, CloudProvider.azure) => (
      'azure_digital_twins',
      'Azure Digital Twins Explorer',
      'azure_entra',
      'none',
    ),
    (DeploymentLayer.l4, CloudProvider.gcp) => (
      'gcp_twin_explorer',
      'GCP Twin Explorer',
      'gcp_iap',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.aws) => (
      'aws_managed_grafana',
      'Amazon Managed Grafana',
      'aws_identity_center',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.azure) => (
      'azure_managed_grafana',
      'Azure Managed Grafana',
      'azure_entra',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.gcp) => (
      'gcp_grafana_oss',
      'Grafana OSS on GKE',
      'generated_viewer',
      'rotate',
    ),
  };
  return {
    'layer': layer.name,
    'provider': provider.name,
    'service_id': config.$1,
    'display_name': config.$2,
    'url': 'https://${layer.name}-${provider.name}.example.invalid/',
    'auth': {
      'mode': config.$3,
      'principal_label': 'researcher@example.invalid',
      'credential_action': config.$4,
    },
    'readiness': {
      'resource': 'ready',
      'access_binding': access,
      'content': 'ready',
      'data_probe': 'ready',
      'browser_sign_in': 'unverified',
    },
    'capabilities': [
      layer == DeploymentLayer.l4
          ? 'Inspect models and relationships.'
          : 'Inspect raw history and rollups.',
    ],
    'limitations': ['Browser sign-in is user verified.'],
  };
}
