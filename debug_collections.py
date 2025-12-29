#!/usr/bin/env python
"""Debug script to list all collections and check pattern matching."""

import asyncio
import os
import re
import sys

import aiohttp
from cookidoo_api import Cookidoo, CookidooConfig, CookidooLocalizationConfig

SEASON_PATTERN = re.compile(
    r"^.+\s+(Primavera|Verano|Otoño|Invierno)\s+>\s+(.+)$"
)


async def main():
    email = os.environ.get("COOKIDOO_USERNAME")
    password = os.environ.get("COOKIDOO_PASSWORD")

    if not email or not password:
        print("Set COOKIDOO_USERNAME and COOKIDOO_PASSWORD", file=sys.stderr)
        sys.exit(1)

    config = CookidooConfig(
        email=email,
        password=password,
        localization=CookidooLocalizationConfig(
            country_code="es",
            language="es-ES",
            url="https://cookidoo.es/foundation/es-ES",
        ),
    )

    async with aiohttp.ClientSession() as session:
        cookidoo = Cookidoo(session, config)
        await cookidoo.login()
        print("Logged in successfully\n")

        # Get all collections
        count_info = await cookidoo.count_custom_collections()
        total_pages = count_info.total_pages if hasattr(count_info, "total_pages") else 1

        all_collections = []
        for page in range(total_pages):
            collections = await cookidoo.get_custom_collections(page)
            all_collections.extend(collections)

        print(f"Found {len(all_collections)} custom collections:\n")

        matched = []
        unmatched = []

        for col in all_collections:
            name = getattr(col, "name", None) or getattr(col, "title", "")
            col_id = getattr(col, "id", "")

            match = SEASON_PATTERN.match(name)
            if match:
                matched.append((name, col_id, match.groups()))
            else:
                unmatched.append((name, col_id))

        print("=== MATCHED (two-level season collections) ===")
        for name, col_id, groups in matched:
            print(f"  '{name}' -> {groups}")
            print(f"    ID: {col_id}")
            print(f"    Raw: {name.encode('utf-8')}")

        print(f"\n=== UNMATCHED ({len(unmatched)} collections) ===")
        for name, col_id in unmatched:
            print(f"  '{name}'")
            print(f"    ID: {col_id}")
            # Check if it contains season words but didn't match
            if any(s in name for s in ["Verano", "Primavera", "Otoño", "Invierno"]):
                print(f"    *** CONTAINS SEASON WORD BUT DIDN'T MATCH ***")
                print(f"    Raw: {name.encode('utf-8')}")


if __name__ == "__main__":
    asyncio.run(main())
