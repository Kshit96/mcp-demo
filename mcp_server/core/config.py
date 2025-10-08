from dotenv import load_dotenv
import os

class Config:
    def __init__(self, env_path: str | None = os.path.join(os.path.dirname(__file__), "..", ".env.local")):
        load_dotenv(dotenv_path=env_path)
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.default_api_url = os.getenv("PUBLIC_API_URL", "https://api.github.com")
    
    def __repr__(self) -> str:
        return f"<Config debug = {self.debug}>"