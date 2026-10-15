from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import secrets
import sqlite3
import os

app = FastAPI(title="SmartAI Commercial Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# 🗄️ डेटाबेस सेटअप (Sign Up यूजर्स और API चाबियाँ दोनों के लिए)
def init_db():
    conn = sqlite3.connect("smartai.db")
    cursor = conn.cursor()
    
    # 1. चाबियों की टेबल
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            api_key TEXT PRIMARY KEY,
            username TEXT
        )
    """)
    
    # 2. यूजर्स रजिस्ट्रेशन टेबल (DeepSeek की तरह)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT
        )
    """)
    
    # डिफ़ॉल्ट एडमिन अकाउंट
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", ("admin@smartai.com", "smartai123"))
    cursor.execute("INSERT OR IGNORE INTO keys VALUES (?, ?)", ("sk-smartai-admin-key", "Admin_User"))
    
    conn.commit()
    conn.close()

init_db()

class AuthRequest(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    model: str = "smartai-private-model"
    messages: list

# 📝 1. DeepSeek जैसा Sign Up एंडपॉइंट (नया यूजर रजिस्टर करने के लिए)
@app.post("/v1/auth/signup")
async def developer_signup(request: AuthRequest):
    conn = sqlite3.connect("smartai.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users VALUES (?, ?)", (request.email, request.password))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered.")
    conn.close()
    return {"status": "success", "message": "User registered successfully!"}

# 🔐 2. Sign In लॉगिन एंडपॉइंट
@app.post("/v1/auth/login")
async def developer_login(request: AuthRequest):
    conn = sqlite3.connect("smartai.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE email = ?", (request.email,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or result[0] != request.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    return {"status": "success", "message": "Authenticated successfully"}

# 🔑 3. चाबी जनरेट करने का एंडपॉइंट
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

# 💬 4. प्राइवेट चैट एंडपॉइंट
@app.post("/v1/chat/completions")
async def chat_with_private_ai(request: ChatRequest, token: HTTPAuthorizationCredentials = Depends(security)):
    user_key = token.credentials
    conn = sqlite3.connect("smartai.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM keys WHERE api_key = ?", (user_key,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid SmartAI Key.")
    
    SMARTAI_SERVER_SECRET = os.getenv("SMARTAI_SERVER_SECRET", "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") 
    gateway_url = "https://groq.com"
    
    headers = {
        "Authorization": f"Bearer {SMARTAI_SERVER_SECRET}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.2-3b-preview",
        "messages": request.messages
    }
    
    try:
        response = requests.post(gateway_url, json=payload, headers=headers)
        res_data = response.json()
        return {
            "id": f"chatcmpl-{secrets.token_hex(12)}",
            "object": "chat.completion",
            "model": "smartai-private-model",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": res_data["choices"][0]["message"]["content"]
                },
                "finish_reason": "stop"
            }]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="SmartAI Core Server Error.")