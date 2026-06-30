#!/usr/bin/env python3
"""Quick test script for the Skippo API.

No credentials needed — the API works with just the Basic auth credential
that is scraped dynamically from the Skippo web app JS bundle.

Usage:
    python3 test_skippo.py                    # fetch all vessels, show first 30
    python3 test_skippo.py --target NO        # change region (SE/NO/DK/FI)
    python3 test_skippo.py --vessel 265023580 # full detail for a specific vessel
    python3 test_skippo.py --limit 0          # show all moving vessels (no cap)
"""

import argparse
import asyncio
import base64
import json
import re
import sys

import aiohttp

API_BASE = "https://boat-data-service.skippo.io"

# Fallback — used only if live scraping fails
_BASIC_FALLBACK = "d2ViQ2xpZW50OndrRGRHa0dqaEtpRnV2TjQ1eA=="


async def fetch_basic_auth(session: aiohttp.ClientSession) -> str:
    """Scrape the Skippo web app JS bundle to get the current Basic auth credential."""
    try:
        async with session.get("https://www.skippo.se/plan") as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            html = await resp.text()

        chunk_paths = list(set(re.findall(r'/(?:plan/)?_next/static/chunks/[^\s"\']+\.js', html)))
        pat1 = re.compile(r'concat\("webClient",":"\)\.concat\("([^"]+)"\)')
        pat2 = re.compile(r'btoa\("webClient:([^"]+)"\)')

        async def _check(path: str) -> str | None:
            try:
                async with session.get(f"https://www.skippo.se{path}") as r:
                    if r.status != 200:
                        return None
                    text = await r.text()
                    for pat in [pat1, pat2]:
                        m = pat.search(text)
                        if m:
                            return m.group(1)
            except aiohttp.ClientError:
                pass
            return None

        results = await asyncio.gather(*[_check(p) for p in chunk_paths])
        secret = next((r for r in results if r), None)
        if secret:
            b64 = base64.b64encode(f"webClient:{secret}".encode()).decode()
            print(f"  Basic auth scraped from JS bundle")
            return b64
    except Exception as exc:
        print(f"  Warning: scraping failed ({exc}), using fallback")

    print("  Warning: using hardcoded fallback Basic auth credential")
    return _BASIC_FALLBACK


def _headers(basic: str, target: str | None = None) -> dict:
    h = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://www.skippo.se",
        "referer": "https://www.skippo.se/",
        "authorization": f"Basic {basic}",
    }
    if target:
        h["target"] = target
    return h


async def fetch_mapall(
    session: aiohttp.ClientSession, basic: str, target: str
) -> list[dict] | None:
    try:
        async with session.get(
            f"{API_BASE}/data/mapAll",
            headers=_headers(basic, target),
        ) as resp:
            print(f"  HTTP {resp.status}")
            if resp.status == 200:
                vessels = await resp.json(content_type=None)
                print(f"  {len(vessels)} vessels found")
                return vessels
            body = await resp.text()
            print(f"  Error body: {body[:120]}")
            return None
    except aiohttp.ClientError as err:
        print(f"  Connection error: {err}")
        return None


async def fetch_detail(
    session: aiohttp.ClientSession, basic: str, vessel_id: str
) -> dict | None:
    async with session.get(
        f"{API_BASE}/data/2412/{vessel_id}",
        headers=_headers(basic),
    ) as resp:
        if resp.status != 200:
            print(f"    detail {vessel_id} → HTTP {resp.status}")
            return None
        return await resp.json(content_type=None)


def vessel_name_from_detail(detail: dict) -> str:
    name = detail.get("name")
    if name:
        return name
    profiles = detail.get("user", {}).get("boatProfiles", [])
    if profiles:
        return (
            profiles[0].get("boatName")
            or profiles[0].get("userAddedBrandName")
            or "—"
        )
    return detail.get("user", {}).get("displayName") or "—"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Skippo API test (no credentials needed)")
    parser.add_argument("--target", default="SE", choices=["SE", "NO", "DK", "FI"])
    parser.add_argument("--vessel", help="Fetch full detail for this vessel ID")
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Max moving vessels to fetch detail for (default 10, 0=all)",
    )
    args = parser.parse_args()

    async with aiohttp.ClientSession() as session:
        print("Fetching Basic auth credential from Skippo JS bundle ...")
        basic = await fetch_basic_auth(session)

        print(f"\nFetching mapAll (target={args.target}) ...")
        vessels = await fetch_mapall(session, basic, args.target)

        if vessels is None:
            print("  mapAll unavailable — check network connection.")
            if args.vessel:
                print(f"\nTrying detail endpoint for {args.vessel} ...")
                detail = await fetch_detail(session, basic, args.vessel)
                if detail:
                    print(json.dumps(detail, indent=2, ensure_ascii=False))
            sys.exit(1)

        # Sort: moving first
        vessels.sort(key=lambda v: (-v.get("s", 0), v["id"]))

        print(f"\n{'ID':<30} {'Lat':>10} {'Lon':>10} {'Course':>7} {'Moving':>7} {'Anchored':>9}")
        print("-" * 80)
        for v in vessels[:30]:
            moving = "yes" if v.get("s") == 1 else "no"
            anchored = "yes" if v.get("a") else "no"
            course = f"{v['c']:.1f}°" if v.get("c", -1) != -1 else "—"
            print(f"{v['id']:<30} {v['lat']:>10.5f} {v['lon']:>10.5f} {course:>7} {moving:>7} {anchored:>9}")
        if len(vessels) > 30:
            print(f"  ... {len(vessels) - 30} more")

        # Fetch detail for moving vessels to get names and speed
        moving = [v for v in vessels if v.get("s") == 1]
        cap = args.limit if args.limit > 0 else len(moving)
        sample = moving[:cap]

        if sample:
            print(f"\nFetching detail for {len(sample)} moving vessel(s) ...")
            print(f"\n{'ID':<30} {'Name':<25} {'Speed (kn)':>10} {'Course':>8} {'Call':>10}")
            print("-" * 90)
            for v in sample:
                detail = await fetch_detail(session, basic, v["id"])
                if detail:
                    loc = detail.get("location", {})
                    name = vessel_name_from_detail(detail)
                    speed = loc.get("speed")
                    course = loc.get("course")
                    call = detail.get("aisData", {}).get("callSign") or "—"
                    speed_str = f"{speed:.2f}" if speed is not None else "—"
                    course_str = f"{course:.1f}°" if course is not None else "—"
                    print(f"{v['id']:<30} {name:<25} {speed_str:>10} {course_str:>8} {call:>10}")

        if args.vessel:
            print(f"\n--- Full detail for vessel {args.vessel} ---")
            detail = await fetch_detail(session, basic, args.vessel)
            if detail:
                print(json.dumps(detail, indent=2, ensure_ascii=False))
            else:
                print("Not found.")


if __name__ == "__main__":
    asyncio.run(main())
