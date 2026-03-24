import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- FUNGSI 1: TTM CALCULATOR (PENTING!) ---
def calculate_ttm_data(df_history):
    if df_history.empty:
        return pd.DataFrame()
    
    df_ttm = df_history.copy()
    
    # PERBAIKAN: Pastikan FS_Date adalah datetime agar tidak error .strftime
    if not pd.api.types.is_datetime64_any_dtype(df_ttm['FS_Date']):
        df_ttm['FS_Date'] = pd.to_datetime(df_ttm['FS_Date'])
    
    df_ttm = df_ttm.sort_values('FS_Date')
    
    # Kolom yang dihitung TTM (Sesuaikan dengan nama kolom di parquet Anda)
    target_cols = ['Profit_for_Period', 
                    'Profit_Attributable_Owner',
                    'Sales_IDR_bn',
                    'EBT_IDR_bn']
    
    for col in target_cols:
        if col in df_ttm.columns:
            # Mengambil jumlah 4 kuartal terakhir
            df_ttm[col] = df_ttm[col].rolling(window=4).sum()
            
#### Pastikan kolom Equity tersedia
            if 'Equity_IDR_bn' in df_ttm.columns:
                # 1. ROE Standar TTM = (Laba Bersih TTM / Ekuitas Terakhir) * 100
                # Kita gunakan ekuitas pada periode laporan terakhir untuk pembagi
                df_ttm['ROE_TTM'] = (df_ttm['Profit_Attributable_Owner'] / df_ttm['Equity_IDR_bn']) * 100
                 
                # 2. ROE Adjusted TTM (Menggunakan Market Cap)
                # market_cap_harian didapat dari data harga saham terbaru
                if 'market_cap_harian' in locals() or 'market_cap_harian' in globals():
                    df_ttm['ROE_Adj_TTM'] = (df_ttm['Profit_Attributable_Owner'] / market_cap_harian) * 100    
    
    # Hapus baris yang kosong (data < 4 kuartal)
    df_ttm = df_ttm.dropna(subset=['Profit_Attributable_Owner'])
    
    return df_ttm
    
def calculate_company_metrics(df_history, df_to_analyze, target_ticker, path_transaksi="Master_Database_Transaksi_IDX.parquet"):
    """
    df_history: Data mentah untuk hitung CAGR (butuh data lama).
    df_to_analyze: Data yang sudah difilter (bisa df_ttm atau df_december) untuk ROE.
    """
    results = {
        "growth_text": "N/A", 
        "category_label": "-", 
        "category_color": "gray",
        "roe_color": "gray", 
        "display_label": "N/A", 
        "roe_end": 0,
        "roe_end_adjusted": 0, 
        "calc_roe_adj": 0, # Nilai float murni untuk kalkulasi MOS
        "market_cap": 0,
        "last_price": 0,   # Ditambahkan untuk perhitungan MOS
        "shares": 0        # Ditambahkan untuk perhitungan BVPS
    }

    if df_to_analyze.empty:
        return results

    # 1. Ambil data terakhir dari dataframe yang sedang dianalisis
    last_record = df_to_analyze.iloc[-1]
    val_end = last_record['Profit_Attributable_Owner']
    results["roe_end"] = last_record.get('ROE_pct', 0)
    results["display_label"] = last_record['FS_Date'].strftime('%d/%m/%Y')

    # 2. Ambil Data Pasar & Hitung ROE Adjusted
    try:
        import os
        if os.path.exists(path_transaksi):
            df_harian = pd.read_parquet(path_transaksi)
            ticker_data_all = df_harian[df_harian['Kode Saham'] == target_ticker]
            
            if not ticker_data_all.empty:
                # Urutkan berdasarkan tanggal terbaru
                ticker_data = ticker_data_all.sort_values('Tanggal Perdagangan Terakhir').iloc[-1]
                
                # Simpan ke results agar bisa dipanggil di run_fundamental
                results["last_price"] = ticker_data['Penutupan']
                results["shares"] = ticker_data['Listed Shares']
                
                mkt_cap = (results["last_price"] * results["shares"]) / 1e9
                results["market_cap"] = mkt_cap
                
                if mkt_cap > 0:
                    results["calc_roe_adj"] = (val_end / mkt_cap) * 100
                    results["roe_end_adjusted"] = results["calc_roe_adj"]
                    # Warna HIJAU jika ROE Adj > ROE Book (Indikasi Undervalued)
                    results["roe_color"] = "green" if results["calc_roe_adj"] > results["roe_end"] else "red"
    except Exception as e:
        print(f"Error pada perhitungan harian: {e}")

# 3. Hitung CAGR (Selalu pakai data tahunan dari df_history)
    df_dec = df_history[df_history['FS_Date'].dt.month == 12].sort_values('FS_Date')
    if len(df_dec) >= 2:
        v_start = df_dec.iloc[0]['Profit_Attributable_Owner']
        v_end = df_dec.iloc[-1]['Profit_Attributable_Owner']
        n = df_dec.iloc[-1]['FS_Date'].year - df_dec.iloc[0]['FS_Date'].year
            
        if n > 0 and v_start > 0:
            cagr = (pow((v_end / v_start), (1/n)) - 1)
            results["growth_text"] = f"{cagr * 100:.2f}%"
                
                # Penentuan Kategori Peter Lynch
            if cagr > 0.15: 
                results["category_label"], results["category_color"] = "UPSTARTS", "green"
            elif cagr >= 0.05: 
                results["category_label"], results["category_color"] = "STALWARTS", "blue"
            elif cagr >= 0.01: 
                results["category_label"], results["category_color"] = "SLUGGARDS", "orange"
            else: 
                results["category_label"], results["category_color"] = "CYCLICAL", "red"
        else:
            results["growth_text"] = "Data Tidak Konsisten"

    return results

def calculate_valuation_metrics(df_active, metrics):
    """
    Fungsi sentral untuk menghitung BVPS, Proyeksi, dan MOS.
    Dapat dipanggil oleh run_fundamental() maupun generate_screener_database().
    """
    valuation = {
        "current_bvps": 0,
        "projected_bvps_5y": 0,
        "mos_val": 0,
        "roe_used": 0
    }
    
    try:
        total_shares = metrics.get('shares', 0)
        current_price = metrics.get('last_price', 0)
        # Kita gunakan ROE Book sebagai standar proyeksi sesuai diskusi sebelumnya
        roe_book_val = metrics.get('roe_end', 0) 
        
        if total_shares > 0 and not df_active.empty:
            latest_fund = df_active.iloc[-1]
            equity_val = float(latest_fund.get('Equity_IDR_bn', 0))
            
            # 1. Hitung BVPS
            current_bvps = (equity_val * 1_000_000_000) / total_shares
            
            # 2. Proyeksi BVPS 5 Tahun (Safe Power Check)
            roe_ttm_decimal = roe_book_val / 100
            base = 1 + roe_ttm_decimal
            
            if base > 0:
                projected_bvps_5y = current_bvps * (base ** 5)
            else:
                projected_bvps_5y = 0
            
            # 3. Hitung MOS
            if projected_bvps_5y > 0:
                mos_val = (1 - (current_price / projected_bvps_5y)) * 100
            else:
                mos_val = -100 # Risiko maksimal
                
            valuation.update({
                "current_bvps": current_bvps,
                "projected_bvps_5y": projected_bvps_5y,
                "mos_val": mos_val,
                "roe_used": roe_book_val
            })
            
    except Exception as e:
        print(f"Error in valuation logic: {e}")
        
    return valuation

# --- FUNGSI 3: SCREENER GENERATOR ---
def generate_screener_database(df_all_fundamental, path_transaksi):
    screener_data = []
    
    # 1. Pastikan Datetime di awal dan gunakan .copy()
    df_main = df_all_fundamental.copy()
    df_main['FS_Date'] = pd.to_datetime(df_main['FS_Date'])
    
    col_ticker = 'Ticker' if 'Ticker' in df_main.columns else 'Code'
    all_tickers = df_main[col_ticker].unique()
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(all_tickers):
        try:
            status_text.text(f"Processing: {ticker}")
            
            # Inisialisasi awal variabel agar tidak NameError
            cagr_val = 0.0 
            
            # Ambil history per ticker
            df_history = df_main[df_main[col_ticker] == ticker].sort_values('FS_Date').copy()
            
            if df_history.empty:
                continue

            # Ambil informasi Sektor dari baris terakhir data ticker tersebut
            sektor_emiten = df_history.iloc[-1].get('Sector', '-')

            # 2. Hitung TTM
            try:
                df_ttm = calculate_ttm_data(df_history)
                df_active = df_ttm if (df_ttm is not None and not df_ttm.empty) else df_history
            except:
                df_active = df_history

            # 3. Hitung Metrics Dasar
            metrics = calculate_company_metrics(df_history, df_active, ticker, path_transaksi)
            
            # AMBIL NILAI CAGR DARI METRICS
            growth_raw = metrics.get('growth_text', '0')
            try:
                if isinstance(growth_raw, str) and '%' in growth_raw:
                    cagr_val = float(growth_raw.replace('%', ''))
                else:
                    cagr_val = float(growth_raw) if growth_raw != "N/A" else 0.0
            except:
                cagr_val = 0.0

            # 4. PANGGIL FUNGSI VALUASI SENTRAL
            # Pastikan Anda sudah menambahkan fungsi calculate_valuation_metrics di menu_fundamental.py
            val_results = calculate_valuation_metrics(df_active, metrics)
            
            # 5. SIMPAN DATA (Ditambahkan kolom Sektor)
            current_price = metrics.get('last_price', 0)
            current_bvps = val_results.get("current_bvps", 0)
            
            # Hitung PBV Ratio
            pbv_ratio = current_price / current_bvps if current_bvps > 0 else 0
            
            screener_data.append({
                "Ticker": ticker,
                "Sector": sektor_emiten,
                "Category": metrics.get('category_label', '-'),
                "CAGR": cagr_val, 
                "ROE_Book": metrics.get('roe_end', 0),
                "ROE_Adj": metrics.get('calc_roe_adj', 0),
                "MOS_%": val_results.get("mos_val", 0),
                "Price": current_price,
                "BVPS_Current": current_bvps,
                "PBV": pbv_ratio  # <--- Pastikan kolom ini ada
            })
            
        except Exception as e:
            print(f"Gagal total pada {ticker}: {e}")
            continue
        
        finally:
            progress_bar.progress((i + 1) / len(all_tickers))

    status_text.empty()
    return pd.DataFrame(screener_data)

# --- FUNGSI BARU: DASHBOARD PROFITABILITY (Sales, EBIT, Profit) ---
# Tambahkan view_option seperti diskusi sebelumnya -----------------vvvvvvvvvvv
def draw_profitability_dashboard(df_plot, target_ticker, mode, view_option):
    # Buat Subplots: 1 Baris, 4 Kolom
    fig = make_subplots(
        rows=1, cols=4, 
        subplot_titles=("Revenue/Sales (bn IDR)", "EBIT (bn IDR)", "Net Profit (bn IDR)", "Profit to Owner (bn IDR)"),
        shared_xaxes=True
    )

    # Konfigurasi data (Metrik, Kolom, Warna Utama, Warna Garis)
    metrics = [
        ('Sales_IDR_bn', '#FFA15A', '#FF7F00', 'Sales'),
        ('EBT_IDR_bn', '#B6E880', '#56C02B', 'EBT'),
        ('Profit_for_Period', '#00CC96', '#009973', 'Net Profit'),
        ('Profit_Attributable_Owner', '#636EFA', '#4F57C1', 'Owner Profit')
    ]
    
    ### 1. Tentukan Nilai Maksimum Berdasarkan SALES (ditambah margin 10% agar tidak mentok)
    max_sales = df_plot['Sales_IDR_bn'].max() * 1.1 
    # Tambahkan batas bawah 0 atau nilai minimum jika ada laba negatif
    min_val = min(0, df_plot[['Sales_IDR_bn', 'EBT_IDR_bn', 'Profit_for_Period']].min().min()) * 1.1
    
    # PROSES PEMBUATAN GRAFIK AREA SEPERTI REFERENSI
    for i, (col, fill_color, line_color, label) in enumerate(metrics, 1):
        if col in df_plot.columns:
            
            # --- TAMPILAN AREA SEPERTI REFERENSI ---
            fig.add_trace(go.Scatter(
                x=df_plot['FS_Date_Str'], 
                y=df_plot[col],
                mode='lines+markers', # Garis dan titik di atas area
                name=label,
                # Efek referensi: Area warna (fill) di bawah garis
                line=dict(color=line_color, width=2.5), 
                fill='tozeroy', 
                fillcolor=fill_color, # Warna area (opacity bisa diatur)
                # Opsi: Atur opacity area agar transparan (misal 50%)
                opacity=0.5, 
                marker=dict(size=6, color=line_color),
                showlegend=False # Legend diatur nanti secara manual
            ), row=1, col=i)
            
            # --- [TAMBAHAN] TAMBAHKAN GARIS PROFIT MARGIN (%) ---
            # Jika mode TTM, margin akan lebih mulus
            if 'Sales_IDR_bn' in df_plot.columns and col != 'Sales_IDR_bn':
                df_plot[f'{col}_Margin'] = (df_plot[col] / df_plot['Sales_IDR_bn']) * 100
                margin_col = f'{col}_Margin'
                
                # Tambahkan garis putus-putus untuk Margin di atas area
                fig.add_trace(go.Scatter(
                    x=df_plot['FS_Date_Str'], 
                    y=df_plot[margin_col],
                    mode='lines',
                    name=f'{label} Margin (%)',
                    line=dict(color='black', width=1, dash='dot'), # Garis hitam putus-putus
                    showlegend=False,
                    # Atur tooltip agar menunjukkan %
                    hovertemplate=f'Margin: %{{y:.2f}}%<extra></extra>', 
                    # Jika ingin sumbu Y kedua, bisa tambahkan logic di sini, 
                    # tapi untuk kesederhanaan, biarkan margin menumpang di sumbu Y yang sama
                ), row=1, col=i)

    # 2. LOCK AXIS: Terapkan range yang sama ke semua subplot Y
    fig.update_yaxes(range=[min_val, max_sales])
    
    # PENGATURAN LAYOUT AKHIR
    fig.update_layout(
        title_text=f"Profitability Analysis: {target_ticker} ({view_option})",
        template="plotly_white",
        height=500, # Tinggi sedikit dinaikkan agar rapi
        showlegend=False,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=80, b=20)
    )
    
    # Pengaturan tooltip agar lebih bersih seperti referensi
    fig.update_traces(hovertemplate='%{y:.2f}')
    
    return fig

# --- FUNGSI BARU: DASHBOARD BALANCE SHEET (Asset, Liability, Equity) ---
def draw_balance_sheet_dashboard(df_plot, target_ticker):
    fig = make_subplots(
        rows=1, cols=3, 
        subplot_titles=("Total Assets", "Total Liabilities", "Total Equity"),
        shared_xaxes=True
    )

    # 1. Tentukan Nilai Maksimum Berdasarkan ASSETS
    max_assets = df_plot['Assets_IDR_bn'].max() * 1.1

    metrics = [
        ('Assets_IDR_bn', '#EF553B', 'Assets'),
        ('Liabilities_IDR_bn', '#FECB52', 'Liabilities'),
        ('Equity_IDR_bn', '#AB63FA', 'Equity')
    ]

    for i, (col, color, label) in enumerate(metrics, 1):
        if col in df_plot.columns:
            fig.add_trace(
                go.Bar(x=df_plot['FS_Date_Str'], y=df_plot[col], marker_color=color),
                row=1, col=i
            )

    # 2. LOCK AXIS: Semua kolom Balance Sheet punya tinggi maksimal yang sama (Assets)
    fig.update_yaxes(range=[0, max_assets])

    fig.update_layout(
        title_text=f"Balance Sheet Scale (Relative to Assets): {target_ticker}",
        template="plotly_white", height=400, showlegend=False
    )
    return fig



def run_fundamental():
    st.title("📊 Fundamental Analysis Dashboard")
    
    @st.cache_data
    def load_data():
        try:
            df = pd.read_parquet('Master_Database_Financials.parquet')
            #if 'Source_Period' in df.columns:
             #   df['Source_Period'] = pd.to_datetime(df['Source_Period'])
            return df
        except FileNotFoundError:
            return None

    df_raw = load_data()
    if df_raw is None:
        st.error("Database tidak ditemukan.")
        return

    # --- STRATEGI PEMBERSIHAN DATA JANGGAL ---
    # Pastikan FS_Date adalah datetime untuk filter bulan
    df_raw['FS_Date'] = pd.to_datetime(df_raw['FS_Date'], errors='coerce')
    
    # Hapus baris yang bulannya bukan 3, 6, 9, atau 12 (Standar IDX)
    # Ini akan otomatis membuang data bulan 10 yang Anda maksud
    valid_months = [3, 6, 9, 12]
    df_raw = df_raw[df_raw['FS_Date'].dt.month.isin(valid_months)]
    
    # Opsional: Buang juga data yang FS_Date-nya NaT (Not a Time)
    df_raw = df_raw.dropna(subset=['FS_Date'])
    
    # --- 1. PROSES FILTER HANYA SOURCE PERIOD TERAKHIR ---
    latest_period = df_raw['Source_Period'].max()
    latest_display = df_raw[df_raw['Source_Period'] == latest_period]['Period_Display'].iloc[0]
    
    # Data khusus untuk screening (hanya yang terbaru)
    df_latest = df_raw[df_raw['Source_Period'] == latest_period].copy()

    st.sidebar.header("Screening (Periode Terbaru)")
    st.sidebar.info(f"Data Berdasarkan Update: {latest_display}")

    # Filter Sektor & PBV pada data terbaru
    sectors = sorted(df_latest['Sector'].unique().tolist())
    selected_sector = st.sidebar.selectbox("Pilih Sektor", ["All"] + sectors)
    
    pbv_min = st.sidebar.number_input("Min PBV", value=0.0, step=0.1, format="%.2f")
    pbv_max = st.sidebar.number_input("Max PBV", value=1.5, step=0.1, format="%.2f")

    # Eksekusi Filter Screening
    df_screen = df_latest.copy()
    if selected_sector != "All":
        df_screen = df_screen[df_screen['Sector'] == selected_sector]
    
    df_screen = df_screen[(df_screen['PBV'] >= pbv_min) & (df_screen['PBV'] <= pbv_max)]

    # Tampilkan Tabel Screening
    st.subheader(f"Screening Result: {selected_sector} (PBV {pbv_min}-{pbv_max})")
    if not df_screen.empty:
        display_cols = ['Ticker', 'Stock_Name', 'Equity_IDR_bn','PBV', 'PER', 'ROE_pct', 'DER', 'FS_Date']
        st.dataframe(df_screen[display_cols].sort_values('PBV'), use_container_width=True, hide_index=True)
    else:
        st.warning("Tidak ada saham yang cocok dengan kriteria screening.")

    st.divider()

    # --- 2. GRAFIK HISTORICAL TREND (Seluruh Periode) ---
    st.subheader("📈 Historical Fundamental Trend")
    st.write("Lihat bagaimana performa fundamental saham pilihan Anda dari waktu ke waktu.")

    col1, col2 = st.columns(2)
    with col1:
        # Pilih Saham (Ticker diambil dari seluruh database agar bisa pilih yang tidak lolos filter screening)
        target_ticker = st.selectbox("Pilih Ticker Saham", sorted(df_raw['Ticker'].unique()))
    
    with col2:
        # Pilih Metrik yang ingin ditampilkan di grafik
        metrics_options = {
            
            'PBV': 'Price to BV (x)',
            'PER': 'P/E Ratio (x)',
            'ROA_pct':'Return on Equity',
            'Profit_for_Period': 'Total Profit (bn)',
            'Profit_Attributable_Owner': 'Profit for Owner (bn)',
            'Equity_IDR_bn': 'Equity (bn)',
            'Assets_IDR_bn': 'Total Assets (bn)'
        }
        selected_metric = st.selectbox("Pilih Metrik Grafik", options=list(metrics_options.keys()), 
                                       format_func=lambda x: metrics_options[x])

    # Ambil seluruh sejarah data untuk ticker terpilih
    df_history = df_raw[df_raw['Ticker'] == target_ticker].sort_values('Source_Period')

    #st.dataframe(df_history[['FS_Date', 'Source_Period', 'PBV']], use_container_width=True)
    
    if not df_history.empty:
        fig_hist = go.Figure()
        
        # Tambahkan garis tren
        fig_hist.add_trace(go.Scatter(
            x=df_history['Source_Period'], 
            y=df_history[selected_metric],
            mode='lines+markers',
            name=target_ticker,
            line=dict(color='#00CC96', width=3),
            marker=dict(size=8)
        ))

        fig_hist.update_layout(
            title=f"Tren {metrics_options[selected_metric]} - {target_ticker}",
            xaxis_title="Periode Update IDX",
            yaxis_title=metrics_options[selected_metric],
            hovermode="x unified",
            template="plotly_white"
        )
        
        st.plotly_chart(fig_hist, use_container_width=True)
        
        # Opsional: Tampilkan tabel perbandingan singkat di bawah grafik
        with st.expander("Lihat Detail Data Historis"):
            st.table(df_history[['Period_Display', 'FS_Date', selected_metric]].tail(6))
        
        
        # --- PROSES DATA HISTORIS UNTUK GRAFIK ---
        
        
        
        """
        # Tambahkan opsi filter di atas grafik
        view_option = st.radio(
            "Tampilkan Data Berdasarkan:",
            ["Semua Laporan (Quarterly)", "Hanya Akhir Tahun (Desember)"],
            horizontal=True
        )  
        """
        # Filter data berdasarkan ticker yang dipilih
        df_history = df_raw[df_raw['Ticker'] == target_ticker].copy()
        
        # Hapus data yang FS_Date nya kosong agar grafik tidak error
        df_history = df_history.dropna(subset=['FS_Date'])
        
        # Pastikan konversi ke datetime berhasil
        df_history['FS_Date'] = pd.to_datetime(df_history['FS_Date'], errors='coerce')

        # Urutkan dataframe berdasarkan tanggal aslinya
        df_history = df_history.sort_values('FS_Date')
        
        # Kelompokkan berdasarkan FS_Date agar jika ada 2 source period untuk 1 FS Date tidak double
        # Kita ambil data terakhir yang dilaporkan untuk setiap FS_Date
        df_history = df_history.sort_values('Source_Period').drop_duplicates('FS_Date', keep='last')
        df_history = df_history.sort_values('FS_Date')
        



        # Format FS_Date untuk tampilan sumbu X yang lebih cantik (Tgl-Bln-Thn)
        try:
            df_history['FS_Date_Str'] = df_history['FS_Date'].dt.strftime('%d/%m/%Y')
        except AttributeError:
            # Fallback jika masih gagal, konversi paksa ke string
            df_history['FS_Date_Str'] = df_history['FS_Date'].astype(str)

        st.subheader(f"📈 Analisa Fundamental: {target_ticker}")
        st.info("Sumbu X menggunakan **FS_Date** (Tanggal Laporan Keuangan).")




# --- LOGIKA PERHITUNGAN GROWTH (CAGR) ---
        df_december = df_history[df_history['FS_Date'].dt.month == 12].sort_values('FS_Date')

        # 1. Inisialisasi semua variabel dengan nilai default
        growth_text = "N/A"
        category_label = "-"
        category_color = "gray"
        roe_color = "gray"
        display_year = "Data Tidak Cukup"
        roe_end = "N/A"
        roe_end_adjusted = "N/A"

        if len(df_december) >= 2:
            # 2. Ambil data fundamental dulu
            first_dec = df_december.iloc[0]
            last_dec = df_december.iloc[-1].copy() # Gunakan .copy() agar aman
            
            val_start = first_dec['Profit_Attributable_Owner']
            val_end = last_dec['Profit_Attributable_Owner']
            roe_end = f"{last_dec['ROE_pct']:.2f}"
            display_year = last_dec['FS_Date'].year
            
            # 3. Baru ambil data harga harian
            try:
                df_harian = pd.read_parquet("Master_Database_Transaksi_IDX.parquet")
                # Filter ticker dan ambil yang paling terbaru (Tanggal terakhir)
                ticker_harian = df_harian[df_harian['Kode Saham'] == target_ticker].sort_values('Tanggal Perdagangan Terakhir')
                
                if not ticker_harian.empty:
                    data_harian_ticker = ticker_harian.iloc[-1]
                    
                    last_price = data_harian_ticker['Penutupan']
                    tradable_shares = data_harian_ticker['Listed Shares']
                    market_cap_harian = last_price * tradable_shares / 1000000000 #dalam milliar rp
                    
                    # Rumus: (Profit / Market Cap) * 100
                    if market_cap_harian > 0:
                        calc_roe_adj = (val_end / market_cap_harian) * 100
                        roe_end_adjusted = f"{calc_roe_adj:.2f}"
                        if calc_roe_adj > last_dec['ROE_pct']:
                            roe_color = "green"
                        else:
                            roe_color = "red"
                        
            except Exception as e:
                st.warning(f"Gagal mengambil data harian: {e}")
            
            # 4. Hitung CAGR
            n = last_dec['FS_Date'].year - first_dec['FS_Date'].year
            if n > 0 and val_start > 0 and val_end > 0:
                cagr_val = (pow((val_end / val_start), (1/n)) - 1)
                growth_text = f"{cagr_val * 100:.2f}%"
                
                # Penentuan Kategori
                if cagr_val > 0.15:
                    category_label, category_color = "UPSTARTS", "green"
                elif cagr_val >= 0.05:
                    category_label, category_color = "STALWARTS", "blue"
                elif cagr_val >= 0.01:
                    category_label, category_color = "SLUGGARDS", "orange"
                else:
                    category_label, category_color = "CYCLICAL", "red"
            else:
                growth_text = "Data Tidak Konsisten"

        else:
            if not df_december.empty:
                display_year = df_december.iloc[-1]['FS_Date'].year
            growth_text = "Data < 2 Tahun"
            

        # --- TAMPILAN ---
        st.metric(label=f"Growth Laba Bersih (CAGR) {target_ticker} s.d. {display_year}", value=growth_text)

        # Gunakan kolom agar tampilan lebih rapi
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("**Kategori:**")
            st.markdown(f"<h3 style='color:{category_color}; margin-top:-15px;'>{category_label}</h3>", unsafe_allow_html=True)
        with col_b:
            st.markdown("**ROE (FS):**")
            st.markdown(f"<h3 style='color:black; margin-top:-15px;'>{roe_end} %</h3>", unsafe_allow_html=True)
        with col_c:
            st.markdown("**ROE Adjusted:**")
            st.markdown(f"<h3 style='color:{roe_color}; margin-top:-15px;'>{roe_end_adjusted} %</h3>", unsafe_allow_html=True)
        
     

        # --- FILTER TIPE PERIODE GRAFIK ---
        st.subheader(f"📈 Tren Fundamental Historis: {target_ticker}")

        # 1. Radio Button untuk memilih tipe data
        view_option = st.radio(
            "Pilih Tipe Tampilan Data:",
            ["Quarterly (Semua Laporan)", "Annual (Hanya Desember)", "TTM (Trailing Twelve Months)"],
            horizontal=True,
            key="view_filter_main"
        )

        # --- 2. PERSIAPAN DATA DASAR ---
        df_base = df_raw[df_raw['Ticker'] == target_ticker].copy()
        df_base['FS_Date'] = pd.to_datetime(df_base['FS_Date'], errors='coerce')
        df_base = df_base.dropna(subset=['FS_Date'])

        # Ambil data terbaru untuk setiap tanggal laporan
        df_base = df_base.sort_values(['FS_Date', 'Source_Period']).drop_duplicates('FS_Date', keep='last')

# --- 3. LOGIKA FILTER BERDASARKAN VIEW_OPTION ---
        df_plot = df_base.sort_values('FS_Date').copy()
        
        accumulative_metrics = [
            'Profit_for_Period', 
            'Profit_Attributable_Owner',
            'Sales_IDR_bn',
            'EBT_IDR_bn'
        ]

        # Proses De-akumulasi (Menghitung Nilai Murni 3 Bulanan)
        # --- LOGIKA DE-AKUMULASI DENGAN PEMBERSIHAN BARIS PERTAMA ---
        # 1. INISIALISASI DEFAULT (PENTING: Agar tidak NameError)
        info_msg = "Menampilkan data fundamental."
        #chart_mode = "bar"
        #accumulative_metrics = ['Profit_for_Period', 'Profit_Attributable_Owner', 'Sales_IDR_bn', 'EBT_IDR_bn']
        
        for col in accumulative_metrics:
            if col in df_plot.columns:
                # 1. Hitung nilai sebelumnya (Shift)
                df_plot['prev_val'] = df_plot.groupby(['Ticker', df_plot['FS_Date'].dt.year])[col].shift(1)
                
                # 2. Tandai baris pertama untuk setiap Ticker di setiap Tahun
                # Jika tidak ada baris sebelumnya (NaN), berarti ini baris pertama di tahun tersebut
                is_first_record = df_plot['prev_val'].isna()
                
                # 3. Logika Kuartal Murni (Discrete)
                is_q1 = df_plot['FS_Date'].dt.month == 3
                
                # Modifikasi: Jika Q1, pakai nilai asli. 
                # Jika BUKAN Q1 tapi data sebelumnya tidak ada (is_first_record), kita beri 0
                # agar tidak muncul lonjakan YTD di tengah grafik.
                df_plot[f'{col}_discrete'] = df_plot[col] - df_plot['prev_val'].fillna(0)
                
                # Eksekusi permintaan Anda: Nolkan baris jika dia adalah data pembuka (bukan Q1)
                # agar grafik mulai dari titik yang benar-benar 'bersih'
                df_plot.loc[is_first_record & ~is_q1, f'{col}_discrete'] = 0
                
                
        # --- LANJUT KE LOGIKA VIEW_OPTION ---
        if view_option == "TTM (Trailing Twelve Months)":
            for col in accumulative_metrics:
                # TTM tetap butuh 4 data, jadi baris awal yang di-nol-kan tadi 
                # secara otomatis akan membuat TTM tidak muncul sampai data ke-4 tersedia.
                df_plot[col] = df_plot[f'{col}_discrete'].rolling(window=4).sum()
                
            #### Pastikan kolom Equity tersedia
                if 'Equity_IDR_bn' in df_plot.columns:
                    # 1. ROE Standar TTM = (Laba Bersih TTM / Ekuitas Terakhir) * 100
                    # Kita gunakan ekuitas pada periode laporan terakhir untuk pembagi
                    df_plot['ROE_TTM'] = (df_plot['Profit_Attributable_Owner'] / df_plot['Equity_IDR_bn']) * 100
                    
                    # 2. ROE Adjusted TTM (Menggunakan Market Cap)
                    # market_cap_harian didapat dari data harga saham terbaru
                    if 'market_cap_harian' in locals() or 'market_cap_harian' in globals():
                        df_plot['ROE_Adj_TTM'] = (df_plot['Profit_Attributable_Owner'] / market_cap_harian) * 100
            ####
            
            df_plot = df_plot.dropna(subset=['Profit_Attributable_Owner'])
            chart_mode = "bar"
            metrics = calculate_company_metrics(df_base, df_plot, target_ticker)
            title_prefix = "TTM Analysis"
            
        elif view_option == "Annual (Hanya Desember)":
            # Untuk tahunan tetap pakai data asli karena Desember YTD = Full Year
            df_plot = df_plot[df_plot['FS_Date'].dt.month == 12].copy()
            chart_mode = "bar"
            metrics = calculate_company_metrics(df_base, df_plot, target_ticker)
            title_prefix = "Annual Analysis"
            
        else: # Quarterly
            for col in accumulative_metrics:
                df_plot[col] = df_plot[f'{col}_discrete']
            chart_mode = "bar"
            metrics = calculate_company_metrics(df_base, df_plot, target_ticker)
            title_prefix = "Quarterly Analysis"

        # --- PENTING: BUAT KOLOM STRING DISINI ---
        # Urutkan dan buat kolom untuk sumbu X agar tidak KeyError
        df_plot = df_plot.sort_values('FS_Date')
        df_plot['FS_Date_Str'] = df_plot['FS_Date'].dt.strftime('%d/%m/%Y')

        df_plot.to_parquet("df_plot_terakhir.parquet") ## simpan untuk analisa
        
        # Bersihkan kolom pembantu setelah FS_Date_Str dibuat
        cols_to_drop = [c for c in df_plot.columns if '_discrete' in c or c == 'prev_val']
        df_plot = df_plot.drop(columns=cols_to_drop)

        # --- 4. FUNGSI GAMBAR (Sekarang aman memanggil FS_Date_Str) ---
        def draw_dynamic_chart(title, y_col, color, label, mode):
            fig = go.Figure()
            # Cek apakah kolom ada di df_plot sebelum gambar
            if y_col not in df_plot.columns:
                return fig
                
            if mode == "line":
                fig.add_trace(go.Scatter(x=df_plot['FS_Date_Str'], y=df_plot[y_col], 
                                         mode='lines+markers', name=label, 
                                         line=dict(color=color, width=3)))
            else:
                fig.add_trace(go.Bar(x=df_plot['FS_Date_Str'], y=df_plot[y_col], 
                                     marker_color=color, name=label))
            
            fig.update_layout(
                title=title,
                xaxis={'categoryorder':'array', 'categoryarray': df_plot['FS_Date_Str'].tolist()},
                template="plotly_white", height=350, margin=dict(l=20, r=20, t=50, b=20),
                hovermode="x unified"
            )
            return fig

       
        
        # Inisialisasi kolom
        c1, c2, c3, c4 = st.columns(4)

        # Kolom 1: Kategori dengan Styling HTML
        with c1:
            st.markdown("**Kategori:**")
            # Gunakan st.html atau st.markdown langsung di dalam 'with' atau c1.markdown
            st.markdown(
                f"<h3 style='color:{metrics['category_color']}; margin-top:-15px;'>"
                f"{metrics['category_label']}</h3>", 
                unsafe_allow_html=True
            )

        # Kolom 2: CAGR
        c2.metric("CAGR (Long Term)", metrics['growth_text'])

        # Kolom 3: ROE Book
        # Pastikan metrics['roe_end'] adalah float/int sebelum diformat
        roe_book_val = float(metrics['roe_end']) if metrics['roe_end'] != "N/A" else 0
        c3.metric("ROE Book", f"{roe_book_val:.2f}%")

        # Kolom 4: ROE Adjusted
        roe_adj_val = float(metrics['roe_end_adjusted']) if metrics['roe_end_adjusted'] != "N/A" else 0
        diff = roe_adj_val - roe_book_val
        
        # Penentuan warna delta: 
        # 'normal' -> Hijau jika naik, Merah jika turun
        # 'inverse' -> Merah jika naik, Hijau jika turun
        # Karena ini perbandingan ROE vs Harga Pasar (ROE Adj), 
        # kita ingin warna HIJAU jika ROE Adj > ROE Book (artinya saham relatif murah/undervalued)
        d_color = "normal" #if diff > 0 else "inverse"

        c4.metric(
            label="ROE Adjusted (Laba/Market Cap)", 
            value=f"{roe_adj_val:.2f}%",
            delta=f"{diff:.2f}%",
            delta_color=d_color
        )
        
        st.markdown("---") # Pemisah visual

        
        # --- 1. AMBIL DATA DARI METRICS (Hasil fungsi calculate_company_metrics) ---
        
        roe_adj_val = float(metrics.get('calc_roe_adj', 0))
        current_price = metrics.get('last_price', 0)
        total_shares = metrics.get('shares', 0)

        # --- 2. LOGIKA PROYEKSI BVPS & MOS ---
        # --- 2. PANGGIL FUNGSI VALUASI SENTRAL ---
        val_results = calculate_valuation_metrics(df_plot, metrics)
        
        # Ekstrak untuk tampilan metric
        current_bvps = val_results["current_bvps"]
        projected_bvps_5y = val_results["projected_bvps_5y"]
        mos_val = val_results["mos_val"]
        roe_book_val = val_results["roe_used"]
        
        
        # Baris Kedua: Valuasi & Proyeksi
        c5, c6, c7 = st.columns(3)
        
        with c5:
            st.metric("Current BVPS (berdasar ekuitas total)", f"Rp {current_bvps:,.0f}")
            st.caption(f"Price/BVPS: {(current_price/current_bvps):.2f}x")

        with c6:
            st.metric("Projected BVPS (5Y)", f"Rp {projected_bvps_5y:,.0f}")
            st.caption(f"Estimasi ROE: {roe_book_val:.2f}%")

        with c7:
            delta_mos = f"{mos_val:.2f}%"
            st.metric(
                label="Margin of Safety (MOS)", 
                value=delta_mos,
                delta="Safe" if mos_val > 30 else "Risk",
                delta_color="normal" if mos_val > 30 else "inverse"
            )
            st.caption("Target MOS: > 30%")
            
            
        # --- TAMPILKAN METRIC DI ATAS GRAFIK ---
 
        # --- 5. EKSEKUSI TAMPILAN DASHBOARD ---
        if not df_plot.empty:
            st.info(f"💡 {info_msg}")
            
            # Dashboard 1: Kelompok Profitability
            fig_profit = draw_profitability_dashboard(df_plot, target_ticker, chart_mode, view_option)
            st.plotly_chart(fig_profit, use_container_width=True)
            
            st.divider()
            
            # Dashboard 2: Kelompok Balance Sheet
            # Khusus Balance Sheet, kita gunakan bar chart karena bukan data akumulatif YTD
            fig_balance = draw_balance_sheet_dashboard(df_plot, target_ticker)
            st.plotly_chart(fig_balance, use_container_width=True)
            
        else:
            st.warning("Data tidak cukup untuk menampilkan dashboard.")
if __name__ == "__main__":
    run_fundamental()