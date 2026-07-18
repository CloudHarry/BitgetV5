"""
trading_bot_v5.py
=================
Engine Strategi V5: Multi-Timeframe Bias 1H -> Confluence Entry 15M -> Confidence Scoring.
Aturan Mutlak: No Spread Limit & Fixed Lot Size 0.01 (Mengabaikan hitungan dynamic lot).
"""

import pandas as pd
import pandas_ta as ta

class TradingBotV5SMC:
    def __init__(self, client, symbol):
        self.client = client
        self.symbol = symbol

    def fetch_candles(self, timeframe, limit=200):
        try:
            bars = self.client.fetch_ohlcv(self.symbol, timeframe=timeframe, limit=limit)
            if not bars:
                return None
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df
        except Exception:
            return None

    def cek_bias_1j(self, df_1h):
        """
        Mengukur arah tren makro dan kekuatan volume di TF 1 Jam.
        Maksimal skor = 4.
        """
        if len(df_1h) < 50:
            return "netral", 0, 0.0

        close = df_1h['close']
        volume = df_1h['volume']

        # Indikator
        ema50 = ta.ema(close, length=50)
        ema200 = ta.ema(close, length=200)
        rsi = ta.rsi(close, length=14)
        vol_ma20 = ta.sma(volume, length=20)
        adx_df = ta.adx(df_1h['high'], df_1h['low'], close, length=14)
        
        if ema50 is None or ema200 is None or rsi is None or vol_ma20 is None or adx_df is None:
            return "netral", 0, 0.0

        adx_1j = adx_df['ADX_14'].iloc[-1]

        # Market structure — 10 candle terakhir dibanding 10 candle sebelumnya
        last_10_high = float(df_1h['high'].iloc[-10:].max())
        prev_10_high = float(df_1h['high'].iloc[-20:-10].max())
        last_10_low = float(df_1h['low'].iloc[-10:].min())
        prev_10_low = float(df_1h['low'].iloc[-20:-10].min())

        higher_high = last_10_high > prev_10_high
        higher_low = last_10_low > prev_10_low

        # Evaluasi LONG
        skor_long = 0
        if close.iloc[-1] > ema50.iloc[-1] and ema50.iloc[-1] > ema200.iloc[-1]:
            skor_long += 1
        if 50 <= rsi.iloc[-1] <= 65:
            skor_long += 1
        if volume.iloc[-1] > vol_ma20.iloc[-1]:
            skor_long += 1
        if higher_high and higher_low:
            skor_long += 1

        if skor_long >= 3:
            return "long", skor_long, adx_1j

        # Evaluasi SHORT
        skor_short = 0
        if close.iloc[-1] < ema50.iloc[-1] and ema50.iloc[-1] < ema200.iloc[-1]:
            skor_short += 1
        if 35 <= rsi.iloc[-1] <= 50:
            skor_short += 1
        if volume.iloc[-1] > vol_ma20.iloc[-1]:
            skor_short += 1
        if not higher_high and not higher_low:
            skor_short += 1

        if skor_short >= 3:
            return "short", skor_short, adx_1j

        return "netral", 0, adx_1j

    def cek_entry_15m(self, df_15m, arah_htf):
        """
        Mencari konfluensi pemicu entry di TF 15 Menit (OB, FVG, RSI).
        """
        if len(df_15m) < 20:
            return 0, 0.0, 0.0, 0.0

        close = df_15m['close']
        open_p = df_15m['open']
        high = df_15m['high']
        low = df_15m['low']
        volume = df_15m['volume']
        
        rsi = ta.rsi(close, length=14)
        vol_ma20_15m = ta.sma(volume, length=20)

        konfluensi = 0
        entry_harga = 0.0
        sl_level = 0.0
        vol_15m_last = volume.iloc[-1]

        if arah_htf == "long":
            # 1. DETECT BULLISH ORDER BLOCK (3 Bearish -> 1 Bullish Break + Retest)
            for i in range(3, len(df_15m) - 1):
                bear_seq = (close.iloc[i-3] < open_p.iloc[i-3]) and (close.iloc[i-2] < open_p.iloc[i-2]) and (close.iloc[i-1] < open_p.iloc[i-1])
                bullish_break = close.iloc[i] > high.iloc[i-1]
                retest = low.iloc[i] <= low.iloc[i-1]
                if bear_seq and bullish_break and retest:
                    konfluensi += 1
                    entry_harga = float(close.iloc[i])
                    sl_level = float(low.iloc[i-3] * 0.998) # 0.2% buffer

            # 2. DETECT BULLISH FVG RETEST
            for i in range(2, len(df_15m) - 1):
                fvg_top = low.iloc[i]     
                fvg_bot = high.iloc[i-1]  
                gap_size = fvg_top - fvg_bot
                if gap_size > 0:
                    retest_fvg = fvg_bot <= close.iloc[i+1] <= fvg_top
                    if retest_fvg:
                        konfluensi += 1
                        if entry_harga == 0.0:
                            entry_harga = float(close.iloc[i+1])
                            sl_level = float(low.iloc[i-2] * 0.998)

            # 3. RSI Reversal
            if rsi.iloc[-1] < 30 and rsi.iloc[-1] > rsi.iloc[-2]:
                konfluensi += 1

        elif arah_htf == "short":
            # 1. DETECT BEARISH ORDER BLOCK (3 Bullish -> 1 Bearish Break + Retest)
            for i in range(3, len(df_15m) - 1):
                bull_seq = (close.iloc[i-3] > open_p.iloc[i-3]) and (close.iloc[i-2] > open_p.iloc[i-2]) and (close.iloc[i-1] > open_p.iloc[i-1])
                bearish_break = close.iloc[i] < low.iloc[i-1]
                retest = high.iloc[i] >= high.iloc[i-1]
                if bull_seq and bearish_break and retest:
                    konfluensi += 1
                    entry_harga = float(close.iloc[i])
                    sl_level = float(high.iloc[i-3] * 1.002) # 0.2% buffer

            # 2. DETECT BEARISH FVG RETEST
            for i in range(2, len(df_15m) - 1):
                fvg_bot = high.iloc[i]    
                fvg_top = low.iloc[i-1]   
                gap_size = fvg_top - fvg_bot
                if gap_size > 0:
                    retest_fvg = fvg_bot <= close.iloc[i+1] <= fvg_top
                    if retest_fvg:
                        konfluensi += 1
                        if entry_harga == 0.0:
                            entry_harga = float(close.iloc[i+1])
                            sl_level = float(high.iloc[i-2] * 1.002)

            # 3. RSI Overbought Reversal
            if rsi.iloc[-1] > 70 and rsi.iloc[-1] < rsi.iloc[-2]:
                konfluensi += 1

        return konfluensi, entry_harga, sl_level, vol_15m_last

    def execute_v5_smc_logic(self):
        """
        Orkestrator Utama Eksekusi V5.
        """
        df_1h = self.fetch_candles('1h', limit=200)
        df_15m = self.fetch_candles('15m', limit=100)

        if df_1h is None or df_15m is None:
            return "SKIP", "Gagal memuat candlestick bursa"

        # 1. Cek Bias Makro 1H
        arah, skor_bias, adx_1j = self.cek_bias_1j(df_1h)
        if arah == "netral" or skor_bias < 3:
            return "WAIT", f"Arah tidak clear. Bias: {arah} ({skor_bias}/4)"

        # 2. Cek Pemicu Entry 15M
        konfluensi, entry, sl, vol_15m_last = self.cek_entry_15m(df_15m, arah)
        if konfluensi < 2 or entry == 0.0:
            return "WAIT", f"Konfluensi entry kurang ({konfluensi}/3) pada arah {arah.upper()}"

        # 3. Hitung Boosted Confidence Score (Keyakinan)
        keyakinan = 0.0

        if skor_bias == 4:
            keyakinan += 3
        elif skor_bias == 3:
            keyakinan += 2

        if konfluensi == 3:
            keyakinan += 4
        elif konfluensi == 2:
            keyakinan += 3

        if adx_1j > 25:
            keyakinan += 1.5

        # Volume MA 15m Booster
        vol_ma20_15m = ta.sma(df_15m['volume'], length=20)
        if vol_ma20_15m is not None and not vol_ma20_15m.isna().iloc[-1]:
            if vol_15m_last > (vol_ma20_15m.iloc[-1] * 1.5):
                keyakinan += 1

        # Syarat Mutlak Eksekusi: Keyakinan >= 8
        if keyakinan < 8:
            return "SKIP", f"Filter keyakinan gagal ({keyakinan}/10). Sinyal dibatalkan."

        # 4. Hitung Target Berdasarkan Jarak Risk Multi-TP
        sl_distance = abs(entry - sl)
        
        if arah == "long":
            tp1 = entry + (sl_distance * 2)
            tp2 = entry + (sl_distance * 3)
            tp3 = entry + (sl_distance * 5)
            status_action = "EXECUTE_LONG"
        else:
            tp1 = entry - (sl_distance * 2)
            tp2 = entry - (sl_distance * 3)
            tp3 = entry - (sl_distance * 5)
            status_action = "EXECUTE_SHORT"

        return status_action, {
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "skor_bias": skor_bias,
            "konfluensi": konfluensi,
            "confidence": keyakinan
        }
