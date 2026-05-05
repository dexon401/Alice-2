import logging
import random
import os
import waitress

from flask import Flask, jsonify, request

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

cities = {
    "москва": ["1652229/15014694a4dc81330922", "1540737/857fc29a4e40e1a0dbce"],
    "нью-йорк": ["1652229/c00be161bdc36e5f8343", "997614/0f94d41cfb9d204a2e4a"],
    "париж": ["1652229/b1a8c8d74c7e54327365", "997614/0652c32e1709ce20f473"],
}

sessionStorage = {}


@app.route("/")
def index():
    return ""


@app.route("/post", methods=["POST"])
def main():
    logging.info("Request: %r", request.json)
    response = {
        "session": request.json["session"],
        "version": request.json["version"],
        "response": {"end_session": False},
    }
    handle_dialog(response, request.json)
    logging.info("Response: %r", response)
    return jsonify(response)


def handle_dialog(res, req):
    user_id = req["session"]["user_id"]

    if req["session"]["new"]:
        res["response"]["text"] = "Привет! Назови своё имя!"
        sessionStorage[user_id] = {
            "first_name": None,
            "game_started": False,
            "guessed_cities": [],
        }
        return

    if sessionStorage[user_id]["first_name"] is None:
        first_name = get_first_name(req)
        if first_name is None:
            res["response"]["text"] = "Не расслышала имя. Повтори, пожалуйста!"
        else:
            sessionStorage[user_id]["first_name"] = first_name
            if "guessed_cities" not in sessionStorage[user_id]:
                sessionStorage[user_id]["guessed_cities"] = []
            res["response"]["text"] = (
                f"Приятно познакомиться, {first_name.title()}. Я Алиса.\n"
                f"Отгадаешь город по фото?"
            )
            res["response"]["buttons"] = [
                {"title": "Да", "hide": True},
                {"title": "Нет", "hide": True},
            ]
        return

    if not sessionStorage[user_id]["game_started"]:
        if len(sessionStorage[user_id]["guessed_cities"]) == len(cities):
            res["response"]["text"] = "Ты отгадал все города! Игра окончена."
            res["response"]["end_session"] = True
            return

        if "да" in req["request"]["nlu"]["tokens"]:
            sessionStorage[user_id]["game_started"] = True
            sessionStorage[user_id]["attempt"] = 1
            play_game(res, req)
        elif "нет" in req["request"]["nlu"]["tokens"]:
            res["response"]["text"] = "Ну и ладно!"
            res["response"]["end_session"] = True
        else:
            res["response"]["text"] = "Не поняла ответа! Так да или нет?"
            res["response"]["buttons"] = [
                {"title": "Да", "hide": True},
                {"title": "Нет", "hide": True},
            ]
    else:
        play_game(res, req)


def play_game(res, req):
    user_id = req["session"]["user_id"]
    attempt = sessionStorage[user_id]["attempt"]
    city = sessionStorage[user_id].get("city")

    if attempt == 1:
        available_cities = [
            c for c in cities if c not in sessionStorage[user_id]["guessed_cities"]
        ]
        if not available_cities:
            res["response"]["text"] = "Поздравляю! Ты отгадал все города."
            res["response"]["end_session"] = True
            return
        city = random.choice(available_cities)
        sessionStorage[user_id]["city"] = city
        sessionStorage[user_id]["attempt"] = 2

        res["response"]["card"] = {
            "type": "BigImage",
            "title": "Что это за город?",
            "image_id": cities[city][0],
        }
        res["response"]["text"] = "Какой город изображён на фото?"
        return

    user_answer = get_city(req)
    if user_answer == city:
        res["response"]["text"] = "Правильно! Сыграем ещё?"
        sessionStorage[user_id]["guessed_cities"].append(city)
        sessionStorage[user_id]["game_started"] = False

        sessionStorage[user_id].pop("city", None)
        sessionStorage[user_id].pop("attempt", None)

        res["response"]["buttons"] = [
            {"title": "Да", "hide": True},
            {"title": "Нет", "hide": True},
        ]
    else:
        if attempt == 3:
            res["response"]["text"] = f"Вы пытались. Это {city.title()}. Сыграем ещё?"
            sessionStorage[user_id]["guessed_cities"].append(city)
            sessionStorage[user_id]["game_started"] = False
            sessionStorage[user_id].pop("city", None)
            sessionStorage[user_id].pop("attempt", None)
            res["response"]["buttons"] = [
                {"title": "Да", "hide": True},
                {"title": "Нет", "hide": True},
            ]
        else:
            sessionStorage[user_id]["attempt"] = 3
            res["response"]["card"] = {
                "type": "BigImage",
                "title": "Неправильно. Вот тебе дополнительное фото",
                "image_id": cities[city][1],
            }
            res["response"]["text"] = "Попробуй угадать ещё раз! Какой это город?"


def get_city(req):
    """Извлекает название города из сущности YANDEX.GEO и приводит к нижнему регистру."""
    for entity in req["request"]["nlu"]["entities"]:
        if entity["type"] == "YANDEX.GEO":
            city = entity["value"].get("city")
            if city:
                return city.lower()
    return None


def get_first_name(req):
    """Извлекает имя из сущности YANDEX.FIO."""
    for entity in req["request"]["nlu"]["entities"]:
        if entity["type"] == "YANDEX.FIO":
            return entity["value"].get("first_name", None)
    return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    waitress.serve(app, host="0.0.0.0", port=port)
