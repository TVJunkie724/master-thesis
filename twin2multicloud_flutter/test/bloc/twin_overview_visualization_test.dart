import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_bloc.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_event.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';
import 'package:twin2multicloud_flutter/services/external_auth_launcher.dart';

class _Api extends Mock implements ManagementApi {}

class _Handle extends Mock implements ExternalAuthLaunchHandle {}

class _Bloc extends TwinOverviewBloc {
  _Bloc(ManagementApi api)
    : super(api: api, logStreamClientFactory: () => throw UnimplementedError());
  void seed(String lifecycle, {String id = 'twin'}) => emit(
    TwinOverviewLoaded(
      twinId: id,
      projectName: 'research',
      twinState: lifecycle,
      canDeploy: false,
      canDestroy: true,
      canEdit: false,
      canDelete: false,
    ),
  );
}

Future<void> tick() => Future<void>.delayed(Duration.zero);

void main() {
  late _Api api;
  late _Handle handle;
  late _Bloc bloc;
  setUp(() {
    api = _Api();
    handle = _Handle();
    bloc = _Bloc(api)..seed('deployed');
    when(() => handle.close()).thenAnswer((_) async {});
    when(() => handle.renderHtml(any())).thenAnswer((_) async => true);
  });
  tearDown(() => bloc.close());

  for (final html in [
    '<html>raw + hourly</html>',
    '<html>No measurements</html>',
  ]) {
    test('opens exact authenticated response: $html', () async {
      when(() => api.getVisualization('twin')).thenAnswer((_) async => html);
      bloc.add(TwinOverviewOpenVisualization(handle));
      await tick();
      await tick();
      verify(() => api.getVisualization('twin')).called(1);
      verify(() => handle.renderHtml(html)).called(1);
      verifyNever(() => handle.close());
      expect((bloc.state as TwinOverviewLoaded).infoMessage, isNull);
    });
  }

  test(
    'upstream failure closes popup without exposing error details',
    () async {
      when(
        () => api.getVisualization('twin'),
      ).thenThrow(StateError('private-detail'));
      bloc.add(TwinOverviewOpenVisualization(handle));
      await tick();
      await tick();
      verify(() => handle.close()).called(1);
      expect(
        (bloc.state as TwinOverviewLoaded).errorMessage,
        contains('Could not open L5'),
      );
      expect(
        (bloc.state as TwinOverviewLoaded).errorMessage,
        isNot(contains('private-detail')),
      );
    },
  );

  test('blocked popup is reported', () async {
    when(() => api.getVisualization('twin')).thenAnswer((_) async => '<html/>');
    when(() => handle.renderHtml(any())).thenAnswer((_) async => false);
    bloc.add(TwinOverviewOpenVisualization(handle));
    await tick();
    await tick();
    verify(() => handle.close()).called(1);
    expect(
      (bloc.state as TwinOverviewLoaded).errorMessage,
      contains('Could not open L5'),
    );
  });

  for (final state in ['draft', 'destroyed', 'error']) {
    test('$state never fetches HTML', () async {
      bloc.seed(state);
      bloc.add(TwinOverviewOpenVisualization(handle));
      await tick();
      verifyNever(() => api.getVisualization(any()));
      verify(() => handle.close()).called(1);
    });
  }

  for (final changedTwin in [false, true]) {
    test('stale response is closed (other Twin: $changedTwin)', () async {
      final response = Completer<String>();
      when(
        () => api.getVisualization('twin'),
      ).thenAnswer((_) => response.future);
      bloc.add(TwinOverviewOpenVisualization(handle));
      await tick();
      bloc.seed(
        changedTwin ? 'deployed' : 'destroyed',
        id: changedTwin ? 'other' : 'twin',
      );
      response.complete('<html/>');
      await tick();
      await tick();
      verifyNever(() => handle.renderHtml(any()));
      verify(() => handle.close()).called(1);
    });
  }

  test(
    'duplicate click closes only extra popup and sends one request',
    () async {
      final response = Completer<String>();
      final extra = _Handle();
      when(() => extra.close()).thenAnswer((_) async {});
      when(
        () => api.getVisualization('twin'),
      ).thenAnswer((_) => response.future);
      bloc.add(TwinOverviewOpenVisualization(handle));
      await tick();
      bloc.add(TwinOverviewOpenVisualization(extra));
      await tick();
      verify(() => extra.close()).called(1);
      response.complete('<html/>');
      await tick();
      await tick();
      verify(() => api.getVisualization('twin')).called(1);
      verify(() => handle.renderHtml('<html/>')).called(1);
    },
  );
}
