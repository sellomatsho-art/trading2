from flask import Flask, jsonify
import os
import time
import logging
import threading
import requests
from datetime import datetime
from collections import defaultdict
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Read dashboard.html
try:
    with open('dashboard.html', 'r') as f:
        dashboard_content = f.read()
except:
    dashboard_content = '<h1>Dashboard not found</h1>'

class TradingBot:
    def __init__(self):
        self.api_key = os.getenv('POLYMARKET_API_KEY')
        self.private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
        self.min_edge = float(os.getenv('MIN_EDGE', '2.5'))
        self.max_position = float(os.getenv('MAX_POSITION', '5000'))
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '0.02'))
        
        self.trades = []
        self.positions = {}
        self.price_history = defaultdict(list)
        self.start_time = datetime.now()
        self.running = False
        
        logger.info(f"Bot initialized: edge={self.min_edge}%, pos=${self.max_position}")
    
    def get_markets(self):
        """Fetch active markets from Polymarket"""
        try:
            response = requests.get(
                'https://clob.polymarket.com/markets',
                params={'limit': 100, 'status': 'active'},
                timeout=5,
                headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
            )
            return response.json() if response.ok else []
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    def get_market_price(self, market_id):
        """Get current price for a market"""
        try:
            response = requests.get(
                f'https://clob.polymarket.com/markets/{market_id}',
                timeout=5,
                headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
            )
            data = response.json() if response.ok else {}
            return data.get('mid_price', 0.5)
        except:
            return None
    
    def detect_opportunity(self, market_id, current_price):
        """Detect repricing opportunities using price volatility"""
        if market_id not in self.price_history or len(self.price_history[market_id]) < 5:
            return False, 0
        
        prices = self.price_history[market_id][-15:]
        if len(prices) < 3:
            return False, 0
        
        changes = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        if not changes:
            return False, 0
        
        try:
            avg_change = statistics.mean(changes)
            volatility = statistics.stdev(changes) if len(changes) > 1 else 0
            edge = (volatility / (avg_change + 0.001)) * 100
            
            return edge > self.min_edge, edge
        except:
            return False, 0
    
    def execute_trade(self, market_id, market_name, price, edge):
        """Simulate trade execution"""
        side = 'buy' if edge > 0 else 'sell'
        size = min(self.max_position * self.risk_per_trade, self.max_position)
        
        if size < 10:
            return None
        
        position = {
            'market_id': market_id,
            'market_name': market_name,
            'entry_price': price,
            'size': size,
            'entry_time': datetime.now().isoformat(),
            'side': side,
            'edge': edge
        }
        
        self.positions[market_id] = position
        logger.info(f"Trade: {market_name} @ {price} edge={edge:.2f}%")
        
        return position
    
    def check_exit_conditions(self):
        """Check if positions should be closed"""
        for market_id in list(self.positions.keys()):
            pos = self.positions[market_id]
            current_price = self.get_market_price(market_id)
            
            if current_price is None:
                continue
            
            roi = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
            pnl = (current_price - pos['entry_price']) * pos['size']
            
            if roi > 20 or roi < -10:
                trade = {
                    'market': pos['market_name'],
                    'entry': pos['entry_price'],
                    'exit': current_price,
                    'roi': roi,
                    'pnl': pnl,
                    'side': pos['side'],
                    'time': datetime.now().isoformat()
                }
                self.trades.append(trade)
                del self.positions[market_id]
                logger.info(f"Closed: ROI={roi:.2f}% PnL=${pnl:.2f}")
    
    def run_bot_loop(self):
        """Main bot trading loop"""
        self.running = True
        logger.info("Bot loop started")
        
        while self.running:
            try:
                markets = self.get_markets()
                if not markets:
                    time.sleep(5)
                    continue
                
                opportunities = []
                for market in markets[:50]:
                    market_id = market.get('id')
                    market_name = market.get('question', 'Unknown')
                    
                    if not market_id:
                        continue
                    
                    price = self.get_market_price(market_id)
                    if price is None:
                        continue
                    
                    self.price_history[market_id].append(price)
                    if len(self.price_history[market_id]) > 100:
                        self.price_history[market_id].pop(0)
                    
                    has_opp, edge = self.detect_opportunity(market_id, price)
                    if has_opp and len(self.positions) < 10:
                        opportunities.append({
                            'id': market_id,
                            'name': market_name,
                            'price': price,
                            'edge': edge
                        })
                
                opportunities.sort(key=lambda x: abs(x['edge']), reverse=True)
                for opp in opportunities[:3]:
                    self.execute_trade(opp['id'], opp['name'], opp['price'], opp['edge'])
                
                self.check_exit_conditions()
                
                if len(self.trades) % 10 == 0 and self.trades:
                    total_pnl = sum(t['pnl'] for t in self.trades)
                    logger.info(f"Trades: {len(self.trades)}, Total PnL: ${total_pnl:.2f}")
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Bot error: {e}")
                time.sleep(5)
    
    def get_stats(self):
        """Return bot statistics"""
        if not self.trades:
            return {
                'total_profit': 0,
                'daily_avg': 0,
                'win_rate': 0,
                'total_trades': 0,
                'active_positions': 0,
                'trades_per_hour': 0,
                'uptime_seconds': 0
            }
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        pnls = [t['pnl'] for t in self.trades]
        wins = len([p for p in pnls if p > 0])
        total_pnl = sum(pnls)
        
        return {
            'total_profit': total_pnl,
            'daily_avg': total_pnl / max(uptime / 86400, 1),
            'win_rate': (wins / len(self.trades)) * 100 if self.trades else 0,
            'total_trades': len(self.trades),
            'active_positions': len(self.positions),
            'trades_per_hour': len(self.trades) / max(uptime / 3600, 1),
            'uptime_seconds': uptime
        }

bot = None

def init_bot():
    global bot
    if bot is None:
        bot = TradingBot()
        thread = threading.Thread(target=bot.run_bot_loop, daemon=True)
        thread.start()
        logger.info("Bot thread started")

@app.route('/')
def home():
    init_bot()
    return '<h1>Polymarket Bot</h1><p><a href="/dashboard.html">Dashboard</a></p>'

@app.route('/dashboard.html')
def dashboard():
    init_bot()
    return dashboard_content

@app.route('/stats')
def stats():
    init_bot()
    return jsonify(bot.get_stats())

@app.route('/trades')
def trades():
    init_bot()
    return jsonify(bot.trades[-20:] if bot.trades else [])

if __name__ == '__main__':
    init_bot()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
