// test/widgets/wizard/step_indicator_test.dart
// Tests for StepIndicator widget

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/wizard/step_indicator.dart';

void main() {
  group('StepIndicator', () {
    group('display', () {
      testWidgets('shows all steps', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: StepIndicator(
                currentStep: 0,
                highestStepReached: 0,
                totalSteps: 3,
                stepLabels: ['Step 1', 'Step 2', 'Step 3'],
              ),
            ),
          ),
        );
        
        expect(find.text('Step 1'), findsOneWidget);
        expect(find.text('Step 2'), findsOneWidget);
        expect(find.text('Step 3'), findsOneWidget);
        expect(find.text('1'), findsOneWidget);
        expect(find.text('2'), findsOneWidget);
        expect(find.text('3'), findsOneWidget);
      });
      
      testWidgets('highlights current step', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: StepIndicator(
                currentStep: 1,
                highestStepReached: 1,
                totalSteps: 3,
                stepLabels: ['Step 1', 'Step 2', 'Step 3'],
              ),
            ),
          ),
        );
        
        // Current step should be styled differently
        expect(find.text('2'), findsOneWidget);
      });
      
      testWidgets('shows checkmark for completed steps', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: StepIndicator(
                currentStep: 2,
                highestStepReached: 2,
                totalSteps: 3,
                stepLabels: ['Step 1', 'Step 2', 'Step 3'],
              ),
            ),
          ),
        );
        
        // Completed steps show checkmark
        expect(find.byIcon(Icons.check), findsNWidgets(2));
      });
    });
    
    group('navigation', () {
      testWidgets('allows tap on reached steps', (tester) async {
        int? tappedStep;
        
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: StepIndicator(
                currentStep: 2,
                highestStepReached: 2,
                totalSteps: 3,
                stepLabels: ['Step 1', 'Step 2', 'Step 3'],
                onStepTapped: (step) => tappedStep = step,
              ),
            ),
          ),
        );
        
        // Tap on first step (already reached)
        await tester.tap(find.text('Step 1'));
        await tester.pump();
        
        expect(tappedStep, 0);
      });
      
      testWidgets('ignores tap on unreached steps', (tester) async {
        int? tappedStep;
        
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: StepIndicator(
                currentStep: 0,
                highestStepReached: 0,
                totalSteps: 3,
                stepLabels: ['Step 1', 'Step 2', 'Step 3'],
                onStepTapped: (step) => tappedStep = step,
              ),
            ),
          ),
        );
        
        // Tap on third step (not reached)
        await tester.tap(find.text('Step 3'));
        await tester.pump();
        
        expect(tappedStep, null);
      });
    });
    
    group('edge cases', () {
      testWidgets('handles single step', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: StepIndicator(
                currentStep: 0,
                highestStepReached: 0,
                totalSteps: 1,
                stepLabels: ['Only Step'],
              ),
            ),
          ),
        );
        
        expect(find.text('Only Step'), findsOneWidget);
      });
      
      testWidgets('handles no onStepTapped callback', (tester) async {
        await tester.pumpWidget(
          const MaterialApp(
            home: Scaffold(
              body: StepIndicator(
                currentStep: 1,
                highestStepReached: 1,
                totalSteps: 3,
                stepLabels: ['A', 'B', 'C'],
              ),
            ),
          ),
        );
        
        // Should not throw when tapping
        await tester.tap(find.text('A'));
        await tester.pump();
      });
    });
  });
}
