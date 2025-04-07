@echo off
echo Installing OtherTales Tools dependencies...

python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

echo Installation complete!
echo Run the server with: python main.py

pause
