import os
import re
import requests
import telegram
from typing import Tuple, Optional, Callable
from telegram.ext import Updater, MessageHandler, filters

Filters = filters.Filters
parser = re.compile(r'^([\\/]_?)((?:[^ 　\t\\]|\\.)+)[ 　\t]*(.*)$')
ESCAPING = ('\\ ', '\\　', '\\\t')
htmlEscape = lambda s: s.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
mentionParser = re.compile(r'@([a-zA-Z]\w{4,})$')
delUsername: Optional[Callable] = None  # placeholder

# Docker env
Token = os.environ.get('TOKEN')
if not Token:
    raise Exception('no token')

telegram_proxy = os.environ.get('PROXY', '')
requests_proxies = {'all': telegram_proxy} if telegram_proxy else None


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
        r = requests.get(f'https://t.me/{self.username}', proxies=requests_proxies)
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
        return f'<a href ="{mention_deep_link}">{name}</a>' if not pure else name

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


def get_users(msg: telegram.Message) -> Tuple[User, User]:
    msg_from = msg
    msg_rpl = msg.reply_to_message or msg_from
    from_user, rpl_user = get_user(msg_from), get_user(msg_rpl)
    return from_user, rpl_user


def parse_command(match: re.Match):
    parsed = match.groups()
    predicate = parsed[1]
    for escape in ESCAPING:
        predicate = delUsername('', predicate)
        predicate = predicate.replace(escape, escape[1:])
    result = {'predicate': htmlEscape(predicate), 'complement': htmlEscape(parsed[2]), 'swap': parsed[0] != '/'}
    return result


def get_text(user_from: User, user_rpl: User, command: dict):
    rpl_self = user_from == user_rpl
    mention_from = user_from.mention()
    mention_rpl = user_rpl.mention(mention_self=rpl_self)
    predicate, complement = command['predicate'], command['complement']

    if predicate == 'me':
        ret = f"{mention_from}{bool(complement) * ' '}{complement}"
        halfwidth_mark = (complement or user_from.mention(pure=True))[-1].isascii()
    elif predicate == 'you':
        ret = f"{mention_rpl}{bool(complement) * ' '}{complement}"
        halfwidth_mark = (complement or user_rpl.mention(mention_self=rpl_self, pure=True))[-1].isascii()
    elif complement:
        ret = f"{mention_from} {predicate} {mention_rpl} {complement}"
        halfwidth_mark = complement[-1].isascii()
    else:
        ret = f"{mention_from} {predicate} 了 {mention_rpl}"
        halfwidth_mark = mention_rpl[-1].isascii()
    ret += '!' if halfwidth_mark else '！'

    return ret


def reply(update: telegram.Update, context: telegram.ext.CallbackContext):
    print(update.to_dict())
    msg = update.effective_message
    from_user, rpl_user = get_users(msg)
    command = parse_command(context.match)

    if from_user == rpl_user:
        mention_match = mentionParser.search(command['predicate'])
        if mention_match:
            mention = mentionParser.search(msg.text).group(1)
            rpl_user = User(username=mention)
            command['predicate'] = command['predicate'][:mention_match.start()]

    if command['swap'] and (not from_user == rpl_user):
        (from_user, rpl_user) = (rpl_user, from_user)

    text = get_text(from_user, rpl_user, command)
    print(text, end='\n\n')

    update.effective_message.reply_text(text, parse_mode='HTML')


if __name__ == '__main__':
    updater = Updater(token=Token, use_context=True, request_kwargs={'proxy_url': telegram_proxy})
    delUsername = re.compile('@' + updater.bot.username, re.I).sub
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.regex(parser), reply))

    updater.start_polling()
    updater.idle()
