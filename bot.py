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
URL_API_VELOURA_ORDER = 'https://velouramlbb.biz.id/api/order/register'
URL_API_VELOURA_GAMES = 'https://velouramlbb.biz.id/api/get/games' # Endpoint baru untuk ambil game
HARGA_VELOURA = {1: 15000, 3: 25000, 7: 50000, 30: 100000, 60: 200000, 90: 250000}

# Konfigurasi Brand 2: Arrowmodz
API_KEY_ARROWMODZ = '0ZEiUu-8MOhL6-lhoQBV-IvpAoh'
URL_API_ARROWMODZ_ORDER = 'https://arrowmodz.site/api/order/register' 
URL_API_ARROWMODZ_GAMES = 'https://arrowmodz.site/api/get/games' # Endpoint baru untuk ambil game
HARGA_ARROWMODZ = {1: 15000, 3: 25000, 7: 50000, 30: 100000, 60: 200000, 90: 250000} 

app = Flask(__name__)
pending_orders = {}

# ==========================================
# 2. LOGIKA BOT TELEGRAM
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Halo! 👋\nKetik /order untuk mulai membuat license key otomatis.")

# TAHAP 1: MENU UTAMA (PILIH BRAND)
@bot.message_handler(commands=['order'])
def send_brand_menu(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎮 Veloura", callback_data="brand_veloura"),
        InlineKeyboardButton("🏹 Arrowmodz", callback_data="brand_arrowmodz")
    )
    bot.reply_to(message, "Silakan pilih Produk/Brand yang ingin Anda order:", reply_markup=markup)

# TAHAP 2: MENU PILIH GAME (Tarik Otomatis dari API)
@bot.callback_query_handler(func=lambda call: call.data.startswith('brand_'))
def process_brand_selection(call):
    bot.answer_callback_query(call.id)
    brand = call.data.split('_')[1] # Ambil nama brand dari callback_data

    # Pesan loading sementara menghubungi API server
    bot.edit_message_text(f"⏳ Sedang mengambil daftar game dari server **{brand.title()}**...", 
                          chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='Markdown')

    # Menentukan endpoint berdasarkan brand
    if brand == "veloura":
        url_games = URL_API_VELOURA_GAMES
        api_key = API_KEY_VELOURA
    else:
        url_games = URL_API_ARROWMODZ_GAMES
        api_key = API_KEY_ARROWMODZ

    try:
        # Menembak API untuk mendapatkan list game
        response = requests.post(url_games, data={'api_key': api_key})
        data = response.json()

        if data.get("status") == True:
            markup = InlineKeyboardMarkup(row_width=1)
            games = data.get("data", [])
            
            # Melakukan perulangan untuk membuat tombol setiap game
            for game in games:
                game_name = game.get("game")
                game_code = game.get("code")
                game_status = game.get("status", "")
                
                btn_text = f"🕹️ {game_name}"
                if game_status.lower() != "safe":
                    btn_text += f" ({game_status})" # Tambah info jika maintenance/update
                
                # Simpan brand dan game_code di callback data (contoh: game_veloura_MLBB)
                markup.add(InlineKeyboardButton(btn_text, callback_data=f"game_{brand}_{game_code}"))

            markup.add(InlineKeyboardButton("🔙 Batal", callback_data="cancel_order"))
            
            bot.edit_message_text(f"Anda memilih **{brand.title()}**.\nSilakan pilih Game:", 
                                  chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.edit_message_text(f"❌ Gagal mengambil daftar game dari {brand.title()}:\n{data.get('message')}", 
                                  chat_id=call.message.chat.id, message_id=call.message.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Terjadi kesalahan saat menghubungi server {brand.title()}.", 
                              chat_id=call.message.chat.id, message_id=call.message.message_id)

# TAHAP 3: MENU DURASI (Setelah Game Dipilih)
@bot.callback_query_handler(func=lambda call: call.data.startswith('game_'))
def process_game_selection(call):
    bot.answer_callback_query(call.id)
    
    # Memecah callback (contoh: "game_veloura_MLBB" -> brand="veloura", game_code="MLBB")
    parts = call.data.split('_')
    brand = parts[1]
    game_code = parts[2]

    markup = InlineKeyboardMarkup(row_width=2)
    # Callback data sekarang membawa durasi (contoh: dur_veloura_MLBB_1)
    markup.add(
        InlineKeyboardButton("1 Hari (15k)", callback_data=f"dur_{brand}_{game_code}_1"),
        InlineKeyboardButton("3 Hari (25k)", callback_data=f"dur_{brand}_{game_code}_3"),
        InlineKeyboardButton("7 Hari (50k)", callback_data=f"dur_{brand}_{game_code}_7"),
        InlineKeyboardButton("30 Hari (100k)", callback_data=f"dur_{brand}_{game_code}_30"),
        InlineKeyboardButton("60 Hari (200k)", callback_data=f"dur_{brand}_{game_code}_60"),
        InlineKeyboardButton("90 Hari (250k)", callback_data=f"dur_{brand}_{game_code}_90"),
        InlineKeyboardButton("🔙 Batal", callback_data="cancel_order")
    )
    bot.edit_message_text(f"Game: **{game_code}** ({brand.title()}).\nSilakan pilih durasi paket:", 
                          chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_order')
def cancel_order(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("❌ Order dibatalkan.", chat_id=call.message.chat.id, message_id=call.message.message_id)

# TAHAP 4: PROSES LINK PEMBAYARAN MIDTRANS
@bot.callback_query_handler(func=lambda call: call.data.startswith('dur_'))
def process_payment_link(call):
    # Memecah callback (contoh: "dur_veloura_MLBB_7")
    parts = call.data.split('_')
    brand = parts[1]
    game_code = parts[2]
    durasi = int(parts[3])
    
    if brand == "veloura":
        harga = HARGA_VELOURA.get(durasi, 0)
    else:
        harga = HARGA_ARROWMODZ.get(durasi, 0)
        
    chat_id = call.message.chat.id
    nama_user = call.from_user.first_name
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text("⏳ Sedang membuat link pembayaran aman via Midtrans...", chat_id=chat_id, message_id=call.message.message_id)

    order_id = f"{brand[:2].upper()}-{chat_id}-{int(time.time())}" 
    
    # Simpan semua detail ke memori (brand, game_code, durasi)
    pending_orders[order_id] = {
        "chat_id": chat_id, "nama_user": nama_user, "durasi": durasi, 
        "brand": brand, "game_code": game_code
    }

    payload_midtrans = {
        "transaction_details": {"order_id": order_id, "gross_amount": harga},
        "customer_details": {"first_name": nama_user, "notes": f"Pelanggan {brand.title()}"},
        "item_details": [{"id": f"{brand}-{game_code}-{durasi}D", "price": harga, "quantity": 1, "name": f"{brand.title()} {game_code} {durasi} Hari"}]
    }

    try:
        response = requests.post(MIDTRANS_URL, json=payload_midtrans, auth=(MIDTRANS_SERVER_KEY, ''))
        data_midtrans = response.json()

        if response.status_code == 201:
            payment_url = data_midtrans['redirect_url']
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("💳 Bayar Sekarang", url=payment_url))
            bot.edit_message_text(
                f"📝 **INVOICE ORDER**\n\n📦 Produk: {brand.title()} ({game_code})\n⏳ Durasi: {durasi} Hari\n💰 Total: Rp {harga:,}\n\nKlik tombol di bawah untuk membayar.",
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
            brand = order_data["brand"]
            game_code = order_data["game_code"]

            bot.send_message(chat_id, f"✅ Pembayaran diterima! Sedang meng-generate License {brand.title()} untuk game {game_code}...")

            # Menyiapkan request ke API pembuat License
            if brand == "veloura":
                url_api_order = URL_API_VELOURA_ORDER
                api_key_order = API_KEY_VELOURA
            elif brand == "arrowmodz":
                url_api_order = URL_API_ARROWMODZ_ORDER
                api_key_order = API_KEY_ARROWMODZ

            # Parameter game mengambil langsung dari pilihan user (game_code)
            payload_api = {"api_key": api_key_order, "nama": nama_user, "durasi": durasi, "game": game_code, "max_devices": 1} 

            try:
                res_api = requests.post(url_api_order, data=payload_api)
                data_api_response = res_api.json()

                if data_api_response.get("status") == True:
                    license_key = data_api_response.get("data", {}).get("License") or data_api_response.get("data", {}).get("license") or "[KEY TIDAK DITEMUKAN]"
                    balasan = f"🎉 **TERIMA KASIH! ORDER SELESAI**\n\n👤 Nama: {nama_user}\n📦 Game: {game_code} ({brand.title()})\n⏳ Paket: {durasi} Hari\n🔑 License: `{license_key}`\n\n*(Ketuk license di atas untuk menyalin)*"
                    bot.send_message(chat_id, balasan, parse_mode='Markdown')
                else:
                    bot.send_message(chat_id, f"⚠️ Pembayaran masuk, tapi gagal generate key {brand.title()}:\n{data_api_response.get('message', 'Error')}\nHubungi Admin.")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Pembayaran berhasil, tapi terjadi error server {brand.title()}.")
            
            del pending_orders[order_id]

    return jsonify({"status": "ok"}), 200

@app.route('/')
def index():
    return "Server Webhook Multi-Brand & Dynamic Games Berjalan Lancar! 🚀", 200

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
