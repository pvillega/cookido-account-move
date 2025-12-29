"""Recipe classification using Gemini 3 Pro.

Uses Google's Gemini 3 Pro model to classify recipes into
Season and Dish Type categories based on recipe name and ingredients.
"""

from __future__ import annotations

import json
import re
import sys
from typing import TYPE_CHECKING

from google import genai

from .models import DishType, RecipeClassification, RecipeDetails, Season

if TYPE_CHECKING:
    from google.genai import Client

# Classification prompt template
CLASSIFICATION_PROMPT = """You are a culinary expert classifying Spanish Thermomix recipes.

For each recipe, determine:
1. **Season** (best fit): Primavera, Verano, Otoño, Invierno
2. **Dish Type** (primary): Sopas, Ensaladas, Carnes, Pescados, Pastas, Arroces, Postres, Panes, Salsas

Classification rules:
- **Season by ingredients and dish characteristics**:
  - Primavera: Light dishes, fresh vegetables, asparagus, peas, artichokes
  - Verano: Cold soups (gazpacho, salmorejo), salads, light dishes, tomatoes, peppers
  - Otoño: Mushrooms, squash, warm soups, legumes, chestnuts
  - Invierno: Heavy stews, cocidos, hot soups, comfort food, root vegetables

- **Dish Type by primary category**:
  - Sopas: Soups, creams, broths (crema, sopa, caldo, gazpacho, salmorejo)
  - Ensaladas: Salads, cold vegetable dishes
  - Carnes: Meat dishes (pollo, cerdo, ternera, cordero)
  - Pescados: Fish and seafood dishes
  - Pastas: Pasta dishes, noodles
  - Arroces: Rice dishes, risottos, paellas
  - Postres: Desserts, sweets, cakes (bizcocho, tarta, helado, flan)
  - Panes: Breads, doughs, pastries (pan, masa, empanada)
  - Salsas: Sauces, dips, condiments (salsa, alioli, mayonesa)

- When a recipe could fit multiple seasons, choose the MOST representative one
- When a recipe could fit multiple dish types, choose the PRIMARY category

Respond ONLY with a valid JSON array (no markdown, no explanation):
[{"id": "r123", "season": "Verano", "dish_type": "Sopas", "confidence": 0.9}, ...]
"""

# Batch size for API calls (balance cost vs context)
BATCH_SIZE = 20

# Model to use
GEMINI_MODEL = "gemini-3-pro-preview"


class RecipeClassifier:
    """Classifies recipes using Gemini 3 Pro."""

    def __init__(self, api_key: str) -> None:
        """Initialize classifier with Google API key."""
        self.api_key = api_key
        self._client: Client | None = None

    async def classify_batch(
        self,
        recipes: list[RecipeDetails],
    ) -> list[RecipeClassification]:
        """Classify a batch of recipes (up to BATCH_SIZE).

        Args:
            recipes: List of recipe details to classify.

        Returns:
            List of classification results.
        """
        if not recipes:
            return []

        # Build recipes text for prompt
        recipes_text = "\n".join(
            f"- {r.recipe_id}: {r.name} (ingredients: {r.ingredients_summary})"
            for r in recipes
        )

        prompt = f"{CLASSIFICATION_PROMPT}\n\nRecipes to classify:\n{recipes_text}"

        # Call Gemini API
        async with genai.Client(api_key=self.api_key).aio as client:
            response = await client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )

        # Parse JSON response
        response_text = response.text.strip()

        # Handle markdown code blocks if present
        if response_text.startswith("```"):
            # Extract JSON from code block
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
            if match:
                response_text = match.group(1).strip()

        try:
            classifications_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse Gemini response: {e}", file=sys.stderr)
            print(f"Response was: {response_text[:500]}", file=sys.stderr)
            return []

        # Convert to RecipeClassification objects
        results = []
        recipe_map = {r.recipe_id: r for r in recipes}

        for c in classifications_data:
            recipe_id = c.get("id")
            if recipe_id not in recipe_map:
                continue

            try:
                classification = RecipeClassification(
                    recipe_id=recipe_id,
                    recipe_name=recipe_map[recipe_id].name,
                    season=Season(c["season"]),
                    dish_type=DishType(c["dish_type"]),
                    confidence=c.get("confidence", 0.8),
                )
                results.append(classification)
            except (KeyError, ValueError) as e:
                print(
                    f"Warning: Invalid classification for {recipe_id}: {e}",
                    file=sys.stderr,
                )

        return results

    async def classify_all(
        self,
        recipes: list[RecipeDetails],
        on_batch_complete: callable | None = None,
    ) -> list[RecipeClassification]:
        """Classify all recipes in batches.

        Args:
            recipes: All recipes to classify.
            on_batch_complete: Optional callback after each batch.

        Returns:
            List of all classification results.
        """
        all_results = []
        total_batches = (len(recipes) + BATCH_SIZE - 1) // BATCH_SIZE

        for i in range(0, len(recipes), BATCH_SIZE):
            batch = recipes[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1

            print(
                f"Classifying batch {batch_num}/{total_batches} "
                f"({len(batch)} recipes)...",
                file=sys.stderr,
            )

            try:
                results = await self.classify_batch(batch)
                all_results.extend(results)

                if on_batch_complete:
                    on_batch_complete(results)

            except Exception as e:
                print(f"Error classifying batch {batch_num}: {e}", file=sys.stderr)

        return all_results
