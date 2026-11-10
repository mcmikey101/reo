"""HTTP-клиент ML-сервиса. Контракт — docs/ml-contract.md."""

import httpx


async def get_health(base_url: str, timeout: float) -> bool:
    """True, если ML-сервис ответил 200 и {"status": "ok"}."""
    # ML — внутренний сервис: прокси из HTTP(S)_PROXY к нему не применяем
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        response = await client.get(f"{base_url}/health")
    if response.status_code != 200:
        return False
    body = response.json()
    return isinstance(body, dict) and body.get("status") == "ok"
