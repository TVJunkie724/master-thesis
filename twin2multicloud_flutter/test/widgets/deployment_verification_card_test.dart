import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/deployment_verification/deployment_verification.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/services/sse_service.dart';
import 'package:twin2multicloud_flutter/widgets/deployment_verification_card.dart';

class MockApiService extends Mock implements ApiService {}

class MockSseService extends Mock implements SseService {}

void main() {
  setUpAll(() {
    registerFallbackValue(<String, dynamic>{});
  });

  testWidgets('renders verification actions and dispatches infrastructure', (
    tester,
  ) async {
    final api = MockApiService();
    final sse = MockSseService();
    when(() => api.verifyInfrastructure('twin-1')).thenAnswer(
      (_) async => {
        'checks': const [],
        'summary': {
          'pass_count': 0,
          'fail_count': 0,
          'skip_count': 0,
          'total': 0,
          'healthy': true,
        },
      },
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: BlocProvider(
              create: (_) => DeploymentVerificationBloc(
                twinId: 'twin-1',
                api: api,
                sseServiceFactory: () => sse,
              ),
              child: const DeploymentVerificationCard(),
            ),
          ),
        ),
      ),
    );

    expect(find.text('DEPLOYMENT VERIFICATION'), findsOneWidget);
    expect(find.text('CHECK INFRASTRUCTURE'), findsOneWidget);
    expect(find.text('VERIFY DATA FLOW'), findsOneWidget);

    await tester.tap(find.text('CHECK INFRASTRUCTURE'));
    await tester.pumpAndSettle();

    verify(() => api.verifyInfrastructure('twin-1')).called(1);
  });
}
