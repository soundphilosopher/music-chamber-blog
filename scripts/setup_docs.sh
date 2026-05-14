#!/usr/bin/env bash
# 📚 Quick setup script for MkDocs documentation

set -e

echo " Setting up MkDocs documentation..."

# Install documentation dependencies
echo " Installing documentation dependencies..."
pip install -e "."

# Build and serve documentation
echo "󱥊 Building documentation..."
properdocs build

echo "󰖟 Starting documentation server..."
echo "  Documentation will be available at: http://127.0.0.1:8000"
echo "󱉊 Press Ctrl+C to stop the server"
properdocs serve -w .
