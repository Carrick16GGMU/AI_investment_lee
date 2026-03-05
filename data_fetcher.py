import yfinance as yf
import pandas as pd
import sys

def get_stock_indicators(ticker):
    try:
        # 최근 2년 데이터 가져오기 (주봉 60주선을 위해 충분한 기간 확보)
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        
        if df.empty:
            raise ValueError(f"{ticker} 데이터가 비어 있습니다. 상장폐지되었거나 잘못된 티커일 수 있습니다.")
            
        # --- 유동성 지표(Liquidity) 계산 (이중 잠금장치) ---
        try:
            shares_outstanding = stock.info.get('sharesOutstanding')
        except Exception:
            shares_outstanding = None
            
        df['AVG_VOL_20'] = df['Volume'].rolling(window=20).mean()
        df['AVG_TRD_VAL_20'] = (df['Close'] * df['Volume']).rolling(window=20).mean()
        
        if shares_outstanding and shares_outstanding > 0:
            df['TURNOVER_RATIO'] = (df['AVG_VOL_20'] / shares_outstanding) * 100
        else:
            df['TURNOVER_RATIO'] = float('nan')
            
        is_kr_market = ticker.upper().endswith('.KS') or ticker.upper().endswith('.KQ')

        # --- 일봉 지표 계산 ---
        # 단순 이동평균선 (SMA)
        for length in [5, 20, 60, 90, 120, 200]:
            df[f'SMA_{length}'] = df['Close'].rolling(window=length).mean()
            
        # RSI (14) - 평활화 방식 적용 (Wilder's Smoothing)
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI_14'] = 100 - (100 / (1 + rs))
        
        # 스토캐스틱 (Stochastic 14, 3, 3)
        low_14 = df['Low'].rolling(window=14).min()
        high_14 = df['High'].rolling(window=14).max()
        fast_k = 100 * (df['Close'] - low_14) / (high_14 - low_14)
        slow_k = fast_k.rolling(window=3).mean()  # %K
        slow_d = slow_k.rolling(window=3).mean()  # %D
        
        df['STOCHk_14_3_3'] = slow_k
        df['STOCHd_14_3_3'] = slow_d
            
        # 일목균형표 (Ichimoku Cloud)
        # 전환선 (Tenkan-sen, 9)
        high_9 = df['High'].rolling(window=9).max()
        low_9 = df['Low'].rolling(window=9).min()
        df['TENKAN_9'] = (high_9 + low_9) / 2
        
        # 기준선 (Kijun-sen, 26)
        high_26 = df['High'].rolling(window=26).max()
        low_26 = df['Low'].rolling(window=26).min()
        df['KIJUN_26'] = (high_26 + low_26) / 2
        
        # 선행스팬1 & 2 (Senkou Span A & B, +26일 Shift)
        df['SENKOU_A_26'] = ((df['TENKAN_9'] + df['KIJUN_26']) / 2).shift(26)
        
        high_52 = df['High'].rolling(window=52).max()
        low_52 = df['Low'].rolling(window=52).min()
        df['SENKOU_B_26'] = ((high_52 + low_52) / 2).shift(26)
        
        # 후행스팬 (Chikou Span, -26일 Shift)
        df['CHIKOU_26'] = df['Close'].shift(-26)
            
        # OBV (On-Balance Volume)
        delta_obv = df['Close'].diff()
        direction = delta_obv.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        df['OBV'] = (direction * df['Volume']).cumsum()
        
        # MFI_14 (Money Flow Index)
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        money_flow = typical_price * df['Volume']
        pos_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        neg_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        pos_mf_sum = pos_flow.rolling(window=14).sum()
        neg_mf_sum = neg_flow.rolling(window=14).sum()
        money_ratio = pos_mf_sum / neg_mf_sum
        df['MFI_14'] = 100 - (100 / (1 + money_ratio))
        
        # --- 주봉 지표 계산 ---
        # 데이터를 주간 단위로 리샘플링
        agg_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        weekly_df = df.resample('W').agg(agg_dict)
        
        # 주봉 이동평균선
        for length in [5, 20, 60]:
            weekly_df[f'W_SMA_{length}'] = weekly_df['Close'].rolling(window=length).mean()
        
        # --- 결과 반환 ---
        # 가장 최근 거래일 데이터 추출
        latest_daily = df.iloc[-1]
        latest_weekly = weekly_df.iloc[-1]
        
        result = {
            "Ticker": ticker,
            "Date": latest_daily.name.strftime('%Y-%m-%d'),
            "Open": float(latest_daily['Open']),
            "High": float(latest_daily['High']),
            "Low": float(latest_daily['Low']),
            "Close": float(latest_daily['Close']),
            "Volume": int(latest_daily['Volume'])
        }
        
        # 이동평균선 담기
        for length in [5, 20, 60, 90, 120, 200]:
            val = latest_daily[f'SMA_{length}']
            result[f'SMA_{length}'] = float(val) if pd.notna(val) else None
            
        result["RSI_14"] = float(latest_daily['RSI_14']) if pd.notna(latest_daily['RSI_14']) else None
        result["STOCHk_14_3_3"] = float(latest_daily['STOCHk_14_3_3']) if pd.notna(latest_daily['STOCHk_14_3_3']) else None
        result["STOCHd_14_3_3"] = float(latest_daily['STOCHd_14_3_3']) if pd.notna(latest_daily['STOCHd_14_3_3']) else None
        
        # 일목균형표 담기
        result["전환선 (Tenkan-sen)"] = float(latest_daily['TENKAN_9']) if pd.notna(latest_daily['TENKAN_9']) else None
        result["기준선 (Kijun-sen)"] = float(latest_daily['KIJUN_26']) if pd.notna(latest_daily['KIJUN_26']) else None
        result["구름대_상단 (Senkou_A)"] = float(latest_daily['SENKOU_A_26']) if pd.notna(latest_daily['SENKOU_A_26']) else None
        result["구름대_하단 (Senkou_B)"] = float(latest_daily['SENKOU_B_26']) if pd.notna(latest_daily['SENKOU_B_26']) else None
        result["후행스팬 (Chikou Span)"] = float(latest_daily['CHIKOU_26']) if pd.notna(latest_daily['CHIKOU_26']) else "해당 날짜 기준 미래 주가이므로 없음"
        
        # 거래량 지표 (OBV, MFI) 담기
        result["OBV"] = float(latest_daily['OBV']) if pd.notna(latest_daily['OBV']) else None
        result["MFI_14"] = float(latest_daily['MFI_14']) if pd.notna(latest_daily['MFI_14']) else None
        
        # 주봉 지표 담기
        for length in [5, 20, 60]:
            val = latest_weekly[f'W_SMA_{length}']
            result[f'W_SMA_{length}'] = float(val) if pd.notna(val) else None
            
        # 유동성 지표 담기 (경고용)
        result["Is_KR_Market"] = is_kr_market
        result["Shares_Outstanding"] = shares_outstanding
        result["Avg_Volume_20d"] = float(latest_daily['AVG_VOL_20']) if pd.notna(latest_daily['AVG_VOL_20']) else None
        result["Avg_Trading_Value_20d"] = float(latest_daily['AVG_TRD_VAL_20']) if pd.notna(latest_daily['AVG_TRD_VAL_20']) else None
        result["Turnover_Ratio"] = float(latest_daily['TURNOVER_RATIO']) if pd.notna(latest_daily['TURNOVER_RATIO']) else None
        
        return result
        
    except Exception as e:
        print(f"데이터가 없거나 가져올 수 없습니다. 원인: {e}")
        sys.exit(1)

if __name__ == "__main__":
    ticker = "AAPL"
    print(f"[{ticker}] 기술적 지표 계산 중...\n")
    indicators = get_stock_indicators(ticker)
    
    print("=" * 40)
    print(f"[{indicators['Ticker']}] 최근 거래일 ({indicators['Date']}) 기술적 지표")
    print("=" * 40)
    
    for key, value in indicators.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
