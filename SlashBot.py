import os
import re
from telegram.ext import Updater, MessageHandler, filters

Filters = filters.Filters
parser = re.compile(r'^\/(\S+)([ 　]*)(.*)$')

# Docker env
if os.environ.get('TOKEN') and os.environ['TOKEN'] != 'X':
    Token = os.environ['TOKEN']
else:
    raise Exception('no token')


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
    elif parsed[2]:
        return f"{mention_from} {parsed[0]} {mention_rpl} {parsed[2]}！"
    else:
        return f"{mention_from} {parsed[0]} 了 {mention_rpl}！"


def reply(update, context):
    print(update.to_dict())
    msg = update.to_dict()['message']
    command = msg['text']
    msg_from = msg['from']

    if 'reply_to_message' in msg.keys() and msg['reply_to_message']['from'] != msg_from:
        msg_rpl = msg['reply_to_message']['from']
    else:
        msg_rpl = {'first_name': '自己', 'id': msg_from['id']}

    mention_from = mention(msg_from)
    mention_rpl = mention(msg_rpl)
    text = get_text(mention_from, mention_rpl, command)
    print(text)

    update.effective_message.reply_text(text, parse_mode='Markdown')


updater = Updater(token=Token, use_context=True)
delUsername = re.compile('@' + updater.bot.username, re.I)
dp = updater.dispatcher
dp.add_handler(MessageHandler(Filters.regex(parser), reply))

updater.start_polling()
updater.idle()
