"""
FastAPI entry point.
Mounts admin panel at /admin and Chainlit chat at /chat.
/ redirects to /chat.
Run with: uvicorn main:app --host 0.0.0.0 --port 8080
"""
import sys
import os
from pathlib import Path

# Add mcp-server to path so app.py can import insurance_broker_mcp
MCP_SERVER_DIR = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(MCP_SERVER_DIR))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from chainlit.utils import mount_chainlit

from shared.db import init_admin_tables
from admin.router import router as admin_router

# Ensure admin DB tables exist on startup
init_admin_tables()

app = FastAPI(title="Alex Insurance Broker")

# Mount admin panel
app.include_router(admin_router, prefix="/admin")

# Root → redirect to chat
@app.get("/")
async def root_redirect():
    return RedirectResponse("/chat", status_code=302)

# Mount Chainlit at /chat (not / — avoids session/cookie path collision with admin routes)
mount_chainlit(app=app, target="app.py", path="/chat")
