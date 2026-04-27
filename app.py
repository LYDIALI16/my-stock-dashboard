import streamlit as st
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta

# ==========================================
# 1. 网页基础设置
# ==========================================
st.set_page_config(page_title="Lydia的交易监控中心", layout="wide")
st.title("📈 Lydia的跨市场交易监控中心")
st.markdown("**(战略低频 + 战术感知双引擎)** | 数据来源: Yahoo Finance")

# ==========================================
# 2. 标的池定义
# ==========================================
# A股在雅虎代码后缀：沪市为 .SS, 深市为 .SZ
TICKERS = {
    "洛阳钼业 (20%仓)": "603993.SS",
    "协创数据": "300850.SZ",
    "大金重工": "002487.SZ",
    "天顺风能": "002531.SZ",
    "国电南瑞": "600406.SS",
    "恒瑞医药": "600276.SS",
    "英伟达": "NVDA",
    "博通": "AVGO",
    "Visa": "V",
    "IBKR": "IBKR"
}

MACRO = {
    "US 10Y国债收益率 (%)": "^TNX",
    "LME 铜价 (洛钼风向标)": "HG=F",
    "恐慌指数 VIX": "^VIX"
}

# ==========================================
# 3. 数据获取与计算函数
# ==========================================
@st.cache_data(ttl=3600) # 缓存数据1小时，加快网页加载速度
def fetch_and_calculate(ticker):
    try:
        # 获取过去半年数据
        df = yf.download(ticker, period="6mo", progress=False)
        if df.empty:
            return None
            
        close = df['Close'].squeeze()
        vol = df['Volume'].squeeze()
        
        # 获取最新价和昨日价
        current_price = close.iloc[-1]
        
        # --- 战略引擎计算 (中长线) ---
        ema50 = ta.trend.ema_indicator(close, window=50).iloc[-1]
        
        if current_price > ema50:
            strategy = "🟢 趋势向上 (可持有)"
        elif current_price < ema50:
            strategy = "🔴 跌破50日线 (需警惕/等待)"
        else:
            strategy = "🟡 震荡盘整"
            
        # --- 战术感知计算 (短线Hint) ---
        hints = []
        
        # 1. RSI 极端情绪
        rsi = ta.momentum.rsi(close, window=14).iloc[-1]
        if rsi > 70: hints.append("🔥 RSI超买")
        elif rsi < 30: hints.append("🧊 RSI超卖")
        
        # 2. 异动成交量 (今日量 > 过去5日均量2倍)
        avg_vol_5 = vol.iloc[-6:-1].mean()
        if vol.iloc[-1] > avg_vol_5 * 2:
            hints.append("⚠️ 异常放量")
            
        # 3. MACD 动能衰竭/加速
        macd = ta.trend.macd_diff(close)
        if macd.iloc[-1] < 0 and macd.iloc[-1] > macd.iloc[-2]:
            hints.append("🌤️ 短期抛压减弱")
        elif macd.iloc[-1] < 0 and macd.iloc[-1] < macd.iloc[-2]:
            hints.append("🌧️ 短期抛压放大")
            
        hint_str = " ".join(hints) if hints else "⏸️ 平淡无明显异动"
        
        return round(current_price, 2), strategy, hint_str
        
    except Exception as e:
        return "N/A", "数据获取失败", "无"

# ==========================================
# 4. 渲染 宏观战区
# ==========================================
st.subheader("🌍 宏观战区 (大盘风向标)")
cols = st.columns(3)
for i, (name, ticker) in enumerate(MACRO.items()):
    try:
        # 改用 history 方法，只取最近5天数据，并去掉所有的空值，确保一定能取到最新价
        tk = yf.Ticker(ticker)
        data = tk.history(period="5d")['Close'].dropna() 
        if len(data) >= 2:
            current = round(data.iloc[-1], 2)
            diff = round(current - data.iloc[-2], 2)
            cols[i].metric(label=name, value=current, delta=diff)
        else:
            cols[i].metric(label=name, value="等待开盘", delta="0")
    except Exception as e:
        cols[i].metric(label=name, value="接口延迟", delta="0")

st.markdown("---")

# ==========================================
# 5. 渲染 个股矩阵
# ==========================================
st.subheader("🛡️ 核心持仓矩阵")

# 准备表格数据
table_data = []
for name, ticker in TICKERS.items():
    res = fetch_and_calculate(ticker)
    if res:
        price, strategy, hints = res
        table_data.append({
            "股票名称": name,
            "代码": ticker,
            "当前价": price,
            "🎯 战略建议 (决定操作)": strategy,
            "🔬 短线战况 (优化买点)": hints
        })

df_display = pd.DataFrame(table_data)
# 使用 Streamlit 漂亮的表格展示
st.dataframe(df_display, use_container_width=True, hide_index=True)

st.markdown("---")
st.info("📧 邮件预警引擎：[待配置] - 网页版已成功上线！")  
