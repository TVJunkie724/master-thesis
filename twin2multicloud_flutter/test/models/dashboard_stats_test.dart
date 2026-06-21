import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/dashboard_stats.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';

void main() {
  group('DashboardStats', () {
    test('parses Management API response', () {
      final stats = DashboardStats.fromJson({
        'deployed_count': 2,
        'draft_count': 1,
        'total_twins': 4,
        'estimated_monthly_cost': 123.45,
      });

      expect(stats.deployedCount, 2);
      expect(stats.draftCount, 1);
      expect(stats.totalTwins, 4);
      expect(stats.estimatedMonthlyCost, 123.45);
    });

    test('coerces numeric strings defensively', () {
      final stats = DashboardStats.fromJson({
        'deployed_count': '2',
        'draft_count': '1',
        'total_twins': '4',
        'estimated_monthly_cost': '123.45',
      });

      expect(stats.deployedCount, 2);
      expect(stats.draftCount, 1);
      expect(stats.totalTwins, 4);
      expect(stats.estimatedMonthlyCost, 123.45);
    });

    test('builds fallback stats from twins', () {
      final stats = DashboardStats.fromTwins([
        Twin(id: 'a', name: 'A', state: 'deployed', providers: const []),
        Twin(id: 'b', name: 'B', state: 'draft', providers: const []),
        Twin(id: 'c', name: 'C', state: 'error', providers: const []),
      ]);

      expect(stats.deployedCount, 1);
      expect(stats.draftCount, 1);
      expect(stats.totalTwins, 3);
      expect(stats.estimatedMonthlyCost, 0);
    });
  });
}
