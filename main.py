import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import json
import os
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "raha.json"
LOAN_FILE = "laenud.json"

# Kontrollime, kas vajalikud failid on olemas
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(LOAN_FILE):
    with open(LOAN_FILE, "w") as f:
        json.dump({}, f)

# Laadime andmed
def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Laenude haldamine
def load_loans():
    with open(LOAN_FILE, "r") as f:
        return json.load(f)

def save_loans(data):
    with open(LOAN_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Funktsioon saldodest lugemiseks
def get_balance(user_id):
    data = load_data()
    return data.get(str(user_id), 1000)

def set_balance(user_id, amount):
    data = load_data()
    data[str(user_id)] = amount
    save_data(data)

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

# Päevaboonuse kontrollimine
def has_claimed_daily_bonus(user_id):
    bonuses = load_data()
    last_claim = bonuses.get(str(user_id), {}).get("last_claim", "1970-01-01")
    last_claim_date = datetime.strptime(last_claim, "%Y-%m-%d")
    if datetime.now() - last_claim_date >= timedelta(days=1):
        return False
    return True

def claim_daily_bonus(user_id):
    bonuses = load_data()
    bonuses[str(user_id)] = {
        "last_claim": datetime.now().strftime("%Y-%m-%d"),
        "bonus_claimed": True
    }
    save_data(bonuses)
    set_balance(user_id, get_balance(user_id) + 100)

# Laenu süsteem
def get_loan(user_id):
    loans = load_loans()
    return loans.get(str(user_id), {"amount": 0, "interest": 0})

def set_loan(user_id, amount, interest):
    loans = load_loans()
    loans[str(user_id)] = {"amount": amount, "interest": interest}
    save_loans(loans)

# Blackjacki klassid
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
            # 1.4x võit
            win_amount = self.bet * 1.4
            balance += win_amount
            msg = f"🎉 Sa võitsid {win_amount:.2f}€! (1.4x sinu panusest)"
        elif result == "lose":
            balance -= self.bet
            msg = f"💀 Kaotasid {self.bet}€."
        else:
            msg = "🤝 Viik, raha jäi samaks."

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
    async def bet10(self, interaction: discord.Interaction, button: Button):
        await self.start_game(interaction, 100)

    @discord.ui.button(label="250€", style=discord.ButtonStyle.secondary)
    async def bet50(self, interaction: discord.Interaction, button: Button):
        await self.start_game(interaction, 250)

    @discord.ui.button(label="500€", style=discord.ButtonStyle.secondary)
    async def bet100(self, interaction: discord.Interaction, button: Button):
        await self.start_game(interaction, 500)

    async def start_game(self, interaction, panus):
        user_id = str(interaction.user.id)
        raha = get_balance(user_id)
        if panus > raha:
            await interaction.response.send_message(f"💸 Sul pole piisavalt raha! Jääk: {raha}€", ephemeral=True)
            return

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
async def leaderboard(ctx):
    leaderboard = get_leaderboard()
    edetabel_str = "Edetabel:\n"
    for rank, (name, score) in enumerate(leaderboard, start=1):
        edetabel_str += f"{rank}. {name} - {score}\n"
    await ctx.send(edetabel_str)



#laen


@bot.command()
@commands.has_permissions(administrator=True)
async def laen(ctx, kasutaja: discord.Member, amount: int):
    user_id = str(kasutaja.id)
    loan = get_loan(user_id)

    if loan["amount"] > 0:
        await ctx.send(f"❌ {kasutaja.display_name} juba omab laenu: {loan['amount']}€.")
        return

    set_loan(user_id, amount, 0.1)  # Intress 10%
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
        await ctx.send(f"📊 **Sinu laen:**\nLaenu summa: {loan['amount']}€\nIntress: {loan['interest']*100}%\nKokku tagastatav summa: {total_due}€")


@bot.command()
@commands.has_permissions(administrator=True)
async def reset_saldo(ctx, kasutaja: discord.Member = None):
    if kasutaja is None:
        kasutaja = ctx.author
    user_id = str(kasutaja.id)
    set_balance(user_id, 0)
    await ctx.send(f"🔁 {kasutaja.display_name} saldo on nullitud (0€).")


def load_leaderboard():
    try:
        with open("leaderboard.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_leaderboard(leaderboard):
    with open("leaderboard.json", "w") as file:
        json.dump(leaderboard, file, indent=4)

def update_leaderboard(user_id, score):
    leaderboard = load_leaderboard()
    user_name = ctx.bot.get_user(int(user_id)).name  # Kogub kasutajanime
    leaderboard[user_name] = score
    save_leaderboard(leaderboard)

def get_leaderboard():
    leaderboard = load_leaderboard()
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
    return sorted_leaderboard





from keep_alive import keep_alive
keep_alive()
bot.run(os.getenv("TOKEN"))
