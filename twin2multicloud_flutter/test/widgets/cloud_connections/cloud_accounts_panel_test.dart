import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_access_inventory.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/cloud_accounts_panel.dart';

void main() {
  Widget buildWidget({
    CloudAccessInventory? inventory,
    bool isLoading = false,
    String? loadError,
    Set<String> busyConnectionIds = const {},
    bool isCreating = false,
    ValueChanged<CloudConnectionCreateRequest>? onCreate,
    ValueChanged<CloudAccessEntry>? onValidate,
    ValueChanged<CloudAccessEntry>? onSetDefault,
    ValueChanged<CloudAccessEntry>? onDelete,
    VoidCallback? onRetry,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: CloudAccountsPanel(
            inventory: inventory,
            isLoading: isLoading,
            loadError: loadError,
            busyConnectionIds: busyConnectionIds,
            isCreating: isCreating,
            onCreate: onCreate ?? (_) {},
            onValidate: onValidate ?? (_) {},
            onSetDefault: onSetDefault ?? (_) {},
            onDelete: onDelete ?? (_) {},
            onRetry: onRetry ?? () {},
          ),
        ),
      ),
    );
  }

  group('CloudAccountsPanel', () {
    testWidgets('renders compact provider summaries with details collapsed', (
      tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(1400, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(buildWidget(inventory: _inventory()));

      expect(find.text('Cloud accounts & access'), findsOneWidget);
      expect(find.text('AWS'), findsOneWidget);
      expect(find.text('Azure'), findsOneWidget);
      expect(find.text('GCP'), findsOneWidget);
      expect(find.text('AWS Pricing Reader'), findsNothing);
      expect(find.textContaining('Fingerprint'), findsNothing);
      expect(find.textContaining('secret_access_key'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('expands purpose-aware access rows and validates from menu', (
      tester,
    ) async {
      CloudAccessEntry? validated;
      await tester.pumpWidget(
        buildWidget(
          inventory: _inventory(),
          onValidate: (entry) => validated = entry,
        ),
      );

      await tester.tap(find.text('Access details (2)').first);
      await tester.pumpAndSettle();
      expect(find.text('AWS Pricing Reader'), findsOneWidget);
      expect(find.text('AWS Deployer'), findsOneWidget);

      await tester.tap(find.byTooltip('Actions for AWS Pricing Reader'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Validate').last);
      await tester.pumpAndSettle();

      expect(validated?.connectionId, 'aws-pricing');
    });

    testWidgets(
      'requires confirmation before deleting default pricing access',
      (tester) async {
        CloudAccessEntry? deleted;
        await tester.pumpWidget(
          buildWidget(
            inventory: _inventory(),
            onDelete: (entry) => deleted = entry,
          ),
        );

        await tester.tap(find.text('Access details (2)').first);
        await tester.pumpAndSettle();
        await tester.tap(find.byTooltip('Actions for AWS Pricing Reader'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Delete').last);
        await tester.pumpAndSettle();

        expect(deleted, isNull);
        expect(
          find.textContaining('Pricing refresh stays disabled'),
          findsOneWidget,
        );
        await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
        await tester.pumpAndSettle();

        expect(deleted?.connectionId, 'aws-pricing');
      },
    );

    testWidgets('shows retry for initial load error', (tester) async {
      var retried = false;
      await tester.pumpWidget(
        buildWidget(
          loadError: 'Management API unavailable',
          onRetry: () => retried = true,
        ),
      );

      expect(find.text('Management API unavailable'), findsOneWidget);
      await tester.tap(find.text('Retry'));
      await tester.pump();
      expect(retried, isTrue);
    });

    testWidgets('keeps cached cards visible with an inline reload error', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(
          inventory: _inventory(),
          loadError: 'Inventory reload unavailable',
        ),
      );

      expect(find.text('Inventory reload unavailable'), findsOneWidget);
      expect(find.text('AWS'), findsOneWidget);
    });

    testWidgets('opens purpose-specific pricing creation', (tester) async {
      await tester.pumpWidget(buildWidget(inventory: _inventory()));

      await tester.tap(find.byTooltip('Add AWS access'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Pricing access').last);
      await tester.pumpAndSettle();

      expect(find.text('New AWS Pricing access'), findsOneWidget);
    });

    testWidgets('selects a non-default pricing option from its action menu', (
      tester,
    ) async {
      CloudAccessEntry? selected;
      await tester.pumpWidget(
        buildWidget(
          inventory: _inventoryWithAlternative(),
          onSetDefault: (entry) => selected = entry,
        ),
      );

      await tester.tap(find.text('Access details (3)').first);
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Actions for AWS Pricing Alternative'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Use for pricing'));
      await tester.pumpAndSettle();

      expect(selected?.connectionId, 'aws-pricing-alt');
    });

    testWidgets('stacks provider cards on compact layouts without overflow', (
      tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(480, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(buildWidget(inventory: _inventory()));

      expect(find.byType(CloudAccountsPanel), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}

CloudAccessInventory _inventory() => CloudAccessInventory.fromJson({
  'schema_version': 'cloud-access-inventory.v1',
  'providers': {
    'aws': {
      'provider': 'aws',
      'pricing': _entry(
        id: 'aws-pricing',
        provider: 'aws',
        purpose: 'pricing',
        label: 'AWS Pricing Reader',
        status: 'active',
        isDefault: true,
        actions: ['validate', 'delete', 'refresh_pricing'],
        accountId: '123456789012',
      ),
      'pricing_options': [
        _entry(
          id: 'aws-pricing',
          provider: 'aws',
          purpose: 'pricing',
          label: 'AWS Pricing Reader',
          status: 'active',
          isDefault: true,
          actions: ['validate', 'delete', 'refresh_pricing'],
          accountId: '123456789012',
        ),
      ],
      'deployment': [
        _entry(
          id: 'aws-deployment',
          provider: 'aws',
          purpose: 'deployment',
          label: 'AWS Deployer',
          status: 'active',
          actions: ['validate', 'delete_blocked'],
          boundLabels: ['Factory Twin'],
        ),
      ],
    },
    'azure': {
      'provider': 'azure',
      'pricing': _entry(
        provider: 'azure',
        purpose: 'pricing',
        label: 'Azure Retail Prices API',
        status: 'active',
        scope: 'public',
      ),
      'pricing_options': [],
      'deployment': [],
    },
    'gcp': {
      'provider': 'gcp',
      'pricing': _entry(
        provider: 'gcp',
        purpose: 'pricing',
        label: 'GCP pricing access not configured',
        status: 'missing',
      ),
      'pricing_options': [],
      'deployment': [],
    },
  },
});

CloudAccessInventory _inventoryWithAlternative() {
  final inventory = _inventory();
  final aws = inventory.providers['aws']!;
  return CloudAccessInventory(
    schemaVersion: inventory.schemaVersion,
    providers: {
      ...inventory.providers,
      'aws': CloudAccessProviderInventory(
        provider: aws.provider,
        pricing: aws.pricing,
        pricingOptions: [
          ...aws.pricingOptions,
          const CloudAccessEntry(
            connectionId: 'aws-pricing-alt',
            provider: 'aws',
            purpose: 'pricing',
            scope: 'user',
            identityLabel: 'AWS Pricing Alternative',
            status: 'needs_validation',
            isDefaultForPricing: false,
            actions: ['validate', 'delete', 'set_pricing_default'],
          ),
        ],
        deployment: aws.deployment,
      ),
    },
  );
}

Map<String, dynamic> _entry({
  String? id,
  required String provider,
  required String purpose,
  required String label,
  required String status,
  String scope = 'user',
  bool isDefault = false,
  List<String> actions = const [],
  String? accountId,
  List<String> boundLabels = const [],
}) => {
  'connection_id': id,
  'provider': provider,
  'purpose': purpose,
  'scope': scope,
  'identity_label': label,
  'status': status,
  'is_default_for_pricing': isDefault,
  'provider_account_id': accountId,
  'bound_twin_count': boundLabels.length,
  'bound_twin_labels': boundLabels,
  'actions': actions,
};
