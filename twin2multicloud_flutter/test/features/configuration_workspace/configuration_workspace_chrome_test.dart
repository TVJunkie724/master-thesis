import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_alert_stack.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_navigation_bar.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_workspace_app_bar.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_workspace_dialogs.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_workspace_header.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/configuration_workspace_scaffold.dart';

void main() {
  testWidgets('workspace scaffold keeps loading isolated from ready chrome', (
    tester,
  ) async {
    await tester.pumpWidget(
      _app(
        ConfigurationWorkspaceScaffold(
          appBar: _appBar(),
          isLoading: true,
          header: const Text('Header'),
          alerts: const Text('Alert'),
          workspace: const Text('Workspace'),
          navigation: const Text('Navigation'),
        ),
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Header'), findsNothing);
    expect(find.text('Workspace'), findsNothing);
  });

  testWidgets('header and alert stack expose exact callback boundaries', (
    tester,
  ) async {
    var closed = false;
    var dismissedError = false;
    var dismissedNotification = false;
    await tester.pumpWidget(
      _app(
        Column(
          children: [
            ConfigurationWorkspaceHeader(
              isCreateMode: false,
              phaseLabel: 'Prepare deployment',
              taskLabel: 'Twin assets',
              onClose: () => closed = true,
            ),
            ConfigurationAlertStack(
              errorMessage: 'Validation failed',
              successMessage: 'Saved',
              warningMessage: 'Review required',
              onDismissError: () => dismissedError = true,
              onDismissNotification: () => dismissedNotification = true,
            ),
          ],
        ),
      ),
    );

    expect(find.text('Edit Digital Twin'), findsOneWidget);
    expect(find.text('Prepare deployment · Twin assets'), findsOneWidget);
    expect(find.text('Validation failed'), findsOneWidget);
    expect(find.text('Saved'), findsNothing);
    expect(find.text('Review required'), findsNothing);

    await tester.tap(find.byTooltip('Close'));
    await tester.tap(find.byTooltip('Dismiss'));
    expect(closed, isTrue);
    expect(dismissedError, isTrue);
    expect(dismissedNotification, isFalse);
  });

  testWidgets('compact navigation preserves every command without overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(640, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final invoked = <String>[];

    await tester.pumpWidget(
      _app(
        Scaffold(
          body: Align(
            alignment: Alignment.bottomCenter,
            child: ConfigurationNavigationBar(
              backLabel: 'Back',
              onBack: () => invoked.add('back'),
              showCalculation: true,
              isCalculating: false,
              calculationDisabledReason: '',
              onCalculate: () => invoked.add('calculate'),
              isSaving: false,
              hasUnsavedChanges: true,
              saveDisabledReason: '',
              onSave: () => invoked.add('save'),
              showFinish: true,
              forwardDisabledReason: '',
              onForward: () => invoked.add('finish'),
            ),
          ),
        ),
      ),
    );

    expect(find.text('CALCULATE'), findsOneWidget);
    expect(find.text('Finish Configuration'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.widgetWithText(FilledButton, 'CALCULATE'));
    await tester.tap(find.widgetWithText(OutlinedButton, 'Back'));
    await tester.tap(find.widgetWithText(OutlinedButton, 'Save'));
    await tester.tap(find.widgetWithText(FilledButton, 'Finish Configuration'));
    expect(invoked, ['calculate', 'back', 'save', 'finish']);
  });

  testWidgets('disabled navigation commands retain their explanations', (
    tester,
  ) async {
    await tester.pumpWidget(
      _app(
        ConfigurationNavigationBar(
          backLabel: 'Exit',
          onBack: () {},
          showCalculation: false,
          isCalculating: false,
          calculationDisabledReason: '',
          onCalculate: null,
          isSaving: false,
          hasUnsavedChanges: false,
          saveDisabledReason: 'Cannot save',
          onSave: null,
          showFinish: false,
          forwardDisabledReason: 'No next task is available',
          onForward: null,
        ),
      ),
    );

    expect(
      tester
          .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Save'))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Continue'))
          .onPressed,
      isNull,
    );
    expect(find.byTooltip('Cannot save'), findsOneWidget);
    expect(find.byTooltip('No next task is available'), findsOneWidget);
  });

  testWidgets('active command disables every competing workspace command', (
    tester,
  ) async {
    const reason = 'Wait for the current command to finish';
    await tester.pumpWidget(
      _app(
        Column(
          children: [
            ConfigurationWorkspaceHeader(
              isCreateMode: true,
              phaseLabel: 'Define workload',
              taskLabel: 'Cloud access',
              onClose: null,
              closeDisabledReason: reason,
            ),
            ConfigurationNavigationBar(
              backLabel: 'Exit',
              backDisabledReason: reason,
              onBack: null,
              showCalculation: true,
              isCalculating: true,
              calculationDisabledReason: 'Calculation in progress',
              onCalculate: null,
              isSaving: false,
              hasUnsavedChanges: true,
              saveDisabledReason: reason,
              onSave: null,
              showFinish: false,
              forwardDisabledReason: reason,
              onForward: null,
            ),
          ],
        ),
      ),
    );

    expect(find.byTooltip(reason), findsNWidgets(4));
    expect(find.byTooltip('Calculation in progress'), findsOneWidget);
    expect(
      tester
          .widget<IconButton>(find.widgetWithIcon(IconButton, Icons.close))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Exit'))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Save'))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Continue'))
          .onPressed,
      isNull,
    );
  });

  testWidgets('wide navigation exposes continue and saving semantics', (
    tester,
  ) async {
    final invoked = <String>[];
    await tester.pumpWidget(
      _app(
        ConfigurationNavigationBar(
          backLabel: 'Back',
          onBack: () => invoked.add('back'),
          showCalculation: false,
          isCalculating: false,
          calculationDisabledReason: '',
          onCalculate: null,
          isSaving: true,
          hasUnsavedChanges: true,
          saveDisabledReason: 'Saving in progress',
          onSave: null,
          showFinish: false,
          forwardDisabledReason: '',
          onForward: () => invoked.add('continue'),
        ),
      ),
    );

    expect(find.text('Continue'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(
      tester
          .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Save'))
          .onPressed,
      isNull,
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Continue'));
    expect(invoked, ['continue']);
  });

  testWidgets('alert stack exposes success and warning states', (tester) async {
    var dismissed = 0;
    Future<void> pumpAlerts({String? success, String? warning}) {
      return tester.pumpWidget(
        _app(
          ConfigurationAlertStack(
            errorMessage: null,
            successMessage: success,
            warningMessage: warning,
            onDismissError: () {},
            onDismissNotification: () => dismissed++,
          ),
        ),
      );
    }

    await pumpAlerts(success: 'Saved');
    expect(find.text('Saved'), findsOneWidget);
    await tester.tap(find.byTooltip('Dismiss'));

    await pumpAlerts(warning: 'Review required');
    expect(find.text('Review required'), findsOneWidget);
    await tester.tap(find.byTooltip('Dismiss'));
    expect(dismissed, 2);
  });

  testWidgets('profile menu emits settings and logout callbacks', (
    tester,
  ) async {
    final invoked = <String>[];
    await tester.pumpWidget(
      _app(
        Scaffold(
          appBar: ConfigurationWorkspaceAppBar(
            isDarkMode: false,
            onToggleTheme: () => invoked.add('theme'),
            onOpenSettings: () => invoked.add('settings'),
            onLogout: () => invoked.add('logout'),
          ),
        ),
      ),
    );

    await tester.tap(find.byTooltip('Toggle theme'));
    await tester.tap(find.byTooltip('Profile menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Profile menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Logout'));
    expect(invoked, ['theme', 'settings', 'logout']);
  });

  testWidgets('profile navigation is disabled while a command is active', (
    tester,
  ) async {
    await tester.pumpWidget(
      _app(
        Scaffold(
          appBar: ConfigurationWorkspaceAppBar(
            isDarkMode: false,
            navigationEnabled: false,
            onToggleTheme: () {},
            onOpenSettings: () => fail('Settings must stay disabled'),
            onLogout: () => fail('Logout must stay disabled'),
          ),
        ),
      ),
    );

    final disabledProfile = find.byTooltip(
      'Wait for the current command to finish',
    );
    expect(disabledProfile, findsOneWidget);
    await tester.tap(disabledProfile);
    await tester.pumpAndSettle();
    expect(find.text('Settings'), findsNothing);
    expect(find.text('Logout'), findsNothing);
  });

  testWidgets('exit dialogs return typed choices and support Escape', (
    tester,
  ) async {
    WorkspaceExitChoice? choice;
    await tester.pumpWidget(
      _app(
        Builder(
          builder: (context) => FilledButton(
            onPressed: () async {
              choice = await ConfigurationWorkspaceDialogs.showUnsavedExit(
                context,
              );
            },
            child: const Text('Open'),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save & Leave'));
    await tester.pumpAndSettle();
    expect(choice, WorkspaceExitChoice.save);

    choice = WorkspaceExitChoice.discard;
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expect(choice, isNull);
  });

  testWidgets('invalidation dialogs return typed destructive choices', (
    tester,
  ) async {
    WorkspaceExitChoice? exitChoice;
    WorkspaceInvalidationChoice? saveChoice;
    await tester.pumpWidget(
      _app(
        Builder(
          builder: (context) => Column(
            children: [
              FilledButton(
                onPressed: () async {
                  exitChoice =
                      await ConfigurationWorkspaceDialogs.showInvalidatedExit(
                        context,
                      );
                },
                child: const Text('Open invalidated exit'),
              ),
              FilledButton(
                onPressed: () async {
                  saveChoice =
                      await ConfigurationWorkspaceDialogs.showInvalidationChoice(
                        context,
                        canRestore: true,
                      );
                },
                child: const Text('Open invalidated save'),
              ),
            ],
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open invalidated exit'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Leave Without Saving'));
    await tester.pumpAndSettle();
    expect(exitChoice, WorkspaceExitChoice.discard);

    await tester.tap(find.text('Open invalidated save'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Discard Changes'));
    await tester.pumpAndSettle();
    expect(saveChoice, WorkspaceInvalidationChoice.restore);
  });
}

Widget _app(Widget child) => MaterialApp(home: child);

PreferredSizeWidget _appBar() => ConfigurationWorkspaceAppBar(
  isDarkMode: false,
  onToggleTheme: () {},
  onOpenSettings: () {},
  onLogout: () {},
);
