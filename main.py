from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import secrets
import sqlite3
import os

app = FastAPI(title="SmartAI Cloud Production Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# क्लाउड डेटाबेस सेटअप
def init_db():
    conn = sqlite3.connect("smartai.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            api_key TEXT PRIMARY KEY,
            username TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO keys VALUES (?, ?)", ("sk-my-llama-key-111", "Admin_User"))
    conn.commit()
    conn.close()

init_db()

class ChatRequest(BaseModel):
    model: str = "llama-3.2-3b-preview" # Groq का सुपरफास्ट मॉडल
    messages: list

@app.post("/v1/keys/generate")
async def generate_new_key(username: str = "Developer"):
    random_hex = secrets.token_hex(16)
    new_key = f"sk-smartai-{random_hex[:20]}"
    conn = sqlite3.connect("smartai.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO keys VALUES (?, ?)", (new_key, username))
    conn.commit()
    conn.close()
    return {"status": "success", "api_key": new_key, "owner": username}

@app.post("/v1/chat/completions")
async def chat_with_llama(request: ChatRequest, token: HTTPAuthorizationCredentials = Depends(security)):
    user_key = token.credentials
    
    conn = sqlite3.connect("smartai.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM keys WHERE api_key = ?", (user_key,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=403, detail="Invalid SmartAI Key.")
    
    # Groq Cloud API को कॉल करना
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    groq_url = "https://groq.com"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": request.model,
        "messages": request.messages
    }
    
    try:
        response = requests.post(groq_url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)