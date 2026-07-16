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

Map<String, dynamic> _supportedLayer(double cost) => {
  'cost': cost,
  'components': {'service': cost},
  'supported': true,
};
