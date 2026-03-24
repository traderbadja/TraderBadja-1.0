import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd

def show_sector_analysis(df):
    st.title("📂 Analisa Sektoral IDX")
    
    # Pastikan kolom Sector ada (hasil merge dari logic.py)
    if 'Sector' not in df.columns:
        st.error("Kolom 'Sector' tidak ditemukan. Pastikan database Financials sudah ter-merge.")
        return

    # --- KONTROL SIDEBAR ---
    st.sidebar.header("Filter Sektoral")
    days = st.sidebar.slider("Rentang Hari", 5, 30, 20)
    mode = st.sidebar.radio("Tampilkan Berdasarkan:", ["Nilai Transaksi", "Net Foreign Buy"])
    
    column_to_plot = 'Nilai' if mode == "Nilai Transaksi" else 'Foreign Net Buy'

    # Filter rentang tanggal
    tanggal_unik = sorted(df['Tanggal Perdagangan Terakhir'].unique())
    rentang_tanggal = tanggal_unik[-days:]
    df_recent = df[df['Tanggal Perdagangan Terakhir'].isin(rentang_tanggal)]

    # --- BAGIAN BARU: ANALISA MARKET CAP (PIE CHART) ---
    st.divider()
    st.subheader("🍰 Bobot Sektor terhadap IHSG (Market Cap)")

    if 'Market_Cap' in df.columns:
        # Mengambil data terbaru (karena Market Cap Fundamental biasanya snapshot terbaru)
        # Kita asumsikan mengambil data dari tanggal terakhir yang tersedia
        tanggal_terakhir = df['Tanggal Perdagangan Terakhir'].max()
        df_latest = df[df['Tanggal Perdagangan Terakhir'] == tanggal_terakhir]

        # Agregasi Market Cap per Sektor
        # Menggunakan drop_duplicates agar emiten yang muncul tiap hari tidak terhitung ganda
        df_market_cap = df_latest.drop_duplicates(subset=['Kode Saham']).groupby('Sector')['Market_Cap'].sum().sort_values(ascending=False)

        # Menghitung persentase untuk label
        total_market_cap = df_market_cap.sum()
        
        # Membuat Plot
        fig3, ax3 = plt.subplots(figsize=(10, 8))
        
        # Meledakkan (explode) potongan terbesar agar terlihat menonjol
        explode = [0.1 if i == 0 else 0 for i in range(len(df_market_cap))]
        
        # Membuat Pie Chart
        wedges, texts, autotexts = ax3.pie(
            df_market_cap, 
            labels=df_market_cap.index,
            autopct='%1.1f%%',
            startangle=140,
            explode=explode,
            colors=plt.cm.Paired(range(len(df_market_cap))),
            pctdistance=0.85 # Posisi persentase
        )

        # Menambahkan lingkaran di tengah agar menjadi Donut Chart (opsional, lebih modern)
        centre_circle = plt.Circle((0,0), 0.70, fc='white')
        fig3.gca().add_artist(centre_circle)

        ax3.axis('equal')  # Memastikan pie berbentuk lingkaran
        plt.tight_layout()
        
        # Menampilkan di Streamlit dengan kolom agar rapi
        col_pie, col_leg = st.columns([2, 1])
        
        with col_pie:
            st.pyplot(fig3)
        
        with col_leg:
            st.write("**Total Market Cap per Sektor:**")
            # Menampilkan data dalam format Rupiah yang mudah dibaca
            df_display = df_market_cap.reset_index()
            df_display.columns = ['Sektor', 'Total Cap']
            st.dataframe(df_display.style.format({'Total Cap': '{:,.0f}'}))

    else:
        st.warning("Kolom 'Market_Cap' tidak ditemukan. Pastikan database sudah diperbarui dengan data kapitalisasi pasar.")


    # --- FITUR BARU: PILIH SEKTOR UNTUK GRAFIK TREN ---
    semua_sektor = sorted(df_recent['Sector'].unique())
    sektor_dipilih_tren = st.multiselect(
        "Pilih Sektor untuk ditampilkan di grafik tren:",
        options=semua_sektor,
        default=semua_sektor # Default tampilkan 3 sektor pertama agar tidak penuh
    )

    if sektor_dipilih_tren:
        st.subheader(f"Tren {mode} Per Sektor ({days} Hari Terakhir)")
        
        # Agregasi data per tanggal dan sektor
        df_sektor = df_recent[df_recent['Sector'].isin(sektor_dipilih_tren)]
        df_sektor_group = df_sektor.groupby(['Tanggal Perdagangan Terakhir', 'Sector'])[column_to_plot].sum().reset_index()
        
        fig1, ax1 = plt.subplots(figsize=(12, 6))
        
        for sektor in sektor_dipilih_tren:
            data_plot = df_sektor_group[df_sektor_group['Sector'] == sektor]
            ax1.plot(data_plot['Tanggal Perdagangan Terakhir'], 
                     data_plot[column_to_plot], 
                     label=sektor, 
                     marker='o', 
                     markersize=4,
                     linewidth=2)

        ax1.set_ylabel(f"Total {mode}")
        ax1.set_xlabel("Tanggal")
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        # Garis bantu 0 jika modenya Foreign Net Buy
        if mode == "Net Foreign Buy":
            ax1.axhline(0, color='black', linewidth=1, linestyle='-')
            
        plt.xticks(rotation=45)
        st.pyplot(fig1)
    else:
        st.info("Silakan pilih setidaknya satu sektor pada menu di atas untuk menampilkan grafik tren.")

    st.divider()
    
    
    # Selectbox tunggal untuk melihat detail 1 sektor secara mendalam
    sektor_detail = st.selectbox("Pilih 1 Sektor untuk melihat emiten penggeraknya:", semua_sektor)
    
    # --- SEBARAN EMITEN: TOP BUY VS TOP SELL (BAGIAN BAWAH) ---
    st.subheader(f"🔍 Dominasi Emiten di Sektor {sektor_detail} ({days} Hari Terakhir)")
    

    
    if sektor_detail:
        df_emiten_sektor = df_recent[df_recent['Sector'] == sektor_detail]
        
        # Hitung total agregat per emiten
        agregat_emiten = df_emiten_sektor.groupby('Kode Saham')[column_to_plot].sum()

        # Buat dua kolom berdampingan
        col_left, col_right = st.columns(2)

        with col_left:
            st.write(f"🟢 **Top 15 {mode} (Tertinggi)**")
            top_buy = agregat_emiten.sort_values(ascending=False).head(15)
            
            fig_buy, ax_buy = plt.subplots(figsize=(8, 6))
            top_buy.plot(kind='bar', ax=ax_buy, color='tab:green')
            ax_buy.set_ylabel(mode)
            plt.xticks(rotation=45)
            st.pyplot(fig_buy)

        with col_right:
            # Jika mode adalah Net Foreign Buy, tampilkan yang paling negatif (Net Sell)
            # Jika mode adalah Nilai Transaksi, tampilkan yang paling sepi (Bottom 15)
            st.write(f"🔴 **Top 15 {mode.replace('Buy', 'Sell')} (Terendah)**")
            top_sell = agregat_emiten.sort_values(ascending=True).head(15)
            
            fig_sell, ax_sell = plt.subplots(figsize=(8, 6))
            # Gunakan warna merah untuk menunjukkan distribusi/nilai rendah
            top_sell.plot(kind='bar', ax=ax_sell, color='tab:red')
            ax_sell.set_ylabel(mode)
            plt.xticks(rotation=45)
            st.pyplot(fig_sell)

        # Tabel Detail untuk angka presisi
        with st.expander("Lihat Tabel Perbandingan Lengkap"):
            col_t1, col_t2 = st.columns(2)
            col_t1.dataframe(top_buy.rename("Top Accumulation"))
            col_t2.dataframe(top_sell.rename("Top Distribution"))
        # --- ANALISA EMITEN SPESIFIK (BOTTOM SECTION) ---
    st.divider()
    st.subheader("🎯 Analisa Historis per Emiten")



    # Multiselect untuk memilih saham (Default kosong agar user memilih sendiri)
    saham_list = sorted(df_recent[df_recent['Sector'] == sektor_detail]['Kode Saham'].unique())
    saham_dipilih = st.multiselect(
        "Pilih Emiten untuk melihat histori harian:",
        options=saham_list,
        help="Pilih satu atau lebih saham untuk dibandingkan grafiknya"
    )

    if saham_dipilih:
        for kode in saham_dipilih:
            df_emiten = df_recent[df_recent['Kode Saham'] == kode].sort_values('Tanggal Perdagangan Terakhir')
            
          
            st.markdown(f"### 📈 Chart Analysis: {kode}")
            # Membuat 3 Subplots (Atas: Price, Tengah: Value, Bawah: Foreign Flow)
            # Kita gunakan sharex=True agar semua sumbu X (tanggal) sejajar
            fig_ind, (ax_price, ax_val, ax_for) = plt.subplots(3, 1, figsize=(11, 12), sharex=True, 
                                                             gridspec_kw={'height_ratios': [2, 1, 1.5]})
            
            # 1. Grafik Harga Penutupan (Line Chart)
            ax_price.plot(df_emiten['Tanggal Perdagangan Terakhir'], df_emiten['Penutupan'], 
                          color='navy', marker='o', markersize=3, linewidth=2, label='Closing Price')
            ax_price.set_title(f"Price Action - {kode}", fontsize=12, fontweight='bold')
            ax_price.set_ylabel("Price (IDR)")
            ax_price.grid(True, linestyle='--', alpha=0.3)
            ax_price.legend(loc='upper left')
            
            # Menambahkan label harga terakhir di titik terakhir
            last_price = df_emiten['Penutupan'].iloc[-1]
            ax_price.annotate(f'{last_price}', 
                              xy=(df_emiten['Tanggal Perdagangan Terakhir'].iloc[-1], last_price),
                              xytext=(5, 5), textcoords='offset points', fontweight='bold', color='darkred')

            st.markdown(f"**Riwayat Transaksi: {kode}**")
            # 2. Grafik Nilai Transaksi (Bar)
            ax_val.bar(df_emiten['Tanggal Perdagangan Terakhir'], df_emiten['Nilai'], color='skyblue', alpha=0.6)
            ax_val.set_ylabel("Value")
            ax_val.set_title("Transaction Value", fontsize=10)
            ax_val.grid(True, linestyle='--', alpha=0.3)
            
            # 3. Grafik Foreign Flow (Net Buy/Sell)
            colors_f = ['tab:green' if x >= 0 else 'tab:red' for x in df_emiten['Foreign Net Buy']]
            ax_for.bar(df_emiten['Tanggal Perdagangan Terakhir'], df_emiten['Foreign Net Buy'], color=colors_f, alpha=0.8)
            
            # Garis akumulasi (Cumulative Net Foreign) di sumbu Y kedua
            ax_for_cum = ax_for.twinx()
            cum_foreign = df_emiten['Foreign Net Buy'].cumsum()
            ax_for_cum.plot(df_emiten['Tanggal Perdagangan Terakhir'], cum_foreign, color='gold', 
                            label='Cum. Foreign Flow', linewidth=2.5, linestyle='-')
            
            ax_for.set_title("Net Foreign Flow & Accumulation", fontsize=10)
            ax_for.set_ylabel("Daily Net Buy/Sell")
            ax_for_cum.set_ylabel("Total Accumulation")
            ax_for.axhline(0, color='black', linewidth=1)
            ax_for.grid(True, linestyle='--', alpha=0.3)
            
            # Estetika Tanggal
            plt.xticks(rotation=45)
            fig_ind.tight_layout()
            st.pyplot(fig_ind)
            
            # --- Ringkasan Performa ---
            price_change = ((df_emiten['Penutupan'].iloc[-1] - df_emiten['Penutupan'].iloc[0]) / df_emiten['Penutupan'].iloc[0]) * 100
            total_net = df_emiten['Foreign Net Buy'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Price Change", f"{price_change:.2f}%")
            c2.metric("Total Foreign Net", f"{total_net:,.0f}")
            c3.metric("Last Price", f"Rp{last_price:,.0f}")
            
            #st.markdown(f"Summary {days} hari terakhir untuk **{kode}**: Total Foreign Net Flow: :{warna_status}[**{total_net:,.0f}**] ({status})")
            st.divider()

    else:
        st.info("Silakan pilih satu atau lebih kode saham di atas untuk melihat detail pergerakan hariannya.")
        
