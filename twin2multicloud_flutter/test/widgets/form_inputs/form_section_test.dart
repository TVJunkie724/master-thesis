// test/widgets/form_inputs/form_section_test.dart
// Tests for FormSection and CollapsibleFormSection widgets

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/form_inputs/form_section.dart';

void main() {
  group('FormSection', () {
    testWidgets('displays title', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: FormSection(
              title: 'Test Section',
              children: [Text('Content')],
            ),
          ),
        ),
      );
      
      expect(find.text('Test Section'), findsOneWidget);
    });
    
    testWidgets('displays children', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: FormSection(
              title: 'Test',
              children: [
                Text('Child 1'),
                Text('Child 2'),
              ],
            ),
          ),
        ),
      );
      
      expect(find.text('Child 1'), findsOneWidget);
      expect(find.text('Child 2'), findsOneWidget);
    });
    
    testWidgets('displays icon when provided', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: FormSection(
              title: 'Test',
              icon: Icons.settings,
              children: [Text('Content')],
            ),
          ),
        ),
      );
      
      expect(find.byIcon(Icons.settings), findsOneWidget);
    });
    
    testWidgets('shows help button when callback provided', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FormSection(
              title: 'Test',
              onHelpPressed: () {},
              children: const [Text('Content')],
            ),
          ),
        ),
      );
      
      expect(find.byIcon(Icons.help_outline), findsOneWidget);
    });
  });
  
  group('CollapsibleFormSection', () {
    testWidgets('shows title when collapsed', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollapsibleFormSection(
              title: 'Collapsible Section',
              initiallyExpanded: false,
              children: [Text('Hidden Content')],
            ),
          ),
        ),
      );
      
      expect(find.text('Collapsible Section'), findsOneWidget);
    });
    
    testWidgets('shows content when expanded', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollapsibleFormSection(
              title: 'Collapsible Section',
              initiallyExpanded: true,
              children: [Text('Visible Content')],
            ),
          ),
        ),
      );
      
      expect(find.text('Visible Content'), findsOneWidget);
    });
    
    testWidgets('toggles on tap', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollapsibleFormSection(
              title: 'Tap to Toggle',
              initiallyExpanded: false,
              children: [Text('Toggle Content')],
            ),
          ),
        ),
      );
      
      // Initially collapsed - content hidden (uses AnimatedCrossFade)
      // Tap to expand
      await tester.tap(find.text('Tap to Toggle'));
      await tester.pumpAndSettle();
      
      // Now visible
      expect(find.text('Toggle Content'), findsOneWidget);
    });
    
    testWidgets('shows expand icon when collapsed', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollapsibleFormSection(
              title: 'Test',
              initiallyExpanded: false,
              children: [Text('Content')],
            ),
          ),
        ),
      );
      
      expect(find.byIcon(Icons.expand_more), findsOneWidget);
    });
    
    testWidgets('shows collapse icon when expanded', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollapsibleFormSection(
              title: 'Test',
              initiallyExpanded: true,
              children: [Text('Content')],
            ),
          ),
        ),
      );
      
      expect(find.byIcon(Icons.expand_less), findsOneWidget);
    });
  });
}
