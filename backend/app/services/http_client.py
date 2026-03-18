from __future__ import annotations

from typing import Any

import requests
from fastapi import HTTPException
from requests.exceptions import RequestException


def fetch_json(
    url: str,
    *,
    timeout: int = 25,
    not_found_detail: str | None = None,
    upstream_error_prefix: str = "Upstream request failed",
) -> Any:
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 404 and not_found_detail:
            raise HTTPException(status_code=404, detail=not_found_detail)
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except RequestException as exc:
        raise HTTPException(status_code=502, detail=f"{upstream_error_prefix}: {exc}") from exc
