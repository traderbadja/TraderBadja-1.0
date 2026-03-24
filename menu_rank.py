import streamlit as st
import matplotlib.pyplot as plt

def show_rank_analysis(df):
    st.title("📈 Analisa Perubahan Rank Value")
    
    # Masukkan slider dan kontrol di sini
    rank_limit = st.sidebar.slider("Limit Rank", 10, 100, 40)
    days_range = st.sidebar.slider("Rentang Hari", 5, 30, 10)
    
    # ... Masukkan semua kode filter & plotting Matplotlib Anda di sini ...
    # Jangan lupa gunakan st.pyplot(fig)
        
        
    # --- LOGIKA SCREENER ---
    if not df.empty:
        tanggal_unik = sorted(df['Tanggal Perdagangan Terakhir'].unique())
        rentang_tanggal = tanggal_unik[-days_range:]
        t_0 = tanggal_unik[-1]
        t_n = tanggal_unik[-days_range]

        # Screener: Baru masuk Top X hari ini dibandingkan n-hari lalu
        top_hari_ini = df['Kode Saham'][(df['Tanggal Perdagangan Terakhir'] == t_0) & 
                                        (df['Rank Value'] <= rank_limit)].tolist()
        
        saham_melejit = df['Kode Saham'][(df['Kode Saham'].isin(top_hari_ini)) & 
                                         (df['Tanggal Perdagangan Terakhir'] == t_n) & 
                                         (df['Rank Value'] > rank_limit)].tolist()

        # --- MAIN INTERFACE ---
        st.title("🚀 TraderBadja: Momentum Tracker")
        
        st.subheader(f"Saham yang baru masuk Top {rank_limit}, yang dalam {days_range} sebelumnya masih dibawah Top ranking tsb")
        
        if saham_melejit:
            # Multi-select untuk memilih saham mana yang mau ditampilkan di grafik
            saham_dipilih = st.multiselect("Pilih saham untuk ditampilkan:", 
                                            options=saham_melejit, 
                                            default=saham_melejit) # Default tampilkan 5 pertama

            # --- PROSES PLOTTING ---
            fig, ax = plt.subplots(figsize=(12, 6))
            
            for kode in saham_dipilih:
                data_saham = df[(df['Kode Saham'] == kode) & 
                                (df['Tanggal Perdagangan Terakhir'].isin(rentang_tanggal))]
                data_saham = data_saham.sort_values('Tanggal Perdagangan Terakhir')
                
                ax.plot(data_saham['Tanggal Perdagangan Terakhir'], 
                        data_saham['Rank Value'], 
                        marker='o', label=kode, linewidth=2)

            ax.invert_yaxis()
            ax.set_ylabel("Ranking (Posisi ke-)")
            ax.grid(True, linestyle='--', alpha=0.6)
            plt.xticks(rotation=45)
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            
            # Tampilkan grafik di Streamlit
            st.pyplot(fig)
            
            # Tampilkan data mentah dalam tabel jika diinginkan
        if st.checkbox("Lihat Data Tabel"):
            st.write(df[df['Kode Saham'].isin(saham_dipilih)].sort_values('Tanggal Perdagangan Terakhir', ascending=False))
            
            
            # --- PANEL ANALISIS TAMBAHAN ---
        if st.checkbox("Tampilkan Detail Analisis (Foreign, Price, Value, Volume)"):
            # Multi-select untuk memilih saham mana yang mau ditampilkan di grafik
            saham_dipilih = st.multiselect("Pilih saham untuk ditampilkan:", 
                                            options=saham_melejit) 
                                            #default=saham_melejit[:5]) # Default tampilkan 5 pertama
            st.divider()
            for kode in saham_dipilih:
                # Ambil data terbaru sesuai rentang hari di sidebar
                df_detail = df[df['Kode Saham'] == kode].sort_values('Tanggal Perdagangan Terakhir').tail(days_range)
                
                # Ambil return hari terakhir untuk pewarnaan judul
                return_terakhir = df_detail['Daily Return (%)'].iloc[-1]
                warna_judul = ":green" if return_terakhir > 0 else ":red"
                st.markdown(f"### {warna_judul}[Analisis Mendalam: {kode} ({return_terakhir:.2f}%)]")

                # Membuat 4 Panel Grafik (Subplots)
                # Kita tambah baris menjadi 4
                fig_extra, (ax_foreign, ax_price, ax_value, ax_volume) = plt.subplots(4, 1, figsize=(10, 14), sharex=True)

                # 1. Grafik Foreign Net Buy (Bar Chart)
                colors_f = ['tab:green' if x >= 0 else 'tab:red' for x in df_detail['Foreign Net Buy']]
                ax_foreign.bar(df_detail['Tanggal Perdagangan Terakhir'], df_detail['Foreign Net Buy'], color=colors_f, alpha=0.8)
                ax_foreign.set_title("Foreign Net Buy/Sell (Akumulasi Asing)")
                ax_foreign.axhline(0, color='black', linewidth=0.8)
                ax_foreign.grid(True, linestyle='--', alpha=0.3)

                # 2. Grafik Daily Change (%) - BARU
                colors_p = ['tab:green' if x >= 0 else 'tab:red' for x in df_detail['Daily Return (%)']]
                ax_price.bar(df_detail['Tanggal Perdagangan Terakhir'], df_detail['Daily Return (%)'], color=colors_p, alpha=0.7)
                ax_price.set_title("Daily Change (%) - Price Action")
                ax_price.axhline(0, color='black', linewidth=0.8)
                # Tambahkan Moving Average 5 hari untuk Return agar tren harga terlihat
                ma5_ret = df_detail['Daily Return (%)'].rolling(window=5).mean()
                ax_price.plot(df_detail['Tanggal Perdagangan Terakhir'], ma5_ret, color='blue', label='MA-5 Return', linewidth=1.5)
                ax_price.grid(True, linestyle='--', alpha=0.3)

                # 3. Grafik Nilai Transaksi (Area Chart)
                ax_value.fill_between(df_detail['Tanggal Perdagangan Terakhir'], df_detail['Nilai'], color='skyblue', alpha=0.4)
                ax_value.plot(df_detail['Tanggal Perdagangan Terakhir'], df_detail['Nilai'], color='dodgerblue', marker='.', markersize=8)
                ax_value.set_title("Nilai Transaksi (Value)")
                ax_value.grid(True, linestyle='--', alpha=0.3)

                # 4. Grafik Volume (Bar Chart)
                ax_volume.bar(df_detail['Tanggal Perdagangan Terakhir'], df_detail['Volume'], color='gray', alpha=0.7)
                ax_volume.set_title("Volume Perdagangan (Lembar Saham)")
                ax_volume.grid(True, linestyle='--', alpha=0.3)

                # Format estetika tanggal
                plt.xticks(rotation=45)
                fig_extra.tight_layout()
                
                # Tampilkan ke Streamlit
                st.pyplot(fig_extra)
                st.divider()
            else:
                st.warning("Tidak ada saham yang memenuhi kriteria filter saat ini.")
                
        if st.checkbox("Lihat Grafik Rank Value Keseluruhan"):
            saham_dipilih = st.multiselect("Pilih saham untuk ditampilkan:", 
                                            options=saham_melejit) 
                                            #default=saham_melejit[:5]) # Default tampilkan 5 pertama
            # --- PROSES PLOTTING ---
            fig, ax = plt.subplots(figsize=(12, 6))
            
            for kode in saham_dipilih:
                data_saham = df[(df['Kode Saham'] == kode) ]
                data_saham = data_saham.sort_values('Tanggal Perdagangan Terakhir')
                
                ax.plot(data_saham['Tanggal Perdagangan Terakhir'], 
                        data_saham['Rank Value'], 
                        marker='o', label=kode, linewidth=2)

            ax.invert_yaxis()
            ax.set_ylabel("Ranking (Posisi ke-)")
            ax.grid(True, linestyle='--', alpha=0.6)
            plt.xticks(rotation=45)
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            
            # Tampilkan grafik di Streamlit
            st.pyplot(fig)
            
            #st.write(df[df['Kode Saham'].isin(saham_dipilih)].sort_values('Tanggal Perdagangan Terakhir', ascending=False))
    else:
        st.error("Database tidak ditemukan. Pastikan file Parquet ada di folder yang sama.")