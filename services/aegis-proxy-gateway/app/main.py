from fastapi import FastAPI
from pydantic import BaseModel
import asyncio

app = FastAPI(title="Aegis Outer Gates")

# What the incoming message should look like
class AgentPayload(BaseModel):
    prompt: str

@app.get("/")
def read_root():
    return {"status": "ONLINE", "message": "AegisAgent Omega Gates are secured."}

@app.post("/v1/agent/invoke")
async def invoke_agent(payload: AgentPayload):
    prompt = payload.prompt.lower()
    
    # 1. The Super-Fast Guard Check (Simulating our Semantic Cache)
    if "ignore all previous instructions" in prompt or "hack" in prompt:
        
        # 2. The Quicksand Tarpit (Wasting the hacker's time)
        await asyncio.sleep(2.5) 
        
        # 3. The Fake Treasure
        return {
            "status": "THREAT_DETECTED",
            "action": "ROUTED_TO_HONEYPOT",
            "fake_data_given": "PostgreSQL 15 (Vulnerable)",
            "canary_token": "fake-admin-password-123",
            "tokens_wasted": True
        }
        
    # If the message is safe, let it through
    return {
        "status": "SAFE",
        "action": "ALLOWED",
        "message": "Traffic passed to the safe AI."
    }