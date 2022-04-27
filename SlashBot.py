from __future__ import annotations

import os
import sys
import re
import requests
import telegram
from loguru import logger as _logger
from typing import Optional, Union, Any
from telegram.ext import Updater, MessageHandler, filters, Dispatcher
from functools import partial
from threading import Thread
from time import sleep

Filters = filters.Filters
parser = re.compile(r'^(?P<slash>[\\/]_?)'
                    r'(?P<predicate>([^\s\\]|\\.)*((?<=\S)\\)?)'
                    r'(\s+(?P<complement>.+))?$')
convertEscapes = partial(re.compile(r'\\(\s)').sub, r'\1')
htmlEscape = lambda s: s.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
mentionParser = re.compile(r'@([a-zA-Z]\w{4,})')

PUNCTUATION_TAIL = '.,?!;:~(' \
                   '。，？！；：～（'

# Docker env
TOKENS = re.compile(r'[^a-zA-Z\-_\d:]+').split(os.environ.get('TOKEN', ''))
if not TOKENS:
    raise ValueError('no any valid token found')

TELEGRAM_PROXY = os.environ.get('PROXY', '')
REQUEST_PROXIES = {'all': TELEGRAM_PROXY} if TELEGRAM_PROXY else None

_logger.remove()
_logger.add(sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>"
                   "|<level>{level:^8}</level>"
                   "|<cyan>{extra[username]:^15}</cyan>"
                   "|<level>{message}</level>",
            level="DEBUG")

_updaters: list[Updater] = []


class User:
    def __init__(self, uid: Optional[int] = None, username: Optional[str] = None, name: Optional[str] = None):
        if not (uid and name) and not username:
            raise ValueError('invalid user')
        self.name = name
        self.uid = uid
        self.username = username
        if not self.name and self.username:
            self.__get_user_by_username()

    def __get_user_by_username(self):
        r = requests.get(f'https://t.me/{self.username}', proxies=REQUEST_PROXIES)
        self.name = re.search(r'(?<=<meta property="og:title" content=").*(?=")', r.text, re.IGNORECASE).group(0)
        page_title = re.search(r'(?<=<title>).*(?=</title>)', r.text, re.IGNORECASE).group(0)
        if page_title == self.name:  # user does not exist
            self.name = None

    def mention(self, mention_self: bool = False, pure: bool = False) -> str:
        if not self.name:
            return f'@{self.username}'

        mention_deep_link = (f'tg://resolve?domain={self.username}'
                             if (self.username and (not self.uid or self.uid < 0))
                             else f'tg://user?id={self.uid}')
        name = self.name if not mention_self else "自己"
        return f'<a href="{mention_deep_link}">{name}</a>' if not pure else name

    def __eq__(self, other):
        return (
                type(self) == type(other)
                and (
                        ((self.uid or other.uid) and self.uid == other.uid) or
                        ((self.username or other.username) and self.username == other.username)
                )
        )


def get_user(msg: telegram.Message) -> User:
    user = msg.sender_chat or msg.from_user
    return User(name=user.full_name or user.title, uid=user.id, username=user.username)


def get_users(msg: telegram.Message) -> tuple[User, User]:
    msg_from = msg
    msg_rpl = msg.reply_to_message or msg_from
    from_user, rpl_user = get_user(msg_from), get_user(msg_rpl)
    return from_user, rpl_user


def parse_command(ctx: telegram.ext.CallbackContext) -> dict[str, Union[str, bool]]:
    match = ctx.match
    parsed = match.groupdict()
    predicate = parsed['predicate']
    omit_le = predicate.endswith('\\')
    predicate = predicate[:-1] if omit_le else predicate
    predicate = convertEscapes(predicate)
    predicate = ctx.bot_data['delUsername'](predicate)
    result = {'predicate': htmlEscape(predicate),
              'complement': htmlEscape(parsed['complement'] or ''),
              'slash': parsed['slash'],
              'swap': parsed['slash'] != '/',
              'omit_le': omit_le}
    return result


def get_tail(tail_char: str) -> str:
    if tail_char in PUNCTUATION_TAIL:
        return ''
    halfwidth_mark = tail_char.isascii()
    return '!' if halfwidth_mark else '！'


def get_text(user_from: User, user_rpl: User, command: dict):
    rpl_self = user_from == user_rpl
    mention_from = user_from.mention()
    mention_rpl = user_rpl.mention(mention_self=rpl_self)
    slash, predicate, complement, omit_le = \
        command['slash'], command['predicate'], command['complement'], command['omit_le']

    if predicate == '':
        ret = '!' if slash == '/' else '¡'
    elif predicate == 'me':
        ret = f"{mention_from}{bool(complement) * ' '}{complement}"
        ret += get_tail((complement or user_from.mention(pure=True))[-1])
    elif predicate == 'you':
        ret = f"{mention_rpl}{bool(complement) * ' '}{complement}"
        ret += get_tail((complement or user_rpl.mention(mention_self=rpl_self, pure=True))[-1])
    elif complement:
        ret = f"{mention_from} {predicate} {mention_rpl} {complement}"
        ret += get_tail(complement[-1])
    else:
        ret = f"{mention_from} {predicate} "
        ret += '了 ' if not omit_le else ''
        ret += mention_rpl
        ret += get_tail(mention_rpl[-1])
    return ret


def reply(update: telegram.Update, ctx: telegram.ext.CallbackContext):
    logger = ctx.bot_data['logger']
    logger.debug(str(update.to_dict()))
    msg = update.effective_message
    from_user, rpl_user = get_users(msg)
    command = parse_command(ctx)

    if from_user == rpl_user:
        mention_match = mentionParser.search(command['predicate'])
        if mention_match:
            mention = mentionParser.search(msg.text).group(1)
            rpl_user = User(username=mention)
            command['predicate'] = command['predicate'][:mention_match.start()]
        else:
            mention_match = mentionParser.search(command['complement'])
            if mention_match:
                mention = mentionParser.search(msg.text).group(1)
                rpl_user = User(username=mention)
                complement = command['complement']
                complement = complement[:mention_match.start()] + complement[mention_match.end():]
                command['complement'] = complement.strip()

    if command['swap'] and (not from_user == rpl_user):
        (from_user, rpl_user) = (rpl_user, from_user)

    text = get_text(from_user, rpl_user, command)
    logger.info(text)

    update.effective_message.reply_text('\u200e' + text, parse_mode='HTML')


def start(token: str):
    updater = Updater(token=token, use_context=True, request_kwargs={'proxy_url': TELEGRAM_PROXY})
    dp: Dispatcher = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.regex(parser), reply, run_async=True))
    username = f'@{updater.bot.username}'
    logger = _logger.bind(username=username)
    dp.bot_data['delUsername'] = partial(re.compile(username, re.I).sub, '')
    dp.bot_data['logger'] = logger

    updater.start_polling()
    logger.info('Started')

    _updaters.append(updater)
    # updater.idle()


def main():
    threads: list[Thread] = []
    for token in TOKENS:
        thread = Thread(target=start, args=(token,), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        threads_and_logger: list[tuple[Thread, Any]] = []
        for updater in _updaters:
            thread = Thread(target=updater.stop, daemon=True)
            threads_and_logger.append((thread, updater.dispatcher.bot_data['logger']))
            thread.start()
        for thread, logger in threads_and_logger:
            thread.join()
            logger.info('Stopped')


if __name__ == '__main__':
    main()
