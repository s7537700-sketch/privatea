import asyncio
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from maxapi import Bot, Dispatcher

from bot.handlers import register_all
from bot.services import _keepalive

log = logging.getLogger("library-bot")


class App:
    def __init__(self) -> None:
        token = os.getenv("MAX_BOT_TOKEN")
        if not token:
            raise SystemExit("MAX_BOT_TOKEN env var not set")
        self.bot = Bot(token)
        self.dp = Dispatcher()

    def setup(self) -> None:
        register_all(self.bot, self.dp)

    async def run(self) -> None:
        _keepalive()
        try:
            await self.bot.delete_webhook()
        except Exception:
            pass
        log.info("polling start...")
        await self.dp.start_polling(self.bot)


async def main() -> None:
    app = App()
    app.setup()
    await app.run()


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO)
    asyncio.run(main())
