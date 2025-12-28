# Cookidoo API and automation: A reverse-engineering guide

**Cookidoo has no official public API**—all automation relies on reverse-engineered endpoints from the Android app and web interface. The most robust approach uses the `cookidoo-api` Python library, which handles OAuth2 authentication through Vorwerk's identity system, though CAPTCHA challenges and Terms of Service restrictions present significant hurdles for any automation project.

## Authentication uses OAuth2 with regional Vorwerk identity servers

Cookidoo authenticates through Vorwerk's Customer Identity and Access Management (CIAM) system using OAuth2 token flows. The primary token endpoints are regional:

- **EU**: `https://eu.login.vorwerk.com/oauth2/token`
- **Mobile API**: `https://{region}.tmmobile.vorwerk-digital.com/ciam/auth/token`

Authentication produces **JWT tokens** stored in the `_oauth2_proxy` cookie when using the web interface. All API requests require a Bearer token header:

```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
```

The `cookidoo-api` library handles this automatically using email/password credentials, but **bot detection frequently triggers CAPTCHAs** during automated logins. The library offers two recovery modes: `user_input` (manual CAPTCHA solving in a headful browser) and planned `capsolver` integration.

## Primary tools: cookidoo-api leads a dozen open-source projects

The Python ecosystem offers the most mature options, with **cookidoo-api** being the recommended starting point:

| Project | Language | Stars | Use Case | Status |
|---------|----------|-------|----------|--------|
| cookidoo-api | Python | 61 | Full API access | Active (Oct 2025) |
| cookidump | Python | 172 | Bulk recipe export | Moderate |
| cookiput | Go | 22 | Recipe importing | Active |
| cookidoo-scraper | Node.js | 67 | REST API wrapper | Moderate |

**cookidoo-api** provides async access to recipes, shopping lists, the weekly planner, and subscription status. It powers the official Home Assistant Cookidoo integration (released in HA 2025.1):

```python
from cookidoo_api import Cookidoo
import asyncio

async def main():
    async with Cookidoo(email="your@mail.com", password="secret") as cookidoo:
        await cookidoo.login()
        recipes = await cookidoo.get_recipes()
        shopping_list = await cookidoo.get_ingredient_items()

asyncio.run(main())
```

The library's `/docs/raw-api-requests` directory contains intercepted Android app traffic—invaluable for understanding the current API structure. **cookidump** uses Selenium for browser automation to export up to ~1,000 recipes per run, generating offline HTML indexes. **cookiput** focuses specifically on importing recipes from external sites like Chefkoch.de.

## Recipe data structure follows a consistent JSON schema

Recipes contain these primary fields based on reverse-engineered endpoints:

```json
{
  "recipeId": "r628448",
  "recipeName": "Creamy Pasta",
  "description": "A quick weeknight dinner",
  "imageUrl": "https://assets.tmecosys.com/image/upload/...",
  "locale": "de-DE",
  "totalTime": 2400,
  "prepTime": 1800,
  "yield": { "value": 4, "unitText": "portion" },
  "tools": ["TM6"],
  "compatibleThermomixes": ["TM6", "TM5"],
  "ingredients": [
    { "type": "INGREDIENT", "text": "500g pasta" }
  ],
  "instructions": [
    { "type": "STEP", "text": "Add pasta to mixing bowl" }
  ]
}
```

Time values are in **seconds** (2400 = 40 minutes). Recipes expose additional sub-endpoints for detailed data:

- `/recipeIngredientGroups` — Structured ingredient lists with groupings
- `/recipeStepGroups` — Steps with HTML formatting and step images
- `/recipeNutritionGroups` — Nutritional information
- `/collections` — Associated collections
- `/thermomixes` — Device compatibility

Shopping list responses include recipe metadata, ingredient quantities with unit references, and shopping category classifications for grocery organization.

## Creating custom recipes requires multiple PATCH requests

Custom recipes are created through a **three-step process** using the `/created-recipes/{locale}` endpoint:

```http
# Step 1: Create recipe shell
POST /created-recipes/de-DE HTTP/2
{"recipeName": "My New Recipe"}
# Returns: recipeId

# Step 2: Add ingredients
PATCH /created-recipes/de-DE/{recipeId}
{
  "ingredients": [
    {"type": "INGREDIENT", "text": "500g flour"},
    {"type": "INGREDIENT", "text": "2 eggs"}
  ]
}

# Step 3: Add instructions and metadata
PATCH /created-recipes/de-DE/{recipeId}
{
  "instructions": [{"type": "STEP", "text": "Mix thoroughly"}],
  "tools": ["TM6"],
  "totalTime": 4200,
  "prepTime": 3900,
  "yield": {"value": 4, "unitText": "portion"}
}
```

Adding recipes to collections uses `POST /api/v1/collections/{collectionId}/recipes` with a body of `{"recipeId": "recipe-id"}`. The **cookiput** project implements this workflow for importing recipes from external sites, requiring manual JWT extraction from the browser's `_oauth2_proxy` cookie.

## Bot detection and ToS restrictions limit automation scope

Cookidoo implements **aggressive anti-automation measures**:

- **CAPTCHA challenges** trigger on repeated login attempts, potentially blocking accounts for ~24 hours
- **Rate limiting** is undocumented but observed; cookidump limits exports to 1,000 recipes per run to avoid detection
- **Behavioral analysis** detects automated traffic patterns
- **Layout changes** periodically break scrapers

The Terms of Service **explicitly prohibit** automation. Section 1.1.9 forbids working around technical limitations or modifying Cookidoo. Section 1.3.6 defines unauthorized use as "downloading Content by technical means other than those provided by Cookidoo." The China-specific ToS explicitly prohibits "any robot, spider, screenshots and other programs" for scraping.

**Violations can result in permanent account blocking** (Section 4.2.10), typically after a warning. All open-source tools include disclaimers about potential ToS violations.

## Practical approaches for developers

For **recipe export**, cookidump with Selenium remains the most reliable approach—the user logs in manually, then the script scrapes. For **ongoing integration**, the `cookidoo-api` library with headful browser mode allows manual CAPTCHA solving when needed:

```python
cookidoo = Cookidoo(headful_browser_config)
await cookidoo.login(captcha_recovery_mode="user_input")
```

The **Home Assistant integration** provides a sanctioned path for smart home use cases, exposing shopping lists as to-do entities with 90-second polling. For AI/LLM integration, **mcp-cookidoo** wraps the API as a Model Context Protocol server.

## Conclusion

Cookidoo automation is technically feasible but legally constrained. The `cookidoo-api` library (install via `pip install cookidoo-api`) offers the most complete implementation, with documented raw API requests for those needing to extend it. The key technical challenges are CAPTCHA handling and staying under rate limits—both best addressed through browser automation with human interaction points. Anyone building on these tools should assume the API structure can change without notice and that Vorwerk may take action against automated access.
