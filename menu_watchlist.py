import pandas as pd
import streamlit as st
import os
import json
import menu_fundamental

# --- FUNGSI HELPER UNTUK PENYIMPANAN FISIK ---
WATCHLIST_FILE = "watchlist_data.json"

def save_watchlist(tickers):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(tickers, f)

def load_watchlist_from_file():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return []

def run_watchlist():
    st.title("⭐ My Watchlist")
    st.markdown("Pantau hingga **15 emiten** pilihan. Data tersimpan otomatis meski program di-restart.")

    # 1. Load Database Utama
    def load_data(path):
        if os.path.exists(path):
            return pd.read_parquet(path)
        return None

    df_all_fund = load_data('Master_Database_Financials.parquet')
    path_transaksi = "Master_Database_Transaksi_IDX.parquet"

    if df_all_fund is None:
        st.error("Database Utama tidak ditemukan!")
        return

    # 2. Ambil data terakhir yang tersimpan saat pertama kali run
    if 'last_watchlist' not in st.session_state:
        st.session_state.last_watchlist = load_watchlist_from_file()

    # 3. Input Watchlist (Multiselect)
    all_available_tickers = sorted(df_all_fund['Ticker'].unique().tolist())
    
    # Gunakan default dari session_state yang diambil dari file JSON
    selected_tickers = st.multiselect(
        "Masukkan Kode Emiten (Maksimal 15):",
        options=all_available_tickers,
        default=st.session_state.last_watchlist,
        max_selections=15,
        key="watchlist_input"
    )

    # 4. Simpan ke file jika ada perubahan antara input saat ini dan yang tersimpan
    if selected_tickers != st.session_state.last_watchlist:
        save_watchlist(selected_tickers)
        st.session_state.last_watchlist = selected_tickers
        # Jangan gunakan st.rerun() di sini agar tidak looping, 
        # Streamlit akan menghitung ulang otomatis karena input berubah.

    if not selected_tickers:
        st.info("Watchlist kosong. Silakan masukkan kode emiten.")
        return

    # 5. Proses Data Watchlist (Sama seperti sebelumnya, dengan proteksi TKIM)
    watchlist_data = []
    
    with st.spinner(f"Menghitung data untuk {len(selected_tickers)} emiten..."):
        for ticker in selected_tickers:
            try:
                df_history = df_all_fund[df_all_fund['Ticker'] == ticker].copy()
                if df_history.empty: continue

                # Proteksi datetime untuk error .dt
                df_history['FS_Date'] = pd.to_datetime(df_history['FS_Date'], errors='coerce')
                df_history = df_history.dropna(subset=['FS_Date']).sort_values('FS_Date')

                latest_row = df_history.iloc[-1]
                sektor = latest_row.get('Sector', '-')

                df_ttm = menu_fundamental.calculate_ttm_data(df_history)
                df_active = df_ttm if (df_ttm is not None and not df_ttm.empty) else df_history
                
                metrics = menu_fundamental.calculate_company_metrics(df_history, df_active, ticker, path_transaksi)
                val_results = menu_fundamental.calculate_valuation_metrics(df_active, metrics)
                
                current_price = metrics.get('last_price', 0)
                current_bvps = val_results.get("current_bvps", 0)
                pbv = current_price / current_bvps if current_bvps > 0 else 0
                
                # Market Cap (T)
                mkt_cap = (current_price * metrics.get('shares', 0)) / 1_000_000_000_000

                # NPM
                profit = df_active.iloc[-1].get('Profit_for_Period', 0)
                sales = df_active.iloc[-1].get('Sales_IDR_bn', 0)
                npm = (profit / sales * 100) if (sales and sales > 0) else 0

                watchlist_data.append({
                    "Ticker": ticker,
                    "Sector": sektor,
                    "Price": current_price,
                    "PBV": pbv,
                    "ROE_Book": metrics.get('roe_end', 0),
                    "ROE_Adj": metrics.get('calc_roe_adj', 0),
                    "CAGR": float(metrics.get('growth_text', '0').replace('%','')) if '%' in str(metrics.get('growth_text','')) else 0,
                    "Market_Cap": mkt_cap,
                    "NPM": npm,
                    "BVPS": current_bvps
                })
            except Exception as e:
                st.warning(f"Gagal memproses {ticker}: {e}")

    # 6. Tampilkan Tabel
    if watchlist_data:
        df_watch = pd.DataFrame(watchlist_data)
        st.dataframe(
            df_watch,
            width='stretch',
            hide_index=True,
            column_config={
                "Ticker": st.column_config.TextColumn("Kode"),
                "Sector": st.column_config.TextColumn("Sektor"),
                "Price": st.column_config.NumberColumn("Last Price", format="Rp %d"),
                "PBV": st.column_config.NumberColumn("P/BV", format="%.2f x"),
                "ROE_Book": st.column_config.NumberColumn("ROE Book", format="%.2f%%"),
                "ROE_Adj": st.column_config.NumberColumn("ROE Adj", format="%.2f%%"),
                "CAGR": st.column_config.NumberColumn("CAGR", format="%.2f%%"),
                "Market_Cap": st.column_config.NumberColumn("Mkt Cap (T)", format="%.2f T"),
                "NPM": st.column_config.NumberColumn("NPM", format="%.2f%%"),
                "BVPS": st.column_config.NumberColumn("BVPS", format="Rp %.0f"),
            }
        )