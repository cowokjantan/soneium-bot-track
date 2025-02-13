import os
import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiohttp import ClientSession

# Load environment variables
TOKEN = os.getenv("BOT_TOKEN")
BLOCKSCOUT_API = "https://soneium.blockscout.com/api"
DATABASE_FILE = "database.json"

# Cek apakah token bot tersedia
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN tidak ditemukan! Pastikan sudah diatur di Railway Variables.")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Inisialisasi logging
logging.basicConfig(level=logging.INFO)

# Fungsi untuk menyimpan database transaksi yang sudah dikirim
def load_db():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "r") as f:
            return json.load(f)
    return {"tracked_addresses": {}, "sent_tx_hashes": set()}

def save_db(db):
    with open(DATABASE_FILE, "w") as f:
        json.dump(db, f)

db = load_db()

# Fungsi untuk menambahkan alamat ke daftar tracking
@dp.message(commands=["add"])
async def add_address(message: Message):
    args = message.text.split()
    if len(args) < 3:
        await message.reply("⚠️ Format salah!\nGunakan: `/add <alamat> <nama>`")
        return

    address, name = args[1], " ".join(args[2:])
    
    db["tracked_addresses"][address.lower()] = name
    save_db(db)
    await message.reply(f"✅ Alamat <b>{name}</b> berhasil ditambahkan untuk tracking!")

# Fungsi untuk menghapus alamat dari daftar tracking
@dp.message(commands=["remove"])
async def remove_address(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("⚠️ Format salah!\nGunakan: `/remove <alamat>`")
        return

    address = args[1].lower()
    if address in db["tracked_addresses"]:
        name = db["tracked_addresses"].pop(address)
        save_db(db)
        await message.reply(f"✅ Alamat <b>{name}</b> telah dihapus dari tracking.")
    else:
        await message.reply("❌ Alamat tidak ditemukan dalam daftar tracking.")

# Fungsi untuk melihat daftar alamat yang dipantau
@dp.message(commands=["list"])
async def list_addresses(message: Message):
    if not db["tracked_addresses"]:
        await message.reply("ℹ️ Tidak ada alamat yang sedang dipantau.")
        return
    
    text = "🔍 <b>Daftar Alamat yang Dipantau:</b>\n"
    for address, name in db["tracked_addresses"].items():
        text += f"- {name} → `{address}`\n"
    await message.reply(text, parse_mode="HTML")

# Fungsi untuk mengecek transaksi terbaru dari Blockscout API
async def check_transactions():
    session = ClientSession()
    while True:
        try:
            for address, name in db["tracked_addresses"].items():
                url = f"{BLOCKSCOUT_API}/v2/addresses/{address}/transactions"
                async with session.get(url) as response:
                    if response.status == 200:
                        transactions = await response.json()
                        for tx in transactions.get("items", []):
                            tx_hash = tx["hash"]
                            if tx_hash in db["sent_tx_hashes"]:
                                continue  # Hindari notifikasi berulang
                            
                            sender = tx["from"]["hash"]
                            receiver = tx["to"]["hash"]
                            value = int(tx["value"]) / 10**18  # Konversi dari wei
                            tx_link = f"https://soneium.blockscout.com/tx/{tx_hash}"

                            # Identifikasi jenis transaksi
                            if sender == address:
                                if tx.get("method") == "buyNFT":
                                    tx_type = "🛒 Buy NFT"
                                else:
                                    tx_type = "📤 Sent"
                            elif receiver == address:
                                if tx.get("method") == "sellNFT":
                                    tx_type = "💰 Sell NFT"
                                else:
                                    tx_type = "📥 Received"
                            else:
                                tx_type = "🔄 Other"

                            # Kirim notifikasi ke Telegram
                            text = f"🔔 <b>Transaksi Baru untuk {name}</b>\n"
                            text += f"🔹 Jenis: <b>{tx_type}</b>\n"
                            text += f"💰 Jumlah: {value} SONE\n"
                            text += f"🔗 <a href='{tx_link}'>Lihat di Explorer</a>"

                            await bot.send_message(chat_id=os.getenv("CHAT_ID"), text=text)
                            db["sent_tx_hashes"].add(tx_hash)
                            save_db(db)

        except Exception as e:
            logging.error(f"Error saat cek transaksi: {e}")

        await asyncio.sleep(10)  # Cek setiap 10 detik

# Fungsi untuk memulai bot
async def main():
    loop = asyncio.get_running_loop()
    loop.create_task(check_transactions())  # Mulai tracking transaksi
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
