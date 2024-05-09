import math
from yandex_gpt import *
from config import *
from database import count_all_limits

logging.basicConfig(filename=LOGS, level=logging.ERROR,
                    format="%(asctime)s FILE: %(filename)s IN: %(funcName)s MESSAGE: %(message)s", filemode="w")


# Проверка лимита символов голосового сообщения
def is_tts_symbol_limit(message, text):
    user_id = message.chat.id
    text_symbols: int = len(text)
    symbols: int = count_all_limits(user_id, "tts_symbols")

    # Функция из БД для подсчёта всех потраченных пользователем символов
    all_symbols = symbols + text_symbols

    # Сравниваем all_symbols с количеством доступных пользователю символов
    if all_symbols >= MAX_USER_TTS_SYMBOLS:
        msg = f"""Превышен общий лимит SpeechKit TTS {MAX_USER_TTS_SYMBOLS}. Использовано: {all_symbols} символов.
                                                                     Доступно: {MAX_USER_TTS_SYMBOLS - all_symbols}"""

        return None, msg

        # Сравниваем количество символов в тексте с максимальным количеством символов в тексте
    if text_symbols >= MAX_TTS_SYMBOLS:
        msg = f"Превышен лимит SpeechKit TTS на запрос {MAX_TTS_SYMBOLS}, в сообщении {text_symbols} символов"

        return None, msg

    return len(text), ""


# проверяем, не превысил ли пользователь лимиты на преобразование аудио в текст
def is_stt_block_limit(message, duration):
    user_id = message.from_user.id

    # Переводим секунды в аудиоблоки
    audio_blocks = math.ceil(duration / 15)  # округляем в большую сторону
    # Функция из БД для подсчёта всех потраченных пользователем аудиоблоков
    all_blocks = count_all_limits(user_id, "stt_blocks") + audio_blocks

    # Сравниваем all_blocks с количеством доступных пользователю аудиоблоков
    if all_blocks >= MAX_USER_STT_BLOCKS:
        msg = f"""Превышен общий лимит SpeechKit STT {MAX_USER_STT_BLOCKS}. Использовано {all_blocks} блоков.
                                                                  Доступно: {MAX_USER_STT_BLOCKS - all_blocks}"""
        return None, msg
    # Проверяем, что аудио длится меньше 30 секунд
    elif duration >= 30:
        msg = "SpeechKit STT работает с голосовыми сообщениями меньше 30 секунд"
        return None, msg
    else:
        return True, ""


# проверяем, не превысил ли пользователь лимиты на общение с GPT
def is_gpt_token_limit(messages, total_spent_tokens):
    all_tokens = count_gpt_tokens(messages) + total_spent_tokens
    if all_tokens > MAX_USER_GPT_TOKENS:
        return None, f"Превышен общий лимит GPT-токенов {MAX_USER_GPT_TOKENS}"
    return all_tokens, ""
