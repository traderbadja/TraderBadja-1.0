import pandas as pd
import os
import shutil

def load_data():
    path = "Master_Database_Transaksi_IDX.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path)
    return pd.DataFrame()
def load_data_financial():
    path2 = "Master_Database_Financials.parquet"
    if os.path.exists(path2):
        return pd.read_parquet(path2)
    return pd.DataFrame()
    
def load_data_lengkap():
    df_transaksi = pd.read_parquet("Master_Database_Transaksi_IDX.parquet")
    
    if os.path.exists("Master_Database_Financials.parquet"):
        df_fund = pd.read_parquet("Master_Database_Financials.parquet")
        
        # Ambil kolom yang dibutuhkan
        df_sektor = df_fund[['Ticker', 'Sector']].drop_duplicates()
        
        # Gabungkan dengan spesifikasi kolom kunci yang berbeda
        df_final = pd.merge(
            df_transaksi, 
            df_sektor, 
            left_on='Kode Saham',  # Kolom di df_transaksi
            right_on='Ticker',       # Kolom di df_sektor
            how='left'
        )
        
        # Setelah merge, kolom 'Code' akan ikut muncul, kita hapus agar tidak duplikat
        df_final = df_final.drop(columns=['Ticker'])
        
        df_final['Sector'] = df_final['Sector'].fillna('Uncategorized')
        df_final['Market_Cap'] = df_final['Tradeble Shares'] * df_final['Penutupan']
        
        return df_final
    
    return df_transaksi
    
def simpan_dan_update(uploaded_file, folder_arsip="data_idx", path_master="Master_Database_Transaksi_IDX.parquet"):
    # 1. Pastikan folder arsip ada
    if not os.path.exists(folder_arsip):
        os.makedirs(folder_arsip)
    
    # 2. Tentukan path tujuan di folder data_idx
    file_path = os.path.join(folder_arsip, uploaded_file.name)
    
    # 3. Simpan file dari Streamlit ke folder fisik
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    try:
        # 4. Baca data baru untuk digabung ke Master
        df_baru = pd.read_excel(file_path)
      
        # Logika perhitungan kolom (Rank, Foreign Net, dll)
        if 'Tanggal Perdagangan Terakhir' in df_baru.columns:
            df_baru['Tanggal Perdagangan Terakhir'] = pd.to_datetime(df_baru['Tanggal Perdagangan Terakhir'])
            df_baru['Rank Value'] = df_baru['Nilai'].rank(method='min', ascending=False)
            df_baru['Foreign Net Buy'] = df_baru['Foreign Buy'] - df_baru['Foreign Sell']
            df_baru['Daily Return (%)'] = ((df_baru['Selisih'] / df_baru['Sebelumnya']) * 100).round(2)
            df_baru['Price Change'] = df_baru['Selisih']

        # 5. Gabungkan ke Master Parquet
        if os.path.exists(path_master):
            df_master = pd.read_parquet(path_master)
            df_master = pd.concat([df_master, df_baru], ignore_index=True)
            df_master = df_master.drop_duplicates(subset=['Tanggal Perdagangan Terakhir', 'Kode Saham'], keep='last')
        else:
            df_master = df_baru
            
        df_master.to_parquet(path_master, index=False)
        return True, f"Berhasil! {uploaded_file.name} disimpan di arsip dan Master diperbarui."
        
    except Exception as e:
        return False, f"Gagal memproses file: {e}"

def simpan_dan_update_financial(uploaded_file2, folder_arsip="data_idx_financial", path_master="Master_Database_Financials.parquet"):
    """
    Fungsi untuk menyimpan file upload ke folder fisik dan memperbarui database master Parquet.
    Mengintegrasikan cleaning, mapping, dan sorting kronologis.
    """
    # 1. Pastikan folder arsip ada
    if not os.path.exists(folder_arsip):
        os.makedirs(folder_arsip)
    
    # 2. Tentukan path tujuan di folder arsip
    file_path = os.path.join(folder_arsip, uploaded_file2.name)
    
    # 3. Simpan file dari Streamlit ke folder fisik
    with open(file_path, "wb") as f:
        f.write(uploaded_file2.getbuffer())
    
    try:
        # 4. Baca data baru (Sesuaikan skiprows jika header ada di baris 5)
        df_baru = pd.read_excel(file_path, header=0, skiprows=4, na_values='-')
        
        # --- PROSES CLEANING & MAPPING ---
        
        # Hapus kolom pertama jika kosong (Unnamed: 0)
        if 'Unnamed: 0' in df_baru.columns:
            df_baru = df_baru.drop(columns=['Unnamed: 0'])
            
        # Mapping nama kolom agar konsisten
        column_mapping = {
            'Unnamed: 1': 'No',
            'Unnamed: 2': 'Sector',
            'Unnamed: 3': 'Sub_Industry_Code',
            'Unnamed: 4': 'Sub_Industry',
            'Unnamed: 5': 'Ticker',
            'Unnamed: 6': 'Stock_Name',
            'Unnamed: 7': 'Sharia',
            'Unnamed: 8': 'FS_Date',
            'Unnamed: 9': 'Fiscal_Year_End',
            'Unnamed: 10': 'Type_of_FS',
            'Unnamed: 11': 'Auditor_Opinion',
            'Assets, b.IDR': 'Assets_IDR_bn',
            'Liabilities, b.IDR': 'Liabilities_IDR_bn',
            'Equity, b.IDR': 'Equity_IDR_bn',
            'Sales, b.IDR': 'Sales_IDR_bn',
            'EBT, b.IDR': 'EBT_IDR_bn',
            'Unnamed: 17': 'Profit_for_Period',
            'Unnamed: 18': 'Profit_Attributable_Owner',
            'EPS, IDR': 'EPS_IDR',
            'Book Value, IDR': 'BV_IDR',
            'P/E Ratio, x': 'PER',
            'Price to BV, x': 'PBV',
            'D/E Ratio, x': 'DER',
            'ROA, %': 'ROA_pct',
            'ROE, %': 'ROE_pct',
            'NPM, %': 'NPM_pct'
        }
        df_baru = df_baru.rename(columns=column_mapping)
        
        # Kolom-kolom yang seharusnya berisi angka (sesuaikan dengan kebutuhan)
        numeric_cols = [
            'Assets, b.IDR', 'Liabilities, b.IDR', 'Equity, b.IDR', 
            'Sales, b.IDR', 'EBT, b.IDR', 'EPS, IDR', 'Book Value, IDR',
            'P/E Ratio, x', 'Price to BV, x', 'D/E Ratio, x', 
            'ROA, %', 'ROE, %', 'NPM, %'
        ]
        for col in numeric_cols:
            if col in df_baru.columns:
                df_baru[col] = pd.to_numeric(df_baru[col], errors='coerce')

        # Buang baris yang Ticker-nya kosong (Menghapus Market PER/PBV & Footer)
        df_baru = df_baru.dropna(subset=['Ticker'])
        # Pastikan Ticker bersih dari spasi dan hanya kode saham valid
        df_baru['Ticker'] = df_baru['Ticker'].astype(str).str.strip()
        df_baru = df_baru[df_baru['Ticker'].str.len() <= 5]

        # --- EKSTRAKSI PERIODE DARI NAMA FILE ---
        # Contoh nama file: 'Financial Data and Ratio - Aug 2025.xlsx'
        try:
            date_part = uploaded_file2.name.replace('Financial Data and Ratio - ', '').replace('.xlsx', '')
            df_baru['Source_Period'] = pd.to_datetime(date_part, format='%b %Y')
            df_baru['Period_Display'] = df_baru['Source_Period'].dt.strftime('%b %Y')
        except:
            # Fallback jika nama file tidak sesuai format
            df_baru['Source_Period'] = pd.Timestamp.now().normalize()
            df_baru['Period_Display'] = "Unknown"

        # --- GABUNG KE MASTER ---
        if os.path.exists(path_master):
            df_master = pd.read_parquet(path_master)
            # Gabungkan data lama dan baru
            df_master = pd.concat([df_master, df_baru], ignore_index=True)
            
            # Pastikan kolom waktu tetap datetime untuk sorting
            df_master['Source_Period'] = pd.to_datetime(df_master['Source_Period'])
            
            # Hapus Duplikat berdasarkan Ticker dan Periode (ambil data yang terbaru diupload)
            df_master = df_master.drop_duplicates(subset=['Ticker', 'Source_Period'], keep='last')
        else:
            df_master = df_baru

        # --- SORTING AKHIR (PENTING) ---
        # Urutkan berdasarkan Ticker (A-Z) dan Periode (Lama ke Baru)
        df_master = df_master.sort_values(by=['Ticker', 'Source_Period'], ascending=[True, True])
        df_master = df_master.reset_index(drop=True)
        
        # Simpan ke Master Parquet
        df_master.to_parquet(path_master, index=False)
        
        return True, f"Berhasil! {uploaded_file2.name} diproses dan Master Financial diperbarui."
        
    except Exception as e:
        return False, f"Gagal memproses file: {str(e)}"

"""      
def simpan_dan_update_financial(uploaded_file2, folder_arsip="data_idx_financial", path_master="Master_Database_Financials.parquet"):
    # 1. Pastikan folder arsip ada
    if not os.path.exists(folder_arsip):
        os.makedirs(folder_arsip)
    
    # 2. Tentukan path tujuan di folder data_idx
    file_path = os.path.join(folder_arsip, uploaded_file2.name)
    
    # 3. Simpan file dari Streamlit ke folder fisik
    with open(file_path, "wb") as f:
        f.write(uploaded_file2.getbuffer())
    
    try:
        # 4. Baca data baru untuk digabung ke Master
        df_baru = pd.read_excel(file_path, index_col=None, header=0, skiprows=4, na_values='-')
        
        # Kolom-kolom yang seharusnya berisi angka (sesuaikan dengan kebutuhan)
        numeric_cols = [
            'Assets, b.IDR', 'Liabilities, b.IDR', 'Equity, b.IDR', 
            'Sales, b.IDR', 'EBT, b.IDR', 'EPS, IDR', 'Book Value, IDR',
            'P/E Ratio, x', 'Price to BV, x', 'D/E Ratio, x', 
            'ROA, %', 'ROE, %', 'NPM, %'
        ]
        # Membersihkan kolom numerik: 
        # Kadang ada spasi atau karakter aneh, kita paksa jadi angka
        for col in numeric_cols:
            if col in df_baru.columns:
                # errors='coerce' akan mengubah teks yang tidak bisa jadi angka menjadi NaN
                df_baru[col] = pd.to_numeric(df_baru[col], errors='coerce')
       
        
        # 2. Hapus kolom pertama jika itu memang kolom kosong (Unnamed: 0)
        if 'Unnamed: 0' in df_baru.columns:
            df_baru = df_baru.drop(columns=['Unnamed: 0'])
        
        # 3. Rename kolom secara manual agar informatif
        # Contoh memetakan kolom Unnamed ke nama yang seharusnya
        # 2. Daftar mapping nama kolom berdasarkan struktur file Anda
        column_mapping = {
            'Unnamed: 1': 'No',
            'Unnamed: 2': 'Sector',
            'Unnamed: 3': 'Sub_Industry_Code',
            'Unnamed: 4': 'Sub_Industry',
            'Unnamed: 5': 'Ticker',
            'Unnamed: 6': 'Stock_Name',
            'Unnamed: 7': 'Sharia',
            'Unnamed: 8': 'FS_Date',
            'Unnamed: 9': 'Fiscal_Year_End',
            'Unnamed: 10': 'Type_of_FS',
            'Unnamed: 11': 'Auditor_Opinion',
            'Assets, b.IDR': 'Assets_IDR_bn',
            'Liabilities, b.IDR': 'Liabilities_IDR_bn',
            'Equity, b.IDR': 'Equity_IDR_bn',
            'Sales, b.IDR': 'Sales_IDR_bn',
            'EBT, b.IDR': 'EBT_IDR_bn',
            'Unnamed: 17': 'Profit_for_Period',
            'Unnamed: 18': 'Profit_Attributable_Owner',
            'EPS, IDR': 'EPS_IDR',
            'Book Value, IDR': 'BV_IDR',
            'P/E Ratio, x': 'PER',
            'Price to BV, x': 'PBV',
            'D/E Ratio, x': 'DER',
            'ROA, %': 'ROA_pct',
            'ROE, %': 'ROE_pct',
            'NPM, %': 'NPM_pct'
        }
        # 3. Terapkan perubahan nama
        df_baru = df_baru.rename(columns=column_mapping)
        
        # Menghapus baris jika SEMUA kolomnya bernilai NaN
        df_baru = df_baru.dropna(how='all')
        
        # Berdasarkan mapping kita, kolom 'Code' di Excel menjadi 'Ticker' di DataFrame
        # Baris Market PER/PBV TIDAK memiliki kode saham, jadi kita buang yang kosong (NaN)
        df_baru = df_baru.dropna(subset=['Ticker'])
        
        base_name = os.path.basename(filename)
        # 2. Ekstrak bagian 'Aug 2025'
        # Kita hapus awalan dan akhiran .xlsx
        date_str = base_name.replace('Financial Data and Ratio - ', '').replace('.xlsx', '')

        
        # 3. Masukkan ke kolom Source_Period sebagai tipe datetime
        # Ini akan mengubah 'Aug 2025' menjadi 2025-08-01
        df_baru['Source_Period'] = pd.to_datetime(date_str, format='%b %Y')
        
        # 4. Tambahkan kolom string untuk tampilan jika perlu (misal: 'Aug-2025')
        df_baru['Period_Display'] = df_baru['Source_Period'].dt.strftime('%b %Y')


        # 5. Gabungkan ke Master Parquet
        if os.path.exists(path_master):
            df_master = pd.read_parquet(path_master)
            df_master = pd.concat([df_master, df_baru], ignore_index=True)
            df_master = df_master.drop_duplicates(subset=['Tanggal Perdagangan Terakhir', 'Kode Saham'], keep='last')
            
            # Pastikan kolom waktu adalah tipe datetime agar sorting-nya benar (Jan -> Feb -> Mar)
            df_master['Source_Period'] = pd.to_datetime(df_master['Source_Period'])
            
            # Hapus Duplikat
            df_master = df_master.drop_duplicates(subset=['Ticker', 'Source_Period'], keep='last')
            
            # SORTING DI SINI
            df_master = df_master.sort_values(by=['Ticker', 'Source_Period'], ascending=[True, True])
            
        else:
            df_master = df_baru
            
        df_master.to_parquet(path_master, index=False)
        return True, f"Berhasil! {uploaded_file.name} disimpan di arsip dan Master Financial diperbarui."
        
    except Exception as e:
        return False, f"Gagal memproses file: {e}"
"""