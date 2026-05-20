from pydantic_settings import BaseSettings

class Settings(BaseSettings): #creating own class name and inherit from base settings
    #this base settings give us to auto red from .env files
    SUPABASE_URL: str
    SUPABASE_KEY: str 
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    SAP_BASE_URL: str = ""
    SAP_USERNAME: str = ""
    SAP_PASSWORD: str = ""
    E2OPEN_BASE_URL: str = ""
    E2OPEN_API_KEY: str = ""
    SAP_MOCK: bool = True 
    E2OPEN_MOCK: bool = True 
    SUPERFEEDR_TOKEN : str = ""
    GAZETTE_RSS_URL: str = ""

    class Config: #base settings look for inner config file
        # so you need to tell where is it
        env_file = "../.env"

settings = Settings()