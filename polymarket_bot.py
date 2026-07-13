#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CATShadow Polymarket Bot v2.1 — Zero Dependency
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, List, Optional

CONFIG = {
    "scan_interval": 15,
    "whale_threshold": 10000,
    "arbitrage_min_diff": 0.02,
    "price_alerts": {},
    "telegram_token": "API_KEY_TELEGRAM_BOT",
    "telegram_chat_id": "CHAT_ID_TELEGRAM",
    "discord_webhook_url": "WEBHOOK_URL",
    "log_file": "polymarket_bot.log"
}

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

def http_get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except:
        return None

def http_post(url, payload):
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in (200, 201, 204)
    except:
        return False

class Logger:
    @staticmethod
    def log(msg, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [{level}] {msg}")
        try:
            with open(CONFIG["log_file"], "a") as f:
                f.write(f"[{ts}] [{level}] {msg}\n")
        except:
            pass

class TelegramNotifier:
    def __init__(self):
        self.token = CONFIG.get("telegram_token", "")
        self.chat_id = CONFIG.get("telegram_chat_id", "")
        self.enabled = bool(self.token and self.chat_id)
        Logger.log(f"Telegram: {'Aktif' if self.enabled else 'Nonaktif'}", "INFO")

    def send(self, text):
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        if http_post(url, payload):
            Logger.log("Telegram terkirim", "INFO")

    def send_whale(self, market, side, value, price):
        self.send(f"WHALE: {market} | {side} ${value:,.0f} @ {price:.4f}")

class DiscordNotifier:
    def __init__(self):
        self.url = CONFIG.get("discord_webhook_url", "")
        self.enabled = bool(self.url)
        Logger.log(f"Discord: {'Aktif' if self.enabled else 'Nonaktif'}", "INFO")

    def send(self, title, desc, fields=None, color=65280):
        if not self.enabled:
            return
        embed = {"title": title, "description": desc, "color": color, "fields": fields or []}
        http_post(self.url, {"embeds": [embed]})

    def send_whale(self, market, side, value, price):
        self.send("WHALE", f"{market} | {side} ${value:,.0f}", 
                  [{"name":"Price","value":f"{price:.4f}","inline":True}], 16711935)

class MarketFetcher:
    @staticmethod
    def get_events():
        return http_get(f"{GAMMA_API}/events") or []

    @staticmethod
    def get_trades(market_id, limit=50):
        return http_get(f"{DATA_API}/trades?market={market_id}&limit={limit}") or []

class WhaleDetector:
    def __init__(self):
        self.seen = set()

    def check(self, trades):
        whales = []
        for t in trades:
            tid = t.get("id")
            if tid in self.seen:
                continue
            val = float(t.get("size", 0)) * float(t.get("price", 0))
            if val >= CONFIG["whale_threshold"]:
                whales.append({"id": tid, "side": t.get("side"), "value": val, "price": float(t.get("price", 0))})
                self.seen.add(tid)
        return whales

class PolymarketBot:
    def __init__(self):
        self.whale = WhaleDetector()
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()
        self.running = True

    def scan(self):
        Logger.log("Scanning...", "INFO")
        events = MarketFetcher.get_events()
        if not events:
            return

        all_markets = []
        for e in events:
            for m in e.get("markets", []):
                all_markets.append(m)

        for m in all_markets[:20]:
            trades = MarketFetcher.get_trades(m.get("id"), 30)
            for w in self.whale.check(trades):
                slug = m.get("slug", "unknown")
                msg = f"WHALE: {slug} | {w['side']} ${w['value']:,.0f} @ {w['price']:.4f}"
                Logger.log(msg, "WHALE")
                self.telegram.send_whale(slug, w["side"], w["value"], w["price"])
                self.discord.send_whale(slug, w["side"], w["value"], w["price"])

    def run(self):
        Logger.log("Bot started", "INFO")
        try:
            while self.running:
                self.scan()
                time.sleep(CONFIG["scan_interval"])
        except KeyboardInterrupt:
            self.running = False
            Logger.log("Stopped", "INFO")

if __name__ == "__main__":
    bot = PolymarketBot()
    bot.run()
