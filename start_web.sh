#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/web"

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

if [ ! -d "dist" ]; then
    echo "Building React app..."
    npm run build
fi

echo "Starting G13 Web GUI on port 3113..."
echo "Open http://$(hostname -I | awk '{print $1}'):3113 in your browser"
echo ""
node server.js
