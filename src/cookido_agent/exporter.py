"""Cookidoo recipe exporter.

Exports all saved recipes (managed collections + custom collections) from Cookidoo
to a JSON file containing recipe IDs for later import.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import aiohttp
from cookidoo_api import Cookidoo, CookidooConfig, CookidooLocalizationConfig


def get_spanish_config(email: str, password: str) -> CookidooConfig:
    """Create configuration for Spanish Cookidoo site."""
    localization = CookidooLocalizationConfig(
        country_code="es",
        language="es-ES",
        url="https://cookidoo.es/foundation/es-ES",
    )
    return CookidooConfig(
        email=email,
        password=password,
        localization=localization,
    )


async def fetch_all_pages(
    fetch_func,
    count_func,
) -> list[Any]:
    """Fetch all pages of a paginated resource."""
    count_info = await count_func()
    total_pages = count_info.total_pages if hasattr(count_info, "total_pages") else 1

    all_items = []
    for page in range(total_pages):
        items = await fetch_func(page)
        all_items.extend(items)

    return all_items


def extract_recipe_ids_from_collection(collection: Any) -> list[str]:
    """Extract recipe IDs from a collection object."""
    recipe_ids = []

    # Handle collections with chapters structure
    if hasattr(collection, "chapters"):
        for chapter in collection.chapters:
            if hasattr(chapter, "recipes"):
                for recipe in chapter.recipes:
                    if hasattr(recipe, "id"):
                        recipe_ids.append(recipe.id)

    return recipe_ids


async def export_recipes(email: str, password: str) -> dict[str, Any]:
    """Export all saved recipes from Cookidoo.

    Returns a dict with:
    - exported_at: ISO timestamp
    - locale: es-ES
    - all_recipes: flat list of all recipe IDs
    - favorites: recipe IDs from managed collections (subscribed official collections)
    - collections: dict mapping collection name to list of recipe IDs
    """
    config = get_spanish_config(email, password)

    async with aiohttp.ClientSession() as session:
        cookidoo = Cookidoo(session, config)

        # Login with headful browser mode for CAPTCHA handling
        print("Logging in to Cookidoo...", file=sys.stderr)
        await cookidoo.login()
        print("Login successful!", file=sys.stderr)

        # Fetch managed collections (subscribed official collections)
        print("Fetching managed collections...", file=sys.stderr)
        managed_collections = await fetch_all_pages(
            cookidoo.get_managed_collections,
            cookidoo.count_managed_collections,
        )

        # Fetch custom collections (user-created lists)
        print("Fetching custom collections...", file=sys.stderr)
        custom_collections = await fetch_all_pages(
            cookidoo.get_custom_collections,
            cookidoo.count_custom_collections,
        )

        # Build the export data structure
        all_recipe_ids: set[str] = set()
        favorite_ids: list[str] = []
        collections_data: dict[str, list[str]] = {}

        # Process managed collections (these are like "favorites")
        for collection in managed_collections:
            recipe_ids = extract_recipe_ids_from_collection(collection)
            favorite_ids.extend(recipe_ids)
            all_recipe_ids.update(recipe_ids)

            # Also store by collection name
            name = getattr(collection, "name", None) or getattr(collection, "title", "Unknown")
            if recipe_ids:
                collections_data[f"[Managed] {name}"] = recipe_ids

        # Process custom collections
        for collection in custom_collections:
            recipe_ids = extract_recipe_ids_from_collection(collection)
            all_recipe_ids.update(recipe_ids)

            name = getattr(collection, "name", None) or getattr(collection, "title", "Unknown")
            if recipe_ids:
                collections_data[f"[Custom] {name}"] = recipe_ids

        print(f"Found {len(all_recipe_ids)} unique recipes", file=sys.stderr)

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "locale": "es-ES",
            "all_recipes": sorted(all_recipe_ids),
            "favorites": sorted(set(favorite_ids)),
            "collections": collections_data,
        }


def main() -> None:
    """CLI entry point for uvx."""
    # Get credentials from environment
    email = os.environ.get("COOKIDOO_USERNAME")
    password = os.environ.get("COOKIDOO_PASSWORD")

    if not email or not password:
        print(
            "Error: COOKIDOO_USERNAME and COOKIDOO_PASSWORD environment variables must be set",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # Run the async export
        result = asyncio.run(export_recipes(email, password))

        # Generate output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"cookidoo-export-{timestamp}.json"

        # Write JSON output
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"Exported {len(result['all_recipes'])} recipes to {filename}")

    except KeyboardInterrupt:
        print("\nExport cancelled", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
