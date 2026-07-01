from flask import Flask, jsonify
import os
import time
import threading
import requests
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

try:
    with open('dashboard.html', 'r') as f:
        dashboard_html = f.read()
except:
    dashboard_html = '<h1>Bot Error</h1>'

class Bot:
    def __init__(self):
        self.trades = []
        self.positions = {}
        self.history = defaultdict(list)
        self.start = datetime.now()
        self.running = False
    
    def loop(self):
        self.running = True
        count = 0
        while self.running:
            try:
                count += 1
                r = requests.get('https://clob.polymarket.com/markets?limit=20', timeout=5)
                markets = r.json() if r.ok else []
                
                for m in markets:
                    mid = m.get('id')
                    name = m.get('question', 'Market')[:40]
                    
                    if not mid:
                        continue
                    
                    p = requests.get(f'https://clob.polymarket.com/markets/{mid}', timeout=3)
                    price = p.json().get('mid_price') if p.ok else None
                    
                    if price and price > 0:
                        self.history[mid].append(price)
                        if len(self.history[mid]) > 20:
                            self.history[mid].pop(0)
                        
                        if len(self.history[mid]) >= 5:
                            h = self.history[mid]
                            vol = (max(h) - min(h)) / min(h) * 100
                            
                            if vol > 0.5 and len(self.positions) < 3:
                                self.positions[mid] = {'name': name, 'entry': price, 'size': 100}
                
                for mid in list(self.positions.keys()):
                    pos = self.positions[mid]
                    p = requests.get(f'https://clob.polymarket.com/markets/{mid}', timeout=3)
                    cp = p.json().get('mid_price') if p.ok else None
                    
                    if cp:
                        roi = ((cp - pos['entry']) / pos['entry']) * 100
                        pnl = (cp - pos['entry']) * pos['size']
                        
                        if roi > 2 or roi < -2:
                            self.trades.append({
                                'market': pos['name'],
                                'entry': round(pos['entry'], 4),
                                'exit': round(cp, 4),
                                'roi': round(roi, 2),
                                'pnl': round(pnl, 2),
                                'side': 'BUY' if roi > 0 else 'SELL',
                                'time': datetime.now().isoformat()
                            })
                            del self.positions[mid]
                
                if count % 3 == 0:
                    print(f"Status: Trades={len(self.trades)}, Open={len(self.positions)}")
                
                time.sleep(2)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(3)
    
    def stats(self):
        up = (datetime.now() - self.start).total_seconds()
        if not self.trades:
            return {'total_profit': 0, 'daily_avg': 0, 'win_rate': 0, 'total_trades': 0,
