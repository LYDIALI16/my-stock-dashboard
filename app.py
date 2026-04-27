import streamlit as st
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta

# ==========================================
# 1. 网页基础设置
# ==========================================
st.set_page_config(page_title="Lydia 的高阶交易引擎", layout="wide", page_icon="🎯")
st.title("🎯 Lydia 跨市场狙击手监控中心 v2.0")
st.markdown("**(宏观风控 + 真破位过滤 + 战术感知)** | 频率: 低频 (<10次/月)")

# ==========================================
# 2. 标的池定义 (按属性分类)
# ==========================================
PORTFOLIO = {
    "🔥 AI与成长 (美股为主)": {
        "NVDA": "NVDA",
        "博通": "AVGO",
        "谷歌C": "GOOG",
        "多邻国(观察)": "DUOL",
        "协创数据": "300850.SZ" # A股高弹性科技算作此类
    },
    "🛡️ 稳健防御与金融 (长线为王)": {
        "Visa": "V",
        "IBKR": "IBKR",
        "NEE(新纪元)": "NEE",
        "恒瑞医药": "600276.SS",
        "国电南瑞": "600406.SS"
    },
    "🏭 周期与制造 (A股轮动)": {
        "洛阳钼业(重仓)": "603993.SS",
        "大金重工": "002487.SZ",
        "天顺风能": "002531.SZ"
    }
}

MACRO = {
    "🇺🇸 10Y美债收益率": "^TNX",
    "🏭 LME 铜价": "HG=F",
    "😨 VIX 恐慌指数": "^VIX"
}

# ==========================================
# 3. 核心计算逻辑 (融入防假摔机制)
# ==========================================
@st.cache_data(ttl=3600)
def analyze_stock(ticker, category_name):
    try:
        # 获取1年数据，确保能算200日均线
        tk = yf.Ticker(ticker)
        df = tk.history(period="1y")
        if len(df) < 200:
            return None
            
        close = df['Close']
        vol = df['Volume']
        current_price = close.iloc[-1]
        
        # 计算均线
        ma50 = ta.trend.sma_indicator(close, window=50)
        ma200 = ta.trend.sma_indicator(close, window=200)
        
        # --- 🎯 战略引擎计算 (基于真实破位逻辑) ---
        strategy = "🟡 震荡盘整"
        
        # 真破位定义：连续2天低于均线2%
        is_true_break_50 = (close.iloc[-1] < ma50.iloc[-1] * 0.98) and (close.iloc[-2] < ma50.iloc[-2] * 0.98)
        is_true_break_200 = (close.iloc[-1] < ma200.iloc[-1] * 0.98) and (close.iloc[-2] < ma200.iloc[-2] * 0.98)
        is_above_both = (current_price > ma50.iloc[-1]) and (current_price > ma200.iloc[-1])
        
        if "AI与成长" in category_name:
            if is_above_both: strategy = "🟢 趋势极强 (持有)"
            elif is_true_break_50 and current_price > ma200.iloc[-1]: strategy = "⚠️ 破MA50 (建议减1/3)"
            elif is_true_break_200: strategy = "🔴 破MA200 (清仓警报)"
            else: strategy = "🟡 均线间震荡 (不动)"
            
        elif "稳健防御" in category_name:
            # 防御股忽略短线跌破，专注长线
            if is_true_break_200: strategy = "🔴 长线趋势恶化"
            elif current_price < ma200.iloc[-1] * 1.05 and current_price > ma200.iloc[-1] * 0.98:
                strategy = "💡 回踩MA200 (极佳买点)"
            elif current_price > ma50.iloc[-1]: strategy = "🟢 稳健上升 (持有)"
            else: strategy = "🟡 回调中 (等待企稳)"
            
        else: # 周期制造
            if is_true_break_50: strategy = "🔴 周期走弱 (减仓观望)"
            elif current_price > ma50.iloc[-1]: strategy = "🟢 周期向上 (持有)"
            else: strategy = "🟡 底部盘整"

        # --- 🔬 战术雷达 (短线Hint) ---
        hints = []
        
        # 1. RSI 情绪
        rsi = ta.momentum.rsi(close, window=14).iloc[-1]
        if rsi > 70: hints.append("🔥 RSI超买(勿追)")
        elif rsi < 30: hints.append("🧊 RSI超卖")
        
        # 2. 布林带狙击 (结合RSI使用胜率极高)
        bb_low = ta.volatility.bollinger_lband(close).iloc[-1]
        bb_high = ta.volatility.bollinger_hband(close).iloc[-1]
        if current_price < bb_low: hints.append("🎯 刺穿布林下轨(强反弹区)")
        if current_price > bb_high: hints.append("⚠️ 触碰布林上轨(抛压区)")
        
        # 3. 异动量能
        avg_vol = vol.iloc[-6:-1].mean()
        if vol.iloc[-1] > avg_vol * 2.5: hints.append("💥 极端放量")
        
        # 4. 动能 MACD
        macd_hist = ta.trend.macd_diff(close)
        if macd_hist.iloc[-1] < 0 and macd_hist.iloc[-1] > macd_hist.iloc[-2]:
            hints.append("🌤️ 短期砸盘衰竭")
            
        hint_str = " | ".join(hints) if hints else "⏸️ 无异常"
        
        return round(current_price, 2), strategy, hint_str
        
    except Exception as e:
        return "N/A", "数据缺失", "N/A"

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
st.markdown("*(💡 解读：美债飙升压制AI估值；铜价决定洛钼生死；VIX>25禁止建仓)*")
st.markdown("---")

# ==========================================
# 5. 渲染 个股矩阵 (分类展示)
# ==========================================
st.subheader("🛡️ 第二层：核心持仓矩阵")

for category_name, stocks in PORTFOLIO.items():
    st.markdown(f"#### {category_name}")
    table_data = []
    
    for name, ticker in stocks.items():
        res = analyze_stock(ticker, category_name)
        if res:
            price, strategy, hints = res
            table_data.append({
                "股票名称": name,
                "当前价": price,
                "🎯 战略建议 (决定动作)": strategy,
                "🔬 战术雷达 (优化买卖点)": hints
            })
            
    df_display = pd.DataFrame(table_data)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.write("") # 增加间距

st.markdown("---")
st.success("🤖 Lydia 专属行动引擎已就绪。记住原则：战略不变，我不乱动；战术亮灯，精准狙击。")
