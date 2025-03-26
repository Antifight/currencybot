import telebot
import requests
import json
import os
import math
from config import TOKEN

bot = telebot.TeleBot(TOKEN)
CURRENCY_API_URL = 'https://api.exchangerate-api.com/v4/latest/'

CURRENCIES = ['USD', 'EUR', 'UAH']
EMOJI = {'USD': '🇺🇸', 'EUR': '🇪🇺', 'UAH': '🇺🇦'}
user_state = {}


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


@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(message.chat.id, f'👋 Привет, {message.from_user.first_name}!')
    show_main_page(message.chat.id)


def show_main_page(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton('💱 Конвертация валюты', callback_data='convert_currency'))
    markup.add(telebot.types.InlineKeyboardButton('📖 Инструкция', callback_data='show_instruction'))
    bot.send_message(chat_id, '📌 Это бот-конвертер валют. Выберите действие:', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'show_instruction')
def instruction(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton('🔙 Вернуться на главную', callback_data='return_main'))
    text = ('📌 *Инструкция по использованию:*\n\n'
            '1. Нажмите "Конвертация валюты".\n'
            '2. Выберите валюту, введите сумму.\n'
            '3. Выберите валюту для конвертации.\n'
            '4. Получите результат.\n\n'
            'Приятного использования!')
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'return_main')
def return_main(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    user_state.pop(call.message.chat.id, None)  # Очистка состояния
    show_main_page(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == 'convert_currency' or call.data == 'continue_convert')
def choose_base_currency(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    user_state.pop(call.message.chat.id, None)  # Очистка состояния
    markup = telebot.types.InlineKeyboardMarkup()
    for curr in CURRENCIES:
        markup.add(telebot.types.InlineKeyboardButton(f'{EMOJI[curr]} {curr}', callback_data=f'base:{curr}'))
    markup.add(telebot.types.InlineKeyboardButton('🔙 Вернуться на главную', callback_data='return_main'))
    bot.send_message(call.message.chat.id, '💰 Выберите исходную валюту:', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('base:'))
def set_base_currency(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    base_currency = call.data.split(':')[1]
    user_state[call.message.chat.id] = {'base': base_currency}
    bot.send_message(call.message.chat.id, f'Выбрана валюта {base_currency}. Введите сумму для конвертации:')


@bot.message_handler(func=lambda message: True)
def input_amount(message):
    state = user_state.get(message.chat.id)
    if not state or 'base' not in state:
        bot.send_message(message.chat.id, '❗️ Пожалуйста, сначала выберите исходную валюту.')
        return
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0 or math.isnan(amount) or amount > 2147483647:
            raise ValueError
        state['amount'] = amount
        markup = telebot.types.InlineKeyboardMarkup()
        for curr in CURRENCIES:
            if curr != state['base']:
                markup.add(telebot.types.InlineKeyboardButton(f'{EMOJI[curr]} {curr}', callback_data=f'target:{curr}'))
        markup.add(telebot.types.InlineKeyboardButton('🔙 Вернуться на главную', callback_data='return_main'))
        bot.send_message(message.chat.id, '🔄 Выберите валюту для конвертации:', reply_markup=markup)
    except ValueError:
        bot.send_message(message.chat.id, '❗️ Введите корректную сумму .')




@bot.callback_query_handler(func=lambda call: call.data.startswith('target:'))
def convert(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    target_currency = call.data.split(':')[1]
    state = user_state.get(call.message.chat.id)
    try:
        r = requests.get(f'{CURRENCY_API_URL}{state["base"]}')
        r.raise_for_status()
        rate = r.json()['rates'].get(target_currency)
        if not rate:
            raise Exception
        result = state['amount'] * rate
        bot.send_message(call.message.chat.id, f'✅ {state["amount"]:.2f} {state["base"]} = {result:.2f} {target_currency}')
        save_conversion({'from': state['base'], 'to': target_currency, 'amount': state['amount'], 'result': round(result, 2)})
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton('🔁 Продолжить', callback_data='continue_convert'))
        markup.add(telebot.types.InlineKeyboardButton('🔙 Вернуться на главную', callback_data='return_main'))
        bot.send_message(call.message.chat.id, 'Выберите дальнейшее действие:', reply_markup=markup)
    except Exception:
        bot.send_message(call.message.chat.id, '❌ Ошибка получения курса валют.')

if __name__ == '__main__':
    print("Bot is running...")
    bot.polling(none_stop=True)
