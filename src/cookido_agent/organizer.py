"""Cookidoo collection organizer.

Flattens two-level Spanish category collections (e.g., "Verano > Pescados")
into single-level English collections (e.g., "Seafood"), and removes
auto-suggested recipes from custom lists.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
from cookidoo_api import Cookidoo, CookidooConfig, CookidooLocalizationConfig

from .collections import CollectionManager
from .models import DishType, DishTypeEN, translate_dish_type

# State file for resume capability
STATE_FILE = ".cookidoo-organize-state.json"

# Delay between Cookidoo API calls to avoid rate limiting
COOKIDOO_DELAY_MS = 500

# Regex to match season-prefixed collections
# Matches: "emoji Season > DishType" (e.g., "☀️ Verano > Pescados")
SEASON_PATTERN = re.compile(
    r"^.+\s+(Primavera|Verano|Otoño|Invierno)\s+>\s+(.+)$"
)

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


@dataclass
class OrganizeState:
    """Persisted state for resume capability."""

    export_file: str
    flattened_collections: set[str] = field(default_factory=set)
    created_collections: dict[str, str] = field(default_factory=dict)
    # Track removals per collection: collection_id -> set of removed recipe_ids
    removed_managed_recipes: dict[str, set[str]] = field(default_factory=dict)
    deleted_collections: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "export_file": self.export_file,
            "flattened_collections": list(self.flattened_collections),
            "created_collections": self.created_collections,
            "removed_managed_recipes": {
                k: list(v) for k, v in self.removed_managed_recipes.items()
            },
            "deleted_collections": list(self.deleted_collections),
        }

    @classmethod
    def from_dict(cls, data: dict) -> OrganizeState:
        """Create from dictionary (JSON deserialization)."""
        # Handle both old format (list) and new format (dict)
        removed = data.get("removed_managed_recipes", {})
        if isinstance(removed, list):
            # Old format - convert to empty dict (will re-process)
            removed = {}
        else:
            removed = {k: set(v) for k, v in removed.items()}

        return cls(
            export_file=data["export_file"],
            flattened_collections=set(data.get("flattened_collections", [])),
            created_collections=data.get("created_collections", {}),
            removed_managed_recipes=removed,
            deleted_collections=set(data.get("deleted_collections", [])),
        )


class CollectionOrganizer:
    """Organizes Cookidoo collections by flattening and translating."""

    def __init__(
        self,
        export_file: str,
        email: str,
        password: str,
        region: str = "es",
        dry_run: bool = False,
    ) -> None:
        """Initialize organizer.

        Args:
            export_file: Path to JSON export file with [Managed] Ideas sencillas
            email: Cookidoo account email
            password: Cookidoo account password
            region: Cookidoo region code (es, de, fr, it, uk, us)
            dry_run: If True, preview changes without modifying Cookidoo
        """
        self.export_file = export_file
        self.config = get_cookidoo_config(email, password, region)
        self.dry_run = dry_run
        self.state = self._load_state()
        self.managed_recipes: set[str] = set()

    def _load_state(self) -> OrganizeState:
        """Load state from file or create new."""
        state_path = Path(STATE_FILE)
        if state_path.exists():
            try:
                with open(state_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("export_file") == self.export_file:
                        print("Resuming from saved state...", file=sys.stderr)
                        return OrganizeState.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load state file: {e}", file=sys.stderr)

        return OrganizeState(export_file=self.export_file)

    def _save_state(self) -> None:
        """Persist state for resume capability."""
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, indent=2, ensure_ascii=False)

    def _load_managed_recipes(self) -> None:
        """Load [Managed] Ideas sencillas recipe IDs from export file."""
        print(f"Loading export file: {self.export_file}", file=sys.stderr)
        with open(self.export_file, encoding="utf-8") as f:
            export_data = json.load(f)

        collections = export_data.get("collections", {})
        managed_key = "[Managed] Ideas sencillas"

        if managed_key in collections:
            self.managed_recipes = set(collections[managed_key])
            print(
                f"Found {len(self.managed_recipes)} recipes in [Managed] Ideas sencillas",
                file=sys.stderr,
            )
        else:
            print("No [Managed] Ideas sencillas collection found", file=sys.stderr)

    def _parse_two_level_name(self, name: str) -> tuple[str, DishType] | None:
        """Parse a two-level collection name.

        Args:
            name: Collection name (e.g., "☀️ Verano > Pescados")

        Returns:
            Tuple of (season, dish_type) or None if not matching
        """
        match = SEASON_PATTERN.match(name)
        if not match:
            return None

        season_name, dish_type_name = match.groups()

        # Try to parse dish type
        try:
            dish_type = DishType(dish_type_name)
            return (season_name, dish_type)
        except ValueError:
            return None

    async def run(self) -> None:
        """Main organize workflow."""
        self._load_managed_recipes()

        async with aiohttp.ClientSession() as session:
            cookidoo = Cookidoo(session, self.config)

            # Step 1: Login
            print("Logging in to Cookidoo...", file=sys.stderr)
            await cookidoo.login()
            print("Login successful!", file=sys.stderr)

            # Initialize collection manager
            manager = CollectionManager(cookidoo)
            await manager.load_existing_collections()

            # Step 2: Find and flatten two-level collections
            await self._flatten_collections(manager)

            # Step 3: Remove managed recipes from all custom collections
            await self._remove_managed_recipes(manager)

            # Step 4: Delete old two-level collections
            await self._delete_old_collections(manager)

        self._print_summary()
        print("\nOrganization complete!", file=sys.stderr)

    async def _flatten_collections(self, manager: CollectionManager) -> None:
        """Flatten two-level collections into single-level English ones."""
        print("\nFlattening collections...", file=sys.stderr)

        # Get all collections that need flattening
        collections_to_flatten: list[tuple[str, str, DishType]] = []

        for name, col_id in list(manager._collections_cache.items()):
            if col_id in self.state.flattened_collections:
                continue

            parsed = self._parse_two_level_name(name)
            if parsed:
                season, dish_type = parsed
                collections_to_flatten.append((name, col_id, dish_type))

        if not collections_to_flatten:
            print("No collections to flatten", file=sys.stderr)
            return

        print(
            f"Found {len(collections_to_flatten)} collections to flatten",
            file=sys.stderr,
        )

        for name, col_id, dish_type in collections_to_flatten:
            english_name = translate_dish_type(dish_type).value
            print(f"  {name} -> {english_name}", file=sys.stderr)

            if self.dry_run:
                continue

            # Get recipes from old collection
            recipes = manager._collection_recipes.get(col_id, set())
            if not recipes:
                print(f"    (no recipes to move)", file=sys.stderr)
                self.state.flattened_collections.add(col_id)
                self._save_state()
                continue

            # Ensure target collection exists
            target_id = await manager.ensure_collection(english_name)
            self.state.created_collections[english_name] = target_id

            # Add recipes to target
            added = await manager.add_recipes_to_collection(target_id, list(recipes))
            print(f"    Moved {added} recipes", file=sys.stderr)

            self.state.flattened_collections.add(col_id)
            self._save_state()

            await asyncio.sleep(COOKIDOO_DELAY_MS / 1000)

    async def _remove_managed_recipes(self, manager: CollectionManager) -> None:
        """Remove [Managed] Ideas sencillas recipes from all custom collections."""
        if not self.managed_recipes:
            return

        print("\nRemoving managed recipes from custom collections...", file=sys.stderr)

        # Get all custom collection IDs
        for name, col_id in list(manager._collections_cache.items()):
            # Skip the managed collection itself
            if name == "[Managed] Ideas sencillas":
                continue

            # Skip old two-level collections (they'll be deleted anyway)
            if self._parse_two_level_name(name):
                continue

            # Get recipes in this collection
            collection_recipes = manager._collection_recipes.get(col_id, set())
            to_remove = collection_recipes & self.managed_recipes

            # Skip recipes we've already removed from THIS collection
            already_removed = self.state.removed_managed_recipes.get(col_id, set())
            to_remove -= already_removed

            if not to_remove:
                continue

            print(
                f"  {name}: removing {len(to_remove)} managed recipes",
                file=sys.stderr,
            )

            if self.dry_run:
                continue

            for recipe_id in to_remove:
                success = await manager.remove_recipe_from_collection(col_id, recipe_id)
                if success:
                    self.state.removed_managed_recipes.setdefault(col_id, set()).add(
                        recipe_id
                    )
                    self._save_state()

                await asyncio.sleep(COOKIDOO_DELAY_MS / 1000)

    async def _delete_old_collections(self, manager: CollectionManager) -> None:
        """Delete the old two-level collections that have been flattened."""
        print("\nDeleting old two-level collections...", file=sys.stderr)

        # Find all two-level collections to delete
        to_delete: list[tuple[str, str]] = []

        for name, col_id in list(manager._collections_cache.items()):
            if col_id in self.state.deleted_collections:
                continue

            parsed = self._parse_two_level_name(name)
            if parsed:
                to_delete.append((name, col_id))

        if not to_delete:
            print("No collections to delete", file=sys.stderr)
            return

        print(f"Found {len(to_delete)} collections to delete", file=sys.stderr)

        for name, col_id in to_delete:
            print(f"  Deleting: {name}", file=sys.stderr)

            if self.dry_run:
                continue

            success = await manager.delete_collection(col_id)
            if success:
                self.state.deleted_collections.add(col_id)
                self._save_state()

            await asyncio.sleep(COOKIDOO_DELAY_MS / 1000)

    def _print_summary(self) -> None:
        """Print summary of changes."""
        print("\n" + "=" * 60, file=sys.stderr)
        if self.dry_run:
            print("DRY RUN SUMMARY (no changes made)", file=sys.stderr)
        else:
            print("SUMMARY", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        print(
            f"Collections flattened: {len(self.state.flattened_collections)}",
            file=sys.stderr,
        )
        print(
            f"New collections created: {len(self.state.created_collections)}",
            file=sys.stderr,
        )
        for name in sorted(self.state.created_collections.keys()):
            print(f"  - {name}", file=sys.stderr)

        # Count total removed recipes across all collections
        total_removed = sum(
            len(recipes) for recipes in self.state.removed_managed_recipes.values()
        )
        print(
            f"Managed recipes removed: {total_removed} (from {len(self.state.removed_managed_recipes)} collections)",
            file=sys.stderr,
        )
        print(
            f"Old collections deleted: {len(self.state.deleted_collections)}",
            file=sys.stderr,
        )

        print("=" * 60, file=sys.stderr)


def main() -> None:
    """CLI entry point for uvx."""
    parser = argparse.ArgumentParser(
        description="Organize Cookidoo collections: flatten and translate to English"
    )
    parser.add_argument(
        "export_file",
        help="Path to JSON export file (for [Managed] Ideas sencillas list)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying Cookidoo",
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
    region = args.region or os.environ.get("COOKIDOO_REGION", "es")

    missing = []
    if not email:
        missing.append("COOKIDOO_USERNAME")
    if not password:
        missing.append("COOKIDOO_PASSWORD")

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

    # Type narrowing
    assert email is not None
    assert password is not None

    organizer = CollectionOrganizer(
        export_file=args.export_file,
        email=email,
        password=password,
        region=region,
        dry_run=args.dry_run,
    )

    try:
        asyncio.run(organizer.run())
    except KeyboardInterrupt:
        print("\nOrganization cancelled (state saved for resume)", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
