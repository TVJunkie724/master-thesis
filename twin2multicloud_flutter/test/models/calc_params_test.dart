import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';

void main() {
  group('CalcParams', () {
    // ============================================================
    // Happy Path Tests
    // ============================================================

    group('construction', () {
      test('defaultParams creates valid instance', () {
        final params = CalcParams.defaultParams();
        
        expect(params.numberOfDevices, 100);
        expect(params.deviceSendingIntervalInMinutes, 2.0);
        expect(params.averageSizeOfMessageInKb, 0.25);
        expect(params.needs3DModel, isFalse);
        expect(params.currency, 'USD');
      });

      test('constructor sets all required fields', () {
        final params = CalcParams(
          numberOfDevices: 500,
          deviceSendingIntervalInMinutes: 5.0,
          averageSizeOfMessageInKb: 1.0,
          hotStorageDurationInMonths: 2,
          coolStorageDurationInMonths: 6,
          archiveStorageDurationInMonths: 24,
          needs3DModel: true,
          dashboardRefreshesPerHour: 10,
          amountOfActiveEditors: 5,
          amountOfActiveViewers: 20,
        );
        
        expect(params.numberOfDevices, 500);
        expect(params.needs3DModel, isTrue);
      });
    });

    group('toJson', () {
      test('serializes all 26 fields', () {
        final params = CalcParams.defaultParams();
        final json = params.toJson();
        
        expect(json.keys.length, 26);
        expect(json['numberOfDevices'], 100);
        expect(json['deviceSendingIntervalInMinutes'], 2.0);
        expect(json['averageSizeOfMessageInKb'], 0.25);
        expect(json['hotStorageDurationInMonths'], 1);
        expect(json['coolStorageDurationInMonths'], 3);
        expect(json['archiveStorageDurationInMonths'], 12);
        expect(json['needs3DModel'], isFalse);
        expect(json['currency'], 'USD');
      });

      test('includes optional fields with their values', () {
        final params = CalcParams(
          numberOfDevices: 100,
          deviceSendingIntervalInMinutes: 2.0,
          averageSizeOfMessageInKb: 0.25,
          hotStorageDurationInMonths: 1,
          coolStorageDurationInMonths: 3,
          archiveStorageDurationInMonths: 12,
          needs3DModel: false,
          dashboardRefreshesPerHour: 2,
          amountOfActiveEditors: 0,
          amountOfActiveViewers: 0,
          useEventChecking: true,
          eventsPerMessage: 5,
          currency: 'EUR',
        );
        final json = params.toJson();
        
        expect(json['useEventChecking'], isTrue);
        expect(json['eventsPerMessage'], 5);
        expect(json['currency'], 'EUR');
      });
    });

    group('fromJson', () {
      test('parses complete JSON', () {
        final json = {
          'numberOfDevices': 200,
          'deviceSendingIntervalInMinutes': 3.0,
          'averageSizeOfMessageInKb': 0.5,
          'hotStorageDurationInMonths': 2,
          'coolStorageDurationInMonths': 6,
          'archiveStorageDurationInMonths': 18,
          'needs3DModel': true,
          'entityCount': 10,
          'dashboardRefreshesPerHour': 5,
          'amountOfActiveEditors': 3,
          'amountOfActiveViewers': 15,
          'currency': 'EUR',
        };
        
        final params = CalcParams.fromJson(json);
        
        expect(params.numberOfDevices, 200);
        expect(params.deviceSendingIntervalInMinutes, 3.0);
        expect(params.needs3DModel, isTrue);
        expect(params.entityCount, 10);
        expect(params.currency, 'EUR');
      });

      test('uses defaults for missing fields', () {
        final json = <String, dynamic>{};
        final params = CalcParams.fromJson(json);
        
        expect(params.numberOfDevices, 100);
        expect(params.currency, 'USD');
        expect(params.useEventChecking, isFalse);
      });
    });

    // ============================================================
    // Edge Case Tests
    // ============================================================

    group('isStorageDurationValid', () {
      test('valid when hot <= cool <= archive', () {
        final params = CalcParams(
          numberOfDevices: 100,
          deviceSendingIntervalInMinutes: 2.0,
          averageSizeOfMessageInKb: 0.25,
          hotStorageDurationInMonths: 1,
          coolStorageDurationInMonths: 3,
          archiveStorageDurationInMonths: 12,
          needs3DModel: false,
          dashboardRefreshesPerHour: 2,
          amountOfActiveEditors: 0,
          amountOfActiveViewers: 0,
        );
        
        expect(params.isStorageDurationValid, isTrue);
      });

      test('valid when durations are equal', () {
        final params = CalcParams(
          numberOfDevices: 100,
          deviceSendingIntervalInMinutes: 2.0,
          averageSizeOfMessageInKb: 0.25,
          hotStorageDurationInMonths: 6,
          coolStorageDurationInMonths: 6,
          archiveStorageDurationInMonths: 6,
          needs3DModel: false,
          dashboardRefreshesPerHour: 2,
          amountOfActiveEditors: 0,
          amountOfActiveViewers: 0,
        );
        
        expect(params.isStorageDurationValid, isTrue);
      });

      test('invalid when hot > cool', () {
        final params = CalcParams(
          numberOfDevices: 100,
          deviceSendingIntervalInMinutes: 2.0,
          averageSizeOfMessageInKb: 0.25,
          hotStorageDurationInMonths: 6,
          coolStorageDurationInMonths: 3, // Less than hot
          archiveStorageDurationInMonths: 12,
          needs3DModel: false,
          dashboardRefreshesPerHour: 2,
          amountOfActiveEditors: 0,
          amountOfActiveViewers: 0,
        );
        
        expect(params.isStorageDurationValid, isFalse);
      });

      test('invalid when cool > archive', () {
        final params = CalcParams(
          numberOfDevices: 100,
          deviceSendingIntervalInMinutes: 2.0,
          averageSizeOfMessageInKb: 0.25,
          hotStorageDurationInMonths: 1,
          coolStorageDurationInMonths: 24, // Greater than archive
          archiveStorageDurationInMonths: 12,
          needs3DModel: false,
          dashboardRefreshesPerHour: 2,
          amountOfActiveEditors: 0,
          amountOfActiveViewers: 0,
        );
        
        expect(params.isStorageDurationValid, isFalse);
      });
    });

    group('type coercion', () {
      test('fromJson converts int to double for numeric fields', () {
        final json = {
          'deviceSendingIntervalInMinutes': 5, // int instead of double
          'averageSizeOfMessageInKb': 1, // int instead of double
        };
        
        final params = CalcParams.fromJson(json);
        
        expect(params.deviceSendingIntervalInMinutes, 5.0);
        expect(params.averageSizeOfMessageInKb, 1.0);
      });
    });
  });
}
