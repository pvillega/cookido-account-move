"""Data models for Cookidoo recipe importer.

Contains enums for seasons and dish types, plus dataclasses for
recipe classification and import state persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Season(str, Enum):
    """Recipe seasonality classification."""

    SPRING = "Primavera"
    SUMMER = "Verano"
    AUTUMN = "Otoño"
    WINTER = "Invierno"

    @property
    def emoji(self) -> str:
        """Get emoji representation for the season."""
        emoji_map = {
            "Primavera": "\U0001F338",  # Cherry blossom
            "Verano": "\u2600\ufe0f",  # Sun
            "Otoño": "\U0001F342",  # Fallen leaf
            "Invierno": "\u2744\ufe0f",  # Snowflake
        }
        return emoji_map[self.value]


class DishType(str, Enum):
    """Recipe dish type classification (Spanish)."""

    SOPAS = "Sopas"
    ENSALADAS = "Ensaladas"
    CARNES = "Carnes"
    PESCADOS = "Pescados"
    PASTAS = "Pastas"
    ARROCES = "Arroces"
    POSTRES = "Postres"
    PANES = "Panes"
    SALSAS = "Salsas"


class DishTypeEN(str, Enum):
    """Recipe dish type classification (English, culinary terms)."""

    SOUPS = "Soups"
    SALADS = "Salads"
    MEATS = "Meats"
    SEAFOOD = "Seafood"
    PASTA = "Pasta"
    RICE_DISHES = "Rice Dishes"
    DESSERTS = "Desserts"
    BREADS = "Breads"
    SAUCES = "Sauces"


# Translation mapping from Spanish DishType to English DishTypeEN
DISH_TYPE_TRANSLATIONS: dict[DishType, DishTypeEN] = {
    DishType.SOPAS: DishTypeEN.SOUPS,
    DishType.ENSALADAS: DishTypeEN.SALADS,
    DishType.CARNES: DishTypeEN.MEATS,
    DishType.PESCADOS: DishTypeEN.SEAFOOD,
    DishType.PASTAS: DishTypeEN.PASTA,
    DishType.ARROCES: DishTypeEN.RICE_DISHES,
    DishType.POSTRES: DishTypeEN.DESSERTS,
    DishType.PANES: DishTypeEN.BREADS,
    DishType.SALSAS: DishTypeEN.SAUCES,
}


def translate_dish_type(spanish: DishType) -> DishTypeEN:
    """Translate Spanish dish type to English equivalent."""
    return DISH_TYPE_TRANSLATIONS[spanish]


@dataclass
class RecipeClassification:
    """Classification result for a single recipe."""

    recipe_id: str
    recipe_name: str
    season: Season
    dish_type: DishType
    confidence: float = 0.8

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "recipe_id": self.recipe_id,
            "recipe_name": self.recipe_name,
            "season": self.season.value,
            "dish_type": self.dish_type.value,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RecipeClassification:
        """Create from dictionary (JSON deserialization)."""
        return cls(
            recipe_id=data["recipe_id"],
            recipe_name=data["recipe_name"],
            season=Season(data["season"]),
            dish_type=DishType(data["dish_type"]),
            confidence=data.get("confidence", 0.8),
        )


@dataclass
class RecipeDetails:
    """Fetched recipe details for classification."""

    recipe_id: str
    name: str
    ingredients_summary: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "recipe_id": self.recipe_id,
            "name": self.name,
            "ingredients_summary": self.ingredients_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RecipeDetails:
        """Create from dictionary (JSON deserialization)."""
        return cls(
            recipe_id=data["recipe_id"],
            name=data["name"],
            ingredients_summary=data["ingredients_summary"],
        )


@dataclass
class ImportState:
    """Persisted state for resume capability.

    Tracks progress through the import workflow to enable resuming
    after failures or interruptions.
    """

    export_file: str
    fetched_recipes: dict[str, dict] = field(default_factory=dict)
    classifications: dict[str, dict] = field(default_factory=dict)
    created_collections: dict[str, str] = field(default_factory=dict)
    assigned_recipes: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "export_file": self.export_file,
            "fetched_recipes": self.fetched_recipes,
            "classifications": self.classifications,
            "created_collections": self.created_collections,
            "assigned_recipes": list(self.assigned_recipes),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ImportState:
        """Create from dictionary (JSON deserialization)."""
        return cls(
            export_file=data["export_file"],
            fetched_recipes=data.get("fetched_recipes", {}),
            classifications=data.get("classifications", {}),
            created_collections=data.get("created_collections", {}),
            assigned_recipes=set(data.get("assigned_recipes", [])),
        )


def get_collection_name(season: Season, dish_type: DishType) -> str:
    """Generate collection name with emoji prefix (legacy two-level format).

    Format: "🌸 Primavera > Sopas"

    Note: This is the legacy format. Use get_flat_collection_name() for
    the new single-level English format.
    """
    return f"{season.emoji} {season.value} > {dish_type.value}"


def get_flat_collection_name(dish_type: DishType) -> str:
    """Generate flat collection name in English.

    Format: "Seafood" (no season prefix, translated to English)
    """
    english = translate_dish_type(dish_type)
    return english.value
