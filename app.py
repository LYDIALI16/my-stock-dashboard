import streamlit as st
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime

# ==========================================
# 0. 页面基础配置
# ==========================================
st.set_page_config(page_title="Lydia 规则引擎 v4.0", layout="wide")
st.title("⚙️ Lydia 规则引擎 (PRD 落地版 v4.0 - Sprint 1)")
st.markdown("**(Top-down 宏观压制 | 状态机分离 | 100%可解释证据链)**")
st.markdown("---")

# ==========================================
# 1. 配置加载 (Config & Ticker Class)
# ==========================================
# 股票分类与对应代码 (修正了 Nebius)
CONFIG_TICKERS = {
    "HIGH_VOL_GROWTH": {"NVDA": "NVDA", "博通": "AVGO", "谷歌C": "GOOG", "多邻国": "DUOL", "Nebius": "NBIS", "协创数据": "300857.SZ"},
    "LOW_VOL_QUALITY": {"Visa": "V", "IBKR": "IBKR", "NEE": "NEE", "恒瑞医药": "600276.SS", "国电南瑞": "600406.SS"},
    "MID_VOL_TREND":   {"洛阳钼业": "603993.SS", "大金重工": "002487.SZ", "天顺风能": "002531.SZ"}
}

# 全局参数阈值 (PRD 规定)
CONFIG_PARAMS = {
    "vix_risk_off": 20,
    "break_buffer_pct": 0.98,
    "pullback_tolerance": 1.05
}

def format_price(ticker, price):
    if pd.isna(price): return "N/A"
    return f"¥{price:.2f}" if ticker.endswith(('.SS', '.SZ')) else f"${price:.2f}"

# ==========================================
# 2. Layer 1: 宏观威胁扫描 (Macro ENV)
# ==========================================
@st.cache_data(ttl=3600)
def compute_macro_layer():
    try:
        vix = yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
        us10y_data = yf.Ticker("^TNX").history(period="5d")['Close']
        us10y_up = us10y_data.iloc[-1] > us10y_data.iloc[0]
        
        evidence = [f"VIX = {vix:.2f} (阈值 {CONFIG_PARAMS['vix_risk_off']})", f"US10Y 5日趋势 = {'上行' if us10y_up else '下行'}"]
        
        if vix > CONFIG_PARAMS['vix_risk_off'] or (us10y_up and vix > 18):
            return "PRESSURE", "高风险避险模式", evidence, False # 不允许加仓高波动
        elif vix < 16 and not us10y_up:
            return "SUPPORTIVE", "风险偏好良好", evidence, True
        else:
            return "NEUTRAL", "无极端宏观冲击", evidence, True
            
    except:
        return "NEUTRAL", "接口数据缺失", ["数据获取失败，默认中性"], True

env_state, env_desc, env_evidence, allow_high_vol_add = compute_macro_layer()

st.subheader("🌍 Layer 1 | 宏观威胁扫描 (Macro ENV)")
if env_state == "PRESSURE": st.error(f"**ENV = {env_state} ({env_desc})** | 🚨 系统已全局禁止对高波动标的下发 ADD 指令！")
elif env_state == "SUPPORTIVE": st.success(f"**ENV = {env_state} ({env_desc})** | 🟢 宏观顺风，加仓逻辑正常放行。")
else: st.info(f"**ENV = {env_state} ({env_desc})** | 🟡 宏观中性，依个股技术面执行。")
st.markdown("---")

# ==========================================
# 3. Layer 2 & 3: 状态机与动作引擎 (State & Action)
# ==========================================
@st.cache_data(ttl=3600)
def process_engine(ticker, name, t_class):
    df = yf.Ticker(ticker).history(period="1y")
    if len(df) < 200: return None
        
    close = df['Close']
    curr_price = close.iloc[-1]
    ma50 = round(ta.trend.sma_indicator(close, window=50).iloc[-1], 2)
    ma200 = round(ta.trend.sma_indicator(close, window=200).iloc[-1], 2)
    atr = round(ta.volatility.average_true_range(df['High'], df['Low'], close, window=14).iloc[-1], 2)
    
    # 证据链容器
    evidence = {
        "market_data": f"当前价: {format_price(ticker, curr_price)} | MA50: {ma50} | MA200: {ma200} | ATR: {atr}",
        "state_rules": [],
        "action_rules": []
    }
    
    # [Layer 2] 判定趋势状态 (Trend State)
    trend_state = "SIDEWAYS"
    if curr_price > ma50 and curr_price > ma200:
        trend_state = "UP_TREND"
        evidence["state_rules"].append(f"通过: Close({curr_price:.2f}) > MA50({ma50}) & MA200({ma200})")
    elif curr_price < ma200 * CONFIG_PARAMS['break_buffer_pct']:
        trend_state = "DOWN_TREND"
        evidence["state_rules"].append(f"触发: Close 跌破 MA200 容忍度 ({ma200 * CONFIG_PARAMS['break_buffer_pct']:.2f})")
    elif ma200 <= curr_price <= ma50 * 1.02:
        trend_state = "DOWN_TRANSITION"
        evidence["state_rules"].append("触发: 处于 MA50 之下，但在 MA200 之上")
        
    # 特殊状态：回踩判定 (UP_PULLBACK)
    pullback_target = ma50 if t_class in ["HIGH_VOL_GROWTH", "MID_VOL_TREND"] else ma200
    if 0.98 * pullback_target <= curr_price <= CONFIG_PARAMS['pullback_tolerance'] * pullback_target:
        trend_state = "UP_PULLBACK"
        evidence["state_rules"].append(f"触发: 价格逼近有效防守线 {pullback_target} (偏差<{CONFIG_PARAMS['pullback_tolerance']-1:.0%})")

    # [Layer 3] 触发动作 (Trigger -> Action)
    action = "[NO_ACTION]"
    intensity = "WEAK"
    action_desc = "未满足任何执行阈值，保持观望。"
    
    if trend_state == "DOWN_TREND":
        action = "[EXIT]"
        intensity = "STRONG"
        action_desc = "长线结构破坏，无条件清仓！"
        evidence["action_rules"].append("命中 EXIT 规则: TrendState == DOWN_TREND")
        
    elif trend_state == "DOWN_TRANSITION" and t_class != "LOW_VOL_QUALITY":
        action = "[TRIM]"
        intensity = "MEDIUM"
        action_desc = "中期防线失守，建议减仓控制敞口。"
        evidence["action_rules"].append("命中 TRIM 规则: 跌破 MA50 且非低波动标的")
        
    elif trend_state == "UP_PULLBACK":
        if t_class == "HIGH_VOL_GROWTH" and not allow_high_vol_add:
            action = "[NO_ACTION]"
            action_desc = "满足技术面买点，但被宏观引擎 [PRESSURE] 强行压制！"
            evidence["action_rules"].append("拦截 ADD: Macro ENV == PRESSURE 禁止高波动加仓")
        else:
            action = "[ADD]"
            intensity = "STRONG"
            action_desc = "回踩关键均线企稳，趋势内上车点。"
            evidence["action_rules"].append(f"命中 ADD 规则: TrendState == UP_PULLBACK & ENV允许")
            
    elif trend_state == "UP_TREND":
        action = "[HOLD]"
        intensity = "MEDIUM"
        action_desc = "趋势健康，让利润奔跑。"
        evidence["action_rules"].append("命中 HOLD 规则: TrendState == UP_TREND")

    return trend_state, action, intensity, action_desc, evidence

# ==========================================
# 4. 页面渲染 (输出 PRD 规定的行动清单)
# ==========================================
st.subheader("📋 Layer 2 & 3 | 引擎行动清单 (Action Engine Output)")

for t_class, stocks in CONFIG_TICKERS.items():
    st.markdown(f"#### 🏷️ 类别: `{t_class}`")
    
    for name, ticker in stocks.items():
        res = process_engine(ticker, name, t_class)
        if not res: continue
        trend_state, action, intensity, action_desc, ev = res
        
        # 颜色映射
        color_map = {"[ADD]": "🟢", "[TRIM]": "🟠", "[EXIT]": "🔴", "[HOLD]": "🔵", "[NO_ACTION]": "⚪"}
        icon = color_map.get(action, "⚫")
        
        # 卡片式 UI
        with st.container():
            col1, col2 = st.columns([2, 5])
            with col1:
                st.markdown(f"**{name}** (`{ticker}`)")
                st.caption(f"Status: `{trend_state}`")
            with col2:
                st.markdown(f"**{icon} Action: {action}**  *(强度: {intensity})*")
                st.markdown(f"> {action_desc}")
            
            # --- PRD核心：100% 可解释证据链 (Expander) ---
            with st.expander("🔍 展开查看判定证据链 (Evidence Chain)"):
                st.markdown(f"**1. 基础数据 (Market Data)**\n- {ev['market_data']}")
                st.markdown("**2. 状态机链路 (State Eval)**")
                for rule in ev['state_rules']: st.markdown(f"- 🔎 {rule}")
                st.markdown("**3. 动作生成链路 (Action Eval)**")
                for rule in ev['action_rules']: st.markdown(f"- ⚙️ {rule}")
                st.markdown(f"**4. 宏观因子作用 (Macro Factor)**\n- ENV = {env_state} (作用于该类别: {'允许加仓' if (t_class!='HIGH_VOL_GROWTH' or allow_high_vol_add) else '禁止加仓'})")
                
            st.write("") # 间距
    st.markdown("---")
