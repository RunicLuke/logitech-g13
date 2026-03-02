#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
echo "Starting G13 daemon..."
echo "Use Ctrl+C to stop"
echo ""
echo "While running, use these CLI commands in another terminal:"
echo "  bash $SCRIPT_DIR/g13cmd.sh lcd \"Hello World\""
echo "  bash $SCRIPT_DIR/g13cmd.sh color red"
echo "  bash $SCRIPT_DIR/g13cmd.sh mode clock"
echo "  bash $SCRIPT_DIR/g13cmd.sh mode stats"
echo "  bash $SCRIPT_DIR/g13cmd.sh reload"
echo ""
sudo venv/bin/python3 -m g13.daemon
