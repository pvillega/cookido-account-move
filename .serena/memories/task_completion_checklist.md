# Task Completion Checklist

When completing a task, verify the following:

## Code Quality
- [ ] Code follows PEP 8 style guidelines
- [ ] Type hints added to all function signatures
- [ ] Docstrings added to public functions
- [ ] No unused imports or variables

## Testing (when test infrastructure exists)
```bash
uv run pytest
```
- [ ] All tests pass
- [ ] New functionality has test coverage

## Linting/Formatting (when set up)
```bash
uv run ruff format .
uv run ruff check .
```
- [ ] No linting errors
- [ ] Code is formatted

## Type Checking (when set up)
```bash
uv run mypy src/
```
- [ ] No type errors

## Build Verification
```bash
uv sync
```
- [ ] Dependencies resolve correctly
- [ ] Package builds successfully

## Documentation
- [ ] README updated if needed
- [ ] Complex logic documented with comments

## Pre-Commit (if configured)
- [ ] All pre-commit hooks pass

## Notes
- Currently the project is in early stages, so not all tooling is configured
- Add ruff, pytest, mypy as dev dependencies when needed
- Update this checklist as tooling is added
