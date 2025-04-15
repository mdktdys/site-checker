import asyncio
import hashlib
import logging
import ssl
import json
import os
from aiohttp import ClientSession, TCPConnector
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

DATA_FILE = "data/data.json"

# 🔧 Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 🤖 Telegram Bot
TOKEN = os.getenv('TOKEN')
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# 💾 Данные пользователя
user_sites: dict[int, dict[str, str]] = {}


# 📥 Загрузка данных из файла
def load_data():
    global user_sites
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                user_sites = json.load(f)
                user_sites = {int(k): v for k, v in user_sites.items()}
                logger.info("📂 Данные загружены из файла")
            except Exception as e:
                logger.warning(f"Ошибка загрузки данных: {e}")


# 💾 Сохранение данных в файл
def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_sites, f, ensure_ascii=False, indent=2)
        logger.info("💾 Данные сохранены в файл")
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")


async def fetch_site_content(url: str) -> str:
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with ClientSession(connector=TCPConnector(ssl=ssl_context)) as session:
            async with session.get(url, timeout=10) as response:
                return await response.text()
    except Exception as e:
        logger.warning(f"❌ Ошибка запроса к {url}: {e}")
        return ""


def get_hash(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()


async def check_sites():
    while True:
        logger.info("🔍 Проверка сайтов...")
        for user_id, sites in user_sites.items():
            for url in list(sites.keys()):
                content = await fetch_site_content(url)
                if not content:
                    continue
                new_hash = get_hash(content)
                if sites[url] != new_hash:
                    sites[url] = new_hash
                    save_data()
                    logger.info(f"🔄 Обнаружено изменение на {url} для пользователя {user_id}")
                    try:
                        await bot.send_message(user_id, f"🔄 Страница изменилась: <code>{url}</code>")
                    except Exception as e:
                        logger.error(f"❗ Ошибка отправки сообщения пользователю {user_id}: {e}")
                else:
                    logger.info(f"Не обнаружено изменение на {url} для пользователя {user_id}")
        await asyncio.sleep(300)  # 5 минут


@dp.message(Command("start"))
async def cmd_start(message: Message):
    logger.info(f"👋 Пользователь {message.from_user.id} начал работу")
    await message.answer("Привет! Пришли мне ссылку на сайт, и я буду отслеживать его изменения.\n"
                         "Команды:\n"
                         "/list — список сайтов\n"
                         "/remove <url> — удалить сайт")


@dp.message(Command("list"))
async def cmd_list(message: Message):
    user_id = message.from_user.id
    sites = user_sites.get(user_id, {})
    if not sites:
        await message.answer("У тебя пока нет отслеживаемых сайтов.")
        return
    msg = "\n".join([f"🔗 <code>{url}</code>" for url in sites.keys()])
    logger.info(f"📋 Пользователь {user_id} запросил список сайтов")
    await message.answer(f"Твои сайты:\n{msg}")


@dp.message(Command("remove"))
async def cmd_remove(message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Используй команду так: /remove <URL>")
        return
    url = args[1].strip()
    if user_id in user_sites and url in user_sites[user_id]:
        del user_sites[user_id][url]
        save_data()
        logger.info(f"❌ Пользователь {user_id} удалил сайт {url}")
        await message.answer(f"Удалил сайт из отслеживания: <code>{url}</code>")
    else:
        await message.answer("Этот сайт не найден в списке.")


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_link(message: Message):
    url = message.text.strip()
    user_id = message.from_user.id

    if not url.startswith("http"):
        await message.answer("Пожалуйста, пришли корректную ссылку.")
        return

    content = await fetch_site_content(url)
    if not content:
        await message.answer("Не удалось получить доступ к сайту.")
        return

    site_hash = get_hash(content)
    if user_id not in user_sites:
        user_sites[user_id] = {}
    user_sites[user_id][url] = site_hash
    save_data()

    logger.info(f"✅ Пользователь {user_id} добавил сайт {url}")
    await message.answer(f"Добавил сайт в отслеживание: <code>{url}</code>")


async def main():
    load_data()
    logger.info("🚀 Бот запущен")
    asyncio.create_task(check_sites())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
