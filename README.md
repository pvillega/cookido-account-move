# Cookido Agent

Cookidoo recipe management agent - automates recipe export/import and organization on cookidoo.es.

## Features

- **Export recipes** to JSON with collection metadata
- **AI-powered categorization** using Google Gemini to classify recipes by season and dish type
- **Auto-organize** recipes into structured collections
- **Resume capability** for interrupted long-running operations
- **Dry-run mode** to preview changes before applying
- **Multi-region support** for different Cookidoo country sites

## Installation

```bash
uv sync
```

## Configuration

Set environment variables (via `.envrc.local`):

| Variable | Required | Description |
|----------|----------|-------------|
| `COOKIDOO_USERNAME` | Yes | Cookidoo account email |
| `COOKIDOO_PASSWORD` | Yes | Cookidoo account password |
| `GOOGLE_API_KEY` | For import | Google AI API key (Gemini) |
| `COOKIDOO_REGION` | No | Region code (default: `es`) |

## Usage

### Export Recipes

Export all saved recipes to a JSON file:

```bash
uvx cookido-agent
```

Creates `cookidoo-export-YYYYMMDD-HHMMSS.json` with recipe IDs organized by collection.

### Import & Categorize Recipes

Import recipes from export file with AI-powered categorization:

```bash
uvx cookido-importer
```

This will:
1. Read recipe IDs from the most recent export file
2. Fetch recipe details (name, ingredients)
3. Classify recipes by season and dish type using Gemini AI
4. Create collections and organize recipes

Use `--dry-run` to preview without making changes:

```bash
uvx cookido-importer --dry-run
```

### Organize Collections

Flatten two-level collections to single-level English names:

```bash
uvx cookido-organizer
```

Use `--dry-run` to preview:

```bash
uvx cookido-organizer --dry-run
```

## Command-line Options

| Flag | Commands | Description |
|------|----------|-------------|
| `--region` | All | Override region (es, de, fr, it, uk, us) |
| `--dry-run` | importer, organizer | Preview changes without modifying Cookidoo |

Example with region override:

```bash
uvx cookido-agent --region de
```

## Resume Interrupted Operations

The importer and organizer save state to resume if interrupted:
- `.cookidoo-import-state.json`
- `.cookidoo-organize-state.json`

Simply re-run the command to continue from where it stopped.
