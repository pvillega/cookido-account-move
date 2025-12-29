"""Collection management for Cookidoo.

Handles creating collections and adding recipes, with idempotency
to avoid duplicates on resume.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from .models import DishType, Season, get_collection_name

if TYPE_CHECKING:
    from cookidoo_api import Cookidoo


class CollectionManager:
    """Manages Cookidoo custom collections."""

    def __init__(self, cookidoo: Cookidoo) -> None:
        """Initialize with Cookidoo client."""
        self.cookidoo = cookidoo
        self._collections_cache: dict[str, str] = {}  # name -> collection_id
        self._collection_recipes: dict[str, set[str]] = {}  # collection_id -> recipe_ids

    async def load_existing_collections(self) -> None:
        """Load and cache existing custom collections.

        Call this before ensure_collection to avoid creating duplicates.
        """
        print("Loading existing collections...", file=sys.stderr)

        # Get count first
        count_info = await self.cookidoo.count_custom_collections()
        total_pages = count_info.total_pages if hasattr(count_info, "total_pages") else 1

        # Fetch all pages
        for page in range(total_pages):
            collections = await self.cookidoo.get_custom_collections(page)
            for col in collections:
                name = getattr(col, "name", None) or getattr(col, "title", "")
                col_id = getattr(col, "id", None)
                if name and col_id:
                    self._collections_cache[name] = col_id

                    # Also track which recipes are already in the collection
                    recipe_ids = self._extract_recipe_ids(col)
                    self._collection_recipes[col_id] = set(recipe_ids)

        print(
            f"Found {len(self._collections_cache)} existing collections",
            file=sys.stderr,
        )

    def _extract_recipe_ids(self, collection) -> list[str]:
        """Extract recipe IDs from a collection object."""
        recipe_ids = []
        if hasattr(collection, "chapters"):
            for chapter in collection.chapters:
                if hasattr(chapter, "recipes"):
                    for recipe in chapter.recipes:
                        if hasattr(recipe, "id"):
                            recipe_ids.append(recipe.id)
        return recipe_ids

    async def ensure_collection(self, name: str) -> str:
        """Get or create a collection by name, returning its ID.

        Args:
            name: Collection name (e.g., "🌸 Primavera > Sopas")

        Returns:
            Collection ID
        """
        # Check cache first
        if name in self._collections_cache:
            return self._collections_cache[name]

        # Create new collection
        print(f"Creating collection: {name}", file=sys.stderr)
        new_col = await self.cookidoo.add_custom_collection(name)

        col_id = getattr(new_col, "id", None)
        if col_id:
            self._collections_cache[name] = col_id
            self._collection_recipes[col_id] = set()

        return col_id

    async def add_recipes_to_collection(
        self,
        collection_id: str,
        recipe_ids: list[str],
    ) -> int:
        """Add recipes to a collection, skipping those already present.

        Args:
            collection_id: Target collection ID
            recipe_ids: Recipe IDs to add

        Returns:
            Number of recipes actually added (excluding skipped)
        """
        # Get already-added recipes for this collection
        existing = self._collection_recipes.get(collection_id, set())

        # Filter to only new recipes
        new_ids = [rid for rid in recipe_ids if rid not in existing]

        if not new_ids:
            return 0

        # Add in batches (Cookidoo may have limits)
        batch_size = 50
        added_count = 0

        for i in range(0, len(new_ids), batch_size):
            batch = new_ids[i : i + batch_size]
            try:
                await self.cookidoo.add_recipes_to_custom_collection(
                    collection_id,
                    batch,
                )
                # Update cache
                self._collection_recipes.setdefault(collection_id, set()).update(batch)
                added_count += len(batch)
            except Exception as e:
                print(f"Error adding recipes to collection: {e}", file=sys.stderr)

        return added_count

    def get_collection_id(self, name: str) -> str | None:
        """Get collection ID by name from cache."""
        return self._collections_cache.get(name)

    def is_recipe_in_collection(self, collection_id: str, recipe_id: str) -> bool:
        """Check if a recipe is already in a collection."""
        return recipe_id in self._collection_recipes.get(collection_id, set())

    async def delete_collection(self, collection_id: str) -> bool:
        """Delete a custom collection.

        Args:
            collection_id: ID of the collection to delete

        Returns:
            True if deleted successfully
        """
        try:
            await self.cookidoo.remove_custom_collection(collection_id)

            # Remove from caches
            name_to_remove = None
            for name, cid in self._collections_cache.items():
                if cid == collection_id:
                    name_to_remove = name
                    break
            if name_to_remove:
                del self._collections_cache[name_to_remove]

            if collection_id in self._collection_recipes:
                del self._collection_recipes[collection_id]

            return True
        except Exception as e:
            print(f"Error deleting collection {collection_id}: {e}", file=sys.stderr)
            return False

    async def remove_recipe_from_collection(
        self,
        collection_id: str,
        recipe_id: str,
    ) -> bool:
        """Remove a recipe from a collection.

        Args:
            collection_id: Target collection ID
            recipe_id: Recipe ID to remove

        Returns:
            True if removed successfully
        """
        try:
            await self.cookidoo.remove_recipe_from_custom_collection(
                collection_id,
                recipe_id,
            )
            # Update cache
            if collection_id in self._collection_recipes:
                self._collection_recipes[collection_id].discard(recipe_id)
            return True
        except Exception as e:
            print(
                f"Error removing recipe {recipe_id} from {collection_id}: {e}",
                file=sys.stderr,
            )
            return False


async def organize_recipes_into_collections(
    cookidoo: Cookidoo,
    classifications: dict[str, dict],
    assigned_recipes: set[str],
    on_collection_complete: callable | None = None,
) -> tuple[dict[str, str], set[str]]:
    """Organize classified recipes into collections.

    Args:
        cookidoo: Cookidoo API client
        classifications: Dict mapping recipe_id -> classification dict
        assigned_recipes: Set of already-assigned recipe IDs (for resume)
        on_collection_complete: Optional callback after each collection

    Returns:
        Tuple of (created_collections dict, updated assigned_recipes set)
    """
    manager = CollectionManager(cookidoo)
    await manager.load_existing_collections()

    # Group recipes by Season > DishType
    groups: dict[str, list[str]] = {}
    for recipe_id, classification in classifications.items():
        if recipe_id in assigned_recipes:
            continue

        try:
            season = Season(classification["season"])
            dish_type = DishType(classification["dish_type"])
            collection_name = get_collection_name(season, dish_type)
            groups.setdefault(collection_name, []).append(recipe_id)
        except (KeyError, ValueError) as e:
            print(f"Warning: Invalid classification for {recipe_id}: {e}", file=sys.stderr)

    # Create collections and add recipes
    created_collections: dict[str, str] = {}
    new_assigned: set[str] = set()

    for collection_name, recipe_ids in sorted(groups.items()):
        print(
            f"Processing: {collection_name} ({len(recipe_ids)} recipes)",
            file=sys.stderr,
        )

        # Ensure collection exists
        collection_id = await manager.ensure_collection(collection_name)
        created_collections[collection_name] = collection_id

        # Add recipes
        added = await manager.add_recipes_to_collection(collection_id, recipe_ids)
        new_assigned.update(recipe_ids)

        print(f"  Added {added} recipes", file=sys.stderr)

        if on_collection_complete:
            on_collection_complete(collection_name, recipe_ids)

    return created_collections, assigned_recipes | new_assigned
