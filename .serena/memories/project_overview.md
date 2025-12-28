# Cookido Agent - Project Overview

## Purpose
A Python agent for automating Cookidoo recipe management. The project aims to:
- Export recipes from a Cookidoo account (favorites, personal lists)
- Import/tag recipes from another user's export
- Organize recipes using custom categories (seasonality, characteristics)

## Tech Stack
- **Language**: Python 3.12+ (specified in `.python-version`)
- **Package Manager**: uv (modern Python package manager)
- **Build System**: hatchling (via pyproject.toml)
- **Environment**: direnv for environment variable management
- **Key Dependencies** (planned): cookidoo-api (async Cookidoo API wrapper)

## Project Structure
```
cookido-agent/
├── src/cookido_agent/     # Main package
│   └── __init__.py        # Package initialization, version
├── docs/
│   └── Research.md        # Cookidoo API reverse-engineering guide
├── pyproject.toml         # Project configuration (hatchling build)
├── TODO.md                # Task tracking / brainstorm commands
├── envrc.template         # Environment variable template
├── .python-version        # Python version (3.12)
└── .envrc.local           # Local env vars (gitignored)
```

## Key Technical Notes
- **No official Cookidoo API** - relies on reverse-engineered endpoints
- Authentication via OAuth2 with regional Vorwerk servers
- CAPTCHA challenges may occur during automated login
- Rate limiting observed; limit operations to avoid detection
- ToS technically prohibits automation

## Environment Variables
- `COOKIDOO_EMAIL`: Cookidoo account email
- `COOKIDOO_PASSWORD`: Cookidoo account password
- `COOKIDOO_REGION`: Region (eu, us, etc.)
