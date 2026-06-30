#!/usr/bin/env python3
"""
Polymarket Quant Bot - Railway Edition (Fixed)
Runs on Railway cloud + Flask API for mobile monitoring
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
import requests
from collections import defaultdict
import statistics
import threading
from flask import Flask, jsonify, request

# Configure logging
logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(levelname)s - %(message)s',
   handlers=[
       logging.FileHandler('bot.log'),
       logging.StreamHandler()
   ]
)
logger = logging.getLogger(__name__)

# Create Flask app (MUST be at module level for gunicorn)
app = Flask(__name__)


@dataclass
class Position:
   """Represents an active position"""
   id: str
   market_id: str
   market_name: str
   entry_price: float
   current_price: float
   size: float
   entry_time: str
   unrealized_pnl: float

   def roi(self) -> float:
       if self.entry_price == 0:
           return 0
       return ((self.current_price - self.entry_price) / self.entry_price) * 100

   def update_price(self, new_price: float):
       self.current_price = new_price
       self.unrealized_pnl = (new_price - self.entry_price) * self.size


@dataclass
class Trade:
   """Completed trade record"""
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
   """Polymarket REST API interface"""

   BASE_URL = "https://clob.polymarket.com"

   def __init__(self, api_key: Optional[str] = None, private_key: Optional[str] = None):
       self.api_key = api_key or os.getenv('POLYMARKET_API_KEY')
       self.private_key = private_key or os.getenv('POLYMARKET_PRIVATE_KEY')
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
           response.raise_for_status()
           return response.json()
       except Exception as e:
           logger.error(f"Error fetching markets: {e}")
           return []

   def get_market_prices(self, market_id: str) -> Optional[Dict]:
       try:
           response = self.session.get(
               f"{self.BASE_URL}/markets/{market_id}",
               timeout=5
           )
           response.raise_for_status()
           return response.json()
       except Exception as e:
           logger.error(f"Error fetching prices: {e}")
           return None

   def place_order(self, market_id: str, side: str, price: float, size: float) -> Optional[Dict]:
       if not self.api_key:
           logger.warning("No API key - simulation mode")
           return {'order_id': f'sim_{market_id}_{int(time.time())}', 'status': 'simulated'}

       try:
           payload = {
               'market_id': market_id,
               'side': side,
               'price': price,
               'size': size
           }
           response = self.session.post(
               f"{self.BASE_URL}/orders",
               json=payload,
               timeout=10
           )
           response.raise_for_status()
           return response.json()
       except Exception as e:
           logger.error(f"Error placing order: {e}")
           return None


class InefficiencyDetector:
   """Detects pricing inefficiencies"""

   def __init__(self, lookback_window: int = 15):
       self.lookback_window = lookback_window
       self.price_history = defaultdict(list)
       self.max_history = 200

   def record_price(self, market_id: str, price: float):
       if len(self.price_history[market_id]) >= self.max_history:
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

       price_changes = [abs(recent_prices[i] - recent_prices[i-1])
                       for i in range(1, len(recent_prices))]

       if not price_changes:
           return False, 0.0

       avg_change = statistics.mean(price_changes)
       volatility = statistics.stdev(price_changes) if len(price_changes) > 1 else 0

       movement_potential = volatility / (avg_change + 0.001)
       edge = movement_potential * 100

       recent_movement = recent_prices[-1] - recent_prices[0]
       direction = 1 if recent_movement > 0 else -1

       return edge > min_edge, direction * edge


class PositionManager:
   """Manages active positions and closed trades"""

   def __init__(self, max_concurrent: int = 50):
       self.positions: Dict[str, Position] = {}
       self.closed_trades: List[Trade] = []
       self.trade_counter = 0

   def open_position(self, market_id: str, market_name: str,
                    entry_price: float, size: float) -> Position:
       pos_id = f"pos_{self.trade_counter}"
       self.trade_counter += 1

       position = Position(
           id=pos_id,
           market_id=market_id,
           market_name=market_name,
           entry_price=entry_price,
           current_price=entry_price,
           size=size,
           entry_time=datetime.now().isoformat(),
           unrealized_pnl=0
       )

       self.positions[pos_id] = position
       logger.info(f"Opened: {market_name} @ {entry_price} x {size}")
       return position

   def close_position(self, pos_id: str, exit_price: float) -> Optional[Trade]:
       if pos_id not in self.positions:
           return None

       pos = self.positions[pos_id]
       pnl = (exit_price - pos.entry_price) * pos.size
       roi = ((exit_price - pos.entry_price) / pos.entry_price) * 100

       trade = Trade(
           market_id=pos.market_id,
           market_name=pos.market_name,
           entry_price=pos.entry_price,
           exit_price=exit_price,
           size=pos.size,
           pnl=pnl,
           roi=roi,
           entry_time=pos.entry_time,
           exit_time=datetime.now().isoformat(),
           trade_type='buy' if exit_price > pos.entry_price else 'sell'
       )

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
       return self.get_active_count() < 50

   def get_stats(self) -> Dict:
       if not self.closed_trades:
           return {
               'total_trades': 0,
               'total_pnl': 0,
               'win_rate': 0,
               'avg_roi': 0,
           }

       pnls = [t.pnl for t in self.closed_trades]
       wins = len([p for p in pnls if p > 0])

       return {
           'total_trades': len(self.closed_trades),
           'total_pnl': sum(pnls),
           'win_rate': wins / len(self.closed_trades),
           'avg_roi': statistics.mean([t.roi for t in self.closed_trades]),
       }


class PolymarketBot:
   """Main trading bot"""

   def __init__(self):
       self.api = PolymarketAPI()
       self.detector = InefficiencyDetector(lookback_window=15)
       self.positions = PositionManager()

       self.min_edge = float(os.getenv('MIN_EDGE', '2.5'))
       self.max_position_size = float(os.getenv('MAX_POSITION', '5000'))
       self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '0.02'))

       self.running = False
       self.start_time = None

       logger.info(f"Bot init: edge={self.min_edge}%, pos=${self.max_position_size}")

   def calculate_position_size(self, market_id: str, edge: float) -> float:
       edge_factor = min(edge / 10.0, 2.0)
       base_size = self.max_position_size * self.risk_per_trade * edge_factor
       return min(base_size, self.max_position_size)

   def scan_markets(self) -> List[Dict]:
       markets = self.api.get_markets(limit=100)
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

               has_opportunity, edge = self.detector.detect_reprice_opportunity(
                   market_id, current_price, min_edge=self.min_edge
               )

               if has_opportunity and self.positions.can_open_new_position():
                   opportunities.append({
                       'market_id': market_id,
                       'market_name': market_name,
                       'current_price': current_price,
                       'edge': edge,
                   })
           except Exception as e:
               logger.error(f"Scan error: {e}")

       return sorted(opportunities, key=lambda x: abs(x['edge']), reverse=True)

   def execute_trade(self, opportunity: Dict) -> Optional[Position]:
       market_id = opportunity['market_id']
       market_name = opportunity['market_name']
       current_price = opportunity['current_price']
       edge = opportunity['edge']

       trade_side = 'buy' if edge > 0 else 'sell'
       position_size = self.calculate_position_size(market_id, abs(edge))

       if position_size < 10:
           return None

       order = self.api.place_order(
           market_id=market_id,
           side=trade_side,
           price=current_price,
           size=position_size
       )

       if not order:
           return None

       position = self.positions.open_position(
           market_id=market_id,
           market_name=market_name,
           entry_price=current_price,
           size=position_size
       )

       return position

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
           except Exception as e:
               logger.error(f"Update error: {e}")

   def run_loop(self):
       self.running = True
       self.start_time = datetime.now()
       logger.info("Bot started")

       try:
           while self.running:
               opportunities = self.scan_markets()

               for opp in opportunities[:5]:
                   if self.positions.can_open_new_position():
                       self.execute_trade(opp)

               self.update_positions()

               stats = self.positions.get_stats()
               if stats['total_trades'] > 0 and stats['total_trades'] % 10 == 0:
                   logger.info(f"Stats: {stats['total_trades']} trades, "
                              f"${stats['total_pnl']:.2f} PnL")

               time.sleep(2)
       except KeyboardInterrupt:
           logger.info("Bot stopped")
       except Exception as e:
           logger.error(f"Bot error: {e}")

   def stop(self):
       self.running = False
       logger.info("Bot stopped cleanly")


# Global bot instance
bot = None
bot_thread = None


# Flask Routes
@app.route('/', methods=['GET'])
def index():
   return '''
   <html>
   <head><title>Polymarket Bot</title></head>
   <body style="background: #0f172a; color: white; font-family: sans-serif; padding: 20px;">
       <h1>Polymarket Trading Bot</h1>
       <p>Bot is running. Visit <a href="/dashboard.html">/dashboard.html</a> to monitor.</p>
       <p>Or check stats at <a href="/stats">/stats</a></p>
   </body>
   </html>
   '''


@app.route('/health', methods=['GET'])
def health():
   return jsonify({'status': 'running', 'timestamp': datetime.now().isoformat()}), 200


@app.route('/stats', methods=['GET'])
def get_stats():
   if not bot:
       return jsonify({'error': 'Bot not initialized'}), 500

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
   }), 200


@app.route('/positions', methods=['GET'])
def get_positions():
   if not bot:
       return jsonify({'error': 'Bot not initialized'}), 500

   positions = [
       {
           'id': pos.id,
           'market': pos.market_name,
           'entry': pos.entry_price,
           'current': pos.current_price,
           'size': pos.size,
           'unrealized': pos.unrealized_pnl,
           'timestamp': pos.entry_time,
       }
       for pos in bot.positions.positions.values()
   ]

   return jsonify(positions), 200


@app.route('/trades', methods=['GET'])
def get_trades():
   if not bot:
       return jsonify({'error': 'Bot not initialized'}), 500

   trades = [
       {
           'type': trade.trade_type,
           'market': trade.market_name,
           'entry': trade.entry_price,
           'exit': trade.exit_price,
           'pnl': trade.pnl,
           'roi': trade.roi,
           'time': trade.exit_time,
       }
       for trade in bot.closed_trades[-20:]
   ]

   return jsonify(trades), 200


def start_bot():
   """Start bot in background thread"""
   global bot, bot_thread

   if bot is None:
       bot = PolymarketBot()
       bot_thread = threading.Thread(target=bot.run_loop, daemon=True)
       bot_thread.start()
       logger.info("Bot thread started")


if __name__ == '__main__':
   start_bot()

   port = int(os.getenv('PORT', 5000))
   logger.info(f"Starting Flask on port {port}")
   app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
