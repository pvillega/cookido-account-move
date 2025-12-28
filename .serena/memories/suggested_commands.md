# Suggested Commands

## Package Management (uv)
```bash
# Install dependencies
uv sync

# Add a dependency
uv add <package>

# Add dev dependency
uv add --dev <package>

# Run a script
uv run python <script.py>

# Run with uvx (installed tool)
uvx cookido-agent
```

## Development
```bash
# Install in editable mode
uv pip install -e .

# Create virtual environment (if needed)
uv venv

# Activate venv manually
source .venv/bin/activate
```

## Testing (when set up)
```bash
# Run tests
uv run pytest

# With coverage
uv run pytest --cov=cookido_agent

# Verbose
uv run pytest -v
```

## Code Quality (when set up)
```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Fix lint issues
uv run ruff check --fix .

# Type check
uv run mypy src/
```

## Environment
```bash
# Allow direnv (first time)
direnv allow

# Set up local env vars
cp envrc.template .envrc
# Edit .envrc.local with your credentials
```

## Git
```bash
git status
git add <file>
git commit -m "message"
git log --oneline -10
```

## System (Darwin/macOS)
```bash
ls -la                  # List files
find . -name "*.py"     # Find files
grep -r "pattern" .     # Search content
```
