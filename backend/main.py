from contextlib import asynccontextmanager
# write startup and shutdown events
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# tool that allows frontend to talk to backend
import httpx
# make HTTP requests to Ollama
from supabase import create_client 
# creates your supaabase connection
from config import settings 

@asynccontextmanager
async def lifespan(app: FastAPI):
    # app is a type of fastapi, then declared at below
    await on_startup(app)
    yield

async def on_startup(app:FastAPI):
    app.state.supabase = create_client(settings.SUPABASE_URL,settings.SUPABASE_KEY)
    app.state.supabase_ok = False
    app.state.ollama_ok = False

    try:
        app.state.supabase.table("shipments").select("id").limit(1).execute()
        app.state.supabase_ok =True
        print("connected to Supabase!")
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags",timeout=5)
            if response.status_code == 200:
                # here only checks if its running or not / not connect it thorugh these code
                app.state.ollama_ok = True
                print("Ollama connected")
    except Exception as e:
        print(f"Ollama connection failed:{e}")
    
    try:
        from scheduler import start_scheduler
        start_scheduler(app)
        print("Scheduler started")
    except ImportError:
        print("Scheduler not available yet")

app = FastAPI(title="Nexa AI tariff",version="1.0.0",lifespan=lifespan)
# the lifespan call the function lifespan above

app.add_middleware(
    CORSMiddleware,
    # allow request from frontend
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # allow any http header
)

@app.get("/api/health")
async def health_check():
    return {
        "status":"ok",
        "supabase": app.state.supabase_ok,
        "ollama":app.state.ollama_ok,
        "version":"1.0.0"
    }



