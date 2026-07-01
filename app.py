from flask import Flask, jsonify
import os
import time
import threading
import requests
from datetime import datetime
from collections import defaultdict
import random

app = Flask(__name__)

try:
    with open('dashboard.html', 'r') as f:
        dashboard_html = f.read()
except:
    dashboard_html = '<h1>Dashboard</h1>'

class AggressiveBot:
    def __init__(self):
        self.trades = []
        self.positions = {}
        self.price_history = defaultdict(list)
        self.start_time = datetime.now()
    
    def get_markets(self):
        try:
            r = requests.get('https://clob.polymarket.com/markets?limit=50', timeout=5)
            return r.json() if r.ok else []
        except:
            return []
    
    def get_price(self, market_id):
        try:
            r = requests.get(f'https://clob.polymarket.com/markets/{market_id}', timeout=3)
            return r.json().get('mid_price') if r.ok else None
        except:
            return None
    
    def run_loop(self):
        scan = 0
        while True:
            try:
                markets = self.get_markets()
                if not markets:
                    time.sleep(2)
                    continue
                
                scan += 1
                
                # Scan all markets
                for m in markets:
                    mid = m.get('id')
                    name = m.get('question', 'Market')[:40]
                    
                    if not mid:
                        continue
                    
                    price = self.get_price(mid)
                    if not price or price <= 0:
                        continue
                    
                    # Record price
                    self.price_history[mid].append(price)
                    if len(self.price_history[mid]) > 30:
                        self.price_history[mid].pop(0)
                    
                    # AGGRESSIVE: Open trades much more easily
                    if len(self.price_history[mid]) >= 3 and len(self.positions) < 5:
                        h = self.price_history[mid]
                        vol = (max(h) - min(h)) / min(h) * 100 if min(h) > 0 else 0
                        
                        # Much lower threshold: 0.1% instead of 0.5%
                        if vol > 0.1 and mid not in self.positions:
                            size = 50 + random.randint(0, 50)
                            self.positions[mid] = {
                                'name': name,
                                'entry': price,
                                'size': size,
                                'vol': vol
                            }
                            print(f"[OPEN] {name[:30]} @ {price:.4f} vol:{vol:.3f}%")
                    
                    # Check existing positions
                    if mid in self.positions:
                        pos = self.positions[mid]
                        roi = ((price - pos['entry']) / pos['entry']) * 100
                        pnl = (price - pos['entry']) * pos['size']
                        
                        # AGGRESSIVE: Close much faster (+1% or -0.5%)
                        if roi > 1 or roi < -0.5:
                            self.trades.append({
                                'market': pos['name'],
                                'entry': round(pos['entry'], 4),
                                'exit': round(price, 4),
                                'roi': round(roi, 2),
                                'pnl': round(pnl, 2),
                                'side': 'BUY' if roi > 0 else 'SELL',
                                'time': datetime.now().isoformat()
                            })
                            del self.positions[mid]
                            print(f"[CLOSE] {pos['name'][:30]} ROI:{roi:.2f}% PnL:${pnl:.2f}")
                
                if scan % 3 == 0:
                    pnl = sum([t['pnl'] for t in self.trades]) if self.trades else 0
                    print(f"[STATUS] Scans:{scan} Trades:{len(self.trades)} Open:{len(self.positions)} PnL:${pnl:.2f}")
                
                time.sleep(1.5)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(3)
    
    def stats(self):
        up = (datetime.now() - self.start_time).total_seconds()
        if not self.trades:
            return {'total_profit': 0, 'daily_avg': 0, 'win_rate': 0, 'total_trades': 0, 'active_positions': len(self.positions), 'trades_per_hour': 0, 'uptime_seconds': int(up)}
        
        pnls = [t['pnl'] for t in self.trades]
        wins = len([p for p in pnls if p > 0])
        tp = sum(pnls)
        return {'total_profit': round(tp, 2), 'daily_avg': round(tp / max(up / 86400, 0.1), 2), 'win_rate': round((wins / len(self.trades)) * 100, 1), 'total_trades': len(self.trades), 'active_positions': len(self.positions), 'trades_per_hour': round(len(self.trades) / max(up / 3600, 0.1), 2), 'uptime_seconds': int(up)}

bot = AggressiveBot()
t = threading.Thread(target=bot.run_loop, daemon=True)
t.start()

@app.route('/')
def home():
    return '<h1>Bot</h1>'

@app.route('/dashboard.html')
def dashboard():
    return dashboard_html

@app.route('/stats')
def stats():
    return jsonify(bot.stats())

@app.route('/trades')
def trades():
    return jsonify(bot.trades[-20:] if bot.trades else [])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, threaded=True)
