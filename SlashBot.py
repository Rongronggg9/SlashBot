from telegram.ext import Updater, MessageHandler, filters
import os
Filters = filters.Filters

# Docker env
if os.environ.get('TOKEN') and os.environ['TOKEN'] != 'X':
    Token = os.environ['TOKEN']
else:
    raise Exception('no token')

def mention(user):
    if 'last_name' not in user:
        user['last_name'] = ''
    return f"[{user['first_name']} {user['last_name']}](tg://user?id={user['id']})"


def reply(update, context):
    print(repr(update.to_dict()))
    msg = update.to_dict()['message']
    msg_from = msg['from']
    command = msg['text'].lstrip('/')
    if 'reply_to_message' in msg.keys():
        msg_rpl = msg['reply_to_message']['from']
    else:
        msg_rpl = msg_from

    update.effective_message.reply_text(f'{mention(msg_from)} {command} 了 {mention(msg_rpl)}！',
                                        parse_mode='Markdown')


updater = Updater(token=Token, use_context=True)
dp = updater.dispatcher
dp.add_handler(MessageHandler(Filters.regex(r'^\/([^\s@]+)$'), reply))

updater.start_polling()
updater.idle()
