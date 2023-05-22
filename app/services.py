from typing import Sequence

from asyncpg import Pool, Record, Connection


def csrf_token_to_request(csrf_token: str, roblox_token: str):
    def interceptor(request):
        request.headers['X-CSRF-TOKEN'] = csrf_token
        request.headers['Cookies'] = ".ROBLOSECURITY=" + roblox_token

    return interceptor


def set_token(driver, token: str) -> None:
    driver.add_cookie({"name": ".ROBLOSECURITY", "value": token, "domain": "www.roblox.com"})


async def fetch_active_tokens(pool: Pool, model_name: str) -> Sequence[str]:
    async with pool.acquire() as conn:
        conn: Connection
        results: Sequence[Record] = await conn.fetch(f"SELECT token FROM {model_name} WHERE is_active = true")
        tokens = []
        for record in results:
            tokens.append(record.get("token"))
        return tokens


async def mark_as_spent(pool: Pool, token: str, model_name: str) -> None:
    async with pool.acquire() as conn:
        conn: Connection
        async with conn.transaction():
            await conn.execute(f"UPDATE {model_name} SET is_active = false WHERE token = $1", token)
