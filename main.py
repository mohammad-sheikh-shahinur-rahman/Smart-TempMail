# -*- coding: utf-8 -*-
# Smart TempMail API + Telegram Bot Integration
# Copyright @ISmartCoder
# Updates Channel: https://t.me/abirxdhackz

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import threading
import time
import os
import socket
from datetime import datetime, timedelta
import uuid
import cloudscraper
from bs4 import BeautifulSoup
import json
import re
import gzip
import brotli
import zstandard as zstd
import base64
from typing import Optional, Dict, Any
import asyncio

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- FastAPI App ---
app = FastAPI(title="Smart TempMail API", version="1.0.0")

# --- TempMail Service ---
class TempMailService:
    def __init__(self):
        self.sessions = {}
        self.email_sessions = {}

    async def decode_api_url(self, encoded_url: str) -> Optional[str]:
        try:
            cleaned_url = re.sub(r'[^A-Za-z0-9+/=]', '', encoded_url)
            cleaned_url = cleaned_url.replace('f56', '6')
            cleaned_url = cleaned_url + '=' * (4 - len(cleaned_url) % 4) if len(cleaned_url) % 4 != 0 else cleaned_url
            decoded = base64.b64decode(cleaned_url).decode('utf-8')
            if not decoded.startswith('http'):
                decoded = 'https://' + decoded.lstrip('?:/')
            return decoded
        except Exception as e:
            print(f"[DEBUG] Error decoding API URL: {str(e)}")
            return None

    def decompress_edu_response(self, response):
        content = response.content
        try:
            if not content:
                return None
            enc = response.headers.get('content-encoding')
            if enc == 'gzip':
                return gzip.decompress(content).decode('utf-8')
            elif enc == 'br':
                try:
                    return brotli.decompress(content).decode('utf-8')
                except brotli.error:
                    return content.decode('utf-8', errors='ignore')
            elif enc == 'zstd':
                try:
                    dctx = zstd.ZstdDecompressor()
                    return dctx.decompress(content).decode('utf-8')
                except zstd.ZstdError:
                    return content.decode('utf-8', errors='ignore')
            return content.decode('utf-8')
        except Exception:
            return None

    async def extract_auth_token(self, html_content: str, cookies: dict) -> Optional[str]:
        try:
            jwt_patterns = [
                r'"jwt"\s*:\s*"(eyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.[A-Za-z0-9_-]+)"',
                r'"token"\s*:\s*"(eyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.[A-Za-z0-9_-]+)"',
                r'window\.token\s*=\s*[\'"]eyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.[A-Za-z0-9_-]+[\'"]',
                r'eyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.[A-Za-z0-9_-]+'
            ]
            for pattern in jwt_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    if match.startswith('eyJ'):
                        return match
            return None
        except Exception as e:
            print(f"[DEBUG] Error extracting auth token: {str(e)}")
            return None

    async def extract_email_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        try:
            email_input = soup.find('input', {'id': 'mail'}) or soup.find('input', {'name': 'mail'})
            if email_input and email_input.get('value'):
                return email_input.get('value')
            email_span = soup.find('span', {'id': 'mail'})
            if email_span and email_span.get_text().strip():
                return email_span.get_text().strip()
            return None
        except Exception as e:
            print(f"[DEBUG] Error extracting email: {str(e)}")
            return None

    async def generate_temp_mail(self, ten_minute: bool = False) -> Dict[str, Any]:
        scraper = cloudscraper.create_scraper()
        try:
            url = 'https://temp-mail.org/en/10minutemail' if ten_minute else 'https://temp-mail.org/en/'
            response = scraper.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to fetch TempMail page")
            soup = BeautifulSoup(response.text, 'html.parser')
            email = await self.extract_email_from_html(soup)
            if not email:
                raise HTTPException(status_code=500, detail="Failed to generate temp mail")
            token = str(uuid.uuid4())
            self.sessions[token] = {
                "email": email,
                "created_at": time.time(),
                "ten_minute": ten_minute
            }
            return {
                "api_owner": "@ISmartCoder",
                "api_dev": "@WeSmartDevelopers",
                "temp_mail": email,
                "access_token": token,
                "expires_at": (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S') if ten_minute else "N/A"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

temp_mail_service = TempMailService()

# --- FastAPI Endpoints ---
@app.get("/api/gen")
async def generate_mail():
    return await temp_mail_service.generate_temp_mail(ten_minute=False)

@app.get("/api/10min/gen")
async def generate_10min_mail():
    return await temp_mail_service.generate_temp_mail(ten_minute=True)

# --- Telegram Bot Integration ---
TELEGRAM_TOKEN = "8081533180:AAEov96AMFNachEiOtIMXgUBrPYW5spdm34"  # Replace with your bot token

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Smart TempMail Bot!\n\n"
        "/gen - Generate Temp Mail\n"
        "/10min - Generate 10-min Temp Mail"
    )

async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await temp_mail_service.generate_temp_mail(ten_minute=False)
    await update.message.reply_text(
        f"Temp Mail: {result['temp_mail']}\nToken: {result['access_token']}"
    )

async def ten_min(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await temp_mail_service.generate_temp_mail(ten_minute=True)
    await update.message.reply_text(
        f"10-Min Temp Mail: {result['temp_mail']}\nToken: {result['access_token']}\nExpires at: {result['expires_at']}"
    )

def run_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("gen", gen))
    app_bot.add_handler(CommandHandler("10min", ten_min))
    app_bot.run_polling()

# --- Background cleanup thread ---
def cleanup_sessions():
    while True:
        current_time = time.time()
        expired_tokens = [t for t, s in temp_mail_service.sessions.items() if s['ten_minute'] and current_time - s['created_at'] > 600]
        for token in expired_tokens:
            del temp_mail_service.sessions[token]
        time.sleep(300)

# --- Main Server Run ---
if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=cleanup_sessions, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()
    
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    local_ip = get_local_ip()
    port = int(os.getenv("PORT", 8000))
    print(f"Server running on: http://{local_ip}:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
