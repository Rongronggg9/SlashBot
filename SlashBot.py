import os
import re
from telegram.ext import Updater, MessageHandler, filters

TELEGRAM = 777000
GROUP = 1087968824
Filters = filters.Filters
parser = re.compile(r'^\/(\S+)([ 　]*)(.*)$')

# Docker env
if os.environ.get('TOKEN') and os.environ['TOKEN'] != 'X':
    Token = os.environ['TOKEN']
else:
    raise Exception('no token')


def get_user(msg):
    if msg['from']['id'] == TELEGRAM:
        return {'first_name': msg['forward_from_chat']['title'], 'id': msg['forward_from_chat']['id']}
    elif msg['from']['id'] == GROUP:
        return {'first_name': msg['chat']['title'], 'id': msg['chat']['id']}
    else:
        return msg['from']


def get_users(msg):
    msg_from = msg
    if 'reply_to_message' in msg.keys():
        msg_rpl = msg['reply_to_message']
    else:
        msg_rpl = msg_from.copy()
    from_user, rpl_user = get_user(msg_from), get_user(msg_rpl)
    if rpl_user == from_user:
        rpl_user = {'first_name': '自己', 'id': rpl_user['id']}
    return from_user, rpl_user


def mention(user):
    space = ' '
    if 'last_name' not in user:
        user['last_name'] = ''
        space = ''
    return f"[{user['first_name']}{space}{user['last_name']}](tg://user?id={user['id']})"


def get_text(mention_from, mention_rpl, command):
    parsed = parser.search(delUsername.sub('', command)).groups()
    if parsed[0] == 'me':
        return f"{mention_from} {parsed[2]}！"
    elif parsed[0] == 'you':
        return f"{mention_rpl} {parsed[2]}！"
    elif parsed[2]:
        return f"{mention_from} {parsed[0]} {mention_rpl} {parsed[2]}！"
    else:
        return f"{mention_from} {parsed[0]} 了 {mention_rpl}！"


def reply(update, context):
    print(update.to_dict())
    msg = update.to_dict()['message']
    command = msg['text']
    from_user, rpl_user = get_users(msg)

    mention_from, mention_rpl = mention(from_user), mention(rpl_user)

    text = get_text(mention_from, mention_rpl, command)
    print(text, end='\n\n')

    update.effective_message.reply_text(text, parse_mode='Markdown')


updater = Updater(token=Token, use_context=True)
delUsername = re.compile('@' + updater.bot.username, re.I)
dp = updater.dispatcher
dp.add_handler(MessageHandler(Filters.regex(parser), reply))

updater.start_polling()
updater.idle()
