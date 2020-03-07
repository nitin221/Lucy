import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, CommandHandler, run_async
from telegram.utils.helpers import mention_html, escape_markdown

from haruka import dispatcher, spamfilters
from haruka.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from haruka.modules.helper_funcs.string_handling import extract_time
from haruka.modules.disable import DisableAbleCommandHandler
from haruka.modules.log_channel import loggable
from haruka.modules.sql import cleaner_sql as sql
from haruka.modules.connection import connected

from haruka.modules.translations.strings import tld
from haruka.modules.helper_funcs.alternate import send_message


@run_async
def clean_blue_text_must_click(bot: Bot, update: Update):
	if sql.is_enable(update.effective_chat.id):
		update.effective_message.delete()

@run_async
@user_admin
def set_blue_text_must_click(bot: Bot, update: Update, args):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	message = update.effective_message  # type: Optional[Message]
	spam = spamfilters(update.effective_message.text, update.effective_message.from_user.id, update.effective_chat.id, update.effective_message)
	if spam == True:
		return

	conn = connected(bot, update, chat, user.id, need_admin=True)
	if conn:
		chat_id = conn
		chat_name = dispatcher.bot.getChat(conn).title
	else:
		if update.effective_message.chat.type == "private":
			send_message(update.effective_message, tld(update.effective_message, "You can do this command on the group, not on PM"))
			return ""
		chat_id = update.effective_chat.id
		chat_name = update.effective_message.chat.title

	if len(args) >= 1:
		val = args[0].lower()
		if val == "off" or val == "no":
			sql.set_cleanbt(chat_id, False)
			if conn:
				text = tld(update.effective_message, "The blue message eraser has been *deactivated* in *{}*.").format(chat_name)
			else:
				text = tld(update.effective_message, "The blue message eraser has been *deactivated*.")
			send_message(update.effective_message, text, parse_mode="markdown")

		elif val == "yes" or val == "ya" or val == "on":
			sql.set_cleanbt(chat_id, True)
			if conn:
				text = tld(update.effective_message, "The blue message eraser has been *activated* in *{}*.").format(chat_name)
			else:
				text = tld(update.effective_message, "The blue message eraser has been *activated*.")
			send_message(update.effective_message, text, parse_mode="markdown")

		else:
			send_message(update.effective_message, tld(update.effective_message, "Unknown argument - please use 'yes', or 'no'."))
	else:
		send_message(update.effective_message, tld(update.effective_message, "The setting for the blue message eraser is currently on {}: *{}*").format(chat_name, "Enabled" if sql.is_enable(chat_id) else "Disabled"), parse_mode="markdown")


__help__ = """
*Admins only:*
- /cleanbluetext on <to enable this module> this will clean every bluetext line.
- /cleanbluetext off <to disable this module> will not delete bluetext line.
"""

__mod_name__ = "Cleaner"

SET_CLEAN_BLUE_TEXT_HANDLER = DisableAbleCommandHandler("cleanbluetext", set_blue_text_must_click, pass_args=True)
CLEAN_BLUE_TEXT_HANDLER = MessageHandler(Filters.command & Filters.group, clean_blue_text_must_click)


dispatcher.add_handler(SET_CLEAN_BLUE_TEXT_HANDLER)
dispatcher.add_handler(CLEAN_BLUE_TEXT_HANDLER, 15)
