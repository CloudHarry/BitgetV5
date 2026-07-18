"""
dashboard.py (V3.3 - Classic Stacked Layout with Vibrant Colors)
==============================================================
Mengembalikan tata letak menumpuk (stacked) yang rapi dan lapang,
namun disuntik dengan skema warna Rich modern (Neon/Vibrant Tags).
"""

from datetime import datetime, timezone, timedelta
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich.align import Align

# =========================================================================
# KELAS BOTSTATE (Ditambahkan kembali agar app.py tidak error saat import)
# =========================================================================
class BotState:
    def __init__(self):
        self.running = False
        self.mode = "DRY RUN"
        self.balance_usdt = 0.0
        self.has_position = False
        self.symbol = ""
        self.side = ""
        self.size = 0.0
        self.entry_price = 0.0
        self.current_price = 0.0
        self.take_profit = 0.0
        self.stop_loss = 0.0
        self.upnl = 0.0

def render_dashboard(state, tripwire, cfg=None, last_command=""):
    # 1. Hitung Jam Live WIB (Tetap Presisi Jam Detik)
    wib_tz = timezone(timedelta(hours=7))
    wib_str = datetime.now(wib_tz).strftime("%H:%M:%S WIB")
    
    # 2. Panel Header Atas (Neon Cyan Border)
    header_table = Table.grid(expand=True)
    header_table.add_column(justify="left")
    header_table.add_column(justify="right")
    
    left_header = Text("🚀 QUANTUM SMC ALGO-TERMINAL v3.3", style="bold bright_cyan")
    right_header = Text()
    right_header.append(f" 🕒 {wib_str} ", style="bold bg:bright_blue white")
    right_header.append(f" [ {state.mode} ] ", style="bold bright_magenta")
    
    header_table.add_row(left_header, right_header)
    header_panel = Panel(header_table, border_style="bright_cyan")
    
    # 3. Kotak Monitor Kembar (Deep Sky Blue Borders)
    status_grid = Table.grid(expand=True, padding=(0, 1))
    status_grid.add_column(ratio=1)
    status_grid.add_column(ratio=1)
    
    # Kolom Kiri: System Monitor
    sys_table = Table(box=None, show_header=False, expand=True)
    sys_table.add_column(style="bold deep_sky_blue", width=18)
    sys_table.add_column(style="bold white")
    
    status_bot = "[bold spring_green3]● ONLINE[/bold spring_green3]" if state.running else "[bold red]○ OFFLINE[/bold red]"
    sys_table.add_row("🤖 Engine Status", f": {status_bot}")
    sys_table.add_row("📊 Radar Interval", f": [bright_yellow]1H[/bright_yellow] → [bright_yellow]30M[/bright_yellow] → [bright_yellow]15M[/bright_yellow]")
    sys_table.add_row("🎯 Strategy Filter", f": Smart Money Concepts (SMC)")
    sys_table.add_row("🛡️ Price Guard", f": [spring_green3]Body Close (Anti-Wick)[/spring_green3]")
    
    # Kolom Kanan: Risk Controller
    acc_table = Table(box=None, show_header=False, expand=True)
    acc_table.add_column(style="bold deep_sky_blue", width=20)
    acc_table.add_column(style="bold white")
    
    acc_table.add_row("💰 Wallet Balance", f": $[bold bright_green]{state.balance_usdt:.4f}[/bold bright_green] USDT")
    acc_table.add_row("🛑 Daily Loss Limit", f": [bold orange_red1]-$10.00[/bold orange_red1] USDT")
    
    if state.has_position:
        margin_used = (state.size * state.entry_price) / state.leverage
        acc_table.add_row("💸 Allocated Margin", f": $[bold bright_yellow]{margin_used:.2f}[/bold bright_yellow] USDT (Lev [purple]{state.leverage}x[/purple])")
    else:
        acc_table.add_row("💸 Allocated Margin", f": $0.00 USDT")
        
    acc_table.add_row("🔌 Exchange API", f": [bold spring_green3]🟢 CONNECTED[/bold spring_green3]")
    
    status_grid.add_row(
        Panel(sys_table, title="[bold white]⚙️ SYSTEM MONITOR[/bold white]", border_style="deep_sky_blue"),
        Panel(acc_table, title="[bold white]💼 RISK CONTROLLER[/bold white]", border_style="deep_sky_blue")
    )
    
    # 4. Panel Posisi Aktif Full-Width (Warna Dinamis Sesuai PnL)
    if state.has_position:
        pos_table = Table(box=None, show_header=False, expand=True)
        pos_table.add_column(ratio=1)
        pos_table.add_column(ratio=1)
        
        side_badge = "[bold bg:spring_green3 white] LONG [/bold bg:spring_green3 white]" if state.side == "long" else "[bold bg:red white] SHORT [/bold bg:red white]"
        pnl_color = "bold bright_green" if state.upnl >= 0 else "bold orange_red1"
        pnl_sign = "+" if state.upnl >= 0 else ""
        
        margin = (state.size * state.entry_price) / state.leverage
        pnl_pct = (state.upnl / margin * 100) if margin > 0 else 0.0
        
        if getattr(state, "be_activated", False):
            sl_str = f"[bold bright_yellow]{state.stop_loss:.4f} [🛡️ BE LOCKED][/bold bright_yellow]"
        else:
            sl_str = f"[bold red]{state.stop_loss:.4f}[/bold red]"
            
        pos_table.add_row(f"🏷️ Asset Symbol : [bold bright_yellow]{state.symbol}[/bold bright_yellow] {side_badge}", f"📈 Current Price : [bold white]${state.current_price:.4f}[/bold white]")
        pos_table.add_row(f"📦 Position Size : [bold cyan]{state.size:.4f} Units[/bold cyan]", f"💵 Entry Price    : [bold white]${state.entry_price:.4f}[/bold white]")
        pos_table.add_row(f"🎯 Take Profit   : [bold bright_green]${state.take_profit:.4f}[/bold bright_green]", f"🛡️ Stop Loss (SL) : {sl_str}")
        pos_table.add_row(f"📊 Unrealized PnL: [{pnl_color}]{pnl_sign}${state.upnl:.4f} ({pnl_sign}{pnl_pct:.2f}%)[/{pnl_color}]", "")
        
        border_color = "bright_green" if state.upnl >= 0 else "orange_red1"
        pos_panel = Panel(pos_table, title="[bold white]📊 ACTIVE POSITION MATRIX[/bold white]", border_style=border_color)
    else:
        empty_text = Align.center("[bold gray40]💤 Standby Mode: Radar active scanning institutional order blocks...[/bold gray40]")
        pos_panel = Panel(empty_text, title="[bold white]📊 ACTIVE POSITION MATRIX[/bold white]", border_style="gray30")
        
    # 5. Panel Logs Full-Width (Purple Border + Tag Neon)
    log_text = Text()
    if hasattr(state, 'log') and hasattr(state.log, 'get_logs'):
        logs = state.log.get_logs()[-6:]
        for log_line in logs:
            if "[SUCCESS]" in log_line:
                log_line = log_line.replace("[SUCCESS]", "[bold bright_green][SUCCESS][/bold bright_green]")
            elif "[INFO]" in log_line:
                log_line = log_line.replace("[INFO]", "[bold bright_cyan][INFO][/bold bright_cyan]")
            elif "[WARNING]" in log_line:
                log_line = log_line.replace("[WARNING]", "[bold bright_yellow][WARNING][/bold bright_yellow]")
            log_text.append(log_line + "\n")
    else:
        log_text.append("[gray40]Terminal ready. Awaiting algo engine initialization...[/gray40]")
        
    log_panel = Panel(log_text, title="[bold white]📜 SYSTEM OPERATION LOGS[/bold white]", border_style="purple")
    
    # 6. Footer Prompt (Bright Cyan & Neon Green Accents)
    footer = Text.from_markup(
        f" [bold bright_cyan]scan[/bold bright_cyan]=[gray60]Force Scan[/gray60] │ "
        f"[bold orange_red1]close[/bold orange_red1]=[gray60]Force Close[/gray60] │ "
        f"[bold bright_magenta]q[/bold magenta]=[gray60]Quit Engine[/gray60] ─── "
        f"[bold white]Console Prompt >[/bold white] [bold bright_green]{last_command}[/bold bright_green]"
    )
    
    return Group(header_panel, status_grid, pos_panel, log_panel, footer)