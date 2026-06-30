#!/usr/bin/env python3
import os
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import requests
from collections import defaultdict
import statistics
import threading
from flask import Flask, jsonify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@dataclass
class Position:
    id: str
    market_id: str
    market_name: str
    entry_price: float
    current_price: float
    size: float
    entry_time: str
    unrealized_pnl: float
    
    def roi(self) -> float:
        return ((self.current_price - self.entry_price) / self.entry_price) * 100 if self.entry_price else 0
    
    def update_price(self, new_price: float):
        self.current_price = new_price
        self.unrealized_pnl = (new_price - self.entry_price) * self.size

@dataclass
class Trade:
    market_id: str
    market_name: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    roi: float
    entry_time: str
    exit_time: str
    trade_type: str

class PolymarketAPI:
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self.api_key = os.getenv('POLYMARKET_API_KEY')
        self.private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({'Authorization': f'Bearer {self.api_key}'})
    
    def get_markets(self, limit: int = 100) -> List[Dict]:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/markets",
                params={'limit': limit, 'status': 'active'},
                timeout=5
            )
            return response.json() if response.ok else []
        except:
            return []
    
    def get_market_prices(self, market_id: str) -> Optional[Dict]:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/markets/{market_id}",
                timeout=5
            )
            return response.json() if response.ok else None
        except:
            return None
    
    def place_order(self, market_id: str, side: str, price: float, size: float) -> Optional[Dict]:
        if not self.api_key:
            return {'order_id': f'sim_{int(time.time())}', 'status': 'simulated'}
        try:
            response = self.session.post(
                f"{self.BASE_URL}/orders",
                json={'market_id': market_id, 'side': side, 'price': price, 'size': size},
                timeout=10
            )
            return response.json() if response.ok else None
        except:
            return None

class InefficiencyDetector:
    def __init__(self, lookback_window: int = 15):
        self.lookback_window = lookback_window
        self.price_history = defaultdict(list)
    
    def record_price(self, market_id: str, price: float):
        if len(self.price_history[market_id]) >= 200:
            self.price_history[market_id].pop(0)
        self.price_history[market_id].append((time.time(), price))
    
    def detect_reprice_opportunity(self, market_id: str, current_price: float, 
                                   min_edge: float = 2.5) -> Tuple[bool, float]:
        if market_id not in self.price_history or len(self.price_history[market_id]) < 5:
            return False, 0.0
        
        prices = self.price_history[market_id]
        recent_prices = [p for t, p in prices if time.time() - t < self.lookback_window]
        
        if len(recent_prices) < 3:
            return False, 0.0
        
        price_changes = [abs(recent_prices[i] - recent_prices[i-1]) for i in range(1, len(recent_prices))]
        
        if not price_changes:
            return False, 0.0
        
        avg_change = statistics.mean(price_changes)
        volatility = statistics.stdev(price_changes) if len(price_changes) > 1 else 0
        
        edge = (volatility / (avg_change + 0.001)) * 100
        direction = 1 if recent_prices[-1] - recent_prices[0] > 0 else -1
        
        return edge > min_edge, direction * edge

class PositionManager:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Trade] = []
        self.trade_counter = 0
    
    def open_position(self, market_id: str, market_name: str, entry_price: float, size: float) -> Position:
        pos_id = f"pos_{self.trade_counter}"
        self.trade_counter += 1
        position = Position(pos_id, market_id, market_name, entry_price, entry_price, size, 
                          datetime.now().isoformat(), 0)
        self.positions[pos_id] = position
        logger.info(f"Opened: {market_name} @ {entry_price}")
        return position
    
    def close_position(self, pos_id: str, exit_price: float) -> Optional[Trade]:
        if pos_id not in self.positions:
            return None
        pos = self.positions[pos_id]
        pnl = (exit_price - pos.entry_price) * pos.size
        roi = ((exit_price - pos.entry_price) / pos.entry_price) * 100
        
        trade = Trade(pos.market_id, pos.market_name, pos.entry_price, exit_price, pos.size, pnl, roi,
                     pos.entry_time, datetime.now().isoformat(), 'buy' if exit_price > pos.entry_price else 'sell')
        self.closed_trades.append(trade)
        del self.positions[pos_id]
        logger.info(f"Closed {pos_id}: PnL=${pnl:.2f}")
        return trade
    
    def update_position(self, pos_id: str, new_price: float):
        if pos_id in self.positions:
            self.positions[pos_id].update_price(new_price)
    
    def get_active_count(self) -> int:
        return len(self.positions)
    
    def can_open_new_position(self) -> bool:
        return len(self.positions) < 50
    
    def get_stats(self) -> Dict:
        if not self.closed_trades:
            return {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0, 'avg_roi': 0}
        
        pnls = [t.pnl for t in self.closed_trades]
        wins = len([p for p in pnls if p > 0])
        
        return {
            'total_trades': len(self.closed_trades),
            'total_pnl': sum(pnls),
            'win_rate': wins / len(self.closed_trades),
            'avg_roi': statistics.mean([t.roi for t in self.closed_trades]),
        }

class PolymarketBot:
    def __init__(self):
        self.api = PolymarketAPI()
        self.detector = InefficiencyDetector(15)
        self.positions = PositionManager()
        
        self.min_edge = float(os.getenv('MIN_EDGE', '2.5'))
        self.max_position_size = float(os.getenv('MAX_POSITION', '5000'))
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '0.02'))
        
        self.running = False
        self.start_time = None
        logger.info(f"Bot init: edge={self.min_edge}%, pos=${self.max_position_size}")
    
    def calculate_position_size(self, edge: float) -> float:
        edge_factor = min(edge / 10.0, 2.0)
        base_size = self.max_position_size * self.risk_per_trade * edge_factor
        return min(base_size, self.max_position_size)
    
    def scan_markets(self) -> List[Dict]:
        markets = self.api.get_markets(100)
        opportunities = []
        
        for market in markets:
            try:
                market_id = market.get('id')
                market_name = market.get('question')
                
                if not market_id or not market_name:
                    continue
                
                price_data = self.api.get_market_prices(market_id)
                if not price_data:
                    continue
                
                current_price = price_data.get('mid_price', 0.5)
                self.detector.record_price(market_id, current_price)
                
                has_opp, edge = self.detector.detect_reprice_opportunity(market_id, current_price, self.min_edge)
                
                if has_opp and self.positions.can_open_new_position():
                    opportunities.append({
                        'market_id': market_id,
                        'market_name': market_name,
                        'current_price': current_price,
                        'edge': edge,
                    })
            except:
                pass
        
        return sorted(opportunities, key=lambda x: abs(x['edge']), reverse=True)
    
    def execute_trade(self, opp: Dict) -> Optional[Position]:
        market_id = opp['market_id']
        market_name = opp['market_name']
        current_price = opp['current_price']
        edge = opp['edge']
        
        side = 'buy' if edge > 0 else 'sell'
        size = self.calculate_position_size(abs(edge))
        
        if size < 10:
            return None
        
        order = self.api.place_order(market_id, side, current_price, size)
        if not order:
            return None
        
        return self.positions.open_position(market_id, market_name, current_price, size)
    
    def update_positions(self):
        for pos_id, position in list(self.positions.positions.items()):
            try:
                price_data = self.api.get_market_prices(position.market_id)
                if price_data:
                    new_price = price_data.get('mid_price', position.current_price)
                    self.positions.update_position(pos_id, new_price)
                    
                    roi = position.roi()
                    if roi > 20 or roi < -10:
                        self.positions.close_position(pos_id, new_price)
            except:
                pass
    
    def run_loop(self):
        self.running = True
        self.start_time = datetime.now()
        logger.info("Bot started")
        
        while self.running:
            try:
                opps = self.scan_markets()
                for opp in opps[:5]:
                    if self.positions.can_open_new_position():
                        self.execute_trade(opp)
                
                self.update_positions()
                stats = self.positions.get_stats()
                if stats['total_trades'] > 0 and stats['total_trades'] % 10 == 0:
                    logger.info(f"Trades: {stats['total_trades']}, PnL: ${stats['total_pnl']:.2f}")
                
                time.sleep(2)
            except Exception as e:
                logger.error(f"Bot error: {e}")

bot = None

def start_bot():
    global bot
    if bot is None:
        bot = PolymarketBot()
        thread = threading.Thread(target=bot.run_loop, daemon=True)
        thread.start()
        logger.info("Bot thread started")

@app.before_request
def initialize():
    start_bot()

@app.route('/')
def index():
    return '<h1>Polymarket Bot</h1><p>Visit <a href="/dashboard.html">/dashboard.html</a>'

@app.route('/stats')
def get_stats():
    if not bot:
        return jsonify({'error': 'Bot starting...'}), 202
    
    stats = bot.positions.get_stats()
    uptime = (datetime.now() - bot.start_time).total_seconds() if bot.start_time else 0
    
    return jsonify({
        'total_profit': stats['total_pnl'],
        'daily_avg': stats['total_pnl'] / max(uptime / 86400, 1),
        'win_rate': stats['win_rate'],
        'total_trades': stats['total_trades'],
        'active_positions': bot.positions.get_active_count(),
        'trades_per_hour': stats['total_trades'] / max(uptime / 3600, 1),
        'uptime_seconds': uptime,
    })

@app.route('/trades')
def get_trades():
    if not bot:
        return jsonify([])
    
    return jsonify([
        {
            'type': t.trade_type,
            'market': t.market_name,
            'entry': t.entry_price,
            'exit': t.exit_price,
            'pnl': t.pnl,
            'roi': t.roi,
            'time': t.exit_time,
        }
        for t in bot.closed_trades[-20:]
    ])

if __name__ == '__main__':
    start_bot()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
