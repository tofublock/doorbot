#!/usr/bin/python

from telegram.ext import Updater, CallbackContext, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Contact, ParseMode
import logging
import urllib3
import time
import emoji
from datetime import datetime, date
from subprocess import call
import atexit
import pickle
import os
import traceback
import html
import json
from util import User
from util import State
import pigpio
#import RPi.GPIO as GPIO

pi = pigpio.pi('gpiod')

#telegram bot token
try:
    bot_token = os.environ['TG_SECRET']
except:
    logging.error("Please set secret key as environtment variable 'TG_SECRET'")
    os.exit(-1)

#pin number for front door and hold time
try:
    opener_pin = int(os.environ["PIN"])
except KeyError:
    logging.error("Opener pin is not defined")
    os.exit(-1)
hold_time = 5

#telegram ids for admin output
try:
    admins = os.environ["ADMINS"].split(";")
except KeyError:
    logging.error("No admin has been defined")
    os.exit(-1)
if len(admins) < 1:
    logging.error("No admin has been defined")
    os.exit(-1)

state = None
updater = None
directory = os.path.dirname(os.path.realpath(__file__)) + "/"

#message helper
def buildMessage(text):
    global state
    if state.locked:
        doorstate = "locked"
    else:
        doorstate = "unlocked"

    message = ""
    message += str(date.today()) + " " + str(datetime.now().time().replace(microsecond=0)) + "\n"
    if state.locked:
        message += emoji.emojize(":no_entry: ", use_aliases=True)
    else:
        message += emoji.emojize(":white_check_mark: ", use_aliases=True)
    message += "Flat door is " + doorstate + ".\n"
    message += "\n" + text
    return message

def build_menu(buttons, n_cols, header_buttons = None, footer_buttons = None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

def saveState():
    global state, directory
    with open(directory + 'doorbot.dat', "wb") as outfile:
        outfile.seek(0)
        outfile.truncate()
        pickle.dump(state, outfile, pickle.HIGHEST_PROTOCOL)

#fetch user from list
def getUser(id, list):
    for user in list:
        if user.contact.user_id == id:
            return user
    return None

def makeKeyboard(user):
    global state
    kb = []
    header = []
    header.append(InlineKeyboardButton('Open front door', callback_data="open_front"))

    if user.permissions >= 7:
        header.append(InlineKeyboardButton('Open flat door', callback_data="open_flat"))
        kb.append(InlineKeyboardButton('Allow access', callback_data="allow"))
        kb.append(InlineKeyboardButton('Restrict access', callback_data="restrict"))
        kb.append(InlineKeyboardButton('Lock flat door', callback_data="lock_flat"))
        kb.append(InlineKeyboardButton('List users', callback_data="list"))
        kb.append(InlineKeyboardButton('Access list', callback_data="access"))
    return InlineKeyboardMarkup(build_menu(kb, n_cols=2, header_buttons=header))

#system level function for opening doors
def openFrontDoor():
    pi.write(opener_pin, 1)
    time.sleep(hold_time)
    pi.write(opener_pin, 0)
    return

def openFlat():
    os.system("homegear -e rc '$hg->setValue(1,1,'OPEN',true);'")
    return

def lockFlat():
    os.system("homegear -e rc '$hg->setValue(2,1,'OPEN',false);'")

def informAdmins(bot, query, message):
    global admins, state
    return
    for user in state.users:
        if user.contact.user_id != query.message.chat_id and user.permissions >= 7:
            result = bot.send_message(chat_id=user.contact.user_id, text=message, reply_markup=makeKeyboard(user))
            user.message_id = result['message_id']

#command handler for bot, creates custom keyboard depending on user roles
def start(update: Update, context: CallbackContext) -> None:
    global state
    user = getUser(update.message.chat_id, state.users)
    if user is None:
        if str(update.message.from_user.id) in admins:
            user = User(Contact("", update.message.from_user.first_name, user_id=update.message.from_user.id), 7)
            state.users.append(user)
            saveState()
        else:
            kb = [[KeyboardButton('/start')]]
            kb_markup = ReplyKeyboardMarkup(kb)
            message = "No access rights. Contact an admin."
            context.bot.send_message(chat_id=update.message.chat_id, text=message, reply_markup=kb_markup)
            return
    if user.permissions == 0:
        kb = [[KeyboardButton('/start')]]
        kb_markup = ReplyKeyboardMarkup(kb)
        message = "No access rights. Contact an admin."
        context.bot.send_message(chat_id=update.message.chat_id, text=message, reply_markup=kb_markup)
        return
            
    message = buildMessage("Welcome")
    result = context.bot.send_message(chat_id=update.message.chat_id, text=message, reply_markup=makeKeyboard(user))
    user.message_id = result['message_id']

def inlineButtons(update: Update, context: CallbackContext):
    global state, admins
    bot = context.bot

    query = update.callback_query
    query.answer()
    user = getUser(query.message.chat_id, state.users)
    if user is None:
        logging.info("Unauthorized user in query callback. How did this happen?")
        return

    if query.data == "open_front":
        state.accesslist.append([datetime.now(), user.contact, state.locked, 0])
        if user.permissions >= 3:
            openFrontDoor()
            informAdmins(bot, query, emoji.emojize(":white_check_mark: " + query.from_user.first_name + " opened front door.", use_aliases=True))
            message = buildMessage("Front door opened.")
        else:
            message = "Insufficient access rights."
    elif query.data == "open_flat":
        if user.permissions >= 7:
            savedoorstate = False
        else:
            savedoorstate = state.locked
        state.accesslist.append([datetime.now(), user.contact, savedoorstate, 1])
        if len(state.accesslist) > 1000:
            state.accesslist.pop(0)
        saveState()
        if user.permissions >= 3:
            if (not state.locked): # or user.permissions >= 7:
                openFlat()
                informAdmins(bot, query, emoji.emojize(":white_check_mark: " + query.from_user.first_name + " opened flat door.", use_aliases=True))
                message = buildMessage("Flat door opened.")
            else:
                informAdmins(bot, query, emoji.emojize(":no_entry: " + query.from_user.first_name + " was denied access.", use_aliases=True))
                message = buildMessage("Door is locked.")
        else:
            message = "Insufficient access rights."
    elif query.data == "lock_flat":
        if user.permissions >= 7:
            state.locked = True
            saveState()
            lockFlat()
            informAdmins(bot, query, emoji.emojize(":no_entry: " + query.from_user.first_name + " locked flat door.", use_aliases=True))
            message = buildMessage("Flat door locked.")
    elif query.data == "restrict":
        if user.permissions >= 7:
            state.locked = True
            saveState()
            informAdmins(bot, query, emoji.emojize(":no_entry: " + query.from_user.first_name + " restricted access to flat.", use_aliases=True))
            message = buildMessage("Flat access is now restricted. ")
        else:
            message = "Insufficient access rights."
    elif query.data == "allow":
        if user.permissions >= 7:
            state.locked = False
            saveState()
            informAdmins(context.bot, query, emoji.emojize(":white_check_mark: " + query.from_user.first_name + " allowed flat access.", use_aliases=True))
            message = buildMessage("Flat access is now allowed.")
        else:
            message = "Insufficient access rights."
    elif query.data == "list":
        if user.permissions >= 7:
            tempmessage = "Users with access rights:\n"
            kb = []
            for contact in state.users:
                kb.append(InlineKeyboardButton(contact.contact.first_name, callback_data="usr" + str(contact.contact.user_id)))
            message = buildMessage(tempmessage)
            query.edit_message_text(text=message, reply_markup=InlineKeyboardMarkup(build_menu(kb, n_cols=2)))
            return
        else:
            message = "Insufficient access rights."
    elif query.data == "access":
        if user.permissions >= 7:
            tempmessage = "Last users to access:\n"

            for entry in state.accesslist[-20:]:
                if entry[3]:
                    if entry[2]:
                        text = emoji.emojize(":no_entry:" + entry[1]['first_name'] + " was denied access.", use_aliases=True)
                    else:
                        text = emoji.emojize(":white_check_mark:" + entry[1]['first_name'] + " opened flat door.", use_aliases=True)
                else:
                    text = entry[1]['first_name'] + " opened front door."
                tempmessage += entry[0].strftime("%Y-%m-%d %H:%M") + " " + text + "\n"
            message = buildMessage(tempmessage)
        else:
            message = "Insufficient access rights."
    elif query.data[0:3] == "cmd":
        cmduser = getUser(int(query.data[6:]), state.users)
        if cmduser:
            if query.data[3:6] == "rem":
                state.users.remove(cmduser)
                message = buildMessage(cmduser.contact.first_name + " has been removed from user list.")
            elif query.data[3:6] == "pm7":
                cmduser.permissions = 7
                message = buildMessage(cmduser.contact.first_name + " has been granted administrator rights.")
            elif query.data[3:6] == "pm3":
                cmduser.permissions = 3
                message = buildMessage(cmduser.contact.first_name + " is no longer an administrator.")
            else:
                message = "Error managing user."
        else:
            message = "Error managing user."
    elif query.data[0:3] == "usr":
        cmduser = getUser(int(query.data[3:]), state.users)
        if cmduser.contact.user_id == user.contact.user_id:
            message = buildMessage("Can't change own settings.")
        elif cmduser:
            if cmduser.permissions >= 7:
                perms = " (Administrator)"
            elif cmduser.permissions >= 3:
                perms = " (Normal user)"
            else:
                perms = " shouldn't be here."
            message = buildMessage("Managing user\n" + cmduser.contact.first_name + perms + "\n ")
            kb = [
                InlineKeyboardButton("Remove user", callback_data="cmdrem"+str(cmduser.contact.user_id)),
                InlineKeyboardButton("Grant admin rights", callback_data="cmdpm7"+str(cmduser.contact.user_id)),
                InlineKeyboardButton("Remove admin rights", callback_data="cmdpm3"+str(cmduser.contact.user_id)),
                InlineKeyboardButton("Back", callback_data="home")
            ]
            query.edit_message_text(text=message, reply_markup=InlineKeyboardMarkup(build_menu(kb, n_cols=2)))
            return
    elif query.data == "home":
        message = buildMessage("Welcome")
    try:
        query.edit_message_text(text=message, reply_markup=makeKeyboard(user))
    except:
        result = bot.send_message(chat_id=query.message.chat_id, text=message, reply_markup=makeKeyboard(user))
        user.message_id = result['message_id']      

def addUser(update: Update, context: CallbackContext):
    global state
    bot = update.message.bot
    user = getUser(update.message.chat_id, state.users)
    if user.permissions >= 7:
        new_user = getUser(update.message.contact.user_id, state.users)
        if new_user is None:
            new_user = User(update.message.contact, 3)
            state.users.append(new_user)
            saveState()
        result = bot.send_message(text=buildMessage(new_user.contact.first_name + " added as user."), chat_id=update.message.chat_id, reply_markup=makeKeyboard(user))
        user.message_id = result['message_id']
        
def error_handler(update: Update, context: CallbackContext) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    message = (
        f'An exception was raised while handling an update\n'
        f'<pre>update = {html.escape(json.dumps(update.to_dict(), indent=2, ensure_ascii=False))}'
        '</pre>\n\n'
        f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n'
        f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n'
        f'<pre>{html.escape(tb_string)}</pre>'
    )

    # Finally, send the message
    for admin in admins:
        context.bot.send_message(chat_id=admin, text=message, parse_mode=ParseMode.HTML)


def shutdown():
    global updater
    updater.stop()

def main():
    #object to hold information about users and state
    global state, directory, updater
    state = State()

    #load information if available
    try:
        with open(directory + "doorbot.dat", "rb+") as infile:
            state = pickle.load(infile)
    except:
        logging.info("No saved state found.")
        lf = open(directory + "doorbot.dat", "wb")
        pickle.dump(state, lf, pickle.HIGHEST_PROTOCOL)
        lf.close()

    #add admins to user list every time
    # for admin in admins:
        # admin_obj = getUser(admin.contact.user_id, state.users)
        # if admin_obj is None:
            # state.users.append(admin)

    #disable ssl warnings
    urllib3.disable_warnings()

    #say hi to the telegram server
    updater = Updater(token=bot_token)
    dispatcher = updater.dispatcher

    #register graceful shutdown function
    atexit.register(shutdown)

    #enable logging (purpose?!)
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

    #create handlers
    start_handler = CommandHandler('start', start)
    callback_handler = CallbackQueryHandler(inlineButtons)
    add_contact = MessageHandler(Filters.contact, addUser)

    #register handlers
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(callback_handler)
    dispatcher.add_handler(add_contact)
    # ...and the error handler
    dispatcher.add_error_handler(error_handler)

    #run
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
