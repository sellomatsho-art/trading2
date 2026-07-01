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
    dashboard_html = '<h1>Dashboard</h1>'

class TradingBot:
    def __init__(self):
        self.trades = []
        self.positions = {}
        self.price_history = defaultdict(list)
        self.start_time = datetime.now()
        self.running = False
    
    def get_markets(self):
        try:
            r = requests.get('https://clob.polymarket.com/markets?limit=30', timeout=5)
            return r.json() if r.ok else []
        except:
            return []
    
    def get_price(self, market_id):
        try:
            r = requests.get(f'https://clob.polymarket.com/markets/{market_id}', timeout=3)
            data = r.json() if r.ok else {}
            return data.get('mid_price')
        except:
            return None
    
    def detect_opportunity(self, market_id, price):
        if market_id not in self.price_history or len(self.price_history[market_id]) < 4:
            return False, 0
        
        prices = self.price_history[market_id][-10:]
        if len(prices) < 3:
            return False, 0
        
        min_price = min(prices)
        max_price = max(prices)
        
        if min_price > 0:
            volatility = ((max_price - min_price) / min_price) * 100
            return volatility > 0.5, volatility
        
        return False, 0
    
    def run_trading_loop(self):
        self.running = True
        scan_count = 0
        
        while self.running:
            try:
                markets = self.get_markets()
                if not markets:
                    time.sleep(3)
                    continue
                
                scan_count += 1
                
                # Scan markets for opportunities
                for market in markets[:20]:
                    market_id = market.get('id')
                    market_name = market.get('question', 'Market')[:50]
                    
                    if not market_id:
                        continue
                    
                    price = self.get_price(market_id)
                    if not price or price <= 0:
                        continue
                    
                    # Record price
                    self.price_history[market_id].append(price)
                    if len(self.price_history[market_id]) > 50:
                        self.price_history[market_id].pop(0)
                    
                    # Detect opportunity
                    has_opportunity, volatility = self.detect_opportunity(market_id, price)
                    
                    # Open position if opportunity found
                    if has_opportunity and len(self.positions) < 3:
                        size = 100 + (len(self.trades) * 5)
                        self.positions[market_id] = {
                            'name': market_name,
                            'entry_price': price,
                            'size': size,
                            'volatility': volatility,
                            'entry_time': datetime.now().isoformat()
                        }
                        print(f"[TRADE OPEN] {market_name} @ {price:.4f} (vol: {volatility:.2f}%)")
                
                # Check positions for exit
                for market_id in list(self.positions.keys()):
                    position = self.positions[market_id]
                    current_price = self.get_price(market_id)
                    
                    if current_price and current_price > 0:
                        roi = ((current_price - position['entry_price']) / position['entry_price']) * 100
                        pnl = (current_price - position['entry_price']) * position['size']
                        
                        # Close at +2% or -1%
                        if roi > 2 or roi < -1:
                            trade = {
                                'market': position['name'],
                                'entry': round(position['entry_price'], 4),
                                'exit': round(current_price, 4),
                                'roi': round(roi, 2),
                                'pnl': round(pnl, 2),
                                'side': 'BUY' if roi > 0 else 'SELL',
                                'time': datetime.now().isoformat()
                            }
                            self.trades.append(trade)
                            del self.positions[market_id]
                            print(f"[TRADE CLOSED] {position['name']} ROI: {roi:.2f}% PnL: ${pnl:.2f}")
                
                # Log status periodically
                if scan_count % 5 == 0:
                    total_pnl = sum([t['pnl'] for t in self.trades]) if self.trades else 0
                    print(f"[STATUS] Scans: {scan_count}, Trades: {len(self.trades)}, Open: {len(self.positions)}, PnL: ${total_pnl:.2f}")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"[ERROR] {str(e)}")
                time.sleep(3)
    
    def get_stats(self):
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
            'daily_avg': round(total_pnl / max(uptime / 86400, 0.1), 2),
            'win_rate': round((wins / len(self.trades)) * 100, 1) if self.trades else 0,
            'total_trades': len(self.trades),
            'active_positions': len(self.positions),
            'trades_per_hour': round(len(self.trades) / max(uptime / 3600, 0.1), 2),
            'uptime_seconds': int(uptime)
        }

# Start bot
bot = TradingBot()
bot_thread = threading.Thread(target=bot.run_trading_loop, daemon=True)
bot_thread.start()

@app.route('/')
def home():
    return '<h1>Trading Bot</h1><a href="/dashboard.html">Dashboard</a>'

@app.route('/dashboard.html')
def dashboard():
    return dashboard_html

@app.route('/stats')
def stats():
    return jsonify(bot.get_stats())

@app.route('/trades')
def trades():
    return jsonify(bot.trades[-20:] if bot.trades else [])

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
