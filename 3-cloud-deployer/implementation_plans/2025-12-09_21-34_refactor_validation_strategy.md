# Refactor Validation Logic to Strategy Pattern

## 1. Executive Summary
### The Problem
The current `validator.py` contains monolithic validation logic with hardcoded `if/elif` blocks for different cloud providers (AWS, Azure, GCP). This makes the code difficult to extend, harder to test in isolation, and violates the Open/Closed Principle. Adding a new provider or changing validation rules requires modifying the core validator file.

### The Solution
Implement the **Strategy Design Pattern** for validation. We will extract provider-specific validation logic into dedicated strategy classes (e.g., `AwsValidationStrategy`, `AzureValidationStrategy`, `GcpValidationStrategy`) that implement a common interface. The main `validator.py` context will delegate to these strategies.

### Impact
- **Extensibility:** Easy to add new providers without changing core logic.
- **Maintainability:** Clear separation of concerns; each strategy handles only its provider's rules.
- **Testability:** Strategies can be unit tested individually.

---

## 2. Current State
Currently, `validator.py` has monolithic functions:
```python
def validate_python_code_aws(code_content): ...
def validate_python_code_azure(code_content): ...
def validate_python_code_google(code_content): ...
```
The consumer (`file_manager.py`) manually switches on the provider string:
```python
if provider == "aws":
    validator.validate_python_code_aws(content)
elif provider == "azure":
    validator.validate_python_code_azure(content)
```

---

## 3. Architecture Design
### Class Diagram (Strategy Pattern)
```
  ┌─────────────────┐             ┌──────────────────────────┐
  │  Context        │             │  <<Interface>>           │
  │ (Validator)     │────────────▶│  ValidationStrategy      │
  │                 │             │                          │
  └─────────────────┘             └────────────┬─────────────┘
           │                                   │
           │ delegation                        ▲
           │                                   │
  ┌────────▼────────┐             ┌────────────┴─────────────┐
  │ Client          │             │                          │
  │ (FileManager)   │    ┌────────┴─────────┐      ┌─────────┴────────┐
  └─────────────────┘    │ AwsValidation    │      │ AzureValidation  │
                         │ Strategy         │      │ Strategy         │
                         └──────────────────┘      └──────────────────┘
```

---

## 4. Proposed Changes

### Component: Validation Strategies

#### [NEW] src/validation/__init__.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/validation/__init__.py`
- **Description:**  Initialize the validation package.

#### [NEW] src/validation/strategies.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/validation/strategies.py`
- **Description:** Defines the abstract base class and concrete implementations.

#### [MODIFY] src/validator.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/validator.py`
- **Description:** Refactor to use the strategies. Remove legacy specific functions.

#### [MODIFY] src/file_manager.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/file_manager.py`
- **Description:** Update to use the unified validation interface.

---

## 5. Code Examples

### 5.1 Abstract Strategy & Concrete Implementation (`src/validation/strategies.py`)
```python
from abc import ABC, abstractmethod
import ast

class ValidationStrategy(ABC):
    """
    Abstract base class for validation strategies. 
    Enforces the Open/Closed principle.
    """
    @abstractmethod
    def validate_code(self, code_content: str) -> None:
        """
        Validates the provided code content.
        Raises ValueError if invalid.
        """
        pass

class AwsValidationStrategy(ValidationStrategy):
    def validate_code(self, code_content: str) -> None:
        try:
            tree = ast.parse(code_content)
        except SyntaxError as e:
            raise ValueError(f"Python Syntax Error: {e.msg}")

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "lambda_handler":
                # Check args: event, context
                args = [arg.arg for arg in node.args.args]
                if len(args) >= 2 and args[0] == "event" and args[1] == "context":
                    return # Valid
        
        raise ValueError("AWS Lambda function must have a 'lambda_handler(event, context)' function.")
```

### 5.2 Context Usage (`src/validator.py`)
```python
from src.validation.strategies import AwsValidationStrategy, AzureValidationStrategy, GoogleValidationStrategy

def get_strategy(provider: str) -> ValidationStrategy:
    strategies = {
        "aws": AwsValidationStrategy(),
        "azure": AzureValidationStrategy(),
        "google": GoogleValidationStrategy()
    }
    strategy = strategies.get(provider.lower())
    if not strategy:
        raise ValueError(f"No validation strategy found for provider: {provider}")
    return strategy

def validate_function_code(provider: str, code_content: str):
    """
    Validates function code using the appropriate strategy.
    
    Args:
        provider: Provider name ('aws', 'azure', 'google')
        code_content: The python code to validate
    """
    strategy = get_strategy(provider)
    strategy.validate_code(code_content)
```

---

## 6. Implementation Phases

### Phase 1: Strategy Implementation
| Step | File | Action |
|------|------|--------|
| 1.1  | `src/validation/__init__.py` | Create empty package file. |
| 1.2  | `src/validation/strategies.py` | Implement `ValidationStrategy`, `AwsValidationStrategy`, `AzureValidationStrategy`, `GoogleValidationStrategy`. |

### Phase 2: Context Value Integration
| Step | File | Action |
|------|------|--------|
| 2.1  | `src/validator.py` | Import strategies. Implement `validate_function_code`. Remove `validate_python_code_aws`, etc. |

### Phase 3: Client Update
| Step | File | Action |
|------|------|--------|
| 3.1  | `src/file_manager.py` | in `update_function_code_file`, replace the `if/elif` block with `validator.validate_function_code(provider, code_content)`. |

---

## 7. Verification Checklist
- [ ] **Unit Test:** Verify `AwsValidationStrategy` correctly identifies `lambda_handler`.
- [ ] **Unit Test:** Verify `AwsValidationStrategy` fails for missing `event`/`context` args.
- [ ] **Unit Test:** Verify `AzureValidationStrategy` checks for `main(req)`.
- [ ] **Unit Test:** Verify `GoogleValidationStrategy` allows any function.
- [ ] **Integration Test:** `update_function_code_file` successfully updates a valid AWS file via `file_manager`.
- [ ] **Integration Test:** `update_function_code_file` raises ValueError for invalid code.

---

## 8. Design Decisions
- **Stateless Strategies:** The strategies are stateless, so they can be instantiated once or on demand. For simplicity in this phase, we instantiate them on demand in the factory method.
- **Pattern adherence:** Strict adherence to the Strategy pattern where the Context (`validator`) sets the strategy and the Client (`file_manager`) is oblivious to the specific validation logic.
