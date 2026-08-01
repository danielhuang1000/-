import streamlit as st
import pandas as pd

# 頁面配置
st.set_page_config(
    page_title="台積電(2330) 當日籌碼統計與分析",
    page_icon="📈",
    layout="wide"
)

st.title("📈 台積電 (2330) 當日籌碼交易統計分析")
st.caption("請在下方輸入當日交易數據，系統將自動計算籌碼動向與淨買賣超。")

st.markdown("---")

# 設定兩欄輸入區域
col_input1, col_input2 = st.columns(2)

with col_input1:
    st.subheader("1️⃣ 信用交易與總成交量 (張)")
    total_volume = st.number_input("當日總交易張數", min_value=0, value=35000, step=1000)
    margin_buy = st.number_input("融資買進張數", min_value=0, value=1200, step=100)
    margin_sell = st.number_input("融資賣出張數", min_value=0, value=800, step=100)
    short_buy = st.number_input("融券買進 (還券)", min_value=0, value=150, step=50)
    short_sell = st.number_input("融券賣出 (放空)", min_value=0, value=200, step=50)

with col_input2:
    st.subheader("2️⃣ 主要三大法人動向 (張)")
    foreign_buy = st.number_input("外資買進張數", min_value=0, value=15000, step=1000)
    foreign_sell = st.number_input("外資賣出張數", min_value=0, value=10000, step=1000)
    trust_buy = st.number_input("投信買進張數", min_value=0, value=3000, step=500)
    trust_sell = st.number_input("投信賣出張數", min_value=0, value=500, step=500)

st.markdown("---")

# 數據計算邏輯
margin_net = margin_buy - margin_sell          # 融資淨增加/減少
short_net = short_sell - short_buy            # 融券淨增加/減少
foreign_net = foreign_buy - foreign_sell      # 外資淨買賣超
trust_net = trust_buy - trust_sell            # 投信淨買賣超
institutional_total_net = foreign_net + trust_net # 外資+投信淨買賣超

# 計算法人參與度
institutional_traded_vol = foreign_buy + foreign_sell + trust_buy + trust_sell
institutional_ratio = (institutional_traded_vol / (total_volume * 2)) * 100 if total_volume > 0 else 0

# 顯示關鍵數據摘要 (Metric Cards)
st.subheader("📊 籌碼結算關鍵指標")

m1, m2, m3, m4 = st.columns(4)
m1.metric("外資買買超", f"{foreign_net:+,d} 張", delta_color="normal" if foreign_net >= 0 else "inverse")
m2.metric("投信買買超", f"{trust_net:+,d} 張", delta_color="normal" if trust_net >= 0 else "inverse")
m3.metric("融資增減", f"{margin_net:+,d} 張", delta_color="inverse" if margin_net >= 0 else "normal") # 融資增加通常對散戶偏向警訊
m4.metric("融券增減", f"{short_net:+,d} 張", delta_color="normal" if short_net >= 0 else "inverse")

# 詳細數據表格
st.subheader("📋 籌碼分類統計表")

summary_data = {
    "類別": ["外資", "投信", "外資+投信合計", "融資 (散戶主力)", "融券 (空頭動向)"],
    "買進/增張數": [foreign_buy, trust_buy, foreign_buy + trust_buy, margin_buy, short_sell],
    "賣出/減張數": [foreign_sell, trust_sell, foreign_sell + trust_sell, margin_sell, short_buy],
    "淨買賣超 (張)": [foreign_net, trust_net, institutional_total_net, margin_net, short_net]
}

df_summary = pd.DataFrame(summary_data)
st.dataframe(df_summary, use_container_width=True)

# 視覺化圖表
st.subheader("📈 主要籌碼淨動向對比")

chart_data = pd.DataFrame({
    "籌碼項目": ["外資", "投信", "外投合計", "融資", "融券"],
    "淨張數": [foreign_net, trust_net, institutional_total_net, margin_net, short_net]
}).set_index("籌碼項目")

st.bar_chart(chart_data)

# 觀點提示與警告欄位
st.subheader("💡 籌碼解析與解讀提示")

if institutional_total_net > 0 and margin_net < 0:
    st.success("🟢 **籌碼集中訊號**：法人呈現買超，且融資減少（散戶退場），籌碼相對健康安定。")
elif institutional_total_net < 0 and margin_net > 0:
    st.warning("🔴 **籌碼渙散警訊**：法人呈現賣超，但融資增加（散戶接盤），短線賣壓可能較重。")
elif institutional_total_net > 0 and margin_net > 0:
    st.info("🔵 **主力散戶同買**：法人與融資同時增加，推升力道強但需注意高檔過熱風險。")
else:
    st.warning("⚪ **主力散戶同賣**：法人賣超且融資退場，市場保守觀望情緒濃厚。")
