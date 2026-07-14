import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_name_header.dart';

void main() {
  Widget buildWidget({String? cloudResourceName = 'cloud-demo'}) {
    return MaterialApp(
      home: Scaffold(
        body: TwinOverviewNameHeader(
          projectName: 'Demo Twin',
          cloudResourceName: cloudResourceName,
        ),
      ),
    );
  }

  group('TwinOverviewNameHeader', () {
    testWidgets('renders project and cloud resource names', (tester) async {
      await tester.pumpWidget(buildWidget());

      expect(find.text('PROJECT NAME'), findsOneWidget);
      expect(find.text('Demo Twin'), findsOneWidget);
      expect(find.text('CLOUD RESOURCE NAME'), findsOneWidget);
      expect(find.text('cloud-demo'), findsOneWidget);
    });

    testWidgets('renders not configured fallback', (tester) async {
      await tester.pumpWidget(buildWidget(cloudResourceName: null));

      expect(find.text('Not configured'), findsOneWidget);
    });

    testWidgets('stacks names below the Twin Overview compact breakpoint', (
      tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(800, 600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(buildWidget());

      final projectTop = tester.getTopLeft(find.text('PROJECT NAME'));
      final resourceTop = tester.getTopLeft(find.text('CLOUD RESOURCE NAME'));

      expect(resourceTop.dy, greaterThan(projectTop.dy));
      expect((resourceTop.dx - projectTop.dx).abs(), lessThan(1));
      expect(tester.takeException(), isNull);
    });
  });
}
