"""
WebSocket API for Live Price Streaming
Provides real-time price updates for trading platform.

Usage:
  ws://localhost:8000/ws/prices/{symbol}
  ws://localhost:8000/ws/prices  (subscribe to multiple via message)
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set, List
import asyncio
import json
import logging
from datetime import datetime
import yfinance as yf

logger = logging.getLogger(__name__)
router = APIRouter()

# =============================================================================
# CONNECTION MANAGER
# =============================================================================

class PriceConnectionManager:
    """Manages WebSocket connections for price streaming"""
    
    def __init__(self):
        # symbol -> set of websocket connections
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        self.active_connections: Set[WebSocket] = set()
        self._price_cache: Dict[str, Dict] = {}
        self._running = False
        self._task = None
    
    async def connect(self, websocket: WebSocket, symbols: List[str] = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        if symbols:
            for symbol in symbols:
                symbol = symbol.upper()
                if symbol not in self.subscriptions:
                    self.subscriptions[symbol] = set()
                self.subscriptions[symbol].add(websocket)
        
        # Start price streaming if not already running
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._stream_prices())
        
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        
        # Remove from all subscriptions
        for symbol, connections in list(self.subscriptions.items()):
            connections.discard(websocket)
            if not connections:
                del self.subscriptions[symbol]
        
        # Stop streaming if no connections
        if not self.active_connections and self._running:
            self._running = False
            if self._task:
                self._task.cancel()
        
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def subscribe(self, websocket: WebSocket, symbol: str):
        """Subscribe a connection to a symbol"""
        symbol = symbol.upper()
        if symbol not in self.subscriptions:
            self.subscriptions[symbol] = set()
        self.subscriptions[symbol].add(websocket)
        
        # Send current price immediately
        if symbol in self._price_cache:
            await websocket.send_json(self._price_cache[symbol])
    
    async def unsubscribe(self, websocket: WebSocket, symbol: str):
        """Unsubscribe a connection from a symbol"""
        symbol = symbol.upper()
        if symbol in self.subscriptions:
            self.subscriptions[symbol].discard(websocket)
    
    async def broadcast_price(self, symbol: str, price_data: Dict):
        """Send price update to all subscribers of a symbol"""
        symbol = symbol.upper()
        self._price_cache[symbol] = price_data
        
        if symbol not in self.subscriptions:
            return
        
        disconnected = set()
        for websocket in self.subscriptions[symbol]:
            try:
                await websocket.send_json(price_data)
            except Exception as e:
                logger.warning(f"Failed to send to websocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected
        for ws in disconnected:
            await self.disconnect(ws)
    
    async def _stream_prices(self):
        """Background task to fetch and stream prices"""
        while self._running:
            try:
                symbols = list(self.subscriptions.keys())
                if not symbols:
                    await asyncio.sleep(1)
                    continue
                
                # Fetch prices for all subscribed symbols
                for symbol in symbols:
                    try:
                        price_data = await self._fetch_price(symbol)
                        if price_data:
                            await self.broadcast_price(symbol, price_data)
                    except Exception as e:
                        logger.error(f"Error fetching price for {symbol}: {e}")
                
                # Update every 2 seconds (to avoid rate limits)
                await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Price streaming error: {e}")
                await asyncio.sleep(5)
    
    async def _fetch_price(self, symbol: str) -> Dict:
        """Fetch current price for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            # Use fast_info for quick price
            try:
                last_price = ticker.fast_info.get('lastPrice', 0)
                prev_close = ticker.fast_info.get('previousClose', 0)
            except:
                # Fallback to history
                hist = ticker.history(period="2d")
                if hist.empty:
                    return None
                last_price = float(hist['Close'].iloc[-1])
                prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else last_price
            
            change = last_price - prev_close
            change_percent = (change / prev_close * 100) if prev_close > 0 else 0
            
            return {
                "type": "price",
                "symbol": symbol,
                "price": round(last_price, 2),
                "change": round(change, 2),
                "changePercent": round(change_percent, 2),
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None

# Global manager instance
price_manager = PriceConnectionManager()

# =============================================================================
# WEBSOCKET ENDPOINTS
# =============================================================================

@router.websocket("/ws/prices/{symbol}")
async def websocket_price_single(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for single symbol price streaming"""
    await price_manager.connect(websocket, [symbol])
    
    try:
        while True:
            # Handle incoming messages (subscribe/unsubscribe commands)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "subscribe":
                    await price_manager.subscribe(websocket, msg.get("symbol", ""))
                elif msg.get("action") == "unsubscribe":
                    await price_manager.unsubscribe(websocket, msg.get("symbol", ""))
                elif msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": int(datetime.now().timestamp() * 1000)})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await price_manager.disconnect(websocket)

@router.websocket("/ws/prices")
async def websocket_price_multi(websocket: WebSocket):
    """WebSocket endpoint for multi-symbol price streaming"""
    await price_manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action")
                symbol = msg.get("symbol", "")
                
                if action == "subscribe" and symbol:
                    await price_manager.subscribe(websocket, symbol)
                    await websocket.send_json({
                        "type": "subscribed",
                        "symbol": symbol.upper(),
                        "timestamp": int(datetime.now().timestamp() * 1000)
                    })
                elif action == "unsubscribe" and symbol:
                    await price_manager.unsubscribe(websocket, symbol)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "symbol": symbol.upper()
                    })
                elif action == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": int(datetime.now().timestamp() * 1000)
                    })
                elif action == "subscribe_batch":
                    symbols = msg.get("symbols", [])
                    for s in symbols:
                        await price_manager.subscribe(websocket, s)
                    await websocket.send_json({
                        "type": "subscribed_batch",
                        "symbols": [s.upper() for s in symbols]
                    })
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
    except WebSocketDisconnect:
        await price_manager.disconnect(websocket)

# =============================================================================
# ALERT WEBSOCKET
# =============================================================================

class AlertManager:
    """Manages price alerts"""
    
    def __init__(self):
        self.alerts: Dict[str, List[Dict]] = {}  # symbol -> list of alerts
        self.connections: Set[WebSocket] = set()
    
    async def check_alerts(self, symbol: str, price: float):
        """Check if any alerts should fire"""
        if symbol not in self.alerts:
            return
        
        triggered = []
        remaining = []
        
        for alert in self.alerts[symbol]:
            condition = alert.get("condition", "above")
            target = alert.get("target", 0)
            
            should_fire = False
            if condition == "above" and price >= target:
                should_fire = True
            elif condition == "below" and price <= target:
                should_fire = True
            
            if should_fire:
                triggered.append(alert)
            else:
                remaining.append(alert)
        
        self.alerts[symbol] = remaining
        
        # Broadcast triggered alerts
        for alert in triggered:
            alert_msg = {
                "type": "alert",
                "symbol": symbol,
                "price": price,
                "condition": alert.get("condition"),
                "target": alert.get("target"),
                "message": f"{symbol} {'above' if alert.get('condition') == 'above' else 'below'} ${alert.get('target')}",
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            await self._broadcast(alert_msg)
    
    async def _broadcast(self, message: Dict):
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except:
                pass

alert_manager = AlertManager()
