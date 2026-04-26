import httpx

TORN_BASE = "https://api.torn.com"

# Torn API error codes
ERROR_INACTIVE   = 13   # user not active for 7 days
ERROR_LOW_ACCESS = 16   # access level too low
ERROR_PAUSED     = 18   # key is paused


class TornAPIError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Torn API error {code}: {message}")


class TornAccessError(TornAPIError):
    """Access level too low (error 16)."""


class TornKeyPausedError(TornAPIError):
    """Key paused (error 18) — mark paused, do NOT delete."""


class TornUserInactiveError(TornAPIError):
    """User inactive (error 13) — mark inactive, do NOT delete."""


def _check_error(data: dict) -> None:
    if "error" not in data:
        return
    code = data["error"]["code"]
    msg  = data["error"]["error"]
    if code == ERROR_INACTIVE:
        raise TornUserInactiveError(code, msg)
    if code == ERROR_LOW_ACCESS:
        raise TornAccessError(code, msg)
    if code == ERROR_PAUSED:
        raise TornKeyPausedError(code, msg)
    raise TornAPIError(code, msg)


async def fetch_basic_profile(api_key: str) -> dict:
    """Returns the caller's own profile including battlestats if the key permits."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{TORN_BASE}/user/",
            params={"selections": "basic,profile,personalstats,battlestats", "key": api_key},
        )
        data = r.json()
    _check_error(data)
    return data


async def fetch_attacks(api_key: str) -> dict:
    """Returns recent attack logs (used to extract fair_fight training data)."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{TORN_BASE}/user/",
            params={"selections": "attacks", "key": api_key},
        )
        data = r.json()
    _check_error(data)
    return data.get("attacks", {})


async def fetch_player_profile(target_id: int, api_key: str) -> dict:
    """Returns another player's profile for prediction purposes."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{TORN_BASE}/user/{target_id}",
            params={"selections": "profile,personalstats", "key": api_key},
        )
        data = r.json()
    _check_error(data)
    return data


async def validate_api_key(api_key: str) -> dict:
    """Validates an API key and returns player info + access level."""
    async with httpx.AsyncClient(timeout=15) as client:
        profile_r, key_r = await _fetch_parallel(client, api_key)

    _check_error(profile_r)
    _check_error(key_r)

    access_level = key_r.get("access_level", 0)
    return {
        "torn_id":          profile_r["player_id"],
        "name":             profile_r["name"],
        "level":            profile_r["level"],
        "rank":             profile_r.get("rank", ""),
        "access_level":     access_level,
        "has_attacks":      access_level >= 3,
        "has_battlestats":  access_level >= 4,
    }


async def fetch_own_events(api_key: str, limit: int = 100) -> dict:
    """Fetches recent events from our own Torn account (used for payment detection)."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{TORN_BASE}/user/",
            params={"selections": "events", "key": api_key, "limit": limit},
        )
        data = r.json()
    _check_error(data)
    return data.get("events", {})


async def _fetch_parallel(client: httpx.AsyncClient, api_key: str):
    import asyncio
    profile_task = client.get(
        f"{TORN_BASE}/user/",
        params={"selections": "basic,profile", "key": api_key},
    )
    key_task = client.get(
        f"{TORN_BASE}/key/",
        params={"selections": "info", "key": api_key},
    )
    profile_r, key_r = await asyncio.gather(profile_task, key_task)
    return profile_r.json(), key_r.json()
