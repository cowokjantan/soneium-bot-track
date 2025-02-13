import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://soneium-api.com/transactions"  # Ganti dengan API Soneium

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

addresses = set()

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply("Kirim alamat Soneium yang ingin Anda lacak.")

@dp.message_handler()
async def track_address(message: types.Message):
    address = message.text.strip()
    if len(address) == 42 and address.startswith("0x"):  # Validasi alamat
        addresses.add(address)
        await message.reply(f"Alamat {address} telah ditambahkan untuk dilacak.")
    else:
        await message.reply("Alamat tidak valid. Coba lagi.")

async def check_transactions():
    while True:
        for address in addresses:
            response = requests.get(f"{API_URL}?address={address}")
            data = response.json()
            if data.get("transactions"):
                for tx in data["transactions"]:
                    await bot.send_message(message.chat.id, f"Transaksi baru: {tx}")
        await asyncio.sleep(30)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(check_transactions())
    executor.start_polling(dp, skip_updates=True)
