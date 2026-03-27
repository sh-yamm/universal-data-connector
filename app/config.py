from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Universal Data Connector"
    MAX_RESULTS: int = 10        # default cap on records returned per request
    OPENAI_API_KEY: str = ""     # kept for reference; demo now uses GROQ_API_KEY

    class Config:
        env_file = ".env"        # automatically loaded from .env at startup
        extra = "allow"          # ignore unknown keys in .env (e.g. GROQ_API_KEY)


settings = Settings()
