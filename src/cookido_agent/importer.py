"""Cookidoo recipe importer with auto-categorization.

Imports recipes from a JSON export file, classifies them using Gemini 3 Pro
into Season > Dish Type categories, and organizes them into Cookidoo
custom collections.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import aiohttp
from cookidoo_api import Cookidoo, CookidooConfig, CookidooLocalizationConfig

from .classifier import RecipeClassifier
from .collections import organize_recipes_into_collections
from .models import (
    DishType,
    ImportState,
    RecipeClassification,
    RecipeDetails,
    Season,
    get_collection_name,
)

# State file for resume capability
STATE_FILE = ".cookidoo-import-state.json"

# Delay between Cookidoo API calls to avoid rate limiting
COOKIDOO_DELAY_MS = 500

# Region configuration mapping
REGION_CONFIG = {
    "es": {
        "country_code": "es",
        "language": "es-ES",
        "url": "https://cookidoo.es/foundation/es-ES",
    },
    "de": {
        "country_code": "de",
        "language": "de-DE",
        "url": "https://cookidoo.de/foundation/de-DE",
    },
    "fr": {
        "country_code": "fr",
        "language": "fr-FR",
        "url": "https://cookidoo.fr/foundation/fr-FR",
    },
    "it": {
        "country_code": "it",
        "language": "it-IT",
        "url": "https://cookidoo.it/foundation/it-IT",
    },
    "uk": {
        "country_code": "uk",
        "language": "en-GB",
        "url": "https://cookidoo.co.uk/foundation/en-GB",
    },
    "us": {
        "country_code": "us",
        "language": "en-US",
        "url": "https://cookidoo.com/foundation/en-US",
    },
}


def get_cookidoo_config(email: str, password: str, region: str) -> CookidooConfig:
    """Create configuration for Cookidoo site based on region."""
    if region not in REGION_CONFIG:
        available = ", ".join(REGION_CONFIG.keys())
        raise ValueError(f"Unknown region '{region}'. Available: {available}")

    config = REGION_CONFIG[region]
    localization = CookidooLocalizationConfig(
        country_code=config["country_code"],
        language=config["language"],
        url=config["url"],
    )
    return CookidooConfig(
        email=email,
        password=password,
        localization=localization,
    )


class RecipeImporter:
    """Imports and categorizes recipes from a JSON export."""

    def __init__(
        self,
        export_file: str,
        email: str,
        password: str,
        google_api_key: str,
        region: str = "es",
        dry_run: bool = False,
    ) -> None:
        """Initialize importer.

        Args:
            export_file: Path to JSON export file
            email: Cookidoo account email
            password: Cookidoo account password
            google_api_key: Google API key for Gemini
            region: Cookidoo region code (es, de, fr, it, uk, us)
            dry_run: If True, classify but don't modify Cookidoo
        """
        self.export_file = export_file
        self.config = get_cookidoo_config(email, password, region)
        self.classifier = RecipeClassifier(google_api_key)
        self.dry_run = dry_run
        self.state = self._load_state()

    def _load_state(self) -> ImportState:
        """Load state from file or create new."""
        state_path = Path(STATE_FILE)
        if state_path.exists():
            try:
                with open(state_path, encoding="utf-8") as f:
                    data = json.load(f)
                    # Only resume if same export file
                    if data.get("export_file") == self.export_file:
                        print("Resuming from saved state...", file=sys.stderr)
                        return ImportState.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load state file: {e}", file=sys.stderr)

        return ImportState(export_file=self.export_file)

    def _save_state(self) -> None:
        """Persist state for resume capability."""
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, indent=2, ensure_ascii=False)

    async def run(self) -> None:
        """Main import workflow."""
        # Load export data
        print(f"Loading export file: {self.export_file}", file=sys.stderr)
        with open(self.export_file, encoding="utf-8") as f:
            export_data = json.load(f)

        recipe_ids = export_data.get("all_recipes", [])
        print(f"Found {len(recipe_ids)} recipes in export", file=sys.stderr)

        if not recipe_ids:
            print("No recipes to import", file=sys.stderr)
            return

        async with aiohttp.ClientSession() as session:
            cookidoo = Cookidoo(session, self.config)

            # Step 1: Login
            print("Logging in to Cookidoo...", file=sys.stderr)
            await cookidoo.login()
            print("Login successful!", file=sys.stderr)

            # Step 2: Fetch recipe details
            await self._fetch_recipe_details(cookidoo, recipe_ids)

            # Step 3: Classify recipes with Gemini
            await self._classify_recipes()

            # Step 4: Create collections and assign recipes
            if not self.dry_run:
                await self._organize_recipes(cookidoo)
            else:
                self._print_dry_run_summary()

        print("\nImport complete!", file=sys.stderr)

    async def _fetch_recipe_details(
        self,
        cookidoo: Cookidoo,
        recipe_ids: list[str],
    ) -> None:
        """Fetch full details for all recipes."""
        # Skip already-fetched recipes
        pending = [
            rid for rid in recipe_ids if rid not in self.state.fetched_recipes
        ]
        total = len(pending)

        if not pending:
            print(
                f"All {len(recipe_ids)} recipes already fetched (resume)",
                file=sys.stderr,
            )
            return

        print(f"Fetching details for {total} recipes...", file=sys.stderr)

        for i, recipe_id in enumerate(pending):
            print(
                f"  Fetching {i + 1}/{total}: {recipe_id}",
                file=sys.stderr,
                end="\r",
            )

            try:
                details = await cookidoo.get_recipe_details(recipe_id)

                # Extract relevant fields
                recipe_data = {
                    "recipe_id": recipe_id,
                    "name": getattr(details, "name", recipe_id),
                    "ingredients_summary": self._summarize_ingredients(details),
                }
                self.state.fetched_recipes[recipe_id] = recipe_data
                self._save_state()

            except Exception as e:
                print(
                    f"\n  Warning: Could not fetch {recipe_id}: {e}",
                    file=sys.stderr,
                )

            # Rate limiting
            await asyncio.sleep(COOKIDOO_DELAY_MS / 1000)

        print(f"\nFetched {len(self.state.fetched_recipes)} recipes", file=sys.stderr)

    def _summarize_ingredients(self, details: Any) -> str:
        """Extract key ingredients for classification."""
        ingredients = []

        # Try different attribute names
        ingredient_list = (
            getattr(details, "ingredients", None)
            or getattr(details, "recipeIngredientGroups", None)
            or []
        )

        if isinstance(ingredient_list, list):
            for item in ingredient_list[:10]:
                # Handle different structures
                if hasattr(item, "text"):
                    text = item.text.split(",")[0]  # Take first part
                    ingredients.append(text)
                elif hasattr(item, "name"):
                    ingredients.append(item.name)
                elif isinstance(item, str):
                    ingredients.append(item.split(",")[0])
                elif hasattr(item, "ingredients"):
                    # Nested ingredient groups
                    for sub in item.ingredients[:5]:
                        if hasattr(sub, "text"):
                            ingredients.append(sub.text.split(",")[0])

        return ", ".join(ingredients[:8]) or "No ingredients found"

    async def _classify_recipes(self) -> None:
        """Classify all recipes using Gemini in batches."""
        # Get recipes that need classification
        pending_recipes = [
            RecipeDetails.from_dict(r)
            for rid, r in self.state.fetched_recipes.items()
            if rid not in self.state.classifications
        ]

        if not pending_recipes:
            print(
                f"All {len(self.state.classifications)} recipes already classified (resume)",
                file=sys.stderr,
            )
            return

        print(f"Classifying {len(pending_recipes)} recipes...", file=sys.stderr)

        def on_batch_complete(results: list[RecipeClassification]) -> None:
            for c in results:
                self.state.classifications[c.recipe_id] = c.to_dict()
            self._save_state()

        await self.classifier.classify_all(
            pending_recipes,
            on_batch_complete=on_batch_complete,
        )

        print(
            f"Classified {len(self.state.classifications)} recipes",
            file=sys.stderr,
        )

    async def _organize_recipes(self, cookidoo: Cookidoo) -> None:
        """Create collections and add recipes."""
        print("Organizing recipes into collections...", file=sys.stderr)

        def on_collection_complete(_name: str, _recipe_ids: list[str]) -> None:
            self._save_state()

        created, assigned = await organize_recipes_into_collections(
            cookidoo,
            self.state.classifications,
            self.state.assigned_recipes,
            on_collection_complete=on_collection_complete,
        )

        self.state.created_collections.update(created)
        self.state.assigned_recipes = assigned
        self._save_state()

        print(
            f"\nCreated/updated {len(created)} collections",
            file=sys.stderr,
        )
        print(
            f"Assigned {len(assigned)} recipes total",
            file=sys.stderr,
        )

    def _print_dry_run_summary(self) -> None:
        """Print what would be done without making changes."""
        print("\n" + "=" * 60, file=sys.stderr)
        print("DRY RUN SUMMARY", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        # Group by collection
        groups: dict[str, list[str]] = {}
        for recipe_id, classification in self.state.classifications.items():
            try:
                season = Season(classification["season"])
                dish_type = DishType(classification["dish_type"])
                collection_name = get_collection_name(season, dish_type)
                recipe_name = self.state.fetched_recipes.get(
                    recipe_id, {}
                ).get("name", recipe_id)
                groups.setdefault(collection_name, []).append(recipe_name)
            except (KeyError, ValueError):
                pass

        # Print summary
        for collection_name, recipes in sorted(groups.items()):
            print(f"\n{collection_name} ({len(recipes)} recipes):", file=sys.stderr)
            for name in recipes[:5]:
                print(f"  - {name}", file=sys.stderr)
            if len(recipes) > 5:
                print(f"  ... and {len(recipes) - 5} more", file=sys.stderr)

        print("\n" + "=" * 60, file=sys.stderr)
        print(
            f"Total: {len(groups)} collections, "
            f"{len(self.state.classifications)} recipes",
            file=sys.stderr,
        )
        print("Run without --dry-run to apply changes", file=sys.stderr)


def main() -> None:
    """CLI entry point for uvx."""
    parser = argparse.ArgumentParser(
        description="Import Cookidoo recipes with auto-categorization"
    )
    parser.add_argument(
        "export_file",
        help="Path to JSON export file from cookido-agent",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview classification without modifying Cookidoo",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="Cookidoo region (es, de, fr, it, uk, us). Overrides COOKIDOO_REGION env var.",
    )
    args = parser.parse_args()

    # Get credentials from environment
    email = os.environ.get("COOKIDOO_USERNAME")
    password = os.environ.get("COOKIDOO_PASSWORD")
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    region = args.region or os.environ.get("COOKIDOO_REGION", "es")

    missing = []
    if not email:
        missing.append("COOKIDOO_USERNAME")
    if not password:
        missing.append("COOKIDOO_PASSWORD")
    if not google_api_key:
        missing.append("GOOGLE_API_KEY")

    if missing:
        print(
            f"Error: Missing environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate export file exists
    if not Path(args.export_file).exists():
        print(f"Error: Export file not found: {args.export_file}", file=sys.stderr)
        sys.exit(1)

    # Type narrowing: at this point we know these are not None
    assert email is not None
    assert password is not None
    assert google_api_key is not None

    importer = RecipeImporter(
        export_file=args.export_file,
        email=email,
        password=password,
        google_api_key=google_api_key,
        region=region,
        dry_run=args.dry_run,
    )

    try:
        asyncio.run(importer.run())
    except KeyboardInterrupt:
        print("\nImport cancelled (state saved for resume)", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
