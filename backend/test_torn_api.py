"""Samm 4: Torn API ühenduse test. Käivita: python test_torn_api.py"""
import asyncio
import sys
import os

# Luba .env laadimine
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from services.torn_api import validate_api_key, fetch_basic_profile, TornAPIError

OUR_KEY = os.getenv("OUR_TORN_API_KEY", "")

async def main():
    if not OUR_KEY:
        print("OUR_TORN_API_KEY puudub .env failist — sisesta testiks käsitsi:")
        test_key = input("API võti: ").strip()
    else:
        test_key = OUR_KEY

    print("\n1) Valideerin API võtit...")
    try:
        info = await validate_api_key(test_key)
        print(f"   torn_id      : {info['torn_id']}")
        print(f"   nimi         : {info['name']}")
        print(f"   tase         : {info['level']}")
        print(f"   rank         : {info['rank']}")
        print(f"   access_level : {info['access_level']}")
        print(f"   has_attacks  : {info['has_attacks']}")
        print(f"   has_battlestats: {info['has_battlestats']}")
    except TornAPIError as e:
        print(f"   VIGA: {e}")
        return

    print("\n2) Laen profiili + personalstats...")
    try:
        profile = await fetch_basic_profile(test_key)
        ps = profile.get("personalstats", {})
        print(f"   gymstrength  : {ps.get('gymstrength', 'N/A')}")
        print(f"   gymdefense   : {ps.get('gymdefense', 'N/A')}")
        print(f"   attackswon   : {ps.get('attackswon', 'N/A')}")
        print(f"   xantaken     : {ps.get('xantaken', 'N/A')}")
    except TornAPIError as e:
        print(f"   VIGA: {e}")

    print("\nTorn API test OK!")

asyncio.run(main())
