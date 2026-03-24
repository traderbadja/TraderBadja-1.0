import streamlit as st
import logic
#from logic import load_data 
#from logic import simpan_dan_update

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="TraderBadja Dashboard", layout="wide")


# --- SIDEBAR MENU NAVIGATION ---
st.sidebar.title("🚀 TraderBadja v1.0")
menu = st.sidebar.selectbox(
    "Pilih Menu:",
    ["Dashboard Utama", "Update Database", "Watchlist", "Analisa Sektoral", "Analisa Rank Value", "Analisa Foreign Flow",
    "Analisa Financial History","Screener"]
)



# Load Data sekali saja untuk digunakan di berbagai menu
df = logic.load_data_lengkap() #load data harian
df_financial = logic.load_data_financial() #load data financial

# --- ROUTER (PENGATUR MENU) ---
if menu == "Dashboard Utama":
    st.title("🚀 Selamat Datang di TraderBadja")
    st.markdown("#### *'Winner Never Quit, Quitter Never Win.'*")
    st.divider()

    if not df.empty:
        # Membuat dua kolom (Ratio 1:1)
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Database Transaksi (Harian)")
            st.metric("Total Emiten", len(df['Kode Saham'].unique()))
            st.metric("Total Hari Bursa", len(df['Tanggal Perdagangan Terakhir'].unique()))
            st.metric("Update Terakhir", str(df['Tanggal Perdagangan Terakhir'].max().date()))
            st.info("Status: Terkoneksi (Parquet)")

        with col2:
            st.subheader("🏢 Database Fundamental (Bulanan)")
            # Misalkan Anda memuat df_fundamental dari file lain
            if not df_financial.empty:
                # 1. Hitung variabel bantuan agar kode lebih rapi
                total_emiten = len(df_financial['Ticker'].unique())
                total_periode = len(df_financial['Source_Period'].unique())
                
                # 2. Ambil nilai tunggal untuk periode terbaru
                # Kita ambil max dari Source_Period, lalu ambil nilai Period_Display yang sesuai
                latest_date = df_financial['Source_Period'].max()
                update_terakhir = df_financial[df_financial['Source_Period'] == latest_date]['Period_Display'].iloc[0]

                # 3. Tampilkan dalam kolom agar rapi secara horizontal (opsional)
                #col1, col2, col3 = st.columns(3)
                
                st.metric("Total Emiten Tercover", f"{total_emiten} Saham")
                st.metric("Total Periode Data", f"{total_periode} Bulan")
                st.metric("Update Terakhir", update_terakhir)

    else:
        st.error("Database utama tidak ditemukan. Silakan lakukan inisialisasi.")
        
elif menu == "Update Database":
    st.title("📂 Update Database")
    # Widget Upload
    st.write("Menu Update Database Harian.")
    uploaded_files = st.file_uploader("Pilih file Excel", type=["xlsx"], accept_multiple_files=True, key="uploader_transaksi")

    if uploaded_files:
        if st.button("Proses Data Baru"):
            for uploaded_file in uploaded_files:
                with st.spinner(f"Memproses {uploaded_file.name}..."):
                    success, message = logic.simpan_dan_update(uploaded_file)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            
            # Memberikan instruksi refresh
            st.info("Klik tombol 'Refresh' di menu utama untuk melihat perubahan di grafik.")
    
    st.write("Menu Update Database Financial.")
    uploaded_files2 = st.file_uploader("Pilih file Excel", type=["xlsx"], accept_multiple_files=True, key="uploader_financial")

    if uploaded_files2:
        if st.button("Proses Data Baru"):
            for uploaded_file2 in uploaded_files2:
                with st.spinner(f"Memproses {uploaded_file2.name}..."):
                    success, message = logic.simpan_dan_update_financial(uploaded_file2)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            
            # Memberikan instruksi refresh
            st.info("Klik tombol 'Refresh' di menu utama untuk melihat perubahan di grafik.")
            
elif menu == "Watchlist":
    # Di app.py
    import menu_watchlist # Import file baru
    menu_watchlist.run_watchlist()


elif menu == "Analisa Sektoral":
    import menu_sector
    menu_sector.show_sector_analysis(df)

elif menu == "Analisa Rank Value":
    # Kita panggil kode plotting yang sudah kita buat
    import menu_rank 
    menu_rank.show_rank_analysis(df)

elif menu == "Analisa Foreign Flow":
    st.title("💰 Foreign Flow Analysis")
    st.write("Menu ini khusus untuk mendeteksi akumulasi asing secara mendalam.")
    # Panggil fungsi dari menu_foreign.py
    
elif menu == "Analisa Financial History":
    import menu_fundamental
    st.title("💰 Financial Report Analysis")
    st.write("Menu ini khusus untuk melakukan analisa Fundamental berdasarkan rasio laporan keuangan.")
    menu_fundamental.run_fundamental()
    # Panggil fungsi dari menu_fundamental.py
    
elif menu == "Screener":
    import menu_screener
    st.title("💰 Screener")
    st.write("Menu ini khusus untuk melakukan Screening.")
    menu_screener.run_screener()
    
    

