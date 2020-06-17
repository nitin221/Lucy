import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, CommandHandler, run_async
from telegram.utils.helpers import mention_html


from haruka import dispatcher, spamfilters
from haruka.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from haruka.modules.helper_funcs.string_handling import extract_time
from haruka.modules.log_channel import loggable
from haruka.modules.sql import antiflood_sql as sql
from haruka.modules.connection import connected

from haruka.modules.translations.strings import tld
from haruka.modules.helper_funcs.alternate import send_message

FLOOD_GROUP = 3


@run_async
@loggable
def check_flood(bot: Bot, update: Update) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    if not user:  # ignore channels
        return ""

    # ignore admins
    if is_user_admin(chat, user.id):
        sql.update_flood(chat.id, None)
        return ""

    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        getmode, getvalue = sql.get_flood_setting(chat.id)
        if getmode == 1:
            chat.kick_member(user.id)
            execstrings = tld(update.effective_message, "Exit!")
            tag = "BANNED"
        elif getmode == 2:
            chat.kick_member(user.id)
            chat.unban_member(user.id)
            execstrings = tld(update.effective_message, "Exit!")
            tag = "KICKED"
        elif getmode == 3:
            bot.restrict_chat_member(chat.id, user.id, can_send_messages=False)
            execstrings = tld(update.effective_message, "Now you are silent!")
            tag = "MUTED"
        elif getmode == 4:
            bantime = extract_time(msg, getvalue)
            chat.kick_member(user.id, until_date=bantime)
            execstrings = tld(update.effective_message, "Out as long {}!").format(getvalue)
            tag = "TBAN"
        elif getmode == 5:
            mutetime = extract_time(msg, getvalue)
            bot.restrict_chat_member(chat.id, user.id, until_date=mutetime, can_send_messages=False)
            execstrings = tld(update.effective_message, "Now you stay silent for {}!").format(getvalue)
            tag = "TMUTE"
        send_message(update.effective_message, tld(update.effective_message, "I don't like people who send successive messages. But you made me "
                       "dissapointed. {}").format(execstrings))

        return "<b>{}:</b>" \
               "\n#{}" \
               "\n<b>User:</b> {}" \
               "\nFlooded the group.".format(tag, html.escape(chat.title),
                                             mention_html(user.id, user.first_name))

    except BadRequest:
        send_message(update.effective_message, tld(update.effective_message, "Does not have kick permission, so automatically disables antiflood."))
        sql.set_flood(chat.id, 0)
        return "<b>{}:</b>" \
               "\n#INFO" \
               "\n{}".format(chat.title, tld(update.effective_message, "Does not have kick permission, so automatically disables antiflood."))


@run_async
@user_admin
@can_restrict
@loggable
def set_flood(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    if len(args) >= 1:
        val = args[0].lower()
        if val == "off" or val == "no" or val == "0":
            sql.set_flood(chat.id, 0)
            message.reply_text(tld(chat.id, "Antiflood has been disabled."))

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat.id, 0)
                message.reply_text(tld(chat.id,  "Antiflood has been disabled."))
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Admin:</b> {}" \
                       "\nDisabled antiflood.".format(html.escape(chat.title), mention_html(user.id, user.first_name))

            elif amount < 3:
                message.reply_text(tld(chat.id, "Antiflood has to be either 0 (disabled), or a number bigger than 3 (enabled)!"))
                return ""

            else:
                sql.set_flood(chat.id, amount)
                message.reply_text(tld(chat.id, "Antiflood has been updated and set to {}").format(amount))
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Admin:</b> {}" \
                       "\nSet antiflood to <code>{}</code>.".format(html.escape(chat.title),
                                                                    mention_html(user.id, user.first_name), amount)

        else:
            message.reply_text(tld(chat.id, "Unrecognised argument - please use a number, 'off', or 'no'."))

    return ""

@run_async
@user_admin
def set_flood_mode(bot: Bot, update: Update, args: List[str]):
    spam = spamfilters(update.effective_message.text, update.effective_message.from_user.id, update.effective_chat.id, update.effective_message)
    if spam == True:
        return
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    conn = connected(bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, tld(update.effective_message, "You can do this command in the group, not the PM"))
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if args:
        if args[0].lower() == 'ban':
            settypeflood = tld(update.effective_message, 'block')
            sql.set_flood_strength(chat_id, 1, "0")
        elif args[0].lower() == 'kick':
            settypeflood = tld(update.effective_message, 'kick')
            sql.set_flood_strength(chat_id, 2, "0")
        elif args[0].lower() == 'mute':
            settypeflood = tld(update.effective_message, 'mute')
            sql.set_flood_strength(chat_id, 3, "0")
        elif args[0].lower() == 'tban':
            if len(args) == 1:
                text = tld(update.effective_message, """It looks like you are trying to set a temporary value for anti-flood, but have not determined the time yet; use `/ setfloodmode tban <timevalue> `.

Example time values: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks.""")
                send_message(update.effective_message, text, parse_mode="markdown")
                return
            settypeflood = tld(update.effective_message, "block while for {}").format(args[1])
            sql.set_flood_strength(chat_id, 4, str(args[1]))
        elif args[0].lower() == 'tmute':
            if len(args) == 1:
                text = tld(update.effective_message, """It looks like you are trying to set a temporary value for anti-flood, but have not determined the time yet; use `/ setfloodmode tmute <timevalue>`.

Example time values: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks.""")
                send_message(update.effective_message, text, parse_mode="markdown")
                return
            settypeflood = tld(update.effective_message, 'block while for {}').format(args[1])
            sql.set_flood_strength(chat_id, 5, str(args[1]))
        else:
            send_message(update.effective_message, tld(update.effective_message, "I only understand ban/kick/mute/tban/tmute!"))
            return
        if conn:
            text = tld(update.effective_message, "Sending too many messages now will result in `{}` in * {} *! ").format(settypeflood, chat_name)
        else:
            text = tld(update.effective_message, "Sending too many messages will now result in `{}`!").format(settypeflood)
        send_message(update.effective_message, text, parse_mode="markdown")
        return "<b>{}:</b>\n" \
                "<b>Admin:</b> {}\n" \
                "Has changed antiflood mode. User will {}.".format(settypeflood, html.escape(chat.title),
                                                                            mention_html(user.id, user.first_name))
    else:
        getmode, getvalue = sql.get_flood_setting(chat.id)
        if getmode == 1:
            settypeflood = tld(update.effective_message, 'block')
        elif getmode == 2:
            settypeflood = tld(update.effective_message, 'kick')
        elif getmode == 3:
            settypeflood = tld(update.effective_message, 'mute')
        elif getmode == 4:
            settypeflood = tld(update.effective_message, 'block while for {}').format(getvalue)
        elif getmode == 5:
            settypeflood = tld(update.effective_message, 'block while for {}').format(getvalue)
        if conn:
            text = tld(update.effective_message, "If a member sends successive messages, he will *{}* in *{}*.").format(settypeflood, chat_name)
        else:
            text = tl(update.effective_message, "If a member sends successive messages, he will be *{}*.").format(settypeflood)
        send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
    return ""


@run_async
def flood(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    limit = sql.get_flood_limit(chat.id)
    if limit == 0:
        update.effective_message.reply_text(tld(chat.id, "I'm not currently enforcing flood control!"))
    else:
        update.effective_message.reply_text(tld(chat.id,
            "I'm currently muting users if they send more than {} consecutive messages.").format(limit))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(bot, update, chat, chatP, user):
    chat_id = chat.id
    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        return "*Not* currently enforcing flood control."
    else:
        return "Antiflood is set to `{}` messages.".format(limit)


__help__ = """
 You know how sometimes, people join, send 100 messages, and ruin your chat? With antiflood, that happens no more!

Antiflood allows you to take action on users that send more than x messages in a row. Actions are: ban/kick/mute/tban/tmute

Available commands are:
 - /flood: gets the current antiflood settings.
 - /setflood <number/off>: sets the number of messages at which to take action on a user.
 - /setfloodmode <mute/ban/kick/tban/tmute>: Select the valid action ex. /setfloodmode tmute 5m.
"""

__mod_name__ = "AntiFlood"

FLOOD_BAN_HANDLER = MessageHandler(Filters.all & ~Filters.status_update & Filters.group, check_flood)
SET_FLOOD_HANDLER = CommandHandler("setflood", set_flood, pass_args=True, filters=Filters.group)
FLOOD_HANDLER = CommandHandler("flood", flood, filters=Filters.group)
SET_FLOOD_MODE_HANDLER = CommandHandler("setfloodmode", set_flood_mode, pass_args=True)#, filters=Filters.group)

dispatcher.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
dispatcher.add_handler(SET_FLOOD_HANDLER)
dispatcher.add_handler(FLOOD_HANDLER)
dispatcher.add_handler(SET_FLOOD_MODE_HANDLER)
