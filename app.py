import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from PIL import Image
import json
import gspread
import time  

# 1. Setup Konfigurasi Web
st.set_page_config(page_title="Auto Input Multi-Live Shopee", page_icon="📸", layout="wide")
st.title("📸 Auto Input Report Shopee Live ke Master")

# 2. Setup API Key Gemini
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# 3. Form Input Manual Umum
target_baris_awal = st.number_input("Mulai Push dari Baris", min_value=2, value=100, step=1)
st.info("💡 Masukkan nomor baris yang sesuai dengan jadwal di Master Schedule.")

if "list_data_mentah" not in st.session_state:
    st.session_state["list_data_mentah"] = []

# 4. Upload Banyak Foto Sekaligus (Multi-Upload)
st.markdown("### 📥 Upload Beberapa Screenshot Sekaligus")
uploaded_files = st.file_uploader(
    "Pilih atau seret (drag & drop) foto screenshot dashboard Shopee Live sekaligus", 
    type=['jpg', 'jpeg', 'png'], 
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"📂 Total {len(uploaded_files)} foto berhasil dipilih.")
    
    if st.button("🪄 Ekstrak Semua Data Foto Sekaligus"):
        st.session_state["list_data_mentah"] = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        extracted_results = []
        
        for idx, file in enumerate(uploaded_files):
            status_text.text(f"Sedang membaca foto ke-{idx+1} dari {len(uploaded_files)}... (Mohon tunggu sebentar)")
            progress_bar.progress((idx + 1) / len(uploaded_files))
            
            try:
                image = Image.open(file)
                prompt = """
                Ekstrak data angka dari screenshot dashboard Shopee Live ini.
                Kembalikan WAJIB HANYA dalam format JSON murni. 
                Gunakan template JSON persis seperti di bawah ini, kamu cukup isi nilai-nilainya saja dari gambar:

                {
                    "Peak_Viewers": 0,
                    "Views": 0,
                    "Unique_Viewers": 0,
                    "Likes": 0,
                    "Shares": 0,
                    "Comments": 0,
                    "New_Followers": 0,
                    "Product_Clicks": 0,
                    "Sales": 0,
                    "Order": 0,
                    "Item_Sold": 0,
                    "Customers": 0,
                    "Add_to_Cart": 0,
                    "Avg_Watch_Time": ""
                }

                Aturan Ketat:
                - Peak_Viewers: ambil dari bagian 'Penonton Terbanyak'
                - Views: HANYA ambil dari angka di bagian 'Ditonton'
                - Unique_Viewers: HANYA ambil dari angka di bagian 'Penonton' (JANGAN tertukar dengan 'Penonton Aktif' atau 'Ditonton')
                - Likes: ambil dari bagian 'Suka'
                - Shares: ambil dari bagian 'Dibagikan'
                - Comments: ambil dari bagian 'Komentar'
                - New_Followers: ambil dari bagian 'Pengikut Baru'
                - Product_Clicks: ambil dari bagian 'Klik Produk'
                - Sales: ambil dari bagian 'Penjualan' utama. Hilangkan 'Rp' dan titik ribuan (misal Rp384.280 jadi 384280)
                - Order: ambil dari bagian 'Pesanan'
                - Item_Sold: ambil dari bagian 'Produk Terjual'
                - Customers: ambil dari bagian 'Pembeli'
                - Add_to_Cart: ambil dari bagian 'Tambah ke Keranjang'
                - Avg_Watch_Time: ambil dari bagian 'Durasi Rata-Rata Menonton', format string HH:MM:SS

                Catatan:
                - Avg_Watch_Time WAJIB string format HH:MM:SS.
                - Sisa data lainnya WAJIB integer angka murni tanpa titik/koma/Rp.
                - DILARANG menambahkan kata-kata pengantar apapun selain JSON ini.
                """
                
                response = client_gemini.models.generate_content(
                    model='gemini-3.5-flash',
                    contents=[prompt, image],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                
                data_json = json.loads(raw_text)
                extracted_results.append(data_json)
                
                # JEDA 15 DETIK AGAR AMAN DARI LIMIT
                time.sleep(15)
                
            except Exception as e:
                st.error(f"Gagal membaca file {file.name}: {e}")
        
        status_text.text("Semua foto selesai diekstrak!")
        st.session_state["list_data_mentah"] = extracted_results
        st.success("✅ Semua data foto berhasil ditarik oleh AI!")

    # 5. INPUT LINK DASHBOARD MASING-MASING FOTO & PREVIEW
    if len(st.session_state["list_data_mentah"]) > 0:
        list_data = st.session_state["list_data_mentah"]
        
        st.write("---")
        st.write("### ⚙️ Atur Baris & Link Dashboard untuk Masing-Masing Foto:")
        
        list_link_dashboard = []
        list_target_row = []
        
        for i, file_obj in enumerate(uploaded_files):
            current_target_row = target_baris_awal + i
            
            col_img, col_info = st.columns([1, 3])
            with col_img:
                st.image(file_obj, width=150)
            with col_info:
                # Membiarkan user mengubah nomor baris secara manual per foto kalau shiftnya lompat-lompat
                row_val = st.number_input(f"Target Baris G-Sheets (Foto {i+1})", value=current_target_row, key=f"row_{i}")
                list_target_row.append(row_val)
                
                link_val = st.text_input(f"Link Dashboard (Foto {i+1})", key=f"link_{i}", placeholder="Paste link After Live Proof di sini...")
                list_link_dashboard.append(link_val)
            st.write("---")

        df_preview_list = []
        for i, item in enumerate(list_data):
            df_preview_list.append({
                "Target Baris": list_target_row[i],
                "Sales": item.get("Sales", 0),
                "Order": item.get("Order", 0),
                "Peak Viewers": item.get("Peak_Viewers", 0),
                "Views": item.get("Views", 0),
                "Unique Viewers": item.get("Unique_Viewers", 0),
                "Link": list_link_dashboard[i]
            })
            
        st.write(f"### 📋 Preview Data yang Akan Masuk ke Shopee Section:")
        st.dataframe(pd.DataFrame(df_preview_list), use_container_width=True)
        st.write("---")

        if st.button(f"🚀 Push Semua Data Sekaligus ke G-Sheets"):
            with st.spinner("Sedang mengirim semua data ke Google Sheets Master..."):
                try:
                    # Menggunakan Service Account untuk otorisasi
                    creds_dict = dict(st.secrets["gcp_service_account"])
                    client_gs = gspread.service_account_from_dict(creds_dict)
                    
                    # Terkoneksi ke file yang BARU menggunakan ID URL nya langsung biar 100% akurat
                    sheet = client_gs.open_by_key("19lxhkIIGunCFudopF0hy3eZM4ZbXd5mredD9UhPG1X8")
                    
                    # Membuka tab "LIVESTREAM SCHEDULE - OCTOBER"
                    worksheet = sheet.worksheet("LIVESTREAM SCHEDULE - OCTOBER")
                    
                    all_updates = []
                    
                    for i, data_mentah in enumerate(list_data):
                        current_row = list_target_row[i]
                        current_link = list_link_dashboard[i]
                        
                        # MAPPING BARU KHUSUS MASTER SCHEDULE (SHOPEE SECTION)
                        all_updates.extend([
                            # Kolom AO sampai AV (Kunjungan & Interaksi)
                            {'range': f'AO{current_row}:AV{current_row}', 'values': [[
                                data_mentah.get("Peak_Viewers", 0),
                                data_mentah.get("Views", 0),
                                data_mentah.get("Unique_Viewers", 0),
                                data_mentah.get("Likes", 0),
                                data_mentah.get("Shares", 0),
                                data_mentah.get("Comments", 0),
                                data_mentah.get("New_Followers", 0),
                                data_mentah.get("Product_Clicks", 0)
                            ]]},
                            # Kolom BA sampai BC (Transaksi: Order, Unit Sold, Buyer)
                            {'range': f'BA{current_row}:BC{current_row}', 'values': [[
                                data_mentah.get("Order", 0),
                                data_mentah.get("Item_Sold", 0),
                                data_mentah.get("Customers", 0)
                            ]]},
                            # Kolom BM sampai BO (Add to Cart, Avg Watch Time, Sales Updated)
                            {'range': f'BM{current_row}:BO{current_row}', 'values': [[
                                data_mentah.get("Add_to_Cart", 0),
                                data_mentah.get("Avg_Watch_Time", ""),
                                data_mentah.get("Sales", 0)
                            ]]},
                            # Kolom BQ (After Live Proof Link)
                            {'range': f'BQ{current_row}', 'values': [[
                                current_link
                            ]]}
                        ])
                    
                    # Mengeksekusi semua pembaruan sekaligus
                    worksheet.batch_update(all_updates, value_input_option='USER_ENTERED')
                    st.success(f"🎉 Sukses! Semua data Shopee berhasil di-push ke Master Schedule.")
                    
                except Exception as e:
                    st.error(f"Gagal mengirim data massal ke Sheets: {e}")
