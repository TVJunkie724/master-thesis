// test/widgets/credentials/credential_validation_status_test.dart
// Tests for CredentialValidationStatus widget

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/credentials/credential_validation_status.dart';

void main() {
  group('CredentialValidationStatus', () {
    group('state display', () {
      testWidgets('none state shows nothing', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: CredentialValidationStatus(
                state: CredentialValidationState.none,
              ),
            ),
          ),
        );
        
        // Should be a SizedBox.shrink
        expect(find.byType(CredentialValidationStatus), findsOneWidget);
        expect(find.byType(SizedBox), findsWidgets);
      });
      
      testWidgets('validating state shows loading indicator', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: CredentialValidationStatus(
                state: CredentialValidationState.validating,
              ),
            ),
          ),
        );
        
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.text('Validating credentials...'), findsOneWidget);
      });
      
      testWidgets('valid state shows success', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: CredentialValidationStatus(
                state: CredentialValidationState.valid,
                message: 'Test success message',
              ),
            ),
          ),
        );
        
        expect(find.byIcon(Icons.check_circle), findsOneWidget);
        expect(find.text('Test success message'), findsOneWidget);
      });
      
      testWidgets('invalid state shows error', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: CredentialValidationStatus(
                state: CredentialValidationState.invalid,
                message: 'Test error message',
              ),
            ),
          ),
        );
        
        expect(find.byIcon(Icons.error_outline), findsOneWidget);
        expect(find.text('Test error message'), findsOneWidget);
      });
    });
    
    group('dual service display', () {
      testWidgets('shows optimizer and deployer status', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: CredentialValidationStatus(
                state: CredentialValidationState.valid,
                showDualServices: true,
                optimizerMessage: 'Optimizer OK',
                deployerMessage: 'Deployer OK',
              ),
            ),
          ),
        );
        
        expect(find.textContaining('Optimizer'), findsOneWidget);
        expect(find.textContaining('Deployer'), findsOneWidget);
      });
    });
    
    group('edge cases', () {
      testWidgets('handles null message', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: CredentialValidationStatus(
                state: CredentialValidationState.valid,
              ),
            ),
          ),
        );
        
        // Should show default message
        expect(find.textContaining('validated'), findsOneWidget);
      });
    });
  });
}
