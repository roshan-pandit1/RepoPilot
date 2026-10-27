"""Create a local ignored .env without printing credentials or replacing existing values."""
import secrets
from pathlib import Path

path = Path(".env")
with path.open("x") as stream:
    path.chmod(0o600)
    stream.write(
        "APP_ENV=development\nDEMO_AUTH_ENABLED=true\n"
        "POSTGRES_USER=repopilot\nPOSTGRES_DB=repopilot\n"
        f"POSTGRES_PASSWORD={secrets.token_hex(24)}\n"
        f"GITHUB_WEBHOOK_SECRET={secrets.token_hex(32)}\n"
        f"DEMO_API_TOKEN={secrets.token_hex(32)}\n"
    )
print("Created .env with fresh local credentials; keep this file private.")
