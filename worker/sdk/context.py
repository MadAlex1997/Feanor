"""ExecutionContext — reads execution parameters from environment variables."""
from __future__ import annotations

import json
import os


class ExecutionContext:
    """Reads execution parameters injected by the dispatcher as env vars."""

    def __init__(self) -> None:
        missing = []
        for var in ("FEANOR_API_URL", "FEANOR_CLIENT_ID", "FEANOR_CLIENT_SECRET",
                    "FEANOR_EXECUTION_ID", "FEANOR_INPUTS"):
            if not os.environ.get(var):
                missing.append(var)
        if missing:
            raise EnvironmentError(
                f"missing required environment variables: {', '.join(missing)}"
            )

        self.api_url: str = os.environ["FEANOR_API_URL"]
        self.client_id: str = os.environ["FEANOR_CLIENT_ID"]
        self.client_secret: str = os.environ["FEANOR_CLIENT_SECRET"]
        self.execution_id: str = os.environ["FEANOR_EXECUTION_ID"]
        self.inputs: dict = json.loads(os.environ["FEANOR_INPUTS"])
