import os
import asyncio
import time
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

# ... [Keep your handlers: start, macro_analysis, etc. exactly as they are] ...

# --- Background Bot Task ---
@app.on_event("startup")
async def start_bot():
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    
    if not token:
        raise ValueError("❌ TELEGRAM_TOKEN not set!")
    
    print("🌐 Initializing Bot Connection...")
    
    # 🛡️ Retry Logic for Network Stability
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # ⏳ Wait 2 seconds for network stack to ready up (Critical for HF Spaces)
            if attempt == 0:
                await asyncio.sleep(2) 
                
            application = ApplicationBuilder().token(token).build()
            
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("macro", macro_analysis))
            application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
            application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
            
            await application.initialize()
            await application.start()
            
            # Start polling in background
            asyncio.create_task(application.updater.start_polling())
            
            print("✅ Bot Connected Successfully!")
            return # Exit function on success
            
        except NetworkError as e:
            print(f"⚠️ Network Error (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise # Fail completely after all retries
            await asyncio.sleep(5) # Wait before retry
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            raise
