import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard_state.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';
import 'package:twin2multicloud_flutter/widgets/results/logical_resolved_flow.dart';
import 'package:twin2multicloud_flutter/widgets/results/resolved_architecture_review.dart';

void main() {
  late ResolvedTwinArchitectureRead resolved;
  late ResolvedTwinArchitectureRead singleCloudResolved;
  late ResolvedTwinArchitectureRead supportingResolved;

  setUpAll(() {
    final architecture = Map<String, dynamic>.from(
      jsonDecode(
            File(
              '../contracts/architecture-profiles/v1/fixtures/valid/'
              'mixed-baseline-resolved-architecture.json',
            ).readAsStringSync(),
          )
          as Map,
    );
    resolved = ResolvedTwinArchitectureRead.fromJson({
      'twin_id': 'twin-1',
      'calculation_run_id': architecture['calculation_run_id'],
      'selected_for_deployment_at': '2026-08-03T10:00:00Z',
      'architecture_compatibility_status': 'ready',
      'origin': 'reconstructed_v1',
      'architecture': architecture,
    });
    final singleCloudArchitecture = Map<String, dynamic>.from(
      jsonDecode(jsonEncode(architecture)) as Map,
    );
    final providerRefs =
        singleCloudArchitecture['provider_profile_refs'] as List;
    final azureProfile = Map<String, dynamic>.from(
      providerRefs.cast<Map>().firstWhere(
        (item) => item['provider'] == 'azure',
      ),
    )..remove('provider');
    for (final raw
        in singleCloudArchitecture['component_assignments'] as List) {
      final assignment = raw as Map<String, dynamic>;
      assignment['provider'] = 'azure';
      assignment['provider_implementation_profile_ref'] =
          Map<String, dynamic>.from(azureProfile);
      assignment['service_id'] =
          'azure.fixture.${assignment['logical_component_id']}';
    }
    for (final raw in singleCloudArchitecture['resolved_edges'] as List) {
      final edge = raw as Map<String, dynamic>;
      if (edge['transfer_route_class'] == 'cross_provider') {
        edge['transfer_route_class'] = 'same_provider_same_region';
        edge['mechanism'] = 'provider_native_trigger';
        edge['edge_implementation_id'] = 'edge-implementation.azure.fixture';
      }
    }
    singleCloudResolved = ResolvedTwinArchitectureRead.fromJson({
      'twin_id': 'twin-1',
      'calculation_run_id': singleCloudArchitecture['calculation_run_id'],
      'selected_for_deployment_at': '2026-08-03T10:00:00Z',
      'architecture_compatibility_status': 'ready',
      'origin': 'reconstructed_v1',
      'architecture': singleCloudArchitecture,
    });
    final supportingArchitecture = Map<String, dynamic>.from(
      jsonDecode(jsonEncode(architecture)) as Map,
    );
    for (final raw
        in (supportingArchitecture['component_assignments'] as List).take(3)) {
      (raw as Map<String, dynamic>)['required'] = false;
    }
    supportingResolved = ResolvedTwinArchitectureRead.fromJson({
      'twin_id': 'twin-1',
      'calculation_run_id': supportingArchitecture['calculation_run_id'],
      'selected_for_deployment_at': '2026-08-03T10:00:00Z',
      'architecture_compatibility_status': 'ready',
      'origin': 'reconstructed_v1',
      'architecture': supportingArchitecture,
    });
  });

  testWidgets('renders generic components, tiering and cross-cloud evidence', (
    tester,
  ) async {
    await tester.pumpWidget(_app(resolved));

    expect(find.text('Functionally complete'), findsOneWidget);
    expect(find.text('five-layer-baseline@1'), findsOneWidget);
    expect(find.text('7.6 USD / month'), findsOneWidget);
    expect(find.byType(LogicalResolvedFlow), findsOneWidget);
    expect(find.byTooltip('Zoom in resolved architecture'), findsOneWidget);
    expect(find.text('azure.archive-storage'), findsOneWidget);
    await tester.ensureVisible(find.text('Cost and evidence'));
    await tester.tap(find.text('Cost and evidence'));
    await tester.pumpAndSettle();
    expect(find.text('responsibility.storage'), findsOneWidget);
    expect(find.textContaining('sha256:'), findsWidgets);
    await tester.ensureVisible(find.text('Connections (6)'));
    await tester.tap(find.text('Connections (6)'));
    await tester.pumpAndSettle();
    expect(find.textContaining('cross_provider_adapter'), findsOneWidget);
    expect(find.byIcon(Icons.cloud_sync), findsOneWidget);
  });

  testWidgets('resolved review wraps at the compact graph boundary', (
    tester,
  ) async {
    for (final width in [640.0, 719.0, 720.0, 1200.0]) {
      tester.view.physicalSize = Size(width, 1800);
      tester.view.devicePixelRatio = 1;
      await tester.pumpWidget(_app(resolved, textScale: 2));
      await tester.pump();
      expect(find.byType(LogicalResolvedFlow), findsOneWidget);
      if (width < 720) {
        expect(find.byTooltip('Zoom in resolved architecture'), findsNothing);
        expect(
          find.bySemanticsLabel(
            'component.ingestion connects to component.processing, '
            'edge.ingestion-to-processing, cross-cloud bridge, '
            'cross_provider_adapter, asynchronous, per_entity',
          ),
          findsOneWidget,
        );
      } else {
        expect(find.byTooltip('Zoom in resolved architecture'), findsOneWidget);
      }
      expect(tester.takeException(), isNull, reason: 'overflow at $width');
    }
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });
  });

  testWidgets('single-cloud resolution exposes only provider-local edges', (
    tester,
  ) async {
    await tester.pumpWidget(_app(singleCloudResolved));

    expect(find.text('1 provider'), findsOneWidget);
    await tester.ensureVisible(find.text('Connections (6)'));
    await tester.tap(find.text('Connections (6)'));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.cloud_sync), findsNothing);
    expect(find.byIcon(Icons.arrow_forward), findsNWidgets(6));
    expect(find.textContaining('cross_provider_adapter'), findsNothing);
  });

  testWidgets('supporting resources remain a bounded disclosure', (
    tester,
  ) async {
    await tester.pumpWidget(_app(supportingResolved));

    expect(find.text('Supporting resources (3)'), findsOneWidget);
    await tester.ensureVisible(find.text('Supporting resources (3)'));
    await tester.tap(find.text('Supporting resources (3)'));
    await tester.pumpAndSettle();

    expect(find.text('azure.archive-storage'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('empty and error states stay explicit and retryable', (
    tester,
  ) async {
    var retries = 0;
    await tester.pumpWidget(_app(null, phase: ResolvedArchitecturePhase.idle));
    expect(find.text('No resolved architecture selected'), findsOneWidget);
    expect(find.byType(LogicalResolvedFlow), findsNothing);

    await tester.pumpWidget(
      _app(
        null,
        phase: ResolvedArchitecturePhase.error,
        error: 'Safe read failure',
        onRetry: () => retries++,
      ),
    );
    expect(find.text('Safe read failure'), findsOneWidget);
    await tester.tap(find.widgetWithText(TextButton, 'Retry'));
    expect(retries, 1);
  });
}

Widget _app(
  ResolvedTwinArchitectureRead? resolved, {
  double textScale = 1,
  ResolvedArchitecturePhase phase = ResolvedArchitecturePhase.ready,
  String? error,
  VoidCallback? onRetry,
}) => MaterialApp(
  home: Builder(
    builder: (context) => MediaQuery(
      data: MediaQuery.of(
        context,
      ).copyWith(textScaler: TextScaler.linear(textScale)),
      child: Scaffold(
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ResolvedArchitectureReview(
            phase: phase,
            resolved: resolved,
            error: error,
            onRetry: onRetry,
          ),
        ),
      ),
    ),
  ),
);
