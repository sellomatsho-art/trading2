from flask import Flask, jsonify
import os
import time
import logging
import threading
import requests
from datetime import datetime
from collections import defaultdict
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

try:
    with open('dashboard.html', 'r') as f:
        dashboard_content = f.read()
except:
    dashboard_content = '<h1>Dashboard not found</h1>'

class AggressiveBot:
    def __init__(self):
        self.trades = []
        self.positions = {}
        self.price_history = defaultdict(list)
        self.start_time = datetime.now()
        self.running = False
        self.min_edge = 1.0
        logger.info("Aggressive Bot initialized")
    
    def get_markets(self):
        try:
            r = requests.get('https://clob.polymarket.com/markets?limit=30', timeout=5)
            return r.json() if r.ok else []
        except:
            return []
    
    def get_price(self, market_id):
        try:
            r = requests.get(f'https://clob.polymarket.com/markets/{market_id}', timeout=5)
            return r.json().get('mid_price') if r.ok else None
        except:
            return None
    
    def run_bot(self):
        self.running = True
        logger.info("Bot trading started")
        scan_count = 0
        
        while self.running:
            try:
                markets = self.get_markets()
                if not markets:
                    time.sleep(2)
                    continue
                
                scan_count += 1
                
                for market in markets[:15]:
                    mid = market.get('id')
                    name = market.get('question', 'Unknown')[:50]
                    
                    if not mid:
                        continue
                    
                    price = self.get_price(mid)
                    if price is None or price <= 0:
                        continue
                    
                    self.price_history[mid].append(price)
                    if len(self.price_history[mid]) > 30:
                        self.price_history[mid].pop(0)
                    
                    if len(self.price_history[mid]) >= 3:
                        prices = self.price_history[mid]
                        min_p = min(prices)
                        max_p = max(prices)
                        
                        if min_p > 0:
                            vol = (max_p - min_p) / min_p * 100
                            
                            if vol > self.min_edge and len(self.positions) < 5:
                                size = random.uniform(50, 200)
                                self.positions[mid] = {
                                    'name': name,
                                    'entry': price,
                                    'size': size,
                                    'vol': vol
                                }
                                logger.info(f"TRADE: {name} @ {price:.4f} vol:{vol:.2f}%")
                
                for mid in list(self.positions.keys()):
                    pos = self.positions[mid]
                    cur_price = self.get_price(mid)
                    
                    if cur_price is None:
                        continue
                    
                    roi = ((cur_price - pos['entry']) / pos['entry']) * 100
                    pnl = (cur_price - pos['entry']) * pos['size']
                    
                    if roi > 5 or roi < -3:
                        self.trades.append({
                            'market': pos['name'],
                            'entry': round(pos['entry'], 4),
                            'exit': round(cur_price, 4),
                            'roi': round(roi, 2),
                            'pnl': round(pnl, 2),
                            'side': 'buy' if roi > 0 else 'sell',
                            'time': datetime.now().isoformat()
                        })
                        del self.positions[mid]
                        logger.info(f"CLOSED: {pos['name']} ROI:{roi:.2f}% PnL:${pnl:.2f}")
                
                if scan_count % 5 == 0:
                    logger.info(f"Status - Scans: {scan_count}, Trades: {len(self.trades)}, Open: {len(self.positions)}")
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Bot error: {str(e)}")
                time.sleep(3)
    
    def stats(self):
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        if not self.trades:
            return {
                'total_profit': 0,
                'daily_avg': 0,
                'win_rate': 0,
                'total_trades': 0,
                'active_positions': len(self.positions),
                'trades_per_hour': 0,
                'uptime_seconds': int(uptime)
            }
        
        pnls = [t['pnl'] for t in self.trades]
        wins = len([p for p in pnls if p > 0])
        total_pnl = sum(pnls)
        
        return {
            'total_profit': round(total_pnl, 2),
            'daily_avg': round(total_pnl / max(uptime / 86400, 1), 2),
            'win_rate': round((wins / len(self.trades)) * 100, 1) if self.trades else 0,
            'total_trades': len(self.trades),
            'active_positions': len(self.positions),
            'trades_per_hour': round(len(self.trades) / max(uptime / 3600, 1), 2),
            'uptime_seconds': int(uptime)
        }

bot = None

def init_bot():
    global bot
    if bot is None:
        bot = AggressiveBot()
        t = threading.Thread(target=bot.run_bot, daemon=True)
        t.start()
        logger.info("Bot thread started")

@app.route('/')
def home():
    init
