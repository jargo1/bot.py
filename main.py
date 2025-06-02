import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
load_dotenv()
import random
import mysql.connector
from datetime import datetime
import os
from decimal import Decimal
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Funktsioon iga DB ühenduse jaoks
def get_db_cursor():
    db = mysql.connector.connect(
        host="sql7.freesqldatabase.com",
        user="sql7782601",
        password="mP1wFwctMn",
        database="sql7782601"
    )
    return db, db.cursor()

# Andmebaasi abifunktsioonid
def get_balance(user_id):
    db, cursor = get_db_cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    return result[0] if result else 1000

def set_balance(user_id, amount):
    db, cursor = get_db_cursor()
    cursor.execute("INSERT INTO users (user_id, balance) VALUES (%s, %s) ON DUPLICATE KEY UPDATE balance = %s", (user_id, amount, amount))
    db.commit()
    cursor.close()
    db.close()

def get_loan(user_id):
    db, cursor = get_db_cursor()
    cursor.execute("SELECT amount, interest FROM loans WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    return {"amount": result[0], "interest": result[1]} if result else {"amount": 0, "interest": 0}

def set_loan(user_id, amount, interest):
    db, cursor = get_db_cursor()
    cursor.execute("INSERT INTO loans (user_id, amount, interest) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE amount = %s, interest = %s", (user_id, amount, interest, amount, interest))
    db.commit()
    cursor.close()
    db.close()

def get_leaderboard():
    db, cursor = get_db_cursor()
    cursor.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    result = cursor.fetchall()
    cursor.close()
    db.close()
    return result

# Blackjacki abifunktsioonid
def get_value(cards):
    value, aces = 0, 0
    for card in cards:
        if card in ['J', 'Q', 'K']:
            value += 10
        elif card == 'A':
            aces += 1
            value += 11
        else:
            value += int(card)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

def get_card():
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    return random.choice(ranks)

class BlackjackView(View):
    def __init__(self, ctx, player_cards, dealer_cards, bet):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.player_cards = player_cards
        self.dealer_cards = dealer_cards
        self.bet = bet

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        self.player_cards.append(get_card())
        val = get_value(self.player_cards)
        if val > 21:
            await self.end_game(interaction, "lose")
        else:
            await interaction.response.edit_message(
                content=f"**Sinu kaardid:** {', '.join(self.player_cards)} ({val})\n**Diileri kaart:** {self.dealer_cards[0]}\nVali järgmine käik:",
                view=self
            )

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.success)
    async def stand(self, interaction: discord.Interaction, button: Button):
        while get_value(self.dealer_cards) < 17:
            self.dealer_cards.append(get_card())

        player_val = get_value(self.player_cards)
        dealer_val = get_value(self.dealer_cards)

        if dealer_val > 21 or player_val > dealer_val:
            await self.end_game(interaction, "win")
        elif player_val < dealer_val:
            await self.end_game(interaction, "lose")
        else:
            await self.end_game(interaction, "draw")

    async def end_game(self, interaction, result):
        user_id = str(interaction.user.id)
        balance = get_balance(user_id)

        if result == "win":
            winnings = self.bet * 2
            set_balance(user_id, balance + winnings)
            msg = f"🎉 Võitsid! Sinu võit: {winnings}€"
        elif result == "draw":
            set_balance(user_id, balance + self.bet)
            msg = f"🤝 Viik! Panus tagastati: {self.bet}€"
        else:
            msg = f"😞 Kaotasid! Panus: {self.bet}€"

        await interaction.response.edit_message(
            content=f"{msg}\n\n**Sinu kaardid:** {', '.join(self.player_cards)} ({get_value(self.player_cards)})\n"
                    f"**Diileri kaardid:** {', '.join(self.dealer_cards)} ({get_value(self.dealer_cards)})",
            view=None
        )

class PanuseView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx

    @discord.ui.button(label="100€", style=discord.ButtonStyle.secondary)
    async def bet100(self, interaction: discord.Interaction, button: Button):
        await self.start_game(interaction, 100)

    @discord.ui.button(label="250€", style=discord.ButtonStyle.secondary)
    async def bet250(self, interaction: discord.Interaction, button: Button):
        await self.start_game(interaction, 250)

    @discord.ui.button(label="500€", style=discord.ButtonStyle.secondary)
    async def bet500(self, interaction: discord.Interaction, button: Button):
        await self.start_game(interaction, 500)

    async def start_game(self, interaction, panus):
        user_id = str(interaction.user.id)
        raha = get_balance(user_id)

        if panus > raha:
            await interaction.response.send_message(f"💸 Sul pole piisavalt raha! Jääk: {raha}€", ephemeral=True)
            return

        set_balance(user_id, raha - panus)
        player_cards = [get_card(), get_card()]
        dealer_cards = [get_card(), get_card()]
        val = get_value(player_cards)

        view = BlackjackView(self.ctx, player_cards, dealer_cards, panus)
        await interaction.response.edit_message(
            content=f"🎰 **Blackjack algas!**\n\n**Sinu kaardid:** {', '.join(player_cards)} ({val})\n"
                    f"**Diileri kaart:** {dealer_cards[0]}\nVali oma käik:",
            view=view
        )

@bot.command()
async def blackjack(ctx):
    await ctx.send("💵 Vali panus blackjacki alustamiseks:", view=PanuseView(ctx))

@bot.command()
async def saldo(ctx):
    raha = get_balance(str(ctx.author.id))
    await ctx.send(f"💰 Sinu kontojääk on {raha}€")

@bot.command()
async def lisa(ctx, summa: int):
    user_id = str(ctx.author.id)
    raha = get_balance(user_id) + summa
    set_balance(user_id, raha)
    await ctx.send(f"✅ Sinu kontole lisati {summa}€. Uus jääk: {raha}€")

@bot.command()
async def edetabel(ctx):
    leaderboard = get_leaderboard()
    edetabel = "\n".join([f"{i+1}. <@{uid}> - {saldo}€" for i, (uid, saldo) in enumerate(leaderboard)])
    await ctx.send(f"🏆 **Edetabel:**\n{edetabel}")

@bot.command()
async def laen_olek(ctx):
    user_id = str(ctx.author.id)
    loan = get_loan(user_id)

    if loan["amount"] == 0:
        await ctx.send("❌ Sul pole laenu.")
    else:
        total_due = loan["amount"] * (1 + loan["interest"])
        await ctx.send(
            f"📊 **Sinu laen:**\nLaenu summa: {loan['amount']}€\nIntress: {loan['interest']*100}%\nKokku tagastatav: {total_due}€"
        )

@bot.command()
@commands.has_permissions(administrator=True)
async def laen(ctx, kasutaja: discord.Member, amount: int):
    user_id = str(kasutaja.id)
    loan = get_loan(user_id)
    if loan["amount"] > 0:
        await ctx.send(f"❌ {kasutaja.display_name} juba omab laenu: {loan['amount']}€.")
        return

    set_loan(user_id, amount, 0.1)
    current_balance = get_balance(user_id)
    set_balance(user_id, current_balance + amount)
    await ctx.send(f"✅ {kasutaja.display_name} sai {amount}€ laenu (intressiga 10%).")

@bot.command()
@commands.has_permissions(administrator=True)
async def reset_saldo(ctx, kasutaja: discord.Member = None):
    if kasutaja is None:
        kasutaja = ctx.author
    user_id = str(kasutaja.id)
    set_balance(user_id, 0)
    await ctx.send(f"🔁 {kasutaja.display_name} saldo on nullitud (0€).")

@bot.command()
async def maksa_tagasi(ctx, summa: float):
    user_id = str(ctx.author.id)
    saldo = get_balance(user_id)
    laen = get_loan(user_id)

    if laen["amount"] == 0:
        await ctx.send("❌ Sul ei ole aktiivset laenu.")
        return

    summa = Decimal(str(summa))

    if summa > saldo:
        await ctx.send(f"❌ Sul ei ole piisavalt raha. Sinu jääk: {saldo}€")
        return

    if summa > laen["amount"]:
        summa = laen["amount"]

    uus_saldo = saldo - summa
    uus_laen = laen["amount"] - summa

    set_balance(user_id, uus_saldo)
    set_loan(user_id, uus_laen, laen["interest"])

    db, cursor = get_db_cursor()
    cursor.execute(
        "INSERT INTO loan_repayments (user_id, amount_paid, repayment_date) VALUES (%s, %s, NOW())",
        (user_id, summa)
    )
    db.commit()
    cursor.close()
    db.close()

    await ctx.send(f"💸 Maksid tagasi {summa}€ laenu. Allesjäänud laen: {uus_laen}€")

keep_alive()
bot.run(os.getenv("TOKEN"))
