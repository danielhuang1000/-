import datetime
import io
import re
import sqlite3
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st
import easyocr

# ==========================================
# 1. 初始化 EasyOCR 讀取器 (快取避免重複載入)
# ==========================================
@st.cache_resource
def get_ocr_reader():
    # ✅ 修正：EasyOCR 的繁體中文語言代碼為 'ch_tra'
    return easyocr.Reader(['ch_tra', 'en'], gpu=False)


# ==========================================
# 2. 資料庫初始化與 Helper 函數
# ==========================================
DB_FILE = "tsmc_chip_data.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
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
    """)
    conn.commit()
    conn.close()


def load_data_by_date(date_str):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM chip_data WHERE trade_date = ?",
        conn,
        params=(date_str,),
    )
    conn.close()
    return df


def save_or_update_data(data_dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
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
    """, (
        data_dict['trade_date'],
        data_dict['total_volume'],
        data_dict['margin_buy'],
        data_dict['margin_sell'],
        data_dict['short_buy'],
        data_dict['short_sell'],
        data_dict['foreign_buy'],
        data_dict['foreign_sell'],
        data_dict['trust_buy'],
        data_dict['trust_sell']
    ))
    conn.commit()
    conn.close()


def fetch_all_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM chip_data ORDER BY trade_date DESC", conn
    )
    conn.close()
    return df


def extract_chip_numbers_local(image: Image.Image):
    """使用本地 EasyOCR 辨識圖片中的文字與數字"""
    reader = get_ocr_reader()
    img_np = np.array(image)

    # 執行 OCR 辨識
    results = reader.readtext(img_np)

    # 依畫面 Top (Y座標) -> Left (X座標) 進行文字排序
    results = sorted(results, key=lambda x: (x[0][0][1], x[0][0][0]))

    parsed = {}
    lines_text = [res[1].strip() for res in results]
    full_text = " | ".join(lines_text)

    # 表格抓取邏輯
    for i, res in enumerate(results):
        text = res[1].strip()

        # 抓取「外資」Row
        if "外資" in text or "外" in text:
            nums = []
            for j in range(i + 1, min(i + 6, len(results))):
                cleaned = re.sub(r"[^\d]", "", results[j][1])
                if cleaned:
                    nums.append(int(cleaned))
            if len(nums) >= 1:
                parsed["foreign_buy"] = nums[0]   # 買進 (例如 42319)
            if len(nums) >= 2:
                parsed["foreign_sell"] = nums[1]  # 賣出 (例如 28539)

        # 抓取「投信」Row
        elif "投信" in text or "投" in text:
            nums = []
            for j in range(i + 1, min(i + 6, len(results))):
                cleaned = re.sub(r"[^\d]", "", results[j][1])
                if cleaned:
                    nums.append(int(cleaned))
            if len(nums) >= 1:
                parsed["trust_buy"] = nums[0]    # 買進 (例如 7244)
            if len(nums) >= 2:
                parsed["trust_sell"] = nums[1]   # 賣出 (例如 180)

    return parsed, full_text


init_db()

# ==========================================
# 3. Streamlit 介面配置
# ==========================================
st.set_page_config(
    page_title="台積電(2330) 籌碼資料庫 (本地OCR免金鑰)",
    page_icon="📸",
    layout="wide"
)

st.title("📈 台積電 (2330) 籌碼資料庫 (100% 本地辨識/免API金鑰)")
st.caption("使用本地端 EasyOCR 引擎進行圖片文字辨識，資料不外傳，完全免費。")

# 側邊欄：資料備份與管理
st.sidebar.header("📁 資料備份與管理")
all_df = fetch_all_data()
if not all_df.empty:
    csv_buffer = io.BytesIO()
    all_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    st.sidebar.download_button(
        label="📥 下載全庫 CSV 備份",
        data=csv_buffer.getvalue(),
        file_name=f"tsmc_chip_history_{datetime.date.today()}.csv",
        mime="text/csv"
    )

uploaded_csv = st.sidebar.file_uploader("匯入 CSV 備份", type=["csv"])
if uploaded_csv is not None:
    try:
        imported_df = pd.read_csv(uploaded_csv)
        for _, row in imported_df.iterrows():
            save_or_update_data(row.to_dict())
        st.sidebar.success("✅ CSV 資料匯入成功！")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"匯入失敗: {e}")

st.markdown("---")

# ==========================================
# 4. 日期選擇與 本地 OCR 拍照/上傳區
# ==========================================
col_date, col_status = st.columns([1, 2])
with col_date:
    selected_date = st.date_input(
        "📅 請選擇交易日期",
        value=datetime.date.today(),
        max_value=datetime.date.today(),
    )
    date_str = selected_date.strftime("%Y-%m-%d")

existing_data = load_data_by_date(date_str)
has_record = not existing_data.empty

with col_status:
    st.write("### 📍 當前編輯日期：", f"`{date_str}`")
    if has_record:
        st.info("ℹ️ 資料庫中已存在此日期紀錄，儲存時將自動覆蓋。")

st.subheader("📷 籌碼看盤畫面辨識 (拍照 / 上傳截圖)")

if 'ocr_parsed_data' not in st.session_state:
    st.session_state['ocr_parsed_data'] = {}

img_col1, img_col2 = st.columns(2)
with img_col1:
    camera_img = st.camera_input("📷 鏡頭拍照")
with img_col2:
    upload_img = st.file_uploader("📤 上傳籌碼截圖", type=["png", "jpg", "jpeg"])

target_image = camera_img or upload_img

if target_image:
    image = Image.open(target_image)
    st.image(image, caption="待辨識的看盤畫面", use_container_width=True)

    if st.button("🔍 啟動本地 OCR 辨識 (免金鑰)"):
        with st.spinner("本地 EasyOCR 辨識中，請稍候..."):
            try:
                parsed_res, raw_text = extract_chip_numbers_local(image)
                st.session_state['ocr_parsed_data'] = parsed_res
                st.success("✅ 辨識完成！數據已帶入下方，請檢查無誤後儲存。")
                with st.expander("📝 檢視 OCR 原始辨識文字"):
                    st.write(raw_text)
            except Exception as e:
                st.error(f"辨識失敗：{e}")

# ==========================================
# 5. 資料表單與預設值帶入
# ==========================================
ocr_data = st.session_state.get('ocr_parsed_data', {})

defaults = {
    "total_volume": int(existing_data["total_volume"].iloc[0]) if has_record else 35000,
    "margin_buy": int(existing_data["margin_buy"].iloc[0]) if has_record else 1200,
    "margin_sell": int(existing_data["margin_sell"].iloc[0]) if has_record else 800,
    "short_buy": int(existing_data["short_buy"].iloc[0]) if has_record else 150,
    "short_sell": int(existing_data["short_sell"].iloc[0]) if has_record else 200,
    "foreign_buy": ocr_data.get('foreign_buy', int(existing_data["foreign_buy"].iloc[0]) if has_record else 15000),
    "foreign_sell": ocr_data.get('foreign_sell', int(existing_data["foreign_sell"].iloc[0]) if has_record else 10000),
    "trust_buy": ocr_data.get('trust_buy', int(existing_data["trust_buy"].iloc[0]) if has_record else 3000),
    "trust_sell": ocr_data.get('trust_sell', int(existing_data["trust_sell"].iloc[0]) if has_record else 500)
}

st.markdown("---")

with st.form("chip_form"):
    col_input1, col_input2 = st.columns(2)

    with col_input1:
        st.subheader("1️⃣ 信用交易與總成交量 (張)")
        total_volume = st.number_input("當日總交易張數", min_value=0, value=defaults["total_volume"], step=1000)
        margin_buy = st.number_input("融資買進張數", min_value=0, value=defaults["margin_buy"], step=100)
        margin_sell = st.number_input("融資賣出張數", min_value=0, value=defaults["margin_sell"], step=100)
        short_buy = st.number_input("融券買進 (還券)", min_value=0, value=defaults["short_buy"], step=50)
        short_sell = st.number_input("融券賣出 (放空)", min_value=0, value=defaults["short_sell"], step=50)

    with col_input2:
        st.subheader("2️⃣ 主要三大法人動向 (張)")
        foreign_buy = st.number_input("外資買進張數", min_value=0, value=int(defaults["foreign_buy"]), step=1000)
        foreign_sell = st.number_input("外資賣出張數", min_value=0, value=int(defaults["foreign_sell"]), step=1000)
        trust_buy = st.number_input("投信買進張數", min_value=0, value=int(defaults["trust_buy"]), step=500)
        trust_sell = st.number_input("投信賣出張數", min_value=0, value=int(defaults["trust_sell"]), step=500)

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
        "trust_sell": trust_sell
    }
    save_or_update_data(record)
    st.session_state['ocr_parsed_data'] = {}
    st.success(f"🎉 日期 `{date_str}` 的籌碼數據已成功寫入 SQLite 資料庫！")
    st.rerun()

st.markdown("---")

# ==========================================
# 6. 指標與歷史資料展現
# ==========================================
foreign_net = foreign_buy - foreign_sell
trust_net = trust_buy - trust_sell
margin_net = margin_buy - margin_sell
short_net = short_sell - short_buy

st.subheader(f"📊 {date_str} 籌碼結算關鍵指標")
m1, m2, m3, m4 = st.columns(4)
m1.metric("外資買賣超", f"{foreign_net:+,d} 張")
m2.metric("投信買賣超", f"{trust_net:+,d} 張")
m3.metric("融資增減", f"{margin_net:+,d} 張")
m4.metric("融券增減", f"{short_net:+,d} 張")

st.subheader("🗄️ SQLite 資料庫全紀錄檢視")
all_history_df = fetch_all_data()
if not all_history_df.empty:
    st.dataframe(all_history_df, use_container_width=True)
