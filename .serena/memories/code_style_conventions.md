# Code Style and Conventions

## Python Style
- Follow **PEP 8** guidelines
- Use **async/await** for all Cookidoo API interactions
- **Type hints** required for all function signatures
- **Docstrings** for all public functions (Google style preferred)

## Naming Conventions
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `_leading_underscore`

## File Organization
- Keep modules focused and single-purpose
- Place all source code under `src/cookido_agent/`
- Use relative imports within the package

## Error Handling
- Use specific exception types
- Handle CAPTCHA and rate limiting gracefully
- Log errors appropriately

## Async Patterns
```python
from cookidoo_api import Cookidoo
import asyncio

async def main():
    async with Cookidoo(email="...", password="...") as cookidoo:
        await cookidoo.login()
        # Use async context manager for proper cleanup
```

## Comments
- Avoid obvious comments
- Explain "why" not "what"
- Document API quirks and workarounds
