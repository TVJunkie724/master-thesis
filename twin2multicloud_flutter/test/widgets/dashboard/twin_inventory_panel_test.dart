import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';
import 'package:twin2multicloud_flutter/widgets/dashboard/twin_inventory_panel.dart';

void main() {
  testWidgets('sorts by latest update and then lowercase name', (tester) async {
    final sameTime = DateTime.utc(2026, 9, 1);
    await _pumpPanel(
      tester,
      twins: [
        _twin(name: 'Zulu', updatedAt: sameTime),
        _twin(name: 'alpha', updatedAt: sameTime),
        _twin(name: 'Newest', updatedAt: DateTime.utc(2026, 9, 2)),
      ],
    );

    final newestY = tester.getTopLeft(find.text('Newest')).dy;
    final alphaY = tester.getTopLeft(find.text('alpha')).dy;
    final zuluY = tester.getTopLeft(find.text('Zulu')).dy;
    expect(newestY, lessThan(alphaY));
    expect(alphaY, lessThan(zuluY));
  });

  testWidgets('uses one state-specific continuation callback', (tester) async {
    Twin? opened;
    final draft = _twin(name: 'Draft', state: 'draft');
    final deployed = _twin(name: 'Live', state: 'deployed');
    await _pumpPanel(
      tester,
      twins: [draft, deployed],
      onOpen: (twin) => opened = twin,
    );

    expect(find.text('Continue configuration'), findsOneWidget);
    expect(find.text('Open lifecycle'), findsOneWidget);
    await tester.tap(
      find.widgetWithText(OutlinedButton, 'Continue configuration'),
    );
    expect(opened, draft);
    await tester.tap(find.widgetWithText(OutlinedButton, 'Open lifecycle'));
    expect(opened, deployed);
  });

  testWidgets('overflow exposes exactly duplicate export and delete', (
    tester,
  ) async {
    final selected = <String>[];
    await _pumpPanel(
      tester,
      twins: [_twin(name: 'Portable')],
      onDuplicate: (_) => selected.add('duplicate'),
      onExport: (_) => selected.add('export'),
      onDelete: (_) => selected.add('delete'),
    );

    for (final action in ['Duplicate', 'Export', 'Delete']) {
      await tester.tap(find.byTooltip('More actions for Portable'));
      await tester.pumpAndSettle();
      expect(find.text(action), findsOneWidget);
      await tester.tap(find.text(action));
      await tester.pumpAndSettle();
    }
    expect(selected, ['duplicate', 'export', 'delete']);
    expect(find.text('Open'), findsNothing);
    expect(find.text('Edit'), findsNothing);
  });

  testWidgets('empty state does not duplicate the primary action', (
    tester,
  ) async {
    await _pumpPanel(tester, twins: const []);

    expect(find.text('No Twin experiments yet'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'New Twin'), findsOneWidget);
    expect(find.text('New Twin'), findsOneWidget);
    expect(find.byType(Card), findsNothing);
  });

  testWidgets('busy state disables mutations and exposes progress', (
    tester,
  ) async {
    await _pumpPanel(tester, twins: [_twin(name: 'Busy')], isBusy: true);

    final newButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'New Twin'),
    );
    final continuation = tester.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, 'Continue configuration'),
    );
    expect(newButton.onPressed, isNull);
    expect(continuation.onPressed, isNull);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    await tester.tap(find.byIcon(Icons.more_vert));
    await tester.pump();
    expect(find.text('Duplicate'), findsNothing);
  });

  testWidgets('all supported non-draft states open lifecycle', (tester) async {
    final twins = <Twin>[
      _twin(name: 'Draft', state: 'draft'),
      for (final state in Twin.supportedStates.where(
        (state) => state != 'draft',
      ))
        _twin(name: state, state: state),
    ];
    await _pumpPanel(tester, twins: twins, size: const Size(1200, 1600));

    expect(find.text('Continue configuration'), findsOneWidget);
    expect(
      find.text('Open lifecycle'),
      findsNWidgets(Twin.supportedStates.length - 1),
    );
  });

  testWidgets('wide boundary renders without overflow', (tester) async {
    await _pumpPanel(
      tester,
      twins: [_twin(name: 'Boundary Twin')],
      size: const Size(800, 900),
    );

    expect(find.text('Boundary Twin'), findsOneWidget);
    final nameY = tester.getCenter(find.text('Boundary Twin')).dy;
    final stateY = tester.getCenter(find.text('DRAFT')).dy;
    final continuationY = tester
        .getCenter(find.text('Continue configuration'))
        .dy;
    expect(stateY, closeTo(nameY, 8));
    expect(continuationY, closeTo(nameY, 8));
    expect(tester.takeException(), isNull);
  });

  testWidgets('compact 200 percent text keeps every action reachable', (
    tester,
  ) async {
    await _pumpPanel(
      tester,
      twins: [_twin(name: 'Compact Twin')],
      size: const Size(640, 1200),
      textScale: 2,
    );

    expect(find.text('Continue configuration'), findsOneWidget);
    expect(find.byTooltip('Refresh experiments'), findsOneWidget);
    expect(find.byTooltip('More actions for Compact Twin'), findsOneWidget);
    final orders = tester
        .widgetList<FocusTraversalOrder>(find.byType(FocusTraversalOrder))
        .map((widget) => (widget.order as NumericFocusOrder).order)
        .toList();
    expect(orders, containsAllInOrder([2, 1]));
    expect(tester.takeException(), isNull);
  });
}

Future<void> _pumpPanel(
  WidgetTester tester, {
  required List<Twin> twins,
  bool isBusy = false,
  Size size = const Size(1200, 900),
  double textScale = 1,
  ValueChanged<Twin>? onOpen,
  ValueChanged<Twin>? onDuplicate,
  ValueChanged<Twin>? onExport,
  ValueChanged<Twin>? onDelete,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(
          context,
        ).copyWith(textScaler: TextScaler.linear(textScale)),
        child: child!,
      ),
      home: Scaffold(
        body: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: TwinInventoryPanel(
              twins: twins,
              isBusy: isBusy,
              onCreate: () {},
              onImport: () {},
              onRefresh: () {},
              onOpen: onOpen ?? (_) {},
              onDuplicate: onDuplicate ?? (_) {},
              onExport: onExport ?? (_) {},
              onDelete: onDelete ?? (_) {},
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pump();
}

Twin _twin({
  required String name,
  String state = 'draft',
  DateTime? updatedAt,
}) => Twin(
  id: name,
  name: name,
  state: state,
  createdAt: DateTime.utc(2026, 8, 1),
  updatedAt: updatedAt ?? DateTime.utc(2026, 9, 1),
);
