#!/usr/bin/env bash
# COMPLETE DEPLOYMENT WORKFLOW
# Run this after testing the pipeline locally

set -e

echo "============================================"
echo "🚀 AskMyDocs Deployment Workflow"
echo "============================================"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if git is initialized
if [ ! -d .git ]; then
    echo -e "${YELLOW}[1/5] Initializing Git repository...${NC}"
    git init
    echo -e "${GREEN}✓ Git initialized${NC}"
else
    echo -e "${GREEN}✓ Git repository exists${NC}"
fi

# Add all files
echo -e "${YELLOW}[2/5] Staging files...${NC}"
git add .
echo -e "${GREEN}✓ Files staged${NC}"

# Commit
echo -e "${YELLOW}[3/5] Creating initial commit...${NC}"
git commit -m "🚀 Initial commit: AskMyDocs RAG pipeline" || echo "No changes to commit"
echo -e "${GREEN}✓ Committed${NC}"

# Instructions for next steps
echo ""
echo -e "${YELLOW}[4/5] NEXT: Add GitHub remote${NC}"
echo "------"
echo "1. Create a new repo at: https://github.com/new"
echo "   (Name it: askmydocs)"
echo "   (Do NOT initialize with README/gitignore)"
echo ""
echo "2. Then run these commands:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/askmydocs.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""

echo -e "${YELLOW}[5/5] THEN: Deploy to Streamlit Cloud${NC}"
echo "------"
echo "1. Go to: https://streamlit.io/cloud"
echo "2. Click: 'New app'"
echo "3. Select: Your GitHub repo (askmydocs)"
echo "4. Branch: main"
echo "5. Main file path: app.py"
echo ""
echo "6. Before deploying, click 'Advanced settings' and add:"
echo "   - NVIDIA_API_KEY"
echo "   - QDRANT_URL"
echo "   - QDRANT_API_KEY"
echo ""
echo "7. Deploy!"
echo ""
echo "============================================"
echo "After these steps, your app will be live at:"
echo "https://your-username-askmydocs.streamlit.app"
echo "============================================"
