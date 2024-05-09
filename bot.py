import telebot
from database import *
from validators import *
from speechkit import *

create_database()
bot = telebot.TeleBot(token)


# Обработчик команды start
@bot.message_handler(commands=["start"])
def start_message(message):
    user_id = message.from_user.id
    bot.send_message(user_id, """Этот GPT-бот ответит на все твои вопросы хоть в текстовом, хоть в голосовом
                                                               формате! Можешь задавать интересующие тебя вопросы""")


# Обработчик команды help
@bot.message_handler(commands=["help"])
def help_message(message):
    user_id = message.from_user.id
    bot.send_message(user_id, """Если задашь вопрос в голосовом формате, то он тоже ответит голосовым сообщением,
                                                                                            так же будет и с текстом""")


# Проверка stt
@bot.message_handler(commands=['stt'])   # stt
def stt_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, """Отправь следующим сообщением голосовое сообщение, чтобы я на него 
                                                                  тоже ответил голосовым сообщением!""")
    bot.register_next_step_handler(message, stt)


# Основная функиция для работы sst
def stt(message):
    user_id = message.from_user.id

    # Проверка, что сообщение действительно голосовое
    if not message.voice:
        bot.send_message(user_id, "Это не голосовое сообщение. Сообщение обязательно должно быть голосовым")
        return

    # Считаем аудиоблоки и проверяем сумму потраченных аудиоблоков
    stt_blocks, error_message = is_stt_block_limit(message, message.voice.duration)
    if not stt_blocks:
        bot.send_message(user_id, error_message)

    file_id = message.voice.file_id  # получаем id голосового сообщения
    file_info = bot.get_file(file_id)  # получаем информацию о голосовом сообщении
    file = bot.download_file(file_info.file_path)  # скачиваем голосовое сообщение

    # Получаем статус и содержимое ответа от SpeechKit
    status, text = speech_to_text(file)  # преобразовываем голосовое сообщение в текст

    # Если статус True - отправляем текст сообщения и сохраняем в БД, иначе - сообщение об ошибке
    if status:
        # Записываем сообщение и кол-во аудиоблоков в БД
        full_gpt_message = [text, 'user', 0, 0, stt_blocks]
        add_message(user_id=user_id, full_message=full_gpt_message)
        bot.send_message(user_id, text, reply_to_message_id=message.id)
    else:
        bot.send_message(user_id, text)


# Проверка tts
@bot.message_handler(commands=['tts'])       # tts
def tts_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь следующим сообщением текст, чтобы я его озвучил!')
    bot.register_next_step_handler(message, tts)


# Основная функиция для работы tts
def tts(message):
    user_id = message.from_user.id
    text = message.text

    # Проверка, что сообщение действительно текстовое
    if message.content_type != 'text':
        bot.send_message(user_id, 'Это не текстовое сообщение. Сообщение обязательно должно быть текстовым')
        return

    # Считаем символы в тексте и проверяем сумму потраченных символов в функции is_tts_symbol_limit из файла validators
    text_symbol = is_tts_symbol_limit(message, text)
    if text_symbol is None:
        return

    # Записываем сообщение и кол-во символов в БД
    full_gpt_message = [message.text, 'user', 0, text_symbol, 0]
    add_message(user_id=user_id, full_message=full_gpt_message)

    # Получаем статус и содержимое ответа от SpeechKit
    status, content = text_to_speech(text)

    # Если статус True - отправляем голосовое сообщение, иначе - сообщение об ошибке
    if status:
        bot.send_voice(user_id, content)
    else:
        bot.send_message(user_id, content)


# Основная функция для обработки ГОЛОСОВОГО сообщения и ответа на нее GPT
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = message.chat.id

    # Проверка на доступность аудиоблоков
    stt_blocks, error_message = is_stt_block_limit(message, message.voice.duration)
    if not stt_blocks:
        bot.send_message(user_id, error_message)

    # Обработка голосового сообщения
    file_id = message.voice.file_id
    file_info = bot.get_file(file_id)
    file = bot.download_file(file_info.file_path)
    status_stt, stt_text = speech_to_text(file)
    if not status_stt:
        bot.send_message(user_id, stt_text)
        return

    # Запись в БД
    add_message(user_id=user_id, full_message=[stt_text, 'user', 0, 0, stt_blocks])

    # Проверка на доступность GPT-токенов
    last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
    total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
    if error_message:
        bot.send_message(user_id, error_message)
        return

    # Запрос к GPT и обработка ответа
    status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
    if not status_gpt:
        bot.send_message(user_id, answer_gpt)
        return
    total_gpt_tokens += tokens_in_answer

    # Проверка на лимит символов для SpeechKit
    tts_symbols, error_message = is_tts_symbol_limit(message, answer_gpt)

    # Запись ответа GPT в БД
    add_message(user_id=user_id, full_message=[answer_gpt, 'assistant', total_gpt_tokens, tts_symbols, 0])

    if error_message:
        bot.send_message(user_id, error_message)
        return

    # Преобразование ответа в аудио и отправка
    status_tts, voice_response = text_to_speech(answer_gpt)
    if status_tts:
        bot.send_voice(user_id, voice_response, reply_to_message_id=message.id)
    else:
        bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)


# Основная функция для обработки ТЕКСТОВОГО сообщения и ответа на нее GPT
@bot.message_handler(content_types=['text'])
def handle_text(message):
    try:
        user_id = message.from_user.id

        # БД: добавляем сообщение пользователя и его роль в базу данных
        full_user_message = [message.text, 'user', 0, 0, 0]
        add_message(user_id=user_id, full_message=full_user_message)

        # ВАЛИДАЦИЯ: считаем количество доступных пользователю GPT-токенов
        # получаем последние 4 (COUNT_LAST_MSG) сообщения и количество уже потраченных токенов
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        # получаем сумму уже потраченных токенов + токенов в новом сообщении и оставшиеся лимиты пользователя
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
        if error_message:
            # если что-то пошло не так — уведомляем пользователя и прекращаем выполнение функции
            bot.send_message(user_id, error_message)
            return

        # GPT: отправляем запрос к GPT
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        # GPT: обрабатываем ответ от GPT
        if not status_gpt:
            # если что-то пошло не так — уведомляем пользователя и прекращаем выполнение функции
            bot.send_message(user_id, answer_gpt)
            return
        # сумма всех потраченных токенов + токены в ответе GPT
        total_gpt_tokens += tokens_in_answer

        # БД: добавляем ответ GPT и потраченные токены в базу данных
        full_gpt_message = [answer_gpt, 'assistant', total_gpt_tokens, 0, 0]
        add_message(user_id=user_id, full_message=full_gpt_message)

        bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)  # отвечаем пользователю текстом
    except Exception as e:
        logging.error(e)  # если ошибка — записываем её в логи
        bot.send_message(message.from_user.id, "Не получилось ответить. Попробуй написать другое сообщение")


# Обрабатываем все остальные типы сообщений
@bot.message_handler(func=lambda: True)
def handler(message):
    bot.send_message(message.from_user.id, "Отправь мне голосовое или текстовое сообщение, и я тебе отвечу")


# Запуск бота
bot.polling()
