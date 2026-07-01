from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot OK'

@app.route('/stats')
def stats():
    return jsonify({'total_profit': 0, 'win_rate': 0, 'total_trades': 0, 'uptime_seconds': 0, 'active_positions': 0, 'daily_avg': 0, 'trades_per_hour': 0})

@app.route('/trades')
def trades():
    return jsonify([])

@app.route('/dashboard.html')
def dashboard():
    return '<h1>Bot Dashboard</h1>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
