import datetime
import io
import sqlite3
import pandas as pd
import streamlit as st

# ==========================================
# 1. 資料庫初始化與 helper 函數
# ==========================================
DB_FILE = "tsmc_chip_data.db"


def init_db():
    """初始化 SQLite 資料庫與資料表"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chip_data (
            trade_date TEXT PRIMARY KEY,
            total_volume INTEGER,
            margin_buy INTEGER,
            margin_sell INTEGER,
            short_buy INTEGER,
            short_sell INTEGER,
            foreign_buy INTEGER,
            foreign_sell INTEGER,
            trust_buy INTEGER,
            trust_sell INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()


def load_data_by_date(date_str):
    """依日期讀取單筆資料"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM chip_data WHERE trade_date = ?",
        conn,
        params=(date_str,),
    )
    conn.close()
    return df


def save_or_update_data(data_dict):
    """新增或覆蓋寫入籌碼資料 (UPSERT)"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO chip_data (
            trade_date, total_volume, margin_buy, margin_sell,
            short_buy, short_sell, foreign_buy, foreign_sell,
            trust_buy, trust_sell, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(trade_date) DO UPDATE SET
            total_volume=excluded.total_volume,
            margin_buy=excluded.margin_buy,
            margin_sell=excluded.margin_sell,
            short_buy=excluded.short_buy,
            short_sell=excluded.short_sell,
            foreign_buy=excluded.foreign_buy,
            foreign_sell=excluded.foreign_sell,
            trust_buy=excluded.trust_buy,
            trust_sell=excluded.trust_sell,
            updated_at=CURRENT_TIMESTAMP
    """,
        (
            data_dict["trade_date"],
            data_dict["total_volume"],
            data_dict["margin_buy"],
            data_dict["margin_sell"],
            data_dict["short_buy"],
            data_dict["short_sell"],
            data_dict["foreign_buy"],
            data_dict["foreign_sell"],
            data_dict["trust_buy"],
            data_dict["trust_sell"],
        ),
    )
    conn.commit()
    conn.close()


def fetch_all_data():
    """讀取資料庫全部資料"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM chip_data ORDER BY trade_date DESC", conn
    )
    conn.close()
    return df


# 初始化資料庫
init_db()

# ==========================================
# 2. Streamlit 介面配置
# ==========================================
st.set_page_config(
    page_title="台積電(2330) 籌碼資料庫管理系統", page_icon="📈", layout="wide"
)

st.title("📈 台積電 (2330) 籌碼交易資料庫 (SQLite)")
st.caption("具備 SQLite 資料庫持久化儲存、歷史查詢與 CSV 匯入/匯出功能")

# 側邊欄：匯入與匯出資料功能
st.sidebar.header("📁 資料備份與管理")

# 匯出資料 (Export)
st.sidebar.subheader("1. 匯出歷史資料")
all_df = fetch_all_data()
if not all_df.empty:
    csv_buffer = io.BytesIO()
    all_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    st.sidebar.download_button(
        label="📥 下載全庫 CSV 備份",
        data=csv_buffer.getvalue(),
        file_name=f"tsmc_chip_history_{datetime.date.today()}.csv",
        mime="text/csv",
    )
else:
    st.sidebar.info("資料庫尚無紀錄可匯出。")

# 匯入資料 (Import)
st.sidebar.subheader("2. 匯入 CSV 資料")
uploaded_file = st.sidebar.file_uploader("選擇 CSV 檔案備份", type=["csv"])
if uploaded_file is not None:
    try:
        imported_df = pd.read_csv(uploaded_file)
        required_cols = [
            "trade_date",
            "total_volume",
            "margin_buy",
            "margin_sell",
            "short_buy",
            "short_sell",
            "foreign_buy",
            "foreign_sell",
            "trust_buy",
            "trust_sell",
        ]

        if all(col in imported_df.columns for col in required_cols):
            conn = sqlite3.connect(DB_FILE)
            for _, row in imported_df.iterrows():
                save_or_update_data(row.to_dict())
            st.sidebar.success("✅ 資料匯入成功！已更新資料庫。")
            st.rerun()
        else:
            st.sidebar.error("❌ 欄位格式不符合，請確認 CSV 檔案架構。")
    except Exception as e:
        st.sidebar.error(f"匯入失敗: {e}")

st.markdown("---")

# ==========================================
# 3. 主頁面：日期選擇與自動帶入
# ==========================================
col_date, col_status = st.columns([1, 2])
with col_date:
    selected_date = st.date_input(
        "📅 請選擇交易日期",
        value=datetime.date.today(),
        max_value=datetime.date.today(),
    )
    date_str = selected_date.strftime("%Y-%m-%d")

# 檢查選擇的日期資料庫中是否有舊資料
existing_data = load_data_by_date(date_str)
has_record = not existing_data.empty

with col_status:
    st.write("### 📍 當前編輯日期：", f"`{date_str}`")
    if has_record:
        st.info("ℹ️ 資料庫中已存在此日期的紀錄（下方已自動載入舊資料，修改後儲存可覆蓋）。")
    else:
        st.write("🆕 資料庫尚無此日紀錄，請填寫數據後儲存。")

# 設定預設填入值 (若有歷史資料則自動載入)
defaults = {
    "total_volume": (
        int(existing_data["total_volume"].iloc[0]) if has_record else 35000
    ),
    "margin_buy": (
        int(existing_data["margin_buy"].iloc[0]) if has_record else 1200
    ),
    "margin_sell": (
        int(existing_data["margin_sell"].iloc[0]) if has_record else 800
    ),
    "short_buy": (
        int(existing_data["short_buy"].iloc[0]) if has_record else 150
    ),
    "short_sell": (
        int(existing_data["short_sell"].iloc[0]) if has_record else 200
    ),
    "foreign_buy": (
        int(existing_data["foreign_buy"].iloc[0]) if has_record else 15000
    ),
    "foreign_sell": (
        int(existing_data["foreign_sell"].iloc[0]) if has_record else 10000
    ),
    "trust_buy": (
        int(existing_data["trust_buy"].iloc[0]) if has_record else 3000
    ),
    "trust_sell": (
        int(existing_data["trust_sell"].iloc[0]) if has_record else 500
    ),
}

# 數據表單輸入區域
with st.form("chip_form"):
    col_input1, col_input2 = st.columns(2)

    with col_input1:
        st.subheader("1️⃣ 信用交易與總成交量 (張)")
        total_volume = st.number_input(
            "當日總交易張數",
            min_value=0,
            value=defaults["total_volume"],
            step=1000,
        )
        margin_buy = st.number_input(
            "融資買進張數",
            min_value=0,
            value=defaults["margin_buy"],
            step=100,
        )
        margin_sell = st.number_input(
            "融資賣出張數",
            min_value=0,
            value=defaults["margin_sell"],
            step=100,
        )
        short_buy = st.number_input(
            "融券買進 (還券)",
            min_value=0,
            value=defaults["short_buy"],
            step=50,
        )
        short_sell = st.number_input(
            "融券賣出 (放空)",
            min_value=0,
            value=defaults["short_sell"],
            step=50,
        )

    with col_input2:
        st.subheader("2️⃣ 主要三大法人動向 (張)")
        foreign_buy = st.number_input(
            "外資買進張數",
            min_value=0,
            value=defaults["foreign_buy"],
            step=1000,
        )
        foreign_sell = st.number_input(
            "外資賣出張數",
            min_value=0,
            value=defaults["foreign_sell"],
            step=1000,
        )
        trust_buy = st.number_input(
            "投信買進張數",
            min_value=0,
            value=defaults["trust_buy"],
            step=500,
        )
        trust_sell = st.number_input(
            "投信賣出張數",
            min_value=0,
            value=defaults["trust_sell"],
            step=500,
        )

    submit_button = st.form_submit_button("💾 儲存 / 更新至 SQLite 資料庫")

if submit_button:
    record = {
        "trade_date": date_str,
        "total_volume": total_volume,
        "margin_buy": margin_buy,
        "margin_sell": margin_sell,
        "short_buy": short_buy,
        "short_sell": short_sell,
        "foreign_buy": foreign_buy,
        "foreign_sell": foreign_sell,
        "trust_buy": trust_buy,
        "trust_sell": trust_sell,
    }
    save_or_update_data(record)
    st.success(f"🎉 日期 `{date_str}` 的籌碼數據已成功寫入 SQLite 資料庫！")
    st.rerun()

st.markdown("---")

# ==========================================
# 4. 當日計算結果與圖表展示
# ==========================================
margin_net = margin_buy - margin_sell
short_net = short_sell - short_buy
foreign_net = foreign_buy - foreign_sell
trust_net = trust_buy - trust_sell
institutional_total_net = foreign_net + trust_net

st.subheader(f"📊 {date_str} 籌碼結算關鍵指標")

m1, m2, m3, m4 = st.columns(4)
m1.metric(
    "外資買賣超",
    f"{foreign_net:+,d} 張",
    delta_color="normal" if foreign_net >= 0 else "inverse",
)
m2.metric(
    "投信買賣超",
    f"{trust_net:+,d} 張",
    delta_color="normal" if trust_net >= 0 else "inverse",
)
m3.metric(
    "融資增減",
    f"{margin_net:+,d} 張",
    delta_color="inverse" if margin_net >= 0 else "normal",
)
m4.metric(
    "融券增減",
    f"{short_net:+,d} 張",
    delta_color="normal" if short_net >= 0 else "inverse",
)

st.subheader("📈 主要籌碼淨動向對比")
chart_data = pd.DataFrame(
    {
        "籌碼項目": ["外資", "投信", "外投合計", "融資", "融券"],
        "淨張數": [
            foreign_net,
            trust_net,
            institutional_total_net,
            margin_net,
            short_net,
        ],
    }
).set_index("籌碼項目")
st.bar_chart(chart_data)

st.markdown("---")

# ==========================================
# 5. SQLite 資料庫歷史總覽
# ==========================================
st.subheader("🗄️ SQLite 資料庫全紀錄檢視")
all_history_df = fetch_all_data()

if not all_history_df.empty:
    # 算好淨買賣超欄位方便呈現
    all_history_df["外資淨買賣"] = (
        all_history_df["foreign_buy"] - all_history_df["foreign_sell"]
    )
    all_history_df["投信淨買賣"] = (
        all_history_df["trust_buy"] - all_history_df["trust_sell"]
    )
    all_history_df["融資淨增減"] = (
        all_history_df["margin_buy"] - all_history_df["margin_sell"]
    )
    all_history_df["融券淨增減"] = (
        all_history_df["short_sell"] - all_history_df["short_buy"]
    )

    st.dataframe(all_history_df, use_container_width=True)
else:
    st.write("目前資料庫內尚無資料。")
