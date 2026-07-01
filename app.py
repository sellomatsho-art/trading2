from flask import Flask, jsonify
import os
import time
import logging
import threading
import requests
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

try:
    with open('dashboard.html', 'r') as f:
        dashboard_content = f.read()
except:
    dashboard_content = '<h1>Dashboard not found</h1>'

class SimplifiedBot:
    def __init__(self):
        self.trades = []
        self.positions = {}
        self.price_history = defaultdict(list)
        self.start_time = datetime.now()
        self.running = False
        self.min_edge = float(os.getenv('MIN_EDGE', '2.5'))
        logger.info("Bot initialized")
    
    def get_markets(self):
        try:
            r = requests.get('https://clob.polymarket.com/markets?limit=30&status=active', timeout=5)
            return r.json() if r.ok else []
        except:
            return []
    
    def get_price(self, market_id):
        try:
            r = requests.get(f'https://clob.polymarket.com/markets/{market_id}', timeout=5)
            return r.json().get('mid_price', 0.5) if r.ok else None
        except:
            return None
    
    def detect_opp(self, market_id, price):
        if market_id not in self.price_history or len(self.price_history[market_id]) < 5:
            return False, 0
        prices = self.price_history[market_id][-10:]
        if len(prices) < 3:
            return False, 0
        volatility = (max(prices) - min(prices)) / min(prices) * 100
        return volatility > self.min_edge, volatility
    
    def run_bot(self):
        self.running = True
        logger.info("Bot loop started")
        while self.running:
            try:
                markets = self.get_markets()
                for market in markets[:20]:
                    mid = market.get('id')
                    name = market.get('question', 'Unknown')
                    if not mid:
                        continue
                    price = self.get_price(mid)
                    if price is None:
                        continue
                    self.price_history[mid].append(price)
                    if len(self.price_history[mid]) > 50:
                        self.price_history[mid].pop(0)
                    has_opp, edge = self.detect_opp(mid, price)
                    if has_opp and len(self.positions) < 3:
                        size = min(5000 * 0.02, 5000)
                        self.positions[mid] = {'name': name, 'entry': price, 'size': size, 'time': datetime.now().isoformat(), 'edge': edge}
                        logger.info(f"Trade: {name} @ {price}")
                
                for mid in list(self.positions.keys()):
                    pos = self.positions[mid]
                    cur_price = self.get_price(mid)
                    if cur_price is None:
                        continue
                    roi = ((cur_price - pos['entry']) / pos['entry']) * 100
                    pnl = (cur_price - pos['entry']) * pos['size']
                    if roi > 20 or roi < -10:
                        self.trades.append({'market': pos['name'], 'entry': pos['entry'], 'exit': cur_price, 'roi': roi, 'pnl': pnl, 'time': datetime.now().isoformat()})
                        del self.positions[mid]
                        logger.info(f"Closed: ROI {roi:.2f}%")
                
                time.sleep(3)
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(5)
    
    def stats(self):
        uptime = (datetime.now() - self.start_time).total_seconds()
        if not self.trades:
            return {'total_profit': 0, 'daily_avg': 0, 'win_rate': 0, 'total_trades': 0, 'active_positions': len(self.positions), 'trades_per_hour': 0, 'uptime_seconds': uptime}
        pnls = [t['pnl'] for t in self.trades]
        wins = len([p for p in pnls if p > 0])
        return {'total_profit': sum(pnls), 'daily_avg': sum(pnls) / max(uptime / 86400, 1), 'win_rate': (wins / len(self.trades)) * 100, 'total_trades': len(self.trades), 'active_positions': len(self.positions), 'trades_per_hour': len(self.trades) / max(uptime / 3600, 1), 'uptime_seconds': uptime}

bot = None

def init_bot():
    global bot
    if bot is None:
        bot = SimplifiedBot()
        threading.Thread(target=bot.run_bot, daemon=True).start()

@app.route('/')
def home():
    init_bot()
    return '<h1>Bot Live</h1><a href="/dashboard.html">Dashboard</a>'

@app.route('/dashboard.html')
def dashboard():
    init_bot()
    return dashboard_content

@app.route('/stats')
def get_stats():
    init_bot()
    return jsonify(bot.stats())

@app.route('/trades')
def get_trades():
    init_bot()
    return jsonify(bot.trades[-20:] if bot.trades else [])

if __name__ == '__main__':
    init_bot()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
