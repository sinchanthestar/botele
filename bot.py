import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import requests
import json
import time
from flask import Flask, request, jsonify
import os

# ==========================================
# 1. KONFIGURASI UTAMA
# ==========================================
TOKEN = '8435634970:AAF57eFmXyHuFru25lCsMETXQzBylPMbC88'
bot = telebot.TeleBot(TOKEN)

# Konfigurasi Midtrans
MIDTRANS_SERVER_KEY = 'Mid-server-Aa6IQjd6Gx4YTuuG9-aDbz25'
MIDTRANS_URL = 'https://app.sandbox.midtrans.com/snap/v1/transactions'
WEBHOOK_URL_BASE = 'https://botele-production.up.railway.app' 

# Konfigurasi Brand 1: Veloura
API_KEY_VELOURA = 'IMyIc3-D1TEqA-GpAoZb-CtKWc2'
URL_API_VELOURA = 'https://velouramlbb.biz.id/api/order/register'
HARGA_VELOURA = {1: 15000, 3: 25000, 7: 50000, 30: 100000, 60: 200000, 90: 250000}

# Konfigurasi Brand 2: Arrowmodz (SILAKAN SESUAIKAN)
API_KEY_ARROWMODZ = '0ZEiUu-8MOhL6-lhoQBV-IvpAoh'
URL_API_ARROWMODZ = 'https://arrowmodz.site/api/order/register' # Ganti dengan URL API Arrowmodz yang asli
HARGA_ARROWMODZ = {1: 15000, 3: 25000, 7: 50000, 30: 100000, 60: 200000, 90: 250000} # Sesuaikan harga Arrowmodz

app = Flask(__name__)
pending_orders = {}

# ==========================================
# 2. LOGIKA BOT TELEGRAM
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Halo! 👋\nKetik /order untuk mulai membuat license key otomatis.")

# MENU UTAMA: PILIH BRAND
@bot.message_handler(commands=['order'])
def send_brand_menu(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎮 Veloura MLBB", callback_data="brand_veloura"),
        InlineKeyboardButton("🏹 Arrowmodz MLBB", callback_data="brand_arrowmodz") # Tombol Brand Baru
    )
    bot.reply_to(message, "Silakan pilih Produk/Brand yang ingin Anda order:", reply_markup=markup)

# MENU DURASI: VELOURA
@bot.callback_query_handler(func=lambda call: call.data == 'brand_veloura')
def process_brand_veloura(call):
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("1 Hari (15k)", callback_data="veloura_1"),
        InlineKeyboardButton("3 Hari (25k)", callback_data="veloura_3"),
        InlineKeyboardButton("7 Hari (50k)", callback_data="veloura_7"),
        InlineKeyboardButton("30 Hari (100k)", callback_data="veloura_30"),
        InlineKeyboardButton("60 Hari (200k)", callback_data="veloura_60"),
        InlineKeyboardButton("90 Hari (250k)", callback_data="veloura_90"),
        InlineKeyboardButton("🔙 Batal", callback_data="cancel_order")
    )
    bot.edit_message_text("Anda memilih **Veloura MLBB**.\nSilakan pilih durasi paket:", 
                          chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

# MENU DURASI: ARROWMODZ
@bot.callback_query_handler(func=lambda call: call.data == 'brand_arrowmodz')
def process_brand_arrowmodz(call):
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    # Perhatikan callback data-nya menggunakan prefix 'arrowmodz_'
    markup.add(
        InlineKeyboardButton("1 Hari (15k)", callback_data="arrowmodz_1"),
        InlineKeyboardButton("3 Hari (25k)", callback_data="arrowmodz_3"),
        InlineKeyboardButton("7 Hari (50k)", callback_data="arrowmodz_7"),
        InlineKeyboardButton("30 Hari (100k)", callback_data="arrowmodz_30"),
        InlineKeyboardButton("🔙 Batal", callback_data="cancel_order")
    )
    bot.edit_message_text("Anda memilih **Arrowmodz MLBB**.\nSilakan pilih durasi paket:", 
                          chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_order')
def cancel_order(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("❌ Order dibatalkan.", chat_id=call.message.chat.id, message_id=call.message.message_id)

# PROSES KLIK DURASI (MENANGANI KEDUA BRAND SEKALIGUS)
@bot.callback_query_handler(func=lambda call: call.data.startswith(('veloura_', 'arrowmodz_')))
def process_payment_link(call):
    # Memecah data callback (contoh: "veloura_7" menjadi brand="veloura" dan durasi=7)
    brand, durasi_str = call.data.split('_')
    durasi = int(durasi_str)
    
    # Menentukan harga dan nama produk berdasarkan brand
    if brand == "veloura":
        harga = HARGA_VELOURA.get(durasi, 0)
        nama_produk = "Veloura MLBB"
    else:
        harga = HARGA_ARROWMODZ.get(durasi, 0)
        nama_produk = "Arrowmodz MLBB"
        
    chat_id = call.message.chat.id
    nama_user = call.from_user.first_name
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text("⏳ Sedang membuat link pembayaran aman via Midtrans...", chat_id=chat_id, message_id=call.message.message_id)

    order_id = f"{brand[:2].upper()}-{chat_id}-{int(time.time())}" # Prefix order ID menjadi VE- atau AR-
    
    # ⚠️ PENTING: Sekarang kita menyimpan data 'brand' di dalam memori
    pending_orders[order_id] = {"chat_id": chat_id, "nama_user": nama_user, "durasi": durasi, "brand": brand}

    payload_midtrans = {
        "transaction_details": {"order_id": order_id, "gross_amount": harga},
        "customer_details": {"first_name": nama_user, "notes": f"Pelanggan {brand.title()}"},
        "item_details": [{"id": f"{brand}-{durasi}D", "price": harga, "quantity": 1, "name": f"{nama_produk} {durasi} Hari"}]
    }

    try:
        response = requests.post(MIDTRANS_URL, json=payload_midtrans, auth=(MIDTRANS_SERVER_KEY, ''))
        data_midtrans = response.json()

        if response.status_code == 201:
            payment_url = data_midtrans['redirect_url']
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("💳 Bayar Sekarang", url=payment_url))
            bot.edit_message_text(
                f"📝 **INVOICE ORDER**\n\n📦 Produk: {nama_produk} ({durasi} Hari)\n💰 Total: Rp {harga:,}\n\nKlik tombol di bawah untuk membayar.",
                chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown'
            )
        else:
            bot.edit_message_text("❌ Gagal membuat link pembayaran.", chat_id=chat_id, message_id=call.message.message_id)
    except Exception as e:
        bot.edit_message_text("❌ Terjadi kesalahan sistem pembayaran.", chat_id=chat_id, message_id=call.message.message_id)

# ==========================================
# 3. FLASK ROUTES (WEBHOOKS)
# ==========================================
@app.route(f'/{TOKEN}', methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Forbidden', 403

@app.route('/webhook/midtrans', methods=['POST'])
def midtrans_webhook():
    data = request.json
    order_id = data.get('order_id')
    transaction_status = data.get('transaction_status')
    fraud_status = data.get('fraud_status')

    if transaction_status == 'settlement' or (transaction_status == 'capture' and fraud_status == 'accept'):
        if order_id in pending_orders:
            order_data = pending_orders[order_id]
            chat_id = order_data["chat_id"]
            nama_user = order_data["nama_user"]
            durasi = order_data["durasi"]
            brand = order_data["brand"] # Mengambil brand dari memori

            bot.send_message(chat_id, f"✅ Pembayaran diterima! Sedang meng-generate License {brand.title()} Anda...")

            # Logika Percabangan Pemilihan API Endpoint
            if brand == "veloura":
                url_api = URL_API_VELOURA
                payload_api = {"api_key": API_KEY_VELOURA, "nama": nama_user, "durasi": durasi, "game": "MLBB", "max_devices": 1}
            elif brand == "arrowmodz":
                url_api = URL_API_ARROWMODZ
                # ASUMSI: Parameter API Arrowmodz sama dengan Veloura. Jika beda, ubah di baris bawah ini.
                payload_api = {"api_key": API_KEY_ARROWMODZ, "nama": nama_user, "durasi": durasi, "game": "MLBB", "max_devices": 1} 

            try:
                res_api = requests.post(url_api, data=payload_api)
                data_api_response = res_api.json()

                if data_api_response.get("status") == True:
                    license_key = data_api_response.get("data", {}).get("License") or data_api_response.get("data", {}).get("license") or "[KEY TIDAK DITEMUKAN]"
                    balasan = f"🎉 **TERIMA KASIH! ORDER SELESAI**\n\n👤 Nama: {nama_user}\n📦 Paket: {brand.title()} {durasi} Hari\n🔑 License: `{license_key}`\n\n*(Ketuk license di atas untuk menyalin)*"
                    bot.send_message(chat_id, balasan, parse_mode='Markdown')
                else:
                    bot.send_message(chat_id, f"⚠️ Pembayaran masuk, tapi gagal generate key {brand.title()}:\n{data_api_response.get('message', 'Error')}\nHubungi Admin.")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Pembayaran berhasil, tapi terjadi error server {brand.title()}.")
            
            del pending_orders[order_id]

    return jsonify({"status": "ok"}), 200

@app.route('/')
def index():
    return "Server Webhook Multi-Brand Berjalan Lancar! 🚀", 200

# ==========================================
# 4. MENJALANKAN SERVER
# ==========================================
if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{WEBHOOK_URL_BASE}/{TOKEN}")
    print("✅ Webhook Telegram Berhasil Dipasang!")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
