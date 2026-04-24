# Enterprise Design Principles — Twin2MultiCloud Flutter

## Principles

| Principle | What it means in practice |
|-----------|--------------------------|
| **Consistency** | Same patterns everywhere. Same spacing tokens. Same BLoC shape. No snowflakes. |
| **Information Density** | Maximize useful information per viewport — operators look at this app for hours. Minimize whitespace waste, but never crowd actions. |
| **Functional Color** | Color conveys meaning (twin state, severity, action type). Never decorative. Pull from `lib/theme/colors.dart`. |
| **Keyboard-First** | Every action reachable without a mouse. Tab order is deliberate. Enter / Esc behave predictably in dialogs. |
| **Instant Feedback** | Every user action has immediate visual response. No dead clicks. Disabled buttons explain why. |
| **Graceful Degradation** | Loading states, error states, empty states — all designed, never afterthoughts. |
| **Responsive by Default** | Every layout adapts between Desktop and Web. Fixed pixel values only where GPU rendering demands them. |
| **Performance Conscious** | Minimize rebuilds. Use `const`. Avoid expensive layouts in scroll paths. Profile before shipping. |
| **Real Backend, Real Logs** | Surface what the Management API + Deployer actually report (SSE log stream). Don't fabricate progress bars when data exists. |

## Anti-Patterns

| Never | Instead |
|-------|---------|
| Vague: "make it look right" | Specify exact dimensions (from tokens), colors (from tokens), spacing (from tokens) |
| Skip the layout diagram | Every plan needs a visual ASCII structure — no exceptions |
| Leave BLoC ownership ambiguous | Name the exact BLoC that owns each piece of state |
| Design only the happy path | Specify loading, error, empty, offline, "Management API down" states |
| Duplicate shared components | Check `lib/widgets/` first, extend if needed |
| Ignore keyboard navigation | Define Tab order and keyboard shortcuts |
| Hardcode dimensions / colors / strings | Use or create design tokens; group strings per screen |
| Design for one screen size | Define responsive breakpoints — Desktop primary, Web mandatory |
| Plan a UI that calls Optimizer / Deployer directly | Always go through Management API |
| Skip the test plan or leave it vague | Specify concrete test cases with types, descriptions, expected outcomes |
| Assume 5 edge cases is always enough | Justify the count — complex units need more, simple need justification for fewer |
| Use Mermaid diagrams | **Mermaid is forbidden.** Always use ASCII diagrams |
| Add a third-party icon library | Use Material `Icons` unless the architect explicitly approves an addition |
| Add a state-management package alongside `flutter_bloc` | One pattern only — `flutter_bloc` |
