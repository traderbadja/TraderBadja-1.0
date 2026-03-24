import pandas as pd
import streamlit as st
import os
import menu_fundamental

def run_screener():
    st.title("🔍 Stock Screener & Valuation Filter")
    st.markdown("""
    Gunakan menu ini untuk memfilter saham berdasarkan **Sektor**, **Margin of Safety (MOS)**, dan perbandingan antara **ROE Adjusted** vs **ROE Book**.
    """)

    # 1. Fungsi Internal untuk Load Data
    def load_data(path):
        if os.path.exists(path):
            try:
                return pd.read_parquet(path)
            except Exception as e:
                st.error(f"Error loading {path}: {e}")
                return None
        return None

    # Load Database Utama
    df_all_fund = load_data('Master_Database_Financials.parquet')
    path_transaksi = "Master_Database_Transaksi_IDX.parquet"
    
    # 2. Database Management
    with st.expander("⚙️ Database Management"):
        st.info("Klik tombol di bawah jika data fundamental atau harga harian baru saja di-update.")
        if st.button("🚀 Re-Generate Screener Database"):
            if df_all_fund is not None:
                with st.spinner("Memproses seluruh emiten... mohon tunggu."):
                    # Pastikan fungsi ini di menu_fundamental sudah return kolom 'Sector'
                    df_final = menu_fundamental.generate_screener_database(df_all_fund, path_transaksi)
                    df_final.to_parquet("Screener_Master.parquet")
                    st.success("Screener Database Berhasil Diperbarui!")
                    st.rerun() 
            else:
                st.error("Master Database Financials tidak ditemukan!")

    st.divider()

    # 3. Load & Filter Database Screener
    df_screen = load_data("Screener_Master.parquet")

    if df_screen is not None and not df_screen.empty:
        # --- UI FILTER SIDEBAR ---
        st.sidebar.header("🎯 Filter Criteria")
        working_df = df_screen.copy()

        # 1. Filter Sektor
        if 'Sector' in working_df.columns:
            list_sektor = sorted(working_df['Sector'].unique().tolist())
            selected_sectors = st.sidebar.multiselect(
                "Pilih Sektor", 
                options=list_sektor, 
                default=list_sektor,
                key="filter_sector_multiselect" # ID Unik
            )
            if selected_sectors:
                working_df = working_df[working_df['Sector'].isin(selected_sectors)]

        # 2. Filter Category
        if 'Category' in working_df.columns:
            all_categories = sorted(working_df['Category'].unique())
            selected_cat = st.sidebar.multiselect(
                "Stock Category", 
                all_categories,
                key="filter_category_multiselect" # ID Unik
            )
            if selected_cat:
                working_df = working_df[working_df['Category'].isin(selected_cat)]

        # 3. Filter PBV Ratio
        if 'PBV' in working_df.columns:
            # Menggunakan unique key agar tidak bentrok dengan slider MOS
            pbv_range = st.sidebar.slider(
                "Range P/BV Ratio", 
                0.0, 15.0, (0.0, 2.0), 
                step=0.1,
                key="filter_pbv_slider" # ID Unik
            )
            working_df = working_df[(working_df['PBV'] >= pbv_range[0]) & (working_df['PBV'] <= pbv_range[1])]

        # 4. Filter Undervalued Checkbox
        undervalued_only = st.sidebar.checkbox(
            "Show Only ROE Adj > ROE Book", 
            key="filter_undervalued_check" # ID Unik
        )
        if undervalued_only:
            working_df = working_df[working_df['ROE_Adj'] > working_df['ROE_Book']]
            
        # 5. Filter Margin of Safety (MOS)
        if 'MOS_%' in working_df.columns:
            min_mos = st.sidebar.slider(
                "Minimum MOS (%)", 
                -100, 100, 30,
                key="filter_mos_slider" # ID Unik
            )
            working_df = working_df[working_df['MOS_%'] >= min_mos]
            
        # --- TAMPILKAN HASIL ---
        col_count, col_info = st.columns([1, 3])
        col_count.metric("Stocks Found", len(working_df))

        # --- TAMPILKAN HASIL ---
        st.dataframe(
            working_df, 
            column_config={
                "Ticker": st.column_config.TextColumn("Kode"),
                "Sector": st.column_config.TextColumn("Sektor"),
                "Category": st.column_config.TextColumn("Kategori"),
                "CAGR": st.column_config.NumberColumn("CAGR (%)", format="%.2f%%"),
                "ROE_Book": st.column_config.NumberColumn("ROE Book", format="%.2f%%"),
                "ROE_Adj": st.column_config.ProgressColumn(
                    "ROE Adjusted", 
                    format="%.2f%%", 
                    min_value=0, 
                    max_value=50
                ),
                "MOS_%": st.column_config.NumberColumn(
                    "Margin of Safety", 
                    format="%.2f%%"
                ),
                "PBV": st.column_config.NumberColumn("P/BV Ratio", format="%.2f x"), # Konfigurasi kolom PBV
                "Price": st.column_config.NumberColumn("Last Price", format="Rp %d"),
                "BVPS_Current": st.column_config.NumberColumn("BVPS", format="Rp %.0f"),
                # ... kolom lainnya
            }, 
            hide_index=True,
            width='stretch'
        )
        
        # Konfigurasi Tampilan Tabel (Update use_container_width -> width='stretch')


        # Download Button
        csv = working_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Screener Result (CSV)",
            data=csv,
            file_name="traderbadja_screener_result.csv",
            mime="text/csv",
        )

    else:
        st.warning("⚠️ Database screener belum tersedia atau kosong.")
        st.info("Silakan buka expander 'Database Management' di atas dan klik 'Re-Generate'.")