#!/bin/bash
# Start the Unified Tools Server

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found. Please install Python 3."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is required but not found. Please install pip."
    exit 1
fi

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    echo "Installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
    
    echo "Installing Playwright browsers..."
    playwright install chromium
else
    source venv/bin/activate
fi

# Start the server
echo "Starting Unified Tools Server..."
python main.py
