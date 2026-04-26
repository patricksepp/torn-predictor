"""Samm 7: predict endpoint testid. Käivita: python test_predict.py"""
import asyncio, httpx, json, sys

BASE = "http://localhost:8000"
API_KEY = "rUgOaon9CzwhIe2S"

async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:

        # Login → token
        r = await c.post("/api/auth/login", json={"api_key": API_KEY})
        token = r.json()["token"]
        auth = {"Authorization": f"Bearer {token}"}
        print(f"Login OK  role={r.json()['role']}")

        # Test 1: NPC blokeerimine
        r = await c.get("/api/predict/4", headers=auth)
        assert r.status_code == 400, f"Ootasin 400, sain {r.status_code}"
        print(f"T1 NPC blokeerimine: OK  ({r.json()['detail']})")

        # Test 2: Token puudub → 401/403
        r = await c.get("/api/predict/100")
        assert r.status_code in (401, 403), f"Ootasin 401/403, sain {r.status_code}"
        print(f"T2 Token puudub: OK  ({r.status_code})")

        # Test 3: Vale token → 401/403
        r = await c.get("/api/predict/100", headers={"Authorization": "Bearer vale.token.xxx"})
        assert r.status_code in (401, 403), f"Ootasin 401/403, sain {r.status_code}"
        print(f"T3 Vale token: OK  ({r.status_code})")

        # Test 4: Päris ennustus — ennusta oma profiili
        print(f"\nT4 Ennusta mängija 4203249 (LickMyDuck)...")
        r = await c.get("/api/predict/4203249", headers=auth)
        if r.status_code == 200:
            d = r.json()
            tbs = d['predicted_tbs']
            fmt = f"{tbs/1e6:.1f}M" if tbs >= 1_000_000 else f"{tbs/1e3:.0f}K"
            print(f"   target_name    : {d['target_name']}")
            print(f"   predicted_tbs  : {fmt}")
            print(f"   method         : {d['method']}")
            print(f"   confidence     : {d['confidence']}")
            print(f"   from_cache     : {d['from_cache']}")
            print(f"   training_samples: {d['training_samples']}")
        else:
            print(f"   VIGA {r.status_code}: {r.text}")

        # Test 5: Sama päring uuesti → cache'ist
        print(f"\nT5 Sama mängija uuesti (peaks olema cache)...")
        r = await c.get("/api/predict/4203249", headers=auth)
        if r.status_code == 200:
            d = r.json()
            print(f"   from_cache: {d['from_cache']}  (peaks olema True)")
            assert d["from_cache"], "Cache ei toedu!"
            print("   Cache OK!")
        else:
            print(f"   VIGA: {r.text}")

        # Test 6: Ennusta tuntud kõrge-taseme mängijat
        print(f"\nT6 Ennusta mängija 1 (Chedburn - adminn)...")
        r = await c.get("/api/predict/1", headers=auth)
        if r.status_code == 200:
            d = r.json()
            tbs = d['predicted_tbs']
            fmt = f"{tbs/1e6:.1f}M" if tbs >= 1_000_000 else f"{tbs/1e3:.0f}K"
            print(f"   {d['target_name']}: {fmt}  [{d['method']}]")
        else:
            print(f"   {r.status_code}: {r.json().get('detail', r.text)}")

    print("\nKõik testid laabusid!")

asyncio.run(main())
