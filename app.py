import os
import asyncio
from fastapi import FastAPI
from telegram import Update, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import NetworkError

import database
from analysis import MacroStrategist

app = FastAPI()

@app.get("/")
def health(): 
    return {"status": "Macro Analysis Bot Active"}

# --- Payment Config ---
STARS_PRICE = 800  # Monthly Premium

# --- Bot Handler Functions (MUST be defined BEFORE start_bot) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status = database.check_user_status(user_id)
    
    msg = "Welcome to the **MicroAnalysis Macro Terminal**. 🔬\n\n"
    if status == "trial":
        msg += "Your 24-hour Professional Trial is **ACTIVE**."
    elif status == "expired":
        msg += "Your trial has expired. Upgrade to Premium for 800 Stars to continue."
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def macro_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status = database.check_user_status(user_id)
    
    if status == "expired":
        await send_upgrade_invoice(update, context)
        return

    symbol = context.args[0].upper() if context.args else "EURUSD"
    analysis = MacroStrategist.get_market_bias(symbol)
    chart_path = MacroStrategist.generate_chart(symbol)

    await update.message.reply_photo(
        photo=open(chart_path, 'rb'),
        caption=f"**{analysis['symbol']} Analysis**\nPrice: {analysis['price']}\nBias: {analysis['bias']}\n\n_{analysis['interpretation']}_",
        parse_mode='Markdown'
    )

async def send_upgrade_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="Premium Macro Access",
        description="Unlock unlimited professional analysis and charts for 30 days.",
        payload="premium_subscription",
        currency="XTR",
        prices=[LabeledPrice("Monthly Subscription", STARS_PRICE)],
        provider_token=""  # Empty for Telegram Stars
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    database.set_premium(user_id)
    await update.message.reply_text("✅ Payment Successful! You now have unlimited Premium access.")

# --- Background Bot Task (MUST be AFTER all handlers) ---
@app.on_event("startup")
async def start_bot():
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    
    if not token:
        raise ValueError("❌ TELEGRAM_TOKEN not set!")
    
    print("🌐 Initializing Bot Connection...")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                await asyncio.sleep(2)  # Wait for network stack
                
            application = ApplicationBuilder().token(token).build()
            
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("macro", macro_analysis))
            application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
            application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
            
            await application.initialize()
            await application.start()
            asyncio.create_task(application.updater.start_polling())
            
            print("✅ Bot Connected Successfully!")
            return
            
        except NetworkError as e:
            print(f"⚠️ Network Error (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            raise
