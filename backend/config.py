from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str
    jwt_secret: str
    fernet_key: str
    our_torn_api_key: str
    our_torn_id: int
    port: int = 8000
    environment: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
