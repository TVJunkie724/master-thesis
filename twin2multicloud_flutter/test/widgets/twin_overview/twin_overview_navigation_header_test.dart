import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_navigation_header.dart';

void main() {
  Widget buildWidget({
    bool canEdit = true,
    bool canDelete = true,
    VoidCallback? onEdit,
    VoidCallback? onDelete,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: TwinOverviewNavigationHeader(
          twinState: 'configured',
          canEdit: canEdit,
          canDelete: canDelete,
          onEdit: onEdit ?? () {},
          onDelete: onDelete ?? () {},
        ),
      ),
    );
  }

  testWidgets('exposes lifecycle status and invokes enabled actions', (
    tester,
  ) async {
    var edited = false;
    var deleted = false;
    await tester.pumpWidget(
      buildWidget(onEdit: () => edited = true, onDelete: () => deleted = true),
    );

    expect(find.text('CONFIGURED'), findsOneWidget);
    await tester.tap(find.text('Edit'));
    await tester.tap(find.text('Delete'));

    expect(edited, isTrue);
    expect(deleted, isTrue);
  });

  testWidgets('keeps disabled action reasons discoverable', (tester) async {
    await tester.pumpWidget(buildWidget(canEdit: false, canDelete: false));

    expect(
      find.byTooltip('Cannot edit deployed twin - destroy resources first'),
      findsOneWidget,
    );
    expect(
      find.byTooltip('Destroy cloud resources before deleting'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Edit'))
          .onPressed,
      isNull,
    );
  });
}
