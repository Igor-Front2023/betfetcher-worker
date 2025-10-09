class Notifier:
    def __init__(self, bot, admin_id: int):
        self.bot = bot
        self.admin_id = admin_id

    async def notify(self, text: str):
        try:
            await self.bot.send_message(chat_id=self.admin_id, text=text)
        except Exception as e:
            print("Notifier error:", e)
