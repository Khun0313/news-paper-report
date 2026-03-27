"""
OpenAI Codex OAuth authentication.

Reads tokens from the shared Codex CLI auth file at ~/.codex/auth.json.
When tokens expire, refreshes them and updates the shared file so
both Codex CLI and this app stay in sync.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

TOKEN_ENDPOINT = "https://auth.openai.com/oauth/token"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"

# Shared Codex CLI auth file
CODEX_AUTH_PATH = Path.home() / ".codex" / "auth.json"


def _load_codex_auth() -> dict | None:
    """Load the shared Codex CLI auth.json."""
    if not CODEX_AUTH_PATH.exists():
        return None
    return json.loads(CODEX_AUTH_PATH.read_text(encoding="utf-8"))


def _save_codex_auth(data: dict):
    """Write back to the shared Codex CLI auth.json."""
    CODEX_AUTH_PATH.write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


async def _refresh_token(refresh_token: str) -> dict:
    """Refresh the access token via OpenAI's token endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "client_id": CODEX_CLIENT_ID,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()


class CodexAuth:
    """
    Manages OpenAI Codex OAuth authentication using the shared
    ~/.codex/auth.json from the Codex CLI.

    No separate login flow needed — just run `codex` CLI once to authenticate,
    and this app reuses that token with automatic refresh.
    """

    def __init__(self, data_dir: Path | None = None):
        # data_dir kept for interface compatibility but not used for token storage
        self._auth_data: dict | None = None

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        if self._auth_data is None:
            self._auth_data = _load_codex_auth()

        if self._auth_data is None:
            raise RuntimeError(
                "Codex CLI auth not found at ~/.codex/auth.json\n"
                "Run `codex` first to authenticate with your ChatGPT account."
            )

        tokens = self._auth_data.get("tokens", {})
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")

        if not access_token:
            raise RuntimeError(
                "No access_token in ~/.codex/auth.json\n"
                "Run `codex` to re-authenticate."
            )

        # Check if token needs refresh based on last_refresh timestamp
        last_refresh_str = self._auth_data.get("last_refresh", "")
        needs_refresh = False

        if last_refresh_str:
            try:
                last_refresh = datetime.fromisoformat(
                    last_refresh_str.replace("Z", "+00:00")
                )
                elapsed = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                # Refresh if older than 50 minutes (tokens typically last 1 hour)
                if elapsed > 3000:
                    needs_refresh = True
            except (ValueError, TypeError):
                needs_refresh = True
        else:
            needs_refresh = True

        if needs_refresh and refresh_token:
            try:
                new_tokens = await _refresh_token(refresh_token)
                # Update the shared auth.json
                tokens["access_token"] = new_tokens.get("access_token", access_token)
                if "refresh_token" in new_tokens:
                    tokens["refresh_token"] = new_tokens["refresh_token"]
                if "id_token" in new_tokens:
                    tokens["id_token"] = new_tokens["id_token"]
                self._auth_data["tokens"] = tokens
                self._auth_data["last_refresh"] = datetime.now(timezone.utc).isoformat()
                _save_codex_auth(self._auth_data)
                access_token = tokens["access_token"]
                print("Token refreshed successfully.")
            except Exception as e:
                print(f"Warning: Token refresh failed ({e}), using existing token.")

        return access_token

    def is_logged_in(self) -> bool:
        """Check if Codex CLI auth exists."""
        data = _load_codex_auth()
        return data is not None and "tokens" in data
