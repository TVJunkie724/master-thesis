import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/screens/login_screen.dart';

void main() {
  testWidgets('dormant login surface contains no provider integrations', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));

    expect(find.text('Interactive sign-in is disabled'), findsOneWidget);
    expect(find.textContaining('not routed'), findsOneWidget);
    expect(find.byType(FilledButton), findsNothing);
    expect(find.textContaining('Google'), findsNothing);
    expect(find.textContaining('UIBK'), findsNothing);
    expect(find.textContaining('Microsoft'), findsNothing);
    expect(find.textContaining('SAML'), findsNothing);
  });
}
