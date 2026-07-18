"""
app.py (V5.0) - SMC Orchestrator dengan Multi-TP & Fixed Lot size 0.01
=====================================================================
Mode: DRY RUN / LIVE Simulator (Dua Arah)
Sistem Proteksi: Confidence Level Check >= 8 & Fixed Lot Execution
"""

import os
import threading
import time
import json
from datetime import datetime
import ccxt
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live

from monitor import Monitor
from risk_manager import TripWire
from trade_journal import TradeJournal
from dashboard import BotState, render_dashboard
from trading_bot_v5 import TradingBotV5SMC 

load_dotenv()
console = Console()

# Ambil konfigurasi mutlak dari file .env
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSWORD = os.getenv("BITGET_API_PASSWORD")
LEVERAGE = int(os.getenv("LEVERAGE", "7"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "15"))
POSITION_CHECK_SECONDS = int(os.getenv("POSITION_CHECK_SECONDS", "15"))

STATE_FILE = "bot_state_v5.json"

client = ccxt.bitget({
    "apiKey": API_KEY, "secret": API_SECRET, "password": API_PASSWORD,
    "enableRateLimit": True, "options": {"defaultType": "swap"},
})

state = BotState()
state.mode = "DRY RUN V5" if DRY_RUN else "LIVE V5"
state.running = True

# ================= FIX LOGGER & TYPO BUGS V5 =================
if not hasattr(state, 'log'):
    class SafeLog:
        def add(self, message, level="INFO"):
            if hasattr(state, 'logs') and hasattr(state.logs, 'add'):
                try: 
                    state.logs.add(message, level)
                    return
                except: pass
            elif hasattr(state, 'logs') and isinstance(state.logs, list):
                state.logs.append(f"[{level}] {message}")
                return
            print(f"[{level}] {message}")
    state.log = SafeLog()
# =============================================================

client.load_markets()

# TARGET PAIR UTAMA (Ubah sesuai dengan koin target harian agar scan berjalan instan)
symbol_list = ["XAUUSD:USDT", "BTC/USDT:USDT", "ETH/USDT:USDT"]

monitor = Monitor(client, dry_run=DRY_RUN)
tripwire = TripWire()
journal = TradeJournal()

active_position = False
current_symbol = None
_stop_event = threading.Event()
_last_command = ""

# ================= PERSISTENCE MEMORI JSON V5 =================
def save_v5_state():
    if not DRY_RUN: return
    try:
        with state.lock:
            data = {
                "active_position": active_position,
                "current_symbol": current_symbol,
                "has_position": state.has_position,
                "symbol": state.symbol,
                "side": state.side,
                "leverage": state.leverage,
                "entry_price": state.entry_price,
                "stop_loss": state.stop_loss,
                "initial_sl": getattr(state, "initial_sl", None),
                "take_profit": state.take_profit,
                "tp1": getattr(state, "tp1", None),
                "tp2": getattr(state, "tp2", None),
                "tp3": getattr(state, "tp3", None),
                "tp1_hit": getattr(state, "tp1_hit", False),
                "tp2_hit": getattr(state, "tp2_hit", False),
                "size": state.size,
                "position_opened_at": state.position_opened_at.isoformat() if state.position_opened_at else None
            }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        state.log.add(f"Gagal simpan state V5: {e}", "WARNING")

def load_v5_state():
    global active_position, current_symbol
    if not DRY_RUN or not os.path.exists(STATE_FILE): return
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        if data.get("active_position"):
            active_position = data["active_position"]
            current_symbol = data["current_symbol"]
            with state.lock:
                state.has_position = data["has_position"]
                state.symbol = data["symbol"]
                state.side = data["side"]
                state.leverage = data["leverage"]
                state.entry_price = data["entry_price"]
                state.stop_loss = data["stop_loss"]
                state.initial_sl = data.get("initial_sl")
                state.take_profit = data["take_profit"]
                state.tp1 = data.get("tp1")
                state.tp2 = data.get("tp2")
                state.tp3 = data.get("tp3")
                state.tp1_hit = data.get("tp1_hit", False)
                state.tp2_hit = data.get("tp2_hit", False)
                state.size = data["size"]
                if data["position_opened_at"]:
                    state.position_opened_at = datetime.fromisoformat(data["position_opened_at"])
            state.log.add(f"⚠️ V5 Mengingat Posisi Gantung: {current_symbol} ({state.side.upper()})", "SUCCESS")
    except Exception as e:
        state.log.add(f"Gagal load state V5: {e}", "WARNING")

def clear_v5_state():
    if not DRY_RUN: return
    if os.path.exists(STATE_FILE):
        try: os.remove(STATE_FILE)
        except: pass
# =============================================================================

def check_entry_v5(manual=False):
    global active_position, current_symbol
    if active_position: return
    if not state.running and not manual: return

    allowed, reason = tripwire.can_trade()
    if not allowed: return

    state.log.add("⚡ V5 SMC Engine: Menyisir Markets (Fixed Lot 0.01, No Spread Limit)...", "INFO")
    
    for symbol in symbol_list:
        if active_position: break
        
        # Real-time scanning log di layar terminal
        state.log.add(f"🔍 Memeriksa indikator & konfluensi SMC pada pair: {symbol}", "INFO")
        time.sleep(0.1)
        
        analyst = TradingBotV5SMC(client, symbol)
        status, setup = analyst.execute_v5_smc_logic()
        
        if status in ["EXECUTE_LONG", "EXECUTE_SHORT"]:
            side = "long" if status == "EXECUTE_LONG" else "short"
            state.log.add(f"🚀 ENTRY EKSEKUSI VALID ({setup['confidence']:.1f}/10 ✅)", "SUCCESS")
            
            entry_price = setup["entry"]
            
            # --- ATURAN MUTLAK V5: FIXED LOT SIZE 0.01 ---
            size = 0.01 
            
            active_position = True
            current_symbol = symbol
            tripwire.record_trade_open()
            
            with state.lock:
                state.has_position = True
                state.symbol = symbol
                state.side = side
                state.leverage = LEVERAGE
                state.entry_price = entry_price
                state.stop_loss = setup["sl"]
                state.initial_sl = setup["sl"]
                state.take_profit = setup["tp3"] # Target utama = TP3 (RR 1:5)
                state.tp1 = setup["tp1"]
                state.tp2 = setup["tp2"]
                state.tp3 = setup["tp3"]
                state.tp1_hit = False
                state.tp2_hit = False
                state.size = size
                state.position_opened_at = datetime.now()
            
            save_v5_state()
            
            usdt_margin = (size * entry_price) / LEVERAGE
            journal.log_entry(state.mode, symbol, side, entry_price, size, usdt_margin, LEVERAGE, setup['skor_bias']*25, setup['confidence']*10, state.balance_usdt)
            break
            
    if not active_position:
        state.log.add("Scanner V5 Selesai: Belum ada pair dengan tingkat keyakinan >= 8.", "INFO")

def check_position_v5():
    global active_position, current_symbol
    if not active_position or not current_symbol: return

    try:
        ticker = client.fetch_ticker(current_symbol)
        price = float(ticker.get("last") or ticker.get("close"))
        
        with state.lock:
            state.current_price = price
            tp1_target = getattr(state, "tp1", state.take_profit)
            tp2_target = getattr(state, "tp2", state.take_profit)
            
            if state.side == "long":
                state.upnl = round((price - state.entry_price) * state.size, 4)
                hit_sl = price <= state.stop_loss
                hit_tp = price >= state.take_profit 
                
                # Monitor hit target parsial
                if price >= tp1_target and not getattr(state, "tp1_hit", False):
                    state.log.add(f"🎯 Target TP1 Terlewati (${tp1_target:.4f}) — Rasio RR 1:2 Tercapai!", "SUCCESS")
                    state.tp1_hit = True
                    save_v5_state()
                if price >= tp2_target and not getattr(state, "tp2_hit", False):
                    state.log.add(f"🎯 Target TP2 Terlewati (${tp2_target:.4f}) — Rasio RR 1:3 Tercapai!", "SUCCESS")
                    state.tp2_hit = True
                    save_v5_state()

            else: # SHORT POSITION
                state.upnl = round((state.entry_price - price) * state.size, 4)
                hit_sl = price >= state.stop_loss
                hit_tp = price <= state.take_profit
                
                if price <= tp1_target and not getattr(state, "tp1_hit", False):
                    state.log.add(f"🎯 Target TP1 Terlewati (${tp1_target:.4f}) — Rasio RR 1:2 Tercapai!", "SUCCESS")
                    state.tp1_hit = True
                    save_v5_state()
                if price <= tp2_target and not getattr(state, "tp2_hit", False):
                    state.log.add(f"🎯 Target TP2 Terlewati (${tp2_target:.4f}) — Rasio RR 1:3 Tercapai!", "SUCCESS")
                    state.tp2_hit = True
                    save_v5_state()

        if hit_tp or hit_sl:
            reason = "TAKE_PROFIT_V5" if hit_tp else "STOP_LOSS"
            state.log.add(f"🔒 Posisi {current_symbol} Keluar via {reason}. Akhir PnL: ${state.upnl}", "SUCCESS")
            
            journal.log_close(state.mode, current_symbol, state.side, price, state.size, reason, state.upnl, state.balance_usdt)
            tripwire.record_trade_close(state.upnl)
            
            active_position = False
            current_symbol = None
            with state.lock:
                state.has_position = False
                state.symbol = "-"
                state.upnl = 0.0
                state.tp1_hit = False
                state.tp2_hit = False
            clear_v5_state()
            
    except Exception as e:
        state.log.add(f"Gagal kawal posisi V5: {e}", "WARNING")

def refresh_balance():
    try:
        balance = client.fetch_balance(params={"type": "swap"})
        usdt = balance.get("USDT", {}) or balance.get("total", {}).get("USDT")
        free = usdt.get("free") if isinstance(usdt, dict) else usdt
        if free is None: free = balance.get("free", {}).get("USDT")
        with state.lock:
            state.balance_usdt = float(free) if free is not None else state.balance_usdt
        tripwire.record_api_call(True)
    except Exception:
        tripwire.record_api_call(False)

# ================= ORKESTRASI LOOP THREADING =================
def entry_scan_loop():
    if not active_position:
        check_entry_v5(manual=True)
    last_run = time.time()
    while not _stop_event.is_set():
        if time.time() - last_run >= INTERVAL_MINUTES * 60:
            check_entry_v5()
            last_run = time.time()
        time.sleep(1)

def position_monitor_loop():
    while not _stop_event.is_set():
        check_position_v5()
        time.sleep(POSITION_CHECK_SECONDS)

def balance_loop():
    while not _stop_event.is_set():
        refresh_balance()
        time.sleep(60)

def command_loop(live: Live):
    global _last_command, active_position, current_symbol
    while not _stop_event.is_set():
        try: cmd = input()
        except EOFError: break
        cmd = cmd.strip()
        if not cmd: continue
        _last_command = cmd
        action = cmd.split()[0].lower()
        if action == "q":
            _stop_event.set()
            break
        elif action == "scan":
            threading.Thread(target=check_entry_v5, kwargs={"manual": True}, daemon=True).start()
        elif action == "close":
            active_position = False 
            current_symbol = None
            with state.lock:
                state.has_position = False
                state.symbol = "-"
                state.upnl = 0.0
            clear_v5_state()
            state.log.add("Posisi simulasi V5 dibersihkan manual.", "INFO")

def render_loop(live: Live):
    while not _stop_event.is_set():
        try: live.update(render_dashboard(state, tripwire, cfg=None, last_command=_last_command))
        except Exception: pass
        time.sleep(1)

if __name__ == "__main__":
    refresh_balance()
    load_v5_state()
    with Live(console=console, screen=True, refresh_per_second=1) as live:
        threading.Thread(target=entry_scan_loop, daemon=True).start()
        threading.Thread(target=position_monitor_loop, daemon=True).start()
        threading.Thread(target=render_loop, args=(live,), daemon=True).start()
        threading.Thread(target=balance_loop, daemon=True).start()
        try: command_loop(live)
        except KeyboardInterrupt: _stop_event.set()
