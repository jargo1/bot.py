import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import mysql.connector
from datetime import datetime, timedelta
import os

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

def init_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, balance INT DEFAULT 1000, last_claim DATE)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS loans (user_id BIGINT PRIMARY KEY, amount INT, interest FLOAT)"
    )
    db.commit()
    cursor.close()
    db.close()

# (Siia tulevad kõik funktsioonid ja käsud, mis olid eelnevas koodis...)
# Faili pikkuse tõttu ülejäänud kood on lõigatud välja

from keep_alive import keep_alive
keep_alive()
init_db()
bot.run(os.getenv("TOKEN"))
