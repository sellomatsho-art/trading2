from flask import Flask, jsonify
import os
import time
import threading
import requests
from datetime import datetime

app = Flask(__name__)

try:
    with open('dashboard.html', 'r') as f:
        dashboard_html = f.read()
except:
    dashboard_html = '<h1>Dashboard</h1>'

class SimpleBot:
    def __init__(self):
        self.trades = []
        self.positions = {}
        self.history = {}
        self.start_time = datetime.now()
    
    def scan_and_trade(self):
        try:
            r = requests.get('https://clob.polymarket.com/markets?limit=25', timeout=5)
            markets = r.json() if r.ok else []
            
            for m in markets:
                mid = m.get('id')
                name = m.get('question', 'Market')[:40]
                if not mid:
                    continue
                
                try:
                    p = requests.get(f'https://clob.polymarket.com/markets/{mid}', timeout=3)
                    price = p.json().get('mid_price') if p.ok else None
                    if not price or price <= 0:
                        continue
                    
                    if mid not in self.history:
                        self.history[mid] = []
                    
                    self.history[mid].append(price)
                    if len(self.history[mid]) > 15:
                        self.history[mid].pop(0)
                    
                    if len(self.history[mid]) >= 5:
                        h = self.history[mid]
                        vol = (max(h) - min(h)) / min(h) * 100
                        
                        if vol > 0.3 and len(self.positions) < 2:
                            self.positions[mid] = {'name': name, 'entry': price, 'size': 50}
                    
                    if mid in self.positions:
                        pos = self.positions[mid]
                        roi = ((price - pos['entry']) / pos['entry']) * 100
                        pnl = (price - pos['entry']) * pos['size']
                        
                        if roi > 2 or roi < -1:
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
                except:
                    pass
        except:
            pass
    
    def run_loop(self):
        while True:
            try:
                self.scan_and_trade()
                time.sleep(2)
            except:
                time.sleep(3)
    
    def stats(self):
        uptime = (datetime.now() - self.start_time).total_seconds()
        if not self.trades:
            return {'total_profit': 0, 'daily_avg': 0, 'win_rate': 0, 'total_trades': 0, 'active_positions': 0, 'trades_per_hour': 0, 'uptime_seconds': int(uptime)}
        
        pnls = [t['pnl'] for t in self.trades]
        wins = len([p for p in pnls if p > 0])
        tp = sum(pnls)
        
        return {'total_profit': round(tp, 2), 'daily_avg': round(tp / max(uptime / 86400, 1), 2), 'win_rate': round((wins / len(self.trades)) * 100, 1), 'total_trades': len(self.trades), 'active_positions': len(self.positions), 'trades_per_hour': round(len(self.trades) / max(uptime / 3600, 1), 2), 'uptime_seconds': int(uptime)}

bot = SimpleBot()
t = threading.Thread(target=bot.run_loop, daemon=True)
t.start()

@app.route('/')
def home():
    return '<h1>Bot</h1><a href="/dashboard.html">Dashboard</a>'

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
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
