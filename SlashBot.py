from telegram.ext import Updater, MessageHandler, filters
import os
Filters = filters.Filters

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


def reply(update, context):
    print(repr(update.to_dict()))
    msg = update.to_dict()['message']
    msg_from = msg['from']
    command = msg['text'].lstrip('/')

    if 'reply_to_message' in msg.keys() and msg['reply_to_message']['from'] != msg_from:
        msg_rpl = msg['reply_to_message']['from']
    else:
        msg_rpl = {'first_name': '自己', 'id': msg_from['id']}

    mention_from = mention(msg_from)
    mention_rpl = mention(msg_rpl)
    text = f"{mention_from} {command} 了 {mention_rpl}！"

    update.effective_message.reply_text(text, parse_mode='Markdown')


updater = Updater(token=Token, use_context=True)
dp = updater.dispatcher
dp.add_handler(MessageHandler(Filters.regex(r'^\/([^\s@]+)$'), reply))

updater.start_polling()
updater.idle()
