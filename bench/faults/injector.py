from typing import Any

import httpx

from backend.common.settings import Settings

from .catalogue import Fault


async def set_fault(
    http: httpx.AsyncClient,
    settings: Settings,
    fault: Fault | None,
    *,
    enabled: bool = True,
    seed: int = 19,
) -> None:
    urls = {
        "gateway": settings.demo_gateway_url,
        "inventory": settings.demo_inventory_url,
        "payments": settings.demo_payments_url,
    }
    for service, url in urls.items():
        payload: dict[str, Any] = {"enabled": False, "flag": "", "params": {}, "seed": seed}
        if fault and service == fault.injection["service"]:
            payload = {
                "enabled": enabled,
                "flag": fault.injection["flag"],
                "params": fault.injection["params"],
                "seed": seed,
            }
        additional = fault.injection.get("additional", {}).get(service) if fault else None
        if additional:
            payload = {
                "enabled": enabled,
                "flag": additional["flag"],
                "params": additional["params"],
                "seed": seed,
            }
        response = await http.post(
            url + "/admin/fault",
            json=payload,
            headers={"Authorization": "Bearer " + settings.demo_token.get_secret_value()},
        )
        response.raise_for_status()
