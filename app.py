import streamlit as st
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta

# ==========================================
# 1. 网页基础设置 (宽屏报表模式)
# ==========================================
st.set_page_config(page_title="Lydia CTA 交易引擎", layout="wide", page_icon="🎯")
st.title("🎯 Lydia 机构级交易监控中心 v3.0")
st.markdown("**(宏观状态机 + 标准指令集 + 盘面智能解读)** | 策略定力：月操作<10次")
st.markdown("---")

# ==========================================
# 2. 标的与参数配置
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
# 3. 第一层过滤：宏观状态机 (Macro Regime)
# ==========================================
@st.cache_data(ttl=3600)
def get_macro_regime():
    try:
        us10y = yf.Ticker("^TNX").history(period="10d")['Close']
        vix = yf.Ticker("^VIX").history(period="10d")['Close']
        
        current_vix = vix.iloc[-1]
        vix_trend = vix.iloc[-1] > vix.iloc[-5] # 5天趋势
        us10y_up = us10y.iloc[-1] > us10y.iloc[-5]
        
        if current_vix > 20 or (us10y_up and current_vix > 18):
            state = "🔴 [RISK_OFF] 避险模式"
            rationale = f"表象：VIX恐慌指数高企({current_vix:.2f})，或美债收益率持续上行。\n\n👉 **系统指引**：全局风险偏好下降！引擎已强行**剥夺**所有高波动成长股的[加仓]许可，必须优先防守。"
            allow_add_growth = False
        elif current_vix < 15 and not us10y_up:
            state = "🟢 [RISK_ON] 进攻模式"
            rationale = f"表象：VIX处于低位({current_vix:.2f})且美债收益率回落。\n\n👉 **系统指引**：宏观环境友好，顺风局。符合回调买点的标的允许[果断加仓]。"
            allow_add_growth = True
        else:
            state = "🟡 [NEUTRAL] 中性震荡"
            rationale = f"表象：VIX指数正常({current_vix:.2f})，无极端宏观冲击。\n\n👉 **系统指引**：宏观不拖后腿，个股独立表现，按既定技术面规则执行即可。"
            allow_add_growth = True
            
        return state, rationale, allow_add_growth
    except Exception as e:
        return "⚪ [UNKNOWN] 宏观数据盲区", "无法获取宏观数据，默认按技术面执行。", True

macro_state, macro_rationale, allow_add_growth = get_macro_regime()

st.subheader("🌍 第一层过滤：宏观引擎 (Macro Regime)")
st.info(f"**当前状态：{macro_state}**\n\n{macro_rationale}")
st.markdown("---")

# ==========================================
# 4. 核心计算与大脑逻辑 (引擎 v3.0)
# ==========================================
@st.cache_data(ttl=3600)
def analyze_stock_v3(ticker, category_name, allow_add_growth):
    try:
        df = yf.Ticker(ticker).history(period="1y")
        if len(df) < 200: return None
            
        close, vol = df['Close'], df['Volume']
        curr_price = close.iloc[-1]
        
        ma50 = round(ta.trend.sma_indicator(close, window=50).iloc[-1], 2)
        ma200 = round(ta.trend.sma_indicator(close, window=200).iloc[-1], 2)
        avg_vol = vol.iloc[-6:-1].mean()
        
        # 真破位判定 (连续2天跌破)
        is_break_50 = (close.iloc[-1] < ma50 * 0.98) and (close.iloc[-2] < ma50 * 0.98)
        is_break_200 = (close.iloc[-1] < ma200 * 0.98) and (close.iloc[-2] < ma200 * 0.98)
        is_uptrend = (curr_price > ma50) and (curr_price > ma200)
        
        # --- 🔬 战术雷达感知层 (产生表象与解读) ---
        rsi = ta.momentum.rsi(close, window=14).iloc[-1]
        macd_up = ta.trend.macd_diff(close).iloc[-1] > ta.trend.macd_diff(close).iloc[-2]
        vol_ratio = vol.iloc[-1] / avg_vol if avg_vol > 0 else 1
        bb_low = ta.volatility.bollinger_lband(close).iloc[-1]
        bb_high = ta.volatility.bollinger_hband(close).iloc[-1]
        
        surfaces = []
        if rsi > 70: surfaces.append(f"🔥RSI超买({int(rsi)})")
        elif rsi < 35: surfaces.append(f"🧊RSI超卖({int(rsi)})")
        if vol_ratio > 1.8: surfaces.append(f"💥异常放量({vol_ratio:.1f}x)")
        elif vol_ratio < 0.6: surfaces.append("💤交投极度清淡")
        surfaces.append("📈动能走强" if macd_up else "📉动能走弱")
        if curr_price < bb_low * 1.02: surfaces.append("🎯砸穿布林下轨")
        
        surface_str = " | ".join(surfaces)
        
        # 短线逻辑总结
        if rsi > 70 and vol_ratio > 1.5:
            tactical_sum = "**[拥挤度 HIGH]** 游资FOMO情绪极高且放量。\n👉 **短线指引**：绝对禁止追高，若有底仓可做 T 逢高减仓锁定利润。"
        elif rsi < 35 and not macd_up and vol_ratio > 1.5:
            tactical_sum = "**[恐慌踩踏]** 资金带量恐慌出逃中。\n👉 **短线指引**：抛压未尽，切勿左侧接飞刀，耐心等待缩量企稳。"
        elif rsi < 40 and macd_up and curr_price < bb_low * 1.02:
            tactical_sum = "**[超跌反弹区]** 跌出恐慌盘且动能开始走强。\n👉 **短线指引**：极佳的短线低吸窗口，胜率极高。"
        elif vol_ratio < 0.6 and not macd_up:
            tactical_sum = "**[阴跌筑底]** 市场缺乏资金关注。\n👉 **短线指引**：处于垃圾震荡时间，多看少动，避免磨损心态。"
        else:
            tactical_sum = "**[平淡震荡]** 盘面无明显极端异动。\n👉 **短线指引**：忽略短线噪音，严格按照下方【战略建议】执行。"

        # --- 🎯 战略决策层 (生成标准 Action) ---
        action = "[DO_NOTHING]" # 默认不动
        rationale = ""
        
        if "AI与成长" in category_name:
            if is_break_200:
                action, rationale = "🚨 [EXIT] 破位清仓", f"收盘价已连续跌穿年线 ({ma200})，长线逻辑破坏，无条件清仓止损。"
            elif is_break_50:
                action, rationale = "⚠️ [TRIM] 减仓防守", f"跌破中期生命线 ({ma50})，趋势走弱。建议减仓 1/3 控制回撤，底线防守 MA200 ({ma200})。"
            elif is_uptrend:
                if rsi > 75:
                    action, rationale = "⚠️ [TRIM] 极度超买减仓", f"趋势虽好，但处于极度拥挤状态。切勿加仓，可适当卖出获利盘。"
                elif 0.98 * ma50 < curr_price < 1.05 * ma50: # 回踩均线
                    if allow_add_growth:
                        action, rationale = "💡 [ADD_ON_PULLBACK] 回调加仓", f"强势股回踩支撑位 ({ma50})，且宏观环境允许。绝佳上车点！"
                    else:
                        action, rationale = "🛑 [DO_NOTHING] 宏观压制加仓", f"虽然回踩了支撑位 ({ma50})，但宏观处于 [RISK_OFF] 模式，取消加仓动作，管住手！"
                else:
                    action, rationale = "🟢 [HOLD] 趋势完好持有", f"趋势极强 (支撑 {ma50})。不要乱做 T 卖飞，让利润奔跑。"
            else:
                action, rationale = "🟡 [DO_NOTHING] 垃圾时间", f"处于均线之间震荡，缺乏方向。耐心等待确认，什么都不要做。"

        elif "稳健防御" in category_name:
            if is_break_200:
                action, rationale = "🚨 [EXIT] 破位清仓", f"作为防御股跌穿年线 ({ma200}) 极不寻常，资金长线撤离，立即出局。"
            elif 0.98 * ma200 < curr_price < 1.05 * ma200 and macd_up:
                action, rationale = "💡 [ADD_ON_PULLBACK] 黄金坑买入", f"稳健标的跌回年线 ({ma200}) 且抛压衰竭，这是低频交易者的[钻石级买点]。"
            elif curr_price > ma50:
                action, rationale = "🟢 [HOLD] 趋势完好持有", f"稳健上升中，已远离买入区。安心持股收息/等涨。"
            else:
                action, rationale = "🟡 [DO_NOTHING] 回调等待", f"正在向底部靠近 (目标年线 {ma200})，现在接盘性价比不高，继续等待。"
                
        else: # 周期
            if is_break_50:
                action, rationale = "⚠️ [TRIM] 周期走弱", f"跌破 50 日均线 ({ma50})。周期股重势，建议立刻减仓观望。"
            elif is_uptrend:
                action, rationale = "🟢 [HOLD] 周期上行", f"趋势完好 (防守点 {ma50})。若LME铜等大宗商品配合，坚决拿住。"
            else:
                action, rationale = "🟡 [DO_NOTHING] 底部盘整", f"缺乏方向。密切关注宏观大宗商品动向再做决断。"
                
        return format_price(ticker, curr_price), surface_str, tactical_sum, action, rationale

    except Exception as e:
        return "N/A", "N/A", "数据缺失", "[ERROR]", "接口抓取失败"

# ==========================================
# 5. 渲染 个股矩阵 (CTA研报式排版)
# ==========================================
st.subheader("🛡️ 第二层：个股决策引擎 (研报视角)")

for category_name, stocks in PORTFOLIO.items():
    st.markdown(f"### {category_name}")
    
    for name, ticker in stocks.items():
        res = analyze_stock_v3(ticker, category_name, allow_add_growth)
        if not res: continue
        price_str, surface_str, tactical_sum, action, rationale = res
        
        # 使用 Streamlit 卡片式布局，替代干瘪的表格
        with st.container():
            col1, col2, col3 = st.columns([1.5, 3, 3])
            
            # 第一列：股票名称与价格
            with col1:
                st.markdown(f"#### **{name}**")
                st.markdown(f"`{ticker}`")
                st.metric(label="当前价", value=price_str)
                
            # 第二列：战略决策 (核心)
            with col2:
                # 根据动作变色
                if "HOLD" in action: st.success(f"🎯 **战略决策：{action}**")
                elif "EXIT" in action or "TRIM" in action: st.error(f"🎯 **战略决策：{action}**")
                elif "ADD" in action: st.info(f"🎯 **战略决策：{action}**")
                else: st.warning(f"🎯 **战略决策：{action}**")
                st.markdown(f"{rationale}")
                
            # 第三列：战术感知 (So What)
            with col3:
                st.markdown(f"**🔬 战术表象：** `{surface_str}`")
                st.markdown(f"{tactical_sum}")
                
            st.markdown("---") # 分割线

st.caption("⚙️ 系统纪律：请忽略战术层面的小幅波动，交易动作【仅】以中央的『战略决策』指令为准。做到：指令不到，绝不扣扳机。")
