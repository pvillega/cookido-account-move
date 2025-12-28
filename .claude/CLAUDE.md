# Cookido Agent - Project Instructions

<project_overview>
A Python agent for automating Cookidoo recipe management. Interacts with cookidoo.es to export/import recipes, manage favorites, and organize recipes into categories.
</project_overview>

<tech_stack>
- **Language**: Python 3.11+
- **Package Manager**: uv (using pyproject.toml)
- **Build System**: hatchling
- **Key Dependencies** (planned): cookidoo-api, asyncio
</tech_stack>

<project_structure>
```
cookido-agent/
├── src/cookido_agent/     # Main package
│   └── __init__.py
├── docs/
│   └── Research.md        # Cookidoo API reverse-engineering guide
├── pyproject.toml         # Project configuration
└── TODO.md                # Task tracking
```
</project_structure>

<build_commands>
```bash
# Install dependencies
uv sync

# Run script with uvx (planned)
uvx cookido-agent

# Development
uv pip install -e .
```
</build_commands>

<code_style>
- Follow PEP 8 guidelines
- Use async/await for API interactions
- Type hints for all function signatures
- Docstrings for public functions
</code_style>

<testing>
```bash
# Run tests (when added)
uv run pytest

# With coverage
uv run pytest --cov=cookido_agent
```
</testing>

<project_notes>
## Cookidoo API Notes

- **No official API** - relies on reverse-engineered endpoints
- Authentication via OAuth2 with regional Vorwerk servers
- CAPTCHA challenges may occur during automated login
- Rate limiting observed; limit operations to avoid detection
- ToS prohibits automation - use responsibly

## Key Endpoints (from Research.md)
- EU Login: `https://eu.login.vorwerk.com/oauth2/token`
- Recipe data includes: recipeId, recipeName, ingredients, instructions
- Collections: `POST /api/v1/collections/{collectionId}/recipes`

## Recommended Library
Use `cookidoo-api` for authentication and API access:
```python
from cookidoo_api import Cookidoo
async with Cookidoo(email="...", password="...") as cookidoo:
    await cookidoo.login()
    recipes = await cookidoo.get_recipes()
```
</project_notes>

<environment>
Environment variables (via .envrc.local):
- COOKIDOO_USERNAME: Cookidoo account email
- COOKIDOO_PASSWORD: Cookidoo account password
</environment>
