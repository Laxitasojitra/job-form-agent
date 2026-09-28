@echo off
REM start_chrome.bat - opens a separate Chrome window that the agent can connect to.
REM Sign in to Google in THIS window once. It uses its own profile folder,
REM so your normal Chrome, bookmarks and passwords are not touched.

set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

start "" %CHROME% --remote-debugging-port=9222 --user-data-dir="%~dp0chrome_agent_profile"
echo Chrome started. Sign in to Google in that window if needed, then run: python agent.py
