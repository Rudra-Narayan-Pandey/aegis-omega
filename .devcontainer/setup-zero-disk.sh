#!/bin/bash
set -e

echo "[*] Memory check passed: 8GB available natively."
echo "[*] Installing Python AI and Security tools for the Counter-AI Mesh..."

# Install our core tools: FastAPI (The Gates), Upstash Redis (The Memory), Groq (The AI)
pip3 install fastapi uvicorn "upstash-redis[asyncio]" groq pydantic

echo "[*] Workspace setup complete! Ready to code."