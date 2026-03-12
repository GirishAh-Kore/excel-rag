# Coding Standards and Best Practices

This document defines the coding standards, design principles, and best practices that MUST be followed when writing or modifying code in this project.

## 1. SOLID Design Principles

### 1.1 Single Responsibility Principle (SRP)
- Each class/module should have ONE reason to change
- Avoid "god classes" that do too many things
- Extract separate concerns into dedicated classes

**Bad:**
```python
class UserService:
    def create_user(self): ...
    def send_email(self): ...
    def generate_report(self): ...
    def validate_payment(self): ...
```

**Good:**
```python
class UserService:
    def create_user(self): ...

class EmailService:
    def send_email(self): ...

class ReportGenerator:
    def generate_report(self): ...
```

### 1.2 Open/Closed Principle (OCP)
- Classes should be open for extension, closed for modification
- Use registry patterns instead of if/elif chains for providers
- New functionality should be added without modifying existing code

**Bad:**
```python
def create_service(provider: str):
    if provider == "openai":
        return OpenAIService()
    elif provider == "anthropic":
        return AnthropicService()
    # Must modify this function for each new provider
```

**Good:**
```python
class ServiceRegistry:
    _registry: Dict[str, Type[Service]] = {}
    
    @classmethod
    def register(cls, name: str, service_class: Type[Service]):
        cls._registry[name] = service_class
    
    @classmethod
    def create(cls, name: str, config: dict) -> Service:
        return cls._registry[name](config)

# Registration happens in each service module
ServiceRegistry.register("openai", OpenAIService)
```

### 1.3 Liskov Substitution Principle (LSP)
- Derived classes must be substitutable for their base classes
- ALL abstract methods must be implemented
- Method signatures must match exactly

**Rule:** If a method exists in ANY concrete implementation, it MUST be declared in the abstract base class.

### 1.4 Interface Segregation Principle (ISP)
- Clients should not depend on interfaces they don't use
- Prefer many small interfaces over one large interface

### 1.5 Dependency Inversion Principle (DIP)
- Depend on abstractions, not concretions
- Use dependency injection for all external dependencies
- Never create dependencies inside constructors

**Bad:**
```python
class QueryEngine:
    def __init__(self, cache_service):
        self.conversation_manager = ConversationManager(cache_service)  # Creates own dependency
```

**Good:**
```python
class QueryEngine:
    def __init__(self, cache_service, conversation_manager):
        self.conversation_manager = conversation_manager  # Injected
```

## 2. Type Safety

### 2.1 Type Hints Required
- ALL function parameters must have type hints
- ALL function return types must be specified
- Use `Optional[T]` for nullable types
- Use `Union[A, B]` sparingly; prefer protocols

```python
# Required format
def process_query(
    self,
    query: str,
    session_id: Optional[str] = None,
    context: Optional[ConversationContext] = None
) -> QueryResult:
    ...
```

### 2.2 No Duplicate Class Names
- Each class name must be unique across the codebase
- If two classes serve similar purposes, use descriptive suffixes:
  - `ExtractionSettings` (dataclass for runtime config)
  - `ExtractionConfig` (Pydantic for API validation)

### 2.3 Abstract Base Classes
- All abstract methods must use `@abstractmethod` decorator
- Concrete implementations must implement ALL abstract methods
- Document the contract in the base class docstring

## 3. Error Handling

### 3.1 Exception Hierarchy
Use a consistent exception hierarchy:

```python
class RAGSystemError(Exception):
    """Base exception for all RAG system errors"""
    pass

class ConfigurationError(RAGSystemError):
    """Configuration-related errors"""
    pass

class ExtractionError(RAGSystemError):
    """Document extraction errors"""
    pass

class QueryError(RAGSystemError):
    """Query processing errors"""
    pass
```

### 3.2 Exception Rules
- Never catch bare `Exception` unless re-raising
- Log exceptions with full context
- Include correlation IDs in error messages
- Provide actionable error messages

## 4. State Management

### 4.1 No Module-Level State
- NEVER use module-level dictionaries for state
- Use proper state management (cache service, database)
- State should be injectable and testable

**Forbidden:**
```python
# At module level
query_history: Dict[str, List] = {}  # NO!
session_contexts: Dict[str, Dict] = {}  # NO!
```

**Required:**
```python
# Use injected services
class QueryHandler:
    def __init__(self, conversation_manager: ConversationManager):
        self.conversation_manager = conversation_manager
```

### 4.2 Thread Safety
- All shared state must be thread-safe
- Use locks for mutable shared state
- Prefer immutable data structures

## 5. Performance

### 5.1 Database
- Use connection pooling for all database connections
- Use prepared statements for repeated queries
- Index frequently queried columns
- Use batch operations for bulk inserts

### 5.2 Caching
- Cache expensive computations
- Set appropriate TTLs
- Implement cache invalidation strategy
- Use LRU eviction for bounded caches

### 5.3 Async/Await
- Use async for I/O-bound operations
- Don't mix sync and async unnecessarily
- If a class has async methods, provide sync wrappers using `asyncio.run()`

## 6. Security

### 6.1 Secrets Management
- NEVER hardcode secrets
- Production MUST require environment variables for secrets
- Development can use defaults with clear warnings

```python
def get_secret(name: str, required_in_production: bool = True) -> str:
    value = os.getenv(name)
    if not value:
        if os.getenv("APP_ENV") == "production" and required_in_production:
            raise ConfigurationError(f"{name} must be set in production")
        return "dev-default-not-for-production"
    return value
```

### 6.2 CORS
- Never use `["*"]` for CORS origins
- Use explicit origin lists even in development
- Validate all origins against allowlist

### 6.3 Input Validation
- Validate all user input
- Use Pydantic models for request validation
- Sanitize data before database operations

## 7. Documentation

### 7.1 Docstring Format (Google Style)
```python
def process_query(
    self,
    query: str,
    session_id: Optional[str] = None
) -> QueryResult:
    """
    Process a natural language query.
    
    Args:
        query: The user's natural language question
        session_id: Optional session ID for conversation context
        
    Returns:
        QueryResult containing the answer and sources
        
    Raises:
        QueryError: If query processing fails
        ConfigurationError: If required services are not configured
    """
```

### 7.2 Module Docstrings
Every module must have a docstring explaining:
- Purpose of the module
- Key classes/functions
- Usage examples if applicable

## 8. Testing

### 8.1 Testability Requirements
- All dependencies must be injectable
- No hidden dependencies (created inside constructors)
- Provide interfaces for external services

### 8.2 Test Coverage
- Unit tests for all business logic
- Integration tests for API endpoints
- Mock external services in tests

## 9. Code Organization

### 9.1 Import Order
1. Standard library imports
2. Third-party imports
3. Local application imports

Each group separated by a blank line.

### 9.2 File Structure
- One primary class per file
- Related helper classes can be in same file
- Keep files under 500 lines; split if larger

## 10. Configuration

### 10.1 No Magic Numbers
```python
# Bad
if len(messages) > 100:
    ...

# Good
MAX_MESSAGES_PER_SESSION = 100  # Or from config
if len(messages) > MAX_MESSAGES_PER_SESSION:
    ...
```

### 10.2 Configuration Sources
- Use environment variables for deployment config
- Use config files for application defaults
- Document all configuration options
