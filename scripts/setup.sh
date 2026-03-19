#!/bin/bash
# JobFlow — Local Setup Script
# Run this once to set up the development environment.

set -e

echo "=== JobFlow Setup ==="

# 1. Check prerequisites
echo ""
echo "[1/6] Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker not installed. Install from https://docker.com"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: Python 3 not installed"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not installed. Install via nvm"; exit 1; }
echo "  Docker: $(docker --version)"
echo "  Python: $(python3 --version)"
echo "  Node:   $(node --version)"

# 2. Create .env from example
echo ""
echo "[2/6] Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env — EDIT THIS FILE with your Groq API key!"
    echo "  Get a free key at: https://console.groq.com/keys"
else
    echo "  .env already exists, skipping"
fi

# 3. Start database + redis
echo ""
echo "[3/6] Starting PostgreSQL + Redis..."
docker compose up -d db redis
echo "  Waiting for database..."
sleep 5

# 4. Set up Python backend
echo ""
echo "[4/6] Setting up Python backend..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Install Playwright browsers
playwright install chromium
cd ..

# 5. Set up Next.js frontend
echo ""
echo "[5/6] Setting up Next.js frontend..."
cd frontend
npm install
cd ..

# 6. Create upload directories
echo ""
echo "[6/6] Creating directories..."
mkdir -p uploads/resumes

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "To start the backend:"
echo "  cd backend && source venv/bin/activate"
echo "  uvicorn app.main:app --reload --port 8000"
echo ""
echo "To start the frontend:"
echo "  cd frontend && npm run dev"
echo ""
echo "Or use Docker Compose for everything:"
echo "  docker compose up"
echo ""
echo "API docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"
echo ""
echo "IMPORTANT: Edit .env with your Groq API key first!"
echo "  Get a free key at: https://console.groq.com/keys"
