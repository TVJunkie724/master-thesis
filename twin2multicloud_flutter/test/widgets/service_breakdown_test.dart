import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';
import 'package:twin2multicloud_flutter/widgets/results/service_breakdown.dart';

void main() {
  testWidgets('renders unsupported provider layers as unavailable', (
    tester,
  ) async {
    const reason = 'GCP L4 deployment path is not implemented.';
    final result = CalcResult.fromJson({
      'totalCost': 12,
      'awsCosts': _providerCosts(),
      'azureCosts': _providerCosts(),
      'gcpCosts': _providerCosts(
        l4: {
          'cost': 0,
          'components': <String, dynamic>{},
          'supported': false,
          'unsupportedReason': reason,
        },
      ),
      'cheapestPath': <String>[],
      'inputParamsUsed': <String, dynamic>{},
    });

    await tester.binding.setSurfaceSize(const Size(1200, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(child: ServiceBreakdown(result: result)),
        ),
      ),
    );

    final l4Tile = find.widgetWithText(
      ExpansionTile,
      'Layer 4: Twin Management',
    );
    expect(l4Tile, findsOneWidget);
    await tester.tap(l4Tile);
    await tester.pumpAndSettle();

    expect(find.text(reason), findsOneWidget);
    expect(find.text('N/A'), findsOneWidget);
  });

  testWidgets('renders all canonical Azure Digital Twins cost components', (
    tester,
  ) async {
    final result = CalcResult.fromJson({
      'totalCost': 12,
      'awsCosts': _providerCosts(),
      'azureCosts': _providerCosts(
        l4: _supportedLayer(
          4,
          components: {
            'digital_twins_operations': 1,
            'digital_twins_query_units': 2,
            'digital_twins_routed_messages': 0,
            'adt_pusher_function': 1,
          },
        ),
      ),
      'gcpCosts': _providerCosts(),
      'cheapestPath': <String>[],
      'inputParamsUsed': <String, dynamic>{},
    });

    await tester.binding.setSurfaceSize(const Size(1200, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(child: ServiceBreakdown(result: result)),
        ),
      ),
    );

    await tester.tap(
      find.widgetWithText(ExpansionTile, 'Layer 4: Twin Management'),
    );
    await tester.pumpAndSettle();

    expect(find.text('ADT Operations'), findsOneWidget);
    expect(find.text('ADT Query Units'), findsOneWidget);
    expect(find.text('ADT Routed Messages'), findsOneWidget);
    expect(find.text('ADT Telemetry Pusher'), findsOneWidget);
  });
}

Map<String, dynamic> _providerCosts({Map<String, dynamic>? l4}) => {
  'L1': _supportedLayer(1),
  'L2': _supportedLayer(1),
  'L3_hot': _supportedLayer(1),
  'L3_cool': _supportedLayer(1),
  'L3_archive': _supportedLayer(1),
  'L4': l4 ?? _supportedLayer(1),
  'L5': _supportedLayer(1),
};

Map<String, dynamic> _supportedLayer(
  double cost, {
  Map<String, dynamic>? components,
}) => {
  'cost': cost,
  'components': components ?? {'service': cost},
  'supported': true,
};
