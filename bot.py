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
TOKEN = 'TOKEN_BOT_TELEGRAM_ANDA' # Masukkan Token (Jika tadi direset, masukkan yang baru)
bot = telebot.TeleBot(TOKEN)

API_KEY_VELOURA = 'IMyIc3-D1TEqA-GpAoZb-CtKWc2'
MIDTRANS_SERVER_KEY = 'SB-Mid-server-Aa6IQjd6Gx4YTuuG9-aDbz25' # Masukkan Server Key Sandbox Midtrans
MIDTRANS_URL = 'https://app.sandbox.midtrans.com/snap/v1/transactions'

# WAJIB DIISI! Masukkan URL publik Railway Anda (Tanpa garis miring di akhir)
# Contoh: 'https://bot-veloura-production.up.railway.app'
WEBHOOK_URL_BASE = 'https://botele-production.up.railway.app' 

app = Flask(__name__)
pending_orders = {}

HARGA_VELOURA = {1: 15000, 3: 25000, 7: 50000, 30: 100000, 60: 200000, 90: 250000}

# ==========================================
# 2. LOGIKA BOT TELEGRAM
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Halo! 👋\nKetik /order untuk mulai membuat license key otomatis.")

@bot.message_handler(commands=['order'])
def send_brand_menu(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🎮 Veloura MLBB", callback_data="brand_veloura"))
    bot.reply_to(message, "Silakan pilih Produk/Brand yang ingin Anda order:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'brand_veloura')
def process_brand_selection(call):
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

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_order')
def cancel_order(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("❌ Order dibatalkan.", chat_id=call.message.chat.id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('veloura_'))
def process_payment_link(call):
    durasi = int(call.data.split('_')[1])
    harga = HARGA_VELOURA.get(durasi, 0)
    chat_id = call.message.chat.id
    nama_user = call.from_user.first_name
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text("⏳ Sedang membuat link pembayaran aman via Midtrans...", chat_id=chat_id, message_id=call.message.message_id)

    order_id = f"VL-{chat_id}-{int(time.time())}"
    pending_orders[order_id] = {"chat_id": chat_id, "nama_user": nama_user, "durasi": durasi}

    payload_midtrans = {
        "transaction_details": {"order_id": order_id, "gross_amount": harga},
        "customer_details": {"first_name": nama_user, "notes": "Pelanggan Telegram Bot"},
        "item_details": [{"id": f"MLBB-{durasi}D", "price": harga, "quantity": 1, "name": f"License MLBB {durasi} Hari"}]
    }

    try:
        response = requests.post(MIDTRANS_URL, json=payload_midtrans, auth=(MIDTRANS_SERVER_KEY, ''))
        data_midtrans = response.json()

        if response.status_code == 201:
            payment_url = data_midtrans['redirect_url']
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("💳 Bayar Sekarang", url=payment_url))
            bot.edit_message_text(
                f"📝 **INVOICE ORDER**\n\n📦 Produk: Veloura MLBB ({durasi} Hari)\n💰 Total: Rp {harga:,}\n\nKlik tombol di bawah untuk membayar. License akan otomatis dikirim ke sini.",
                chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown'
            )
        else:
            bot.edit_message_text("❌ Gagal membuat link pembayaran.", chat_id=chat_id, message_id=call.message.message_id)
    except Exception as e:
        bot.edit_message_text("❌ Terjadi kesalahan sistem pembayaran.", chat_id=chat_id, message_id=call.message.message_id)

# ==========================================
# 3. FLASK ROUTES (WEBHOOKS)
# ==========================================
# A. Route untuk Menerima Pesan dari Telegram
@app.route(f'/{TOKEN}', methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Forbidden', 403

# B. Route untuk Menerima Notifikasi dari Midtrans
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

            bot.send_message(chat_id, "✅ Pembayaran diterima! Sedang meng-generate License Veloura Anda...")

            url_veloura = "https://velouramlbb.biz.id/api/order/register"
            payload_veloura = {"api_key": API_KEY_VELOURA, "nama": nama_user, "durasi": durasi, "game": "MLBB", "max_devices": 1}

            try:
                res_veloura = requests.post(url_veloura, data=payload_veloura)
                data_veloura = res_veloura.json()

                if data_veloura.get("status") == True:
                    license_key = data_veloura.get("data", {}).get("License") or data_veloura.get("data", {}).get("license") or "[KEY TIDAK DITEMUKAN]"
                    balasan = f"🎉 **TERIMA KASIH! ORDER SELESAI**\n\n👤 Nama: {nama_user}\n📦 Paket: {durasi} Hari\n🔑 License: `{license_key}`\n\n*(Ketuk license di atas untuk menyalin)*"
                    bot.send_message(chat_id, balasan, parse_mode='Markdown')
                else:
                    bot.send_message(chat_id, f"⚠️ Pembayaran masuk, tapi gagal generate key:\n{data_veloura.get('message', 'Error')}\nHubungi Admin.")
            except Exception as e:
                bot.send_message(chat_id, "⚠️ Pembayaran berhasil, tapi terjadi error server Veloura.")
            
            del pending_orders[order_id]

    return jsonify({"status": "ok"}), 200

# C. Route Utama untuk Pengecekan
@app.route('/')
def index():
    return "Server Webhook Bot Telegram & Midtrans Berjalan Lancar! 🚀", 200

# ==========================================
# 4. MENJALANKAN SERVER
# ==========================================
if __name__ == '__main__':
    # Hapus Webhook lama dan pasang Webhook baru ke URL Railway
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{WEBHOOK_URL_BASE}/{TOKEN}")
    print("✅ Webhook Telegram Berhasil Dipasang!")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
