import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# --- 1. CLOUD DATABASE CONNECTION ---
try:
    DB_URI = st.secrets["DB_URL"]
    engine = create_engine(DB_URI, pool_pre_ping=True)
except Exception as e:
    st.error("Database Connection Failed. Check your Secrets configuration.")
    st.stop()

# --- 2. HIGH-CLARITY CENTERED UI CSS ---
st.set_page_config(page_title="Ramdev Enterprise", layout="wide", page_icon="🚛")

st.markdown("""
    <style>
    /* Global Theme */
    .stApp { background: #0f172a; color: #ffffff; }
    .block-container { max-width: 1100px !important; margin: auto !important; padding-top: 2rem !important; }
    [data-testid="stSidebar"] { display: none; }

    /* BRAND HEADING */
    h1 {
        text-align: center !important;
        font-family: 'Impact', 'Arial Black', sans-serif !important;
        background: linear-gradient(135deg, #ffffff 0%, #60a5fa 50%, #1e40af 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 72px !important;
        font-weight: 900 !important;
        margin-bottom: 0px !important;
        text-transform: uppercase;
        filter: drop-shadow(0px 5px 10px rgba(0, 0, 0, 0.5));
    }
    .sub-header {
        text-align: center; color: #60a5fa; font-weight: 700; font-size: 16px;
        letter-spacing: 8px; margin-top: -10px; margin-bottom: 40px; text-transform: uppercase;
    }

    /* NAVIGATION */
    div.stRadio > div {
        display: flex; flex-direction: row; justify-content: center !important;
        gap: 15px; background: #1e293b; padding: 10px; border-radius: 12px;
        border: 2px solid #334155; margin: 0 auto 40px auto; width: fit-content;
    }
    div.stRadio > div > label {
        color: #cbd5e1 !important; padding: 10px 22px !important;
        border-radius: 8px !important; font-weight: 700 !important; font-size: 16px !important;
    }
    div.stRadio > div > label[data-checked="true"] {
        background: #3b82f6 !important; color: #ffffff !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.5);
    }
    div.stRadio div[role="radiogroup"] > label > div:first-child { display: none !important; }

    /* METRICS */
    div[data-testid="metric-container"] {
        background: #1e293b !important; border: 2px solid #3b82f6 !important;
        padding: 25px !important; border-radius: 15px !important; text-align: center;
    }
    div[data-testid="stMetricValue"] > div { font-size: 40px !important; font-weight: 800 !important; color: #ffffff !important; }
    div[data-testid="stMetricLabel"] > div { font-size: 18px !important; color: #94a3b8 !important; font-weight: 600 !important; }

    .stButton>button {
        border-radius: 10px; background: #3b82f6; color: white; font-weight: 700;
        height: 3.5rem; width: 100%; font-size: 18px; border: none;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. HEADER & MENU ---
st.markdown("<h1>RAMDEV SUPER SERVICE</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Simply Super Logistics</p>", unsafe_allow_html=True)

choice = st.radio("NAV", ["📊 Dashboard", "➕ New Entry", "📂 Ledger", "🧾 Billing", "👥 Directory"], 
                  horizontal=True, label_visibility="collapsed")
st.markdown("<hr style='border-color: #334155;'>", unsafe_allow_html=True)

# --- 4. PAGE LOGIC ---

if choice == "📊 Dashboard":
    with engine.connect() as conn:
        df_p = pd.read_sql("SELECT * FROM parcels", conn)
        df_i = pd.read_sql("SELECT * FROM invoices", conn)
    
    col1, col2, col3 = st.columns(3)
    if not df_p.empty:
        col1.metric("Gross Weight", f"{df_p['weight'].sum():,.1f} KG")
        col2.metric("Shipments", f"{len(df_p)}")
    if not df_i.empty:
        pending = df_i[df_i['status'] == 'Unpaid']['total_amount'].sum()
        col3.metric("Pending Dues", f"₹{pending:,.0f}")

elif choice == "➕ New Entry":
    st.write("## Register Shipment")
    with engine.connect() as conn:
        clients = pd.read_sql("SELECT name FROM clients", conn)['name'].tolist()
    
    with st.form("ship_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        date = c1.date_input("Loading Date")
        lr = c2.text_input("LR / Receipt Number")
        sender = st.text_input("Sender Party")
        receiver = st.selectbox("Receiver Client", [""] + clients)
        
        c3, c4, c5 = st.columns(3)
        bale = c3.text_input("Bale No")
        qty = c4.number_input("Qty", min_value=1)
        wt = c5.number_input("Weight (KG)", min_value=0.1)
        
        if st.form_submit_button("✅ SECURE ENTRY TO CLOUD"):
            if receiver and lr:
                with engine.connect() as conn:
                    query = text("INSERT INTO parcels (date, receipt, sender, receiver, bale_no, parcel_count, weight) VALUES (:d, :r, :s, :rec, :b, :q, :w)")
                    conn.execute(query, {"d": str(date), "r": lr, "s": sender, "rec": receiver, "b": bale, "q": qty, "w": wt})
                    conn.commit()
                st.success("Synchronized with Cloud Database.")
            else:
                st.error("LR No and Receiver are mandatory.")

elif choice == "📂 Ledger":
    st.write("## Historical Ledger")
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM parcels ORDER BY id DESC", conn)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

elif choice == "🧾 Billing":
    st.write("## Invoicing Hub")
    with engine.connect() as conn:
        c_df = pd.read_sql("SELECT * FROM clients", conn)
    
    target = st.selectbox("Select Account", [""] + c_df['name'].tolist())
    if target:
        meta = c_df[c_df['name'] == target].iloc[0]
        with engine.connect() as conn:
            data = pd.read_sql(text("SELECT * FROM parcels WHERE receiver = :n"), conn, params={"n": target})
        
        if not data.empty:
            data['Charge'] = data['weight'].apply(lambda x: max(x * meta['default_rate'], meta['min_amount']))
            st.dataframe(data, use_container_width=True)
            st.metric("Statement Balance", f"₹{data['Charge'].sum():,.2f}")

elif choice == "👥 Directory":
    st.write("## Client Master Directory")
    with st.expander("Register New Account"):
        with st.form("creg"):
            n = st.text_input("Company Name").upper()
            r = st.number_input("Rate (₹/KG)", value=7.5)
            m = st.number_input("Min Bill (₹)", value=200.0)
            if st.form_submit_button("SAVE PARTNER"):
                if n:
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO clients (name, default_rate, min_amount) VALUES (:n, :r, :m)"), {"n": n, "r": r, "m": m})
                        conn.commit()
                    st.rerun()
