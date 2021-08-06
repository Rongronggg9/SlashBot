import os
import re
from typing import List, Dict, Union

import requests
from telegram.ext import Updater, MessageHandler, filters

TELEGRAM = 777000
GROUP = 1087968824
Filters = filters.Filters
parser = re.compile(r'^([\\/]_?)((?:[^ 　\\]|\\.)+)[ 　]*(.*)$')
escaping = ('\\ ', '\\　')
markdownEscape = lambda s: s.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")

# Docker env
if os.environ.get('TOKEN') and os.environ['TOKEN'] != 'X':
    Token = os.environ['TOKEN']
else:
    raise Exception('no token')


# Find someone's full name by their username
def find_name_by_username(username: str) -> str:
    r = requests.get(f'https://t.me/{username}')
    return re.search('(?<=<meta property="og:title" content=").*(?=")', r.text, re.IGNORECASE).group(0)


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
    reply_self = rpl_user == from_user

    # Not replying to anything
    if reply_self:

        # Detect if the message contains a mention. If it has, use the mentioned user.
        entities: List[Dict[str, Union[str, int]]] = msg['entities']
        mentions = [e for e in entities if e['type'] == 'mention']
        if mentions:

            # Find username
            offset = mentions[0]['offset']
            length = mentions[0]['length']
            text = msg['text']
            username = text[offset : offset + length].replace("@", "")
            rpl_user = {'first_name': find_name_by_username(username), 'username': username}

            # Remove mention from message text
            msg['text'] = text[:offset] + text[offset + length:]

        else:
            rpl_user = {'first_name': '自己', 'id': rpl_user['id']}

    return from_user, rpl_user, reply_self


# Create mention string from user
def mention(user: Dict[str, str]) -> str:

    # Combine name
    last = user.get('last_name', '')
    first = user['first_name']
    name = first + (f' {last}' if last else '')

    # Create user reference link
    username = user.get('username', '')
    uid = user.get('id', '')
    link = f'tg://resolve?domain={username}' if username else f'tg://user?id={uid}'

    return f"[{name}]({link})"


def parse_command(command):
    parsed = list(parser.search(command).groups())
    predicate = parsed[1]
    for escape in escaping:
        predicate = predicate.replace(escape, escape[1:])
    result = {'predicate': markdownEscape(predicate), 'complement': markdownEscape(parsed[2]), 'swap': parsed[0] != '/'}
    return result

def get_text(mention_from, mention_rpl, command):
    if command['predicate'] == 'me':
        return f"{mention_from}{bool(command['complement'])*' '}{command['complement']}！"
    elif command['predicate'] == 'you':
        return f"{mention_rpl}{bool(command['complement'])*' '}{command['complement']}！"
    elif command['complement']:
        return f"{mention_from} {command['predicate']} {mention_rpl} {command['complement']}！"
    else:
        return f"{mention_from} {command['predicate']} 了 {mention_rpl}！"


def reply(update, context):
    print(update.to_dict())
    msg = update.to_dict()['message']
    from_user, rpl_user, reply_self = get_users(msg)

    command = parse_command(del_username.sub('', msg['text']))
    if command['swap'] and not reply_self:
        (from_user, rpl_user) = (rpl_user, from_user)

    text = get_text(mention(from_user), mention(rpl_user), command)
    print(text, end='\n\n')

    update.effective_message.reply_text(text, parse_mode='Markdown')


if __name__ == '__main__':
    updater = Updater(token=Token, use_context=True)
    del_username = re.compile('@' + updater.bot.username, re.I)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.regex(parser), reply))

    updater.start_polling()
    updater.idle()
