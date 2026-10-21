from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    bot_token: str
    database_url: str
    session_days: int = 90
    init_data_max_age: int = 86400  # seconds; Telegram's own recommendation is up to 1 day
    allowed_origins: str = ""       # comma separated
    registration_mode: str = "open"  # open = anyone, code = needs INVITE_CODE, list = only allowed_students
    invite_code: str = ""
    admin_username: str = ""
    admin_password: str = ""  # secret; never commit real credentials
    dev_mode: bool = False  # LOCAL TESTING ONLY: accepts fake "dev:<id>:<username>:<name>" initData. Never enable in production.


settings = Settings()
