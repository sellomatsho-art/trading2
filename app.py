from flask import Flask, jsonify
import os
import time
import threading
import requests
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# Load dashboard
try:
    with open('dashboard.html', 'r') as f:
        dashboard_html = f.read()
except:
    dashboard_html = '<h1>Dashboard</h1>'

class WorkingBot:
    def __init__(self):
        self.trades = []
        self.positions = {}
        self.history = defaultdict(list)
        self.start = datetime.now()
        self.running = False
    
    def run(self):
        self.running = True
        print("Bot started - scanning markets...")
        
        while self.running:
            try:
                # Get markets
                r = requests.get('https://clob.polymarket.com/markets?limit=30', timeout=5)
                markets = r.json() if r.ok else []
                
                # Scan each market
                for m in markets:
                    mid = m.get('id')
                    name = m.get('question', 'Market')[:50]
                    
                    if not mid:
                        continue
                    
                    # Get price
                    p = requests.get(f'https://clob.polymarket.com/markets/{mid}', timeout=3)
                    price = p.json().get('mid_price') if p.ok else None
                    
                    if not price or price <= 0:
                        continue
                    
                    # Record price
                    self.history[mid].append(price)
                    if len(self.history[mid]) > 20:
                        self.history[mid].pop(0)
                    
                    # Check for trade opportunity
                    if len(self.history[mid]) >= 4:
                        h = self.history[mid]
                        volatility = (max(h) - min(h)) / min(h) * 100
                        
                        # If volatility > 0.5% and we have space, open position
                        if volatility > 0.5 and len(self.positions) < 3:
                            size = 100 + (len(self.trades) * 10)
                            self.positions[mid] = {
                                'name': name,
                                'entry': price,
                                'size': size,
                                'vol': volatility
                            }
                            print(f"OPENED: {name} @ {price:.4f}")
                
                # Check positions for exit
                for mid in list(self.positions.keys()):
                    pos = self.positions[mid]
                    p = requests.get(f'https://clob.polymarket.com/markets/{mid}', timeout=3)
                    cp = p.json().get('mid_price') if p.ok else None
                    
                    if cp:
                        roi = ((cp - pos['entry']) / pos['entry']) * 100
                        pnl = (cp - pos['entry']) * pos['size']
                        
                        # Close if +3% or -1.5%
                        if roi > 3 or roi < -1.5:
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
                            print(f"CLOSED: {pos['name']} ROI: {roi:.2f}% PnL: ${pnl:.2f}")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(3)
    
    def get_stats(self):
        up = (datetime.now() - self.start).total_seconds()
        
        if not self.trades:
            return {
                'total_profit': 0,
                'daily_avg': 0,
                'win_rate': 0,
                'total_trades': 0,
                'active_positions': len(self.positions),
                'trades_per
