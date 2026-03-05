import streamlit as st
import pandas as pd
from streamlit_cookies_manager import CookieManager
from datetime import datetime
from groq import Groq
from data_fetcher import get_stock_indicators

# 페이지 설정
st.set_page_config(
    page_title="AI 투자 위원회",
    page_icon="📈",
    layout="wide"
)

# 쿠키 매니저 초기화
cookies = CookieManager()
if not cookies.ready():
    st.stop()

# Pretendard 폰트 강제 주입
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
html, body, [class*="css"]  {
    font-family: 'Pretendard', sans-serif !important;
    font-size: 16px !important;
    line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)

# 사이드바: API 키 입력
with st.sidebar:
    st.header("🔑 설정")
    saved_key = cookies.get('groq_api_key', '')
    api_key_input = st.text_input("Groq API 키를 입력하세요 (gsk_...):", value=saved_key, type="password")
    
    # 새로운 키가 입력되면 쿠키에 저장
    if api_key_input and api_key_input != saved_key:
        cookies['groq_api_key'] = api_key_input
        cookies.save()
        
    st.markdown("---")
    st.markdown("API 키 발급은 [Groq Console](https://console.groq.com/keys)에서 가능합니다.")

if not api_key_input:
    st.info("👈 사이드바에 API 키를 먼저 입력해 주세요.", icon="ℹ️")
    st.stop()

# 메인 화면
st.title("🚀 AI 투자 위원회 분석 시스템")
st.markdown("메타(Meta)의 강력한 Llama 3 모델을 기반으로 한 차트 및 거래량 심층 분석 리포트를 받아보세요.")

# KRX 데이터 프레임 캐싱 로드 (KIND 기업공시채널 활용)
@st.cache_data(show_spinner="상장종목 데이터를 불러오고 있습니다...")
def load_krx_data():
    url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
    df = pd.read_html(url, header=0)[0]
    # 종목코드를 6자리 문자열로 맞춤 (예: 5930 -> 005930)
    df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
    return df[['회사명', '종목코드']]

df_krx = load_krx_data()

# 종목 검색기 (KIND 스크래핑 패치)
with st.expander("🔍 티커(종목 코드) 찾기"):
    search_query = st.text_input("기업명 입력 (예: 삼성전자, 카카오):", key="search_query").strip()
    if st.button("검색"):
        if search_query:
            # 대소문자 구분 없이 포함된 문자열 검색
            filtered_df = df_krx[df_krx['회사명'].str.contains(search_query, case=False, na=False)]
            
            if not filtered_df.empty:
                st.markdown(f"**'{search_query}'** 검색 결과 ({len(filtered_df)}건):")
                
                # 출력용 데이터 프레임 사용
                st.dataframe(filtered_df, use_container_width=True)
                
                st.info("💡 **안내:** 코스피 종목은 검색된 6자리 코드 뒤에 `.KS`를, 코스닥 종목은 `.KQ`를 붙여서 메인 검색창에 입력해 주세요. (예: 삼성전자 ➡️ 005930.KS)")
            else:
                st.warning("일치하는 종목이 없습니다.")
        else:
            st.warning("검색할 기업명을 입력해주세요.")

# 종목 입력
ticker_input = st.text_input(
    "🔍 분석할 종목의 티커를 입력하세요 (예: AAPL, TSLA, 005930.KS):", 
    placeholder="종목 티커 입력"
).strip().upper()

# 실행 버튼
if st.button("🚀 AI 분석 시작", type="primary"):
    if not ticker_input:
        st.warning("티커를 입력해 주세요.", icon="🚫")
    else:
        with st.spinner("AI 투자 위원회가 차트와 거래량을 심층 분석 중입니다..."):
            try:
                # 1. 데이터 수집
                indicators = get_stock_indicators(ticker_input)
                
                # 유동성 경고 로직 (이중 잠금장치 시각화)
                is_kr_market = indicators.get("Is_KR_Market", False)
                turnover_ratio = indicators.get("Turnover_Ratio")
                avg_trading_value_20d = indicators.get("Avg_Trading_Value_20d")
                
                liquidity_warning_needed = False
                if turnover_ratio is not None and turnover_ratio < 0.1:
                    liquidity_warning_needed = True
                elif avg_trading_value_20d is not None:
                    if is_kr_market and avg_trading_value_20d < 1000000000:  # 한국 10억
                        liquidity_warning_needed = True
                    elif not is_kr_market and avg_trading_value_20d < 1000000:   # 미국 1M
                        liquidity_warning_needed = True
                
                if liquidity_warning_needed:
                    st.error(
                        "🚨 **[주의: 저유동성 종목]**\n\n"
                        "본 종목은 최근 20일 평균 회전율이 0.1% 미만이거나, 평균 거래대금이 기준치(10억 원/100만 달러) 미만으로 유동성이 매우 부족한 상태입니다. "
                        "거래량이 적은 소형주/품절주의 경우 적은 금액에도 주가가 크게 출렁일 수 있으며, "
                        "OBV 등 거래량 기반 지표와 이평선의 신뢰도가 크게 떨어져 거짓 신호가 발생할 확률이 높으므로 투자에 각별한 주의가 필요합니다.",
                        icon="🚨"
                    )
                
                # 2. 분석을 위한 데이터 파싱
                current_market_price = indicators['Close']
                l_open = indicators.get('Open', 0.0)
                l_high = indicators.get('High', 0.0)
                l_low = indicators.get('Low', 0.0)
                volume = indicators.get('Volume', 0)
                
                ma_values = {
                    'MA5': indicators.get('SMA_5'),
                    'MA20': indicators.get('SMA_20'),
                    'MA60': indicators.get('SMA_60'),
                    'MA90': indicators.get('SMA_90'),
                    'MA120': indicators.get('SMA_120'),
                    'MA200': indicators.get('SMA_200'),
                }
                w_ma_values = {
                    'MA5': indicators.get('W_SMA_5'),
                    'MA20': indicators.get('W_SMA_20'),
                    'MA60': indicators.get('W_SMA_60'),
                }
                rsi_14 = indicators.get('RSI_14')
                stoch_k = indicators.get('STOCHk_14_3_3')
                stoch_d = indicators.get('STOCHd_14_3_3')
                
                tenkan = indicators.get('전환선 (Tenkan-sen)')
                kijun = indicators.get('기준선 (Kijun-sen)')
                senkou_a = indicators.get('구름대_상단 (Senkou_A)')
                senkou_b = indicators.get('구름대_하단 (Senkou_B)')
                chikou = indicators.get('후행스팬 (Chikou Span)')
                
                obv_val = indicators.get('OBV')
                mfi_14_val = indicators.get('MFI_14')
                
                def fmt_val(val):
                    if isinstance(val, (int, float)) and val is not None:
                        return f"{val:.2f}"
                    return str(val) if val is not None else "N/A"
                    
                ichimoku_str = (
                    f"전환선: {fmt_val(tenkan)}, "
                    f"기준선: {fmt_val(kijun)}, "
                    f"구름대 상단(선행A): {fmt_val(senkou_a)}, "
                    f"구름대 하단(선행B): {fmt_val(senkou_b)}, "
                    f"후행스팬: {chikou}"
                )
                
                date_str = indicators.get('Date', 'N/A')
                today_date = datetime.now().strftime("%Y-%m-%d")
                
                user_prompt = f"""[AI 투자 위원회 전문 분석 프롬프트]
대상 종목: {ticker_input} ({date_str} 기준)
현재 주가 (종가): ${fmt_val(current_market_price)}

[일간 시장 데이터]
- 시가: ${fmt_val(l_open)}
- 고가: ${fmt_val(l_high)}
- 저가: ${fmt_val(l_low)}
- 당일 거래량: {volume:,}

[일봉 이동평균선(SMA)]
- 5일선: ${fmt_val(ma_values['MA5'])}
- 20일선: ${fmt_val(ma_values['MA20'])}
- 60일선: ${fmt_val(ma_values['MA60'])}
- 90일선: ${fmt_val(ma_values['MA90'])}
- 120일선: ${fmt_val(ma_values['MA120'])}
- 200일선: ${fmt_val(ma_values['MA200'])}

[주봉 이동평균선(Weekly SMA)]
- 5주선: ${fmt_val(w_ma_values['MA5'])}
- 20주선: ${fmt_val(w_ma_values['MA20'])}
- 60주선: ${fmt_val(w_ma_values['MA60'])}

[기술적 보조 지표 (일봉 기준)]
- RSI (14): {fmt_val(rsi_14)}
- 스토캐스틱 (14,3,3) K / D: {fmt_val(stoch_k)} / {fmt_val(stoch_d)}
- 일목균형표: {ichimoku_str}
- OBV (누적 거래량): {fmt_val(obv_val)}
- MFI (자금 흐름 지수, 14): {fmt_val(mfi_14_val)}

[사용자 맥락 (Context)]
- 포트폴리오 상태: 신규 진입자 관점 (보유 주식 없음)

[AI 분석 요청 사항]
위의 객관적 시장 데이터와 기술적 지표, 그리고 신규 진입자 관점을 모두 종합하여, 현재 시점에서 가장 최적화된 트레이딩 전략(매수/매도/관망 및 대응 시나리오)을 상세하게 제시해 주십시오. 주요 지지와 저항 라인을 명시하고, 전문가적 관점 및 리스크 관리를 함께 고려한 다각적 분석을 요구합니다.
"""
                
                system_prompt = f"""당신은 한국 최고의 AI 투자 위원회입니다. 반드시 100% 순수 한국어(한글), 영어(티커명/지표명), 숫자만 사용하십시오. 한자(漢字, 예: 慎重, 管理 등)나 기타 외국어(예: 베트남어 등)가 단 한 글자라도 포함되면 안 됩니다. 주린이(초보자)를 위해 모든 전문 용어(이평선, RSI 등) 뒤에는 항상 괄호로 (현재 가격)이나 (쉬운 설명)을 덧붙이세요.

[엄격한 출력 규칙 - 위반 시 시스템 오류 발생]
1. 절대 서론, 인사말, 일반적인 줄글 요약을 작성하지 마십시오.
2. 기업의 정성적 가치(뉴스, 실적 등)는 일절 배제하고 철저히 기술적 데이터(가격, 추세, 거래량) 기반으로만 작성하십시오.
3. 반드시 아래의 마크다운 템플릿 목차(1번~6번)를 100% 똑같이 복사해서 내용만 채워라. 임의로 목차를 병합하거나 생략하거나 기호를 바꾸지 마라.
4. 새로 추가된 OBV와 MFI 지표를 반드시 분석에 포함하여, 현재 하락/상승이 진짜 세력의 움직임인지 가짜 속임수인지 전문가 토론에서 깊이 있게 다루어라.

[필수 포함 템플릿]
## [{ticker_input}] 분석 Report ({today_date}) ##
> [한줄 요약] : (여기에 핵심 결론)
### 1. 📋 현재 시장 상황 (신규 진입자 관점)
### 2. 🕵️‍♂️ 주요 지지와 저항 라인
### 3. 📊 신규 진입 전략 및 매력도
### 4. ⚔️ 전문가 토론 (Debate)
   - 🗣️ 전문가 A (단기 차티스트):
   - 🧘 전문가 B (장기 매집 투자자):
### 5. ⚖️ 의장 (포트폴리오 매니저)의 결론
### 6. 🦁 최종 전략 및 시나리오
"""
                
                # 3. Groq API 호출
                client = Groq(api_key=api_key_input)
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.1, 
                )
                
                # 4. 리포트 포매팅
                guide_text = (
                    "[ 읽기 전 필수 안내 (Guide & Disclaimer) ]\n\n"
                    "1. 핵심 지표 도입 이유 및 참고 방법\n"
                    "본 AI 투자 위원회는 감정을 배제하고 객관적인 차트 데이터로만 시장을 분석합니다.\n"
                    "- 방향성 (이동평균선, 일목균형표): 현재 주가의 거대한 '추세'와 강력한 '방어벽(지지/저항선)'을 확인합니다. 대세 상승장인지 하락장인지 판별하는 뼈대가 됩니다.\n"
                    "- 자금 흐름과 매집 (OBV, MFI): 주가의 '진짜 연료'인 거래량을 분석합니다. OBV(누적 거래량)와 MFI(자금 흐름 지수)를 통해 현재 주가의 움직임이 세력의 '진짜 매집/이탈'인지, 거래량 없는 '속임수'인지 판별하여 분석의 신뢰도를 높입니다.\n"
                    "- 타이밍 (RSI, 스토캐스틱): 단기적인 '매수/매도의 힘'을 측정합니다. 시장이 비이성적으로 열광하는지(과매수), 공포에 질려 과도하게 하락했는지(과매도)를 파악하여 정밀한 진입/탈출 타점을 잡는 데 사용합니다.\n\n"
                    "2. 투자 유의사항\n"
                    "본 리포트는 기업의 정성적 가치(실적, 뉴스 등)를 배제하고, 오직 '가격, 거래량, 추세 데이터'만을 기반으로 작성된 기술적 분석 참고 자료입니다. 투자는 개인의 선택이며, AI의 분석 결과는 과거의 확률일 뿐 미래를 100% 보장하지 않습니다. 최종 투자 결정과 그에 따른 모든 책임은 전적으로 투자자 본인에게 있습니다.\n\n"
                    "--------------------------------------------------\n\n"
                )
                
                footer_text = "\n\n---\n*데이터 출처: Yahoo Finance (yfinance API)*\n"
                llm_response = chat_completion.choices[0].message.content
                report_text = guide_text + llm_response + footer_text
                
                st.success("✅ AI 위원회 분석 완료!")
                
                # 리포트 화면 출력
                with st.expander("📊 AI 투자 리포트 확인하기", expanded=True):
                    st.markdown(report_text)
                
                # 다운로드 버튼
                output_filename = f"AI_Investment_Report_{ticker_input}_{today_date}.txt"
                st.download_button(
                    label="📥 리포트 텍스트 파일 저장",
                    data=report_text,
                    file_name=output_filename,
                    mime="text/plain"
                )
                
            except Exception as e:
                st.error(f"데이터 수집, 서버 통신 또는 분석 중 문제가 발생했습니다.\n\n원인: {e}", icon="💥")
