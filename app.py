import streamlit as st
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta

# ==========================================
# 1. 网页基础设置
# ==========================================
st.set_page_config(page_title="Lydia 的高阶交易引擎", layout="wide", page_icon="🎯")
st.title("🎯 Lydia 跨市场狙击手监控中心 v2.1")
st.markdown("**(货币智能识别 + 战术雷达高敏版)**")

# ==========================================
# 2. 标的池定义 & 货币格式化函数
# ==========================================
PORTFOLIO = {
    "🔥 AI与成长 (美股为主, 盯紧MA50)": {
        "NVDA": "NVDA",
        "博通": "AVGO",
        "谷歌C": "GOOG",
        "多邻国(观察)": "DUOL",
        "协创数据": "300850.SZ" 
    },
    "🛡️ 稳健防御与金融 (忽略短线, 盯紧MA200)": {
        "Visa": "V",
        "IBKR": "IBKR",
        "NEE(新纪元)": "NEE",
        "恒瑞医药": "600276.SS",
        "国电南瑞": "600406.SS"
    },
    "🏭 周期与制造 (紧盯商品/板块风向)": {
        "洛阳钼业(重仓)": "603993.SS",
        "大金重工": "002487.SZ",
        "天顺风能": "002531.SZ"
    }
}

MACRO = {
    "🇺🇸 10Y美债收益率(%)": "^TNX",
    "🏭 LME 铜价($)": "HG=F",
    "😨 VIX 恐慌指数": "^VIX"
}

def format_price(ticker, price):
    """根据股票代码后缀自动匹配货币符号"""
    if pd.isna(price) or price == "N/A": return "N/A"
    if ticker.endswith('.SS') or ticker.endswith('.SZ'):
        return f"¥ {price:.2f}"
    elif ticker.endswith('.HK'):
        return f"HK$ {price:.2f}"
    else:
        return f"$ {price:.2f}"

# ==========================================
# 3. 核心计算逻辑
# ==========================================
@st.cache_data(ttl=3600)
def analyze_stock(ticker, category_name):
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period="1y")
        if len(df) < 200:
            return None
            
        close = df['Close']
        vol = df['Volume']
        current_price = close.iloc[-1]
        
        ma50 = ta.trend.sma_indicator(close, window=50)
        ma200 = ta.trend.sma_indicator(close, window=200)
        
        # --- 🎯 战略引擎 (严格防摔，低频触发) ---
        strategy = "🟡 震荡盘整"
        is_true_break_50 = (close.iloc[-1] < ma50.iloc[-1] * 0.98) and (close.iloc[-2] < ma50.iloc[-2] * 0.98)
        is_true_break_200 = (close.iloc[-1] < ma200.iloc[-1] * 0.98) and (close.iloc[-2] < ma200.iloc[-2] * 0.98)
        is_above_both = (current_price > ma50.iloc[-1]) and (current_price > ma200.iloc[-1])
        
        if "AI与成长" in category_name:
            if is_above_both: strategy = "🟢 趋势极强 (持有)"
            elif is_true_break_50 and current_price > ma200.iloc[-1]: strategy = "⚠️ 破MA50 (留意风险)"
            elif is_true_break_200: strategy = "🔴 破MA200 (清仓警报)"
            else: strategy = "🟡 均线间震荡"
            
        elif "稳健防御" in category_name:
            if is_true_break_200: strategy = "🔴 长线趋势恶化"
            elif current_price < ma200.iloc[-1] * 1.05 and current_price > ma200.iloc[-1] * 0.98:
                strategy = "💡 回踩MA200 (极佳买点)"
            elif current_price > ma50.iloc[-1]: strategy = "🟢 稳健上升 (持有)"
            else: strategy = "🟡 回调中 (等年线)"
            
        else: 
            if is_true_break_50: strategy = "🔴 周期走弱 (减仓)"
            elif current_price > ma50.iloc[-1]: strategy = "🟢 周期向上 (持有)"
            else: strategy = "🟡 底部盘整"

        # --- 🔬 战术雷达 (高敏感度，日常播报) ---
        hints = []
        
        # 1. RSI (放宽界限，提早预警)
        rsi = ta.momentum.rsi(close, window=14).iloc[-1]
        if rsi > 65: hints.append(f"🔥 RSI偏高({int(rsi)})")
        elif rsi < 35: hints.append(f"🧊 RSI偏低({int(rsi)})")
        
        # 2. 布林带狙击 (稍微靠近就提示)
        bb_low = ta.volatility.bollinger_lband(close).iloc[-1]
        bb_high = ta.volatility.bollinger_hband(close).iloc[-1]
        if current_price < bb_low * 1.015: hints.append("🎯 逼近布林下轨(强支撑)")
        if current_price > bb_high * 0.985: hints.append("⚠️ 逼近布林上轨(抛压区)")
        
        # 3. 异动量能 (1.8倍即提示，A股经常异动)
        avg_vol = vol.iloc[-6:-1].mean()
        if vol.iloc[-1] > avg_vol * 1.8: hints.append("💥 明显放量")
        elif vol.iloc[-1] < avg_vol * 0.6: hints.append("💤 极度缩量")
        
        # 4. 动能 MACD (每日播报强弱)
        macd_hist = ta.trend.macd_diff(close)
        if macd_hist.iloc[-1] > macd_hist.iloc[-2]:
            hints.append("📈 动能走强")
        else:
            hints.append("📉 动能减弱")
            
        hint_str = " | ".join(hints)
        
        return format_price(ticker, current_price), strategy, hint_str
        
    except Exception as e:
        return "N/A", "数据缺失", "接口获取失败"

# ==========================================
# 4. 渲染 宏观雷达
# ==========================================
st.subheader("🌍 第一层过滤：宏观总闸")
cols = st.columns(3)
for i, (name, ticker) in enumerate(MACRO.items()):
    try:
        tk = yf.Ticker(ticker)
        data = tk.history(period="5d")['Close'].dropna()
        if len(data) >= 2:
            current = round(data.iloc[-1], 2)
            diff = round(current - data.iloc[-2], 2)
            cols[i].metric(label=name, value=current, delta=diff)
        else:
            cols[i].metric(label=name, value="等待开盘", delta="0")
    except:
        cols[i].metric(label=name, value="接口延迟", delta="0")
st.markdown("---")

# ==========================================
# 5. 渲染 个股矩阵
# ==========================================
st.subheader("🛡️ 第二层：核心持仓矩阵 (自动识别中美货币)")

for category_name, stocks in PORTFOLIO.items():
    st.markdown(f"#### {category_name}")
    table_data = []
    
    for name, ticker in stocks.items():
        res = analyze_stock(ticker, category_name)
        if res:
            price_str, strategy, hints = res
            table_data.append({
                "股票名称": name,
                "当前价": price_str,
                "🎯 战略建议 (决定动作)": strategy,
                "🔬 战术雷达 (了解短线状态)": hints
            })
            
    df_display = pd.DataFrame(table_data)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.write("") 

st.markdown("---")
st.caption("注：A股价格单位为¥，美股为$。战术雷达仅供感受市场水位，交易动作请严格遵守'战略建议'列。")
