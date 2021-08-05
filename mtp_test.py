import asyncio

import socks
from telethon import TelegramClient, functions

# Configuration
proxy = (socks.SOCKS5, 'localhost', 7890)
api_id = 7000000
api_hash = '506828842c80ea408b94d1**********'
bot = TelegramClient('Bot', api_id, api_hash, proxy=proxy).start(bot_token='16679*****:***hCZ-*******RNRx9BYd-Hb**********')


async def main():
    # Find user by username
    user = await bot(functions.contacts.ResolveUsernameRequest(username='hykilpikonna'))
    print(user)
    print()
    user = user.users[0]
    name = user.first_name + (' ' + user.last_name if user.last_name else '')
    print(name)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
