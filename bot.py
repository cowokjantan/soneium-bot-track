import asyncio
import json
import os
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.markdown import hlink

# Konfigurasi bot
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
API_URL = "https://soneium.blockscout.com/api?module=account&action=txlist&address="
EXPLORER_URL = "https://soneium.blockscout.com/tx/"

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

# File untuk menyimpan alamat dan hash transaksi
ADDRESSES_FILE = "tracked_addresses.json"
TX_FILE = "sent_transactions.json"

# Load data dari file
def load_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}

def save_data(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

# Data alamat yang dilacak dan transaksi yang dikirim
tracked_addresses = load_data(ADDRESSES_FILE)  # {chat_id: {address: name}}
sent_transactions = load_data(TX_FILE)  # {tx_hash: True}

# Handler /start
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("👋 Halo! Kirimkan perintah:\n"
                         "✅ /add <alamat> <nama> → Tambah alamat\n"
                         "📜 /list → Lihat daftar alamat\n"
                         "❌ /remove <alamat> → Hapus alamat\n")

# Handler untuk menambahkan alamat
@dp.message(Command("add"))
async def add_address(message: Message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("⚠️ Format salah! Gunakan: /add <alamat> <nama>")
            return

        address, name = parts[1], " ".join(parts[2:])
        chat_id = str(message.chat.id)

        if chat_id not in tracked_addresses:
            tracked_addresses[chat_id] = {}

        tracked_addresses[chat_id][address] = name
        save_data(ADDRESSES_FILE, tracked_addresses)
        
        await message.answer(f"✅ Alamat `{address}` dengan nama **{name}** berhasil ditambahkan!")
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

# Handler untuk melihat daftar alamat
@dp.message(Command("list"))
async def list_addresses(message: Message):
    chat_id = str(message.chat.id)
    if chat_id not in tracked_addresses or not tracked_addresses[chat_id]:
        await message.answer("📭 Tidak ada alamat yang dilacak.")
        return

    msg = "📜 **Daftar Alamat yang Dilacak:**\n"
    for addr, name in tracked_addresses[chat_id].items():
        msg += f"🔹 **{name}**: `{addr}`\n"

    await message.answer(msg)

# Handler untuk menghapus alamat
@dp.message(Command("remove"))
async def remove_address(message: Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("⚠️ Format salah! Gunakan: /remove <alamat>")
            return

        address = parts[1]
        chat_id = str(message.chat.id)

        if chat_id in tracked_addresses and address in tracked_addresses[chat_id]:
            del tracked_addresses[chat_id][address]
            save_data(ADDRESSES_FILE, tracked_addresses)
            await message.answer(f"✅ Alamat `{address}` telah dihapus.")
        else:
            await message.answer("⚠️ Alamat tidak ditemukan.")
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

# Fungsi untuk mengambil transaksi
async def fetch_transactions(address):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL + address) as response:
                data = await response.json()
                return data.get("result", []) if data.get("status") == "1" else []
    except Exception as e:
        logging.error(f"Error fetching transactions: {e}")
        return []

# Fungsi utama untuk mengecek transaksi baru
async def check_transactions():
    while True:
        try:
            for chat_id, addresses in tracked_addresses.items():
                for address, name in addresses.items():
                    transactions = await fetch_transactions(address)
                    for tx in transactions:
                        tx_hash = tx["hash"]

                        # Cek apakah transaksi sudah dikirim sebelumnya
                        if tx_hash in sent_transactions:
                            continue

                        from_address = tx["from"]
                        to_address = tx["to"]
                        value = int(tx["value"]) / 10**18
                        token_symbol = "SONE"

                        # Klasifikasi transaksi
                        if to_address.lower() == address.lower():
                            tx_type = "📥 RECEIVE"
                        elif from_address.lower() == address.lower():
                            tx_type = "📤 SEND"
                        else:
                            tx_type = "🔄 UNKNOWN"

                        # Format pesan dengan tautan ke Blockscout
                        tx_link = hlink("🔗 Lihat di Explorer", EXPLORER_URL + tx_hash)
                        message = (
                            f"🔔 **Transaksi Baru**\n"
                            f"👤 Dari: `{from_address}`\n"
                            f"📩 Ke: `{to_address}`\n"
                            f"💰 Jumlah: `{value} {token_symbol}`\n"
                            f"📌 Jenis: `{tx_type}`\n"
                            f"{tx_link}"
                        )

                        # Kirim notifikasi ke user
                        await bot.send_message(chat_id, message)

                        # Tandai transaksi sudah dikirim
                        sent_transactions[tx_hash] = True
                        save_data(TX_FILE, sent_transactions)

        except Exception as e:
            logging.error(f"Error checking transactions: {e}")

        await asyncio.sleep(10)  # Periksa setiap 10 detik

# Jalankan bot dan pemantauan transaksi
async def main():
    asyncio.create_task(check_transactions())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
