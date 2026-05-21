"""
One-time script to get a YouTube OAuth refresh token.

Run this ONCE on your local machine:
    pip install requests
    python src/youtube_auth.py

Then copy the printed YOUTUBE_REFRESH_TOKEN into your GitHub Secrets.
You never need to run this again unless the token is revoked.
"""

import os
import json
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests


CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", input("Enter YOUTUBE_CLIENT_ID: "))
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", input("Enter YOUTUBE_CLIENT_SECRET: "))
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "https://www.googleapis.com/auth/youtube.upload"

auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h1>Auth complete! You can close this tab.</h1>")

    def log_message(self, *args):
        pass


auth_url = (
    "https://accounts.google.com/o/oauth2/v2/auth"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&response_type=code"
    f"&scope={urllib.parse.quote(SCOPES)}"
    f"&access_type=offline"
    f"&prompt=consent"
)

print("\nOpening browser for Google OAuth...")
print(f"If it doesn't open automatically, visit:\n{auth_url}\n")
webbrowser.open(auth_url)

server = HTTPServer(("localhost", 8080), CallbackHandler)
server.handle_request()

if not auth_code:
    print("No auth code received. Exiting.")
    exit(1)

token_resp = requests.post("https://oauth2.googleapis.com/token", data={
    "code": auth_code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
})
token_resp.raise_for_status()
tokens = token_resp.json()

print("\n" + "="*60)
print("SUCCESS! Add this to your GitHub Secrets:")
print("="*60)
print(f"YOUTUBE_REFRESH_TOKEN={tokens['refresh_token']}")
print("="*60 + "\n")
