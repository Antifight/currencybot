import telebot
import requests
import json
import os
from config import TOKEN

bot = telebot.TeleBot(TOKEN)

CURRENCY_API_URL = 'https://api.exchangerate-api.com/v4/latest/'


CURRENCIES = ['UAH', 'USD', 'EUR']
CURRENCY_EMOJIS = {'UAH': '🇺🇦', 'USD': '🇺🇸', 'EUR': '🇪🇺'}

def save_conversion(conversion):
    filename = 'conversions.json'

    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                conversions = json.load(f)
            except json.JSONDecodeError:
                conversions = []
    else:
        conversions = []

    conversions.append(conversion)
    if len(conversions) > 10:
        conversions.pop(0)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(conversions, f, ensure_ascii=False, indent=2)

def send_currency_choice(chat_id, first_name):
    markup = telebot.types.InlineKeyboardMarkup()
    for currency in CURRENCIES:
        markup.add(telebot.types.InlineKeyboardButton(f"{CURRENCY_EMOJIS[currency]} {currency}", callback_data=f'set_currency:{currency}'))
    bot.send_message(
        chat_id,
        f'👋 Привет, {first_name}!\nВыбери исходную валюту:',
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['start'])
def welcome(message):
    send_currency_choice(message.chat.id, message.from_user.first_name)

@bot.message_handler(commands=['history'])
def show_history(message):
    filename = 'conversions.json'
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            conversions = json.load(f)
            if conversions:
                history_text = '\n'.join(
                    [f"🔹 {conv['amount']} {conv['from_currency']} → {conv['result']} {conv['to_currency']}" for conv in conversions]
                )
                bot.send_message(message.chat.id, f'📋 *История последних конвертаций:*\n{history_text}', parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, 'История конвертаций пуста.')
    else:
        bot.send_message(message.chat.id, 'История конвертаций пуста.')

user_currency = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_currency:'))
def choose_currency(call):
    currency = call.data.split(':')[1]
    user_currency[call.message.chat.id] = currency
    bot.send_message(call.message.chat.id, f'💱 Исходная валюта: *{currency}*\nОтправь сумму для конвертации:', parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def get_amount(message):
    try:
        amount = float(message.text)
        markup = telebot.types.InlineKeyboardMarkup()
        from_currency = user_currency.get(message.chat.id)
        for currency in CURRENCIES:
            if currency != from_currency:
                markup.add(telebot.types.InlineKeyboardButton(f"{CURRENCY_EMOJIS[currency]} {currency}", callback_data=f'{amount}:{from_currency}:{currency}'))
        markup.add(telebot.types.InlineKeyboardButton('🔙 Вернуться', callback_data='return_to_main'))
        bot.send_message(message.chat.id, "🔄 Выбери валюту для конвертации:", reply_markup=markup)
    except ValueError:
        bot.send_message(message.chat.id, "❗️ Пожалуйста, введи корректную сумму цифрами.")

@bot.callback_query_handler(func=lambda call: call.data == 'return_to_main')
def return_to_main(call):
    send_currency_choice(call.message.chat.id, call.from_user.first_name)

@bot.callback_query_handler(func=lambda call: not call.data.startswith('set_currency:') and call.data != 'return_to_main')
def callback_inline(call):
    amount, from_currency, target_currency = call.data.split(':')
    amount = float(amount)

    try:
        response = requests.get(CURRENCY_API_URL + from_currency)
        response.raise_for_status()
        rates = response.json()['rates']

        if target_currency in rates:
            result = amount * rates[target_currency]
            message_text = f"✅ *{amount:.2f} {from_currency}* = *{result:.2f} {target_currency}*"
            bot.send_message(call.message.chat.id, message_text, parse_mode='Markdown')

            conversion = {
                'amount': amount,
                'from_currency': from_currency,
                'to_currency': target_currency,
                'result': round(result, 2)
            }
            save_conversion(conversion)
        else:
            bot.send_message(call.message.chat.id, "❌ Валюта не найдена.")
    except requests.RequestException:
        bot.send_message(call.message.chat.id, "🚫 Ошибка при подключении к API курсов валют.")

    send_currency_choice(call.message.chat.id, call.from_user.first_name)

if __name__ == '__main__':
    print('Bot is running...')
    bot.polling()



