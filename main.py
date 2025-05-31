import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import os
from datetime import datetime, timedelta
from keep_alive import keep_alive
from pymongo import MongoClient

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# MongoDB ühendus
MONGO_URI = "PASTA_SIINDE_SINU_CONNECTION_STRING"  # Pane siia MongoDB ühenduse string
client = MongoClient(MONGO_URI)
db = client["discord_bot"]
users_col = db["users"]
loans_col = db["loans"]

ALLOWED_CHANNEL_ID = 1377701866183331850  # <- MUUDA SEE ÕIGE KANALI IDKS

def get_balance(user_id):
    user = users_col.find_one({"_id": str(user_id)})
    return user.get("balance", 1000) if user else 1000

def set_balance(user_id, amount):
    users_col.update_one(
        {"_id": str(user_id)},
        {"$set": {"balance": amount}},
        upsert=True
    )

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

def has_claimed_daily_bonus(user_id):
    user = users_col.find_one({"_id": str(user_id)})
    if not user or "last_claim" not in user:
        return False
    last_claim = datetime.strptime(user["last_claim"], "%Y-%m-%d")
    return (datetime.now() - last_claim) < timedelta(days=1)

def claim_daily_bonus(user_id):
    balance = get_balance(user_id) + 100
    users_col.update_one(
        {"_id": str(user_id)},
        {
            "$set": {
                "balance": balance,
                "last_claim": datetime.now().strftime("%Y-%m-%d")
            }
        },
        upsert=True
    )

def get_loan(user_id):
    loan = loans_col.find_one({"_id": str(user_id)})
    return loan if loan else {"amount": 0, "interest": 0}

def set_loan(user_id, amount, interest):
    loans_col.update_one(
        {"_id": str(user_id)},
        {"$set": {"amount": amount, "interest": interest}},
        upsert=True
    )

def get_leaderboard():
    top_users = users_col.find().sort("balance", -1).limit(10)
    leaderboard = []
    for user in top_users:
        user_obj = bot.get_user(int(user["_id"]))
        name = user_obj.name if user_obj else f"ID: {user['_id']}"
        leaderboard.append((name, user.get("balance", 0)))
    return leaderboard

class BlackjackView(View):
    def __init__(self, ctx, player_cards, dealer_cards, bet):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.player_cards = player_cards
        self.dealer_cards = dealer_cards
        self.bet = bet

    async def end_game(self, interaction, result):
        user_id = str(interaction.user.id)
        balance = get_balance(user_id)

        if result == "win":
            win_amount = self.bet * 1.4
            balance += win_amount
            msg = f"🎉 Sa võitsid {win_amount:.2f}€! (1.4x sinu panusest)"
        elif result == "lose":
            msg = f"💀 Kaotasid {self.bet}€."
        else:
            balance += self.bet
            msg = "🤝 Viik, raha tagastati."

        set_balance(user_id, balance)
        await interaction.response.edit_message(
            content=f"{msg}\n\n**Sinu kaardid:** {', '.join(self.player_cards)} ({get_value(self.player_cards)})\n**Diileri kaardid:** {', '.join(self.dealer_cards)} ({get_value(self.dealer_cards)})\n💰 Jääk: {balance}€",
            view=None
        )

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
            content=f"🎰 **Blackjack algas!**\n\n**Sinu kaardid:** {', '.join(player_cards)} ({val})\n**Diileri kaart:** {dealer_cards[0]}\nVali oma käik:",
            view=view
        )

@bot.command()
async def blackjack(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("🚫 Seda käsku saab kasutada ainult kindlas kanalis.")
        return
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
async def daily(ctx):
    user_id = str(ctx.author.id)
    if has_claimed_daily_bonus(user_id):
        await ctx.send("❌ Sa oled juba täna boonuse saanud!")
    else:
        claim_daily_bonus(user_id)
        await ctx.send("✅ Sa said oma päevaboonuse: 100€")

@bot.command()
async def edetabel(ctx):
    leaderboard = get_leaderboard()
    edetabel = "\n".join([f"{i+1}. {name} - {score}€" for i, (name, score) in enumerate(leaderboard)])
    await ctx.send(f"🏆 **Edetabel:**\n{edetabel}")

@bot.command()
@commands.has_permissions(administrator=True)
async def laen(ctx, kasutaja: discord.Member, amount: int):
    user_id = str(kasutaja.id)
    loan = get_loan(user_id)
    if loan["amount"] > 0:
        await ctx.send(f"❌ {kasutaja.display_name} juba omab laenu: {loan['amount']}€.")
        return
    set_loan(user_id, amount, 0.1)
    set_balance(user_id, get_balance(user_id) + amount)
    await ctx.send(f"✅ {kasutaja.display_name} sai {amount}€ laenu (intressiga 10%).")

@bot.command()
async def laen_olek(ctx):
    user_id = str(ctx.author.id)
    loan = get_loan(user_id)
    if loan["amount"] == 0:
        await ctx.send("❌ Sul pole laenu.")
    else:
        total_due = loan["amount"] * (1 + loan["interest"])
        await ctx.send(f"📊 **Sinu laen:**\nLaenu summa: {loan['amount']}€\nIntress: {loan['interest']*100}%\nKohustuslik tasumine: {total_due:.2f}€")

keep_alive()
bot.run("mongodb+srv://bot:<kammerihull1A>@bot.pcrx3yf.mongodb.net/?retryWrites=true&w=majority&appName=bot")

