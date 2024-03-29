from __future__ import annotations

import os
import sys
import re
import html
import requests
import telegram
from loguru import logger as _logger
from typing import Optional, Union, Any, Callable
from telegram.ext import Updater, MessageHandler, filters, Dispatcher
from functools import partial
from threading import Thread
from time import sleep
from itertools import product as _product
from itertools import starmap
from random import Random, SystemRandom
from collections import deque, Counter

Filters = filters.Filters

parser = re.compile(
    r'^(?P<slash>[\\/]_?\$?)'
    r'(?P<predicate>([^\s\\]|\\.)*((?<=\S)\\)?)'
    r'(\s+(?P<complement>.+))?$'
)
ouenParser = re.compile(
    r'^('
    r'\\+ .* /+'
    r'|'
    r'＼+ .* ／+'
    r'|'
    r'(\\.*/\s*){2,}'
    r'|'
    r'(＼.*／\s*){2,}'
    r'|'
    r'\\{2,}/{2,}'
    r'|'
    r'＼{2,}／{2,}'
    r')$'
)
pinParser = re.compile(
    r'^[\\/]_?pin$'
)
randomStickerParser = re.compile(
    r'^([\\/]_?){2,}$'
)

convertEscapes = partial(re.compile(r'\\(\s)').sub, r'\1')
htmlEscape = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
mentionParser = re.compile(r'@([a-zA-Z]\w{4,})')

product = lambda a, b: tuple(map('，'.join, _product(a, b)))

PUNCTUATION_TAIL = '.,?!;:~(' \
                   '。，？！；：～（'


class RandomizerMeta(type):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        cls._counter = Counter()


class Randomizer(metaclass=RandomizerMeta):
    def __class_getitem__(cls, item: str) -> Any:
        collection = getattr(cls, item)
        if cls._counter[item] % len(collection) == 0:
            random.shuffle(collection)
        cls._counter[item] += 1
        collection.rotate()
        return collection[-1]


class Vegetable(Randomizer):
    permission_denied = deque(
        product(
            {'我太菜了', '我好菜', '我好菜啊', '我菜死了'},
            {'pin 不了这条消息', '学不会怎么 pin 这条消息', '连 pin 都不被允许'}
        )
        +
        product(
            {'我学不会怎么 pin 这条消息', '这么简单的消息我都 pin 不了', '好想 pin 这条消息啊，但我做不到'},
            {'需要浇浇', '怎么会有我这么菜的 bot', '我只能混吃等死', '我怎么会菜成这样'}
        )
        +
        product(
            {'这可要我怎么 pin 呀', '怎么才能 pin 这条消息呀', 'pin 不动呀，这可怎么办'},
            {'拿大头针钉上吗', '找把锤子敲到柱子上吗', '触及知识盲区了都'}
        )
    )
    reject = deque(
        product(
            {'我累了', '我好懒，又懒又菜', '我的 bot 生只要像这样躺着混日子就已经很幸福了'},
            {'根本不想 pin 这条消息', '才不要 pin 这条消息', '还是另请高明吧', '一点 pin 的动力都没有'}
        )
    )


class Stickers(Randomizer):
    _cnstr = partial(telegram.Sticker,
                     width=512,
                     height=512,
                     is_animated=False,
                     is_video=False,
                     type=telegram.Sticker.REGULAR)

    stickers = deque(
        starmap(
            _cnstr,
            (
                ('CAACAgUAAxkBAAInuWOcpUaH6eiL7vc9bIw6GedK-DNzAALNAQAC3x9yGXsiKdzwYgnWLAQ', 'AgADzQEAAt8fchk'),
                ('CAACAgUAAxkBAAInu2OcpakDQaHnVWVo_80AAVgE7EcujAAC2gEAAt8fchkAAbkxR5lrlfUsBA', 'AgAD2gEAAt8fchk'),
                ('CAACAgUAAxkBAAInvWOcpcUcJDWODiIxUoSTs840QJaFAALbAQAC3x9yGcc6smv9nZmELAQ', 'AgAD2wEAAt8fchk'),
                ('CAACAgUAAxkBAAKNaWOcn1dZP5Ooe5wX8JrCKkK2qXGzAALnAQAC3x9yGfJozMIlJl_kLAQ', 'AgAD5wEAAt8fchk'),
                ('CAACAgUAAxkBAAInt2Ocor-N-gnaJTGR-RtyopIgI0l5AALrAQAC3x9yGWlN_RGM1AESLAQ', 'AgAD6wEAAt8fchk'),
                ('CAACAgUAAxkBAAInv2Ocph3PT5XiCArmoehOYzCn1sJRAALyAQAC3x9yGSLk1aHaA09kLAQ', 'AgAD8gEAAt8fchk'),
                ('CAACAgUAAxkBAAInwWOcplEELbRuIBkuy3Yyv6YCScxdAAISAgAC3x9yGaW3ftfZrg8eLAQ', 'AgADEgIAAt8fchk'),
                ('CAACAgUAAxkBAAInw2Ocpm8VgaPVTUhDPTGHWjnDjzsDAAIbAgAC3x9yGWCDLF4OLhaMLAQ', 'AgADGwIAAt8fchk'),
            )
        )
    )

    def __new__(cls) -> telegram.Sticker:
        return cls.__class_getitem__('stickers')


_logger.remove()
_logger.add(sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>"
                   "|<level>{level:^8}</level>"
                   "|<cyan>{extra[username]:^15}</cyan>"
                   "|<level>{message}</level>",
            level="DEBUG")


def log(func: Callable):
    def wrapper(update: telegram.Update, ctx: telegram.ext.CallbackContext):
        logger = ctx.bot_data['logger']
        logger.debug(str(update.to_dict()))
        return func(update, ctx, logger)

    return wrapper


try:
    random = SystemRandom()
except NotImplementedError:
    random = Random()
    _logger.warning('SystemRandom is not available, using Random instead')

# Docker env
TOKENS = re.compile(r'[^a-zA-Z\-_\d:]+').split(os.environ.get('TOKEN', ''))
if not TOKENS:
    raise ValueError('no any valid token found')

TELEGRAM_PROXY = os.environ.get('PROXY', '')
REQUEST_PROXIES = {'all': TELEGRAM_PROXY} if TELEGRAM_PROXY else None

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
        og_t = re.search(r'(?<=<meta property="og:title" content=").*(?=")', r.text, re.IGNORECASE).group(0)
        name = html.unescape(og_t) if og_t else None
        page_title = re.search(r'(?<=<title>).*(?=</title>)', r.text, re.IGNORECASE).group(0)
        if page_title == og_t:  # user does not exist
            self.name = None
        elif name:
            self.name = name

    def mention(self, mention_self: bool = False, pure: bool = False) -> str:
        if not self.name:
            return f'@{self.username}'

        mention_deep_link = (f'tg://resolve?domain={self.username}'
                             if (self.username and (not self.uid or self.uid < 0))
                             else f'tg://user?id={self.uid}')
        name = self.name if not mention_self else "自己"
        name = htmlEscape(name)
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


def parse_command(ctx: telegram.ext.CallbackContext) -> Optional[dict[str, Union[str, bool]]]:
    match = ctx.match
    parsed = match.groupdict()
    predicate = parsed['predicate']
    complement = parsed['complement']
    if not predicate and complement:
        return None  # invalid command

    omit_le = predicate.endswith('\\')
    predicate = predicate[:-1] if omit_le else predicate
    predicate = convertEscapes(predicate)
    predicate = ctx.bot_data['delUsername'](predicate)
    result = {'predicate': htmlEscape(predicate),
              'complement': htmlEscape(complement or ''),
              'slash': parsed['slash'],
              'swap': parsed['slash'] not in ('/', '/$'),
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
        ret = '!' if not command['swap'] else '¡'
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
    command = parse_command(ctx)
    if not command:
        return

    logger = ctx.bot_data['logger']
    logger.debug(str(update.to_dict()))
    msg = update.effective_message
    from_user, rpl_user = get_users(msg)

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


@log
def repeat(update: telegram.Update, ctx: telegram.ext.CallbackContext, logger: _logger):
    chat = update.effective_chat
    msg = update.effective_message
    if chat.id < 0:
        chat = ctx.bot.get_chat(chat.id)

    logger.info(msg.text)
    msg.copy(chat.id) if chat.has_protected_content else msg.forward(chat.id)


@log
def pin(update: telegram.Update, _ctx: telegram.ext.CallbackContext, logger: _logger):
    msg = update.effective_message
    msg_to_pin = msg.reply_to_message
    if not msg_to_pin:
        vegetable = f'{Vegetable["reject"]} (Reply to a message to use the command)'
        msg.reply_text(vegetable)
        logger.warning(vegetable)
        return

    try:
        msg_to_pin.unpin()
        msg_to_pin.pin(disable_notification=True)
        logger.info(f'Pinned {msg_to_pin.text}')
    except telegram.error.BadRequest as e:
        vegetable = f'{Vegetable["permission_denied"]} ({e})'
        msg_to_pin.reply_text(vegetable)
        logger.warning(vegetable)


@log
def random_sticker(update: telegram.Update, _ctx: telegram.ext.CallbackContext, logger: _logger):
    msg = update.effective_message
    sticker = Stickers()
    logger.info(sticker)
    msg.reply_sticker(sticker)


def start(token: str):
    updater = Updater(token=token, use_context=True, request_kwargs={'proxy_url': TELEGRAM_PROXY})
    dp: Dispatcher = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.regex(ouenParser) & ~Filters.update.edited_message, repeat, run_async=True))
    dp.add_handler(MessageHandler(Filters.regex(randomStickerParser) & ~Filters.update.edited_message, random_sticker,
                                  run_async=True))
    dp.add_handler(MessageHandler(Filters.regex(pinParser) & ~Filters.update.edited_message, pin, run_async=True))
    dp.add_handler(MessageHandler(Filters.regex(parser) & ~Filters.update.edited_message, reply, run_async=True))
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
