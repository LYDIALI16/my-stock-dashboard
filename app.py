import streamlit as st
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta

# ==========================================
# 1. 网页基础设置
# ==========================================
st.set_page_config(page_title="Lydia CTA 交易引擎", layout="wide", page_icon="🎯")
st.title("🎯 Lydia 机构级交易监控中心 v3.1")
st.markdown("**(恢复精确点位显示 + 增强宏观数据容错)** | 策略定力：月操作<10次")
st.markdown("---")

# ==========================================
# 2. 标的池
# ==========================================
PORTFOLIO = {
    "🔥 AI与成长 (高波动：严控MA50防守线)": {
        "NVDA": "NVDA", "博通": "AVGO", "谷歌C": "GOOG", "多邻国": "DUOL", "协创数据": "300857.SZ"
    },
    "🛡️ 稳健防御与金融 (低波动：专注MA200黄金坑)": {
        "Visa": "V", "IBKR": "IBKR", "NEE(新纪元)": "NEE", "恒瑞医药": "600276.SS", "国电南瑞": "600406.SS"
    },
    "🏭 周期与制造 (中波动：盯紧趋势与商品)": {
        "洛阳钼业": "603993.SS", "大金重工": "002487.SZ", "天顺风能": "002531.SZ"
    }
}

def format_price(ticker, price):
    if pd.isna(price): return "N/A"
    if ticker.endswith(('.SS', '.SZ')): return f"¥{price:.2f}"
    elif ticker.endswith('.HK'): return f"HK${price:.2f}"
    else: return f"${price:.2f}"

# ==========================================
# 3. 第一层过滤：宏观状态机 (增强容错版)
# ==========================================
@st.cache_data(ttl=3600)
def get_macro_regime():
    try:
        # 改用 1mo (一个月)，确保即使有长假也能抓到数据
        us10y_data = yf.Ticker("^TNX").history(period="1mo")['Close']
        vix_data = yf.Ticker("^VIX").history(period="1mo")['Close']
        
        if us10y_data.empty or vix_data.empty:
            raise ValueError("雅虎财经接口暂时无返回")
            
        current_vix = vix_data.iloc[-1]
        us10y_up = us10y_data.iloc[-1] > us10y_data.iloc[-5] # 近5个交易日对比
        
        if current_vix > 20 or (us10y_up and current_vix > 18):
            state = "🔴 [RISK_OFF] 避险模式"
            rationale = f"指标：VIX当前 {current_vix:.2f}，美债上行。\n👉 **引擎指引**：全局风险偏好下降，已强行【剥夺】成长股加仓许可。"
            allow_add = False
        elif current_vix < 15 and not us10y_up:
            state = "🟢 [RISK_ON] 进攻模式"
            rationale = f"指标：VIX低位 {current_vix:.2f}，美债回落。\n👉 **引擎指引**：宏观环境友好，符合技术面买点的标的允许【果断加仓】。"
            allow_add = True
        else:
            state = "🟡 [NEUTRAL] 中性震荡"
            rationale = f"指标：VIX {current_vix:.2f}，无极端冲击。\n👉 **引擎指引**：宏观不拖后腿，个股按技术面规则执行即可。"
            allow_add = True
            
        return state, rationale, allow_add
    except Exception as e:
        return "⚪ [接口延迟] 宏观数据盲区", "暂时无法获取宏观数据，默认不压制交易信号，请以个股技术面为准。", True

macro_state, macro_rationale, allow_add_growth = get_macro_regime()

st.subheader("🌍 第一层过滤：宏观引擎 (Macro Regime)")
st.info(f"**状态：{macro_state}** | {macro_rationale}")
st.markdown("---")

# ==========================================
# 4. 核心计算 (包含精确指标 ATR/MA)
# ==========================================
@st.cache_data(ttl=3600)
def analyze_stock_v3_1(ticker, category_name, allow_add):
    try:
        df = yf.Ticker(ticker).history(period="1y")
        if len(df) < 200: return None
            
        close, high, low, vol = df['Close'], df['High'], df['Low'], df['Volume']
        curr_price = close.iloc[-1]
        
        # 计算具体数值
        ma50_val = round(ta.trend.sma_indicator(close, window=50).iloc[-1], 2)
        ma200_val = round(ta.trend.sma_indicator(close, window=200).iloc[-1], 2)
        atr_val = round(ta.volatility.average_true_range(high, low, close, window=14).iloc[-1], 2)
        avg_vol = vol.iloc[-6:-1].mean()
        
        # 破位判定
        is_break_50 = (close.iloc[-1] < ma50_val * 0.98) and (close.iloc[-2] < ma50_val * 0.98)
        is_break_200 = (close.iloc[-1] < ma200_val * 0.98) and (close.iloc[-2] < ma200_val * 0.98)
        is_uptrend = (curr_price > ma50_val) and (curr_price > ma200_val)
        
        # --- 🔬 战术雷达感知层 ---
        rsi = ta.momentum.rsi(close, window=14).iloc[-1]
        macd_up = ta.trend.macd_diff(close).iloc[-1] > ta.trend.macd_diff(close).iloc[-2]
        vol_ratio = vol.iloc[-1] / avg_vol if avg_vol > 0 else 1
        bb_low = ta.volatility.bollinger_lband(close).iloc[-1]
        
        surfaces = []
        if rsi > 70: surfaces.append(f"🔥RSI超买({int(rsi)})")
        elif rsi < 35: surfaces.append(f"🧊RSI超卖({int(rsi)})")
        if vol_ratio > 1.8: surfaces.append(f"💥放量({vol_ratio:.1f}x)")
        elif vol_ratio < 0.6: surfaces.append("💤缩量")
        surfaces.append("📈动能走强" if macd_up else "📉动能走弱")
        if curr_price < bb_low * 1.02: surfaces.append("🎯近布林下轨")
        
        surface_str = " | ".join(surfaces)
        
        # 短线总结
        if rsi > 70 and vol_ratio > 1.5: tactical_sum = "【短线拥挤】绝对禁止追高，有底仓可逢高做T锁定利润。"
        elif rsi < 35 and not macd_up: tactical_sum = "【恐慌抛压】切勿左侧接飞刀，耐心等待跌势放缓。"
        elif rsi < 40 and macd_up and curr_price < bb_low * 1.02: tactical_sum = "【超跌反弹】极佳短线低吸窗口，胜率极高。"
        elif vol_ratio < 0.6 and not macd_up: tactical_sum = "【阴跌垃圾期】缺乏资金关注，多看少动。"
        else: tactical_sum = "【平淡震荡】忽略短线噪音，严格遵守本行中央的『战略决策』。"

        # --- 🎯 战略决策层 ---
        action = "[DO_NOTHING]" 
        rationale = ""
        
        if "AI与成长" in category_name:
            if is_break_200: action, rationale = "🚨 [EXIT] 破位清仓", f"跌破年线 {ma200_val}，无条件离场。"
            elif is_break_50: action, rationale = "⚠️ [TRIM] 减仓防守", f"跌穿中期生命线 {ma50_val}，减仓控制回撤。"
            elif is_uptrend:
                if rsi > 75: action, rationale = "⚠️ [TRIM] 超买减仓", f"远离均线，极度拥挤，卖出部分获利盘。"
                elif 0.98 * ma50_val < curr_price < 1.05 * ma50_val:
                    if allow_add: action, rationale = "💡 [ADD_ON_PULLBACK] 回调买入", f"回踩 {ma50_val} 支撑有效，绝佳上车点！"
                    else: action, rationale = "🛑 [DO_NOTHING] 宏观压制", f"虽回踩 {ma50_val}，但宏观避险，取消买入许可。"
                else: action, rationale = "🟢 [HOLD] 趋势完好", f"依托 {ma50_val} 稳健上升，拿住底仓。"
            else: action, rationale = "🟡 [DO_NOTHING] 等待方向", f"震荡期。阻力 {ma50_val}，支撑 {ma200_val}。"

        elif "稳健防御" in category_name:
            if is_break_200: action, rationale = "🚨 [EXIT] 长线破位", f"跌穿年线 {ma200_val}，防守失效。"
            elif 0.98 * ma200_val < curr_price < 1.05 * ma200_val and macd_up: action, rationale = "💡 [ADD_ON_PULLBACK] 黄金坑", f"跌回年线 {ma200_val} 且动能走强，低频钻石买点。"
            elif curr_price > ma50_val: action, rationale = "🟢 [HOLD] 稳健上升", f"安全垫深厚，安心持有收息。"
            else: action, rationale = "🟡 [DO_NOTHING] 回调等待", f"下看年线 {ma200_val}，未到底部。"
                
        else: # 周期
            if is_break_50: action, rationale = "⚠️ [TRIM] 周期走弱", f"跌破 {ma50_val}，周期逆风，减仓观望。"
            elif is_uptrend: action, rationale = "🟢 [HOLD] 周期上行", f"趋势完好。若铜价等大宗商品配合，坚决拿住。"
            else: action, rationale = "🟡 [DO_NOTHING] 底部盘整", f"无明显方向，继续观察。"
                
        return format_price(ticker, curr_price), ma50_val, ma200_val, atr_val, surface_str, tactical_sum, action, rationale

    except Exception as e:
        return "N/A", "N/A", "N/A", "N/A", "数据获取异常", "无", "[ERROR]", "请检查雅虎财经接口"

# ==========================================
# 5. 渲染 个股矩阵
# ==========================================
st.subheader("🛡️ 第二层：个股决策引擎 (研报视角)")

for category_name, stocks in PORTFOLIO.items():
    st.markdown(f"### {category_name}")
    
    for name, ticker in stocks.items():
        res = analyze_stock_v3_1(ticker, category_name, allow_add_growth)
        if not res: continue
        price_str, m50, m200, atr, surface_str, tactical_sum, action, rationale = res
        
        with st.container():
            col1, col2, col3 = st.columns([1.5, 3, 3])
            
            # 明确展示关键数据点位
            with col1:
                st.markdown(f"#### **{name}**")
                st.markdown(f"`{ticker}` | 价: **{price_str}**")
                st.caption(f"**MA50**: {m50}")
                st.caption(f"**MA200**: {m200}")
                st.caption(f"**ATR(波动)**: {atr}")
                
            # 战略决策
            with col2:
                if "HOLD" in action: st.success(f"🎯 **战略决策：{action}**")
                elif "EXIT" in action or "TRIM" in action: st.error(f"🎯 **战略决策：{action}**")
                elif "ADD" in action: st.info(f"🎯 **战略决策：{action}**")
                else: st.warning(f"🎯 **战略决策：{action}**")
                st.markdown(f"{rationale}")
                
            # 战术感知
            with col3:
                st.markdown(f"**🔬 盘面表象：** `{surface_str}`")
                st.markdown(f"**👉 战术总结：** {tactical_sum}")
                
            st.markdown("---")
