from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "Sentinel"
    database_url: str = "sqlite+aiosqlite:///data/sentinel.db"
    data_dir: Path = Path("/app/data")
    btc_price_api: str = "https://api.coingecko.com/api/v3"
    mempool_api: str = "https://mempool.space/api"
    debug: bool = False

    # Plaid
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # sandbox, development, production

    # Coinbase
    coinbase_api_key: str = ""
    coinbase_api_secret: str = ""

    # Ollama (for receipt parsing LLM)
    ollama_host: str = "ollama"  # Docker service name; use "localhost" for local dev

    model_config = {"env_prefix": "SENTINEL_"}


settings = Settings()
