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

# Read dashboard.html
try:
    with open('dashboard.html', 'r') as f:
        dashboard_content = f.read()
except:
    dashboard_content = '<h1>Dashboard not found</h1>'

class SimplifiedBot:
    def __init__(self):
        self.private_key = os.getenv('POLYMARKET_PRIVATE_KEY', '')
        self.min_edge = float(os.getenv('MIN_EDGE', '2.5'))
        self.max_position = float(os.getenv('MAX_POSITION', '5000'))
        
        self.trades = []
        self.positions = {}
        self.price_history = defaultdict(list)
        self.start_time = datetime.now()
        self.running = False
        self.api_base = 'https://clob.polymarket.com'
        
        logger.info(f"Bot initialized - Edge: {self.min_edge}%, Max Position: ${self.max_position}")
    
    def get_markets(self):
        """Fetch markets from Polymarket"""
        try:
            response = requests.get(
                f'{self.api_base}/markets',
                params={'limit': 50, 'status': 'active'},
                timeout=5
            )
            return response.json() if response.ok else []
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    def get_market_price(self, market_id):
        """Get market price"""
        try:
            response =
