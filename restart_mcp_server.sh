#!/bin/bash

# Script to restart MCP server with cache clearing

echo "🧹 Clearing Python cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
echo "✅ Cache cleared"

echo "🛑 Killing old MCP server processes..."
pkill -f "mcp_server"
echo "✅ Processes killed"

echo "⏳ Waiting 2 seconds..."
sleep 2

echo "🚀 Starting fresh MCP server..."
python -m src.mcp_server
