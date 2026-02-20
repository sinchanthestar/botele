import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
import time
from flask import Flask, request, jsonify
import threading
import os # WAJIB DITAMBAHKAN UNTUK RAILWAY

# ==========================================
# KONFIGURASI UTAMA
# ==========================================
# 1. Telegram Token
TOKEN = '8390879657:AAGvN0dI-P7r6hM2eIifNGSz-rwE6JJSUxw'
bot = telebot.TeleBot(TOKEN)

# 2. Veloura API Key
API_KEY_VELOURA = 'IMyIc3-D1TEqA-GpAoZb-CtKWc2'

# 3. Midtrans Konfigurasi (GANTI DENGAN SERVER KEY SANDBOX ANDA)
MIDTRANS_SERVER_KEY = '
Mid-server-Aa6IQjd6Gx4YTuuG9-aDbz25' 
MIDTRANS_URL = 'https://app.sandbox.midtrans.com/snap/v1/transactions'

app = Flask(__name__)
pending_orders = {}

HARGA_VELOURA = {
    1: 15000, 3: 25000, 7: 50000, 
    30: 100000, 60: 200000, 90: 250000
}

# ==========================================
# BAGIAN 1: LOGIKA BOT TELEGRAM
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Halo! 👋\nKetik /order untuk mulai membuat license key otomatis.")

@bot.message_handler(commands=['order'])
def send_brand_menu(message):
    markup = InlineKeyboardMarkup(row_width=1)
    btn_veloura = InlineKeyboardButton("🎮 Veloura MLBB", callback_data="brand_veloura")
    markup.add(btn_veloura)
    bot.reply_to(message, "Silakan pilih Produk/Brand yang ingin Anda order:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'brand_veloura')
def process_brand_selection(call):
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    
    btn1 = InlineKeyboardButton("1 Hari (15k)", callback_data="veloura_1")
    btn3 = InlineKeyboardButton("3 Hari (25k)", callback_data="veloura_3")
    btn7 = InlineKeyboardButton("7 Hari (50k)", callback_data="veloura_7")
    btn30 = InlineKeyboardButton("30 Hari (100k)", callback_data="veloura_30")
    btn60 = InlineKeyboardButton("60 Hari (200k)", callback_data="veloura_60")
    btn90 = InlineKeyboardButton("90 Hari (250k)", callback_data="veloura_90")
    btn_back = InlineKeyboardButton("🔙 Batal", callback_data="cancel_order")
    
    markup.add(btn1, btn3, btn7, btn30, btn60, btn90, btn_back)
    
    bot.edit_message_text(
        "Anda memilih **Veloura MLBB**.\nSilakan pilih durasi paket:", 
        chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown'
    )

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
            btn_pay = InlineKeyboardButton("💳 Bayar Sekarang", url=payment_url)
            markup.add(btn_pay)
            
            bot.edit_message_text(
                f"📝 **INVOICE ORDER**\n\n"
                f"📦 Produk: Veloura MLBB ({durasi} Hari)\n"
                f"💰 Total: Rp {harga:,}\n\n"
                f"Klik tombol di bawah untuk membayar. "
                f"License akan otomatis dikirim ke sini setelah sukses.",
                chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown'
            )
        else:
            bot.edit_message_text(f"❌ Gagal membuat pembayaran: {data_midtrans.get('error_messages', ['Error'])[0]}", chat_id=chat_id, message_id=call.message.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Terjadi kesalahan sistem pembayaran.", chat_id=chat_id, message_id=call.message.message_id)


# ==========================================
# BAGIAN 2: WEB SERVER FLASK (UNTUK WEBHOOK)
# ==========================================
@app.route('/webhook/midtrans', methods=['POST'])
def midtrans_webhook():
    data = request.json
    print(f"\n[WEBHOOK MASUK] Notifikasi: {data.get('transaction_status')} Order: {data.get('order_id')}")

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
            payload_veloura = {
                "api_key": API_KEY_VELOURA, "nama": nama_user, "durasi": durasi, "game": "MLBB", "max_devices": 1
            }

            try:
                res_veloura = requests.post(url_veloura, data=payload_veloura)
                data_veloura = res_veloura.json()

                if data_veloura.get("status") == True:
                    data_api = data_veloura.get("data", {})
                    license_key = data_api.get("License") or data_api.get("license") or "[KEY TIDAK DITEMUKAN]"
                    
                    balasan = (
                        f"🎉 **TERIMA KASIH! ORDER SELESAI**\n\n"
                        f"👤 Nama: {nama_user}\n"
                        f"📦 Paket: {durasi} Hari\n"
                        f"🔑 License: `{license_key}`\n\n"
                        f"*(Ketuk license di atas untuk menyalin)*"
                    )
                    bot.send_message(chat_id, balasan, parse_mode='Markdown')
                else:
                    error_msg = data_veloura.get("message", "Error sistem Veloura.")
                    bot.send_message(chat_id, f"⚠️ Pembayaran masuk, tapi gagal generate key:\n{error_msg}\nHubungi Admin.")

            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Pembayaran berhasil, tapi terjadi error saat menghubungi server Veloura.")
            
            del pending_orders[order_id]

    return jsonify({"status": "ok"}), 200

# ==========================================
# BAGIAN 3: MENJALANKAN (PENYESUAIAN RAILWAY)
# ==========================================
def run_bot():
    print("🤖 Bot Telegram sedang berjalan...")
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot).start()
    
    # RAILWAY MENGGUNAKAN DYNAMIC PORT
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Server Webhook berjalan di port {port}...")
    
    # Host diubah menjadi 0.0.0.0 agar bisa diakses internet
    app.run(host='0.0.0.0', port=port)
