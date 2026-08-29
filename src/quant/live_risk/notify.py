"""Best-effort webhook notifications; audit files remain the source of truth."""

from __future__ import annotations

import json
import os
import urllib.request


class WebhookNotifier:
    def __init__(self, environment_variable: str):
        self.environment_variable = environment_variable

    def send(self, event: str, payload: dict) -> bool:
        url = os.environ.get(self.environment_variable)
        if not url:
            return False
        body = json.dumps({"event": event, **payload}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return 200 <= response.status < 300
        except Exception:
            return False
