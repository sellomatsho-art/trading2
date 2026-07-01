from flask import Flask, jsonify
import os
import time
import threading
from datetime import datetime
import random

app = Flask(__name__)

try:
    with open('dashboard.html', 'r') as f:
        dashboard_html = f.read()
except:
    dashboard_html = '<h1>Dashboard</h1>'

class SimulationBot:
    def __init__(self):
        self.trades = []
        self.start_time = datetime.now()
    
    def run_simulation(self):
        while True:
            try:
                # Generate realistic trades every 10-30 seconds
                time.sleep(random.uniform(10, 30))
                
                # Random trade data
                markets = [
                    'BTC Price Above $70k by Dec 31',
                    'Trump Wins 2024 Election',
                    'Fed Cuts Rates in Q4 2024',
                    'ETH Above $4000 by Year End',
                    'S&P 500 Reaches 6000',
                    'Bitcoin Dominance Above 50%',
                    'Ethereum Price Surge',
                    'AI Stock Rally Continues'
                ]
                
                market = random.choice(markets)
                entry = random.uniform(0.3, 0.7)
                roi = random.uniform(-0.8, 2.5)
                pnl = random.uniform(-50, 150)
                
                trade = {
                    'market': market,
                    'entry': round(entry, 4),
                    'exit': round(entry + (entry * roi / 100), 4),
                    'roi': round(roi, 2),
                    'pnl': round(pnl, 2),
                    'side': 'BUY' if roi > 0 else 'SELL',
                    'time': datetime.now().isoformat()
                }
                
                self.trades.append(trade)
                print(f"[TRADE] {market} ROI: {roi:.2f}% PnL: ${pnl:.2f}")
                
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
    
    def stats(self):
        up = (datetime.now() - self.start_time).total_seconds()
        
        if not self.trades:
            return {
                'total_profit': 0,
                'daily_avg': 0,
                'win_rate': 0,
                'total_trades': 0,
                'active_positions': 0,
                'trades_per_hour': 0,
                'uptime_seconds': int(up)
            }
        
        pnls = [t['pnl'] for t in self.trades]
        wins = len([p for p in pnls if p > 0])
        tp = sum(pnls)
        
        return {
            'total_profit': round(tp, 2),
            'daily_avg': round(tp / max(up / 86400, 0.1), 2),
            'win_rate': round((wins / len(self.trades)) * 100, 1),
            'total_trades': len(self.trades),
            'active_positions': random.randint(0, 3),
            'trades_per_hour': round(len(self.trades) / max(up / 3600, 0.1), 2),
            'uptime_seconds': int(up)
        }

bot = SimulationBot()
t = threading.Thread(target=bot.run_simulation, daemon=True)
t.start()

@app.route('/')
def home():
    return '<h1>Polymarket Trading Bot (SIMULATION MODE)</h1>'

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
