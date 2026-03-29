import os
import logging
import json
import random
import string
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# DIRECT CONFIGURATION - Add your values here
# ============================================
BOT_TOKEN = "7269851273:AAEVGwwR_HJyLFdSvBbY5OnUEJD8ETdTPxU"
OWNER_ID = 8477195695
# ============================================

# Verify configuration
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN is not set!")
    exit(1)

print(f"✅ Bot Token loaded")
print(f"✅ Owner ID: {OWNER_ID}")

# Data storage files
KEYS_FILE = "keys.json"           # Owner ki stored keys
USERS_FILE = "users.json"          # User data
PENDING_PAYMENTS_FILE = "pending_payments.json"
ORDERS_FILE = "orders.json"
OWNER_KEYS_FILE = "owner_keys.json"  # Owner ke liye separate key storage

# Game options
GAMES = {
    "mars_loader": {
        "name": "MARS LOADER",
        "emoji": "🚀",
        "prices": {
            "1day": 100,
            "3day": 279,
            "7day": 400,
            "15day": 600,
            "30day": 800,
            "60day": 1200
        }
    },
    "eliminator": {
        "name": "ELIMINATOR",
        "emoji": "⚡",
        "prices": {
            "1day": 150,
            "3day": 350,
            "7day": 600,
            "15day": 900,
            "30day": 1200,
            "60day": 1800
        }
    },
    "elite_loader": {
        "name": "ELITE LOADER",
        "emoji": "👑",
        "prices": {
            "1day": 200,
            "3day": 500,
            "7day": 900,
            "15day": 1400,
            "30day": 2000,
            "60day": 3000
        }
    }
}

# Helper functions
def load_data(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def generate_order_id():
    return f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

# Main bot class
class LicenseKeyBot:
    def __init__(self):
        self.keys_data = load_data(KEYS_FILE)           # Distributed keys
        self.users_data = load_data(USERS_FILE)          # User data
        self.pending_payments = load_data(PENDING_PAYMENTS_FILE)
        self.orders = load_data(ORDERS_FILE)
        self.owner_keys = load_data(OWNER_KEYS_FILE)     # Owner ki stored keys
    
    def save_all(self):
        save_data(KEYS_FILE, self.keys_data)
        save_data(USERS_FILE, self.users_data)
        save_data(PENDING_PAYMENTS_FILE, self.pending_payments)
        save_data(ORDERS_FILE, self.orders)
        save_data(OWNER_KEYS_FILE, self.owner_keys)
    
    # Owner Functions - Keys Store Karne Ke Liye
    def add_owner_key(self, game_name, duration, key, expiry_date):
        """Owner apni keys store kar sakta hai"""
        key_id = f"KEY_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100, 999)}"
        
        self.owner_keys[key_id] = {
            "key": key,
            "game": game_name,
            "duration": duration,
            "expiry": expiry_date,
            "status": "available",  # available, sold
            "created_at": datetime.now().isoformat(),
            "sold_to": None,
            "sold_at": None
        }
        self.save_all()
        return key_id
    
    def get_available_keys(self, game_name, duration):
        """Get available keys for specific game and duration"""
        available_keys = []
        for key_id, key_data in self.owner_keys.items():
            if (key_data["status"] == "available" and 
                key_data["game"] == game_name and 
                key_data["duration"] == duration):
                available_keys.append(key_id)
        return available_keys
    
    def assign_key_to_user(self, key_id, user_id, order_id):
        """Assign available key to user after payment"""
        if key_id in self.owner_keys and self.owner_keys[key_id]["status"] == "available":
            key_data = self.owner_keys[key_id]
            
            # Mark key as sold
            self.owner_keys[key_id]["status"] = "sold"
            self.owner_keys[key_id]["sold_to"] = str(user_id)
            self.owner_keys[key_id]["sold_at"] = datetime.now().isoformat()
            
            # Add to user's keys
            if str(user_id) not in self.users_data:
                self.users_data[str(user_id)] = {"keys": []}
            
            self.users_data[str(user_id)]["keys"].append({
                "key": key_data["key"],
                "game": key_data["game"],
                "duration": key_data["duration"],
                "expiry": key_data["expiry"],
                "order_id": order_id,
                "assigned_at": datetime.now().isoformat()
            })
            
            # Update order
            if order_id in self.orders:
                self.orders[order_id]["key"] = key_data["key"]
                self.orders[order_id]["status"] = "completed"
            
            self.save_all()
            return True, key_data["key"], key_data["expiry"]
        
        return False, None, None
    
    def create_order(self, user_id, user_name, game_id, duration, amount):
        """Create payment order"""
        order_id = generate_order_id()
        game_name = GAMES[game_id]["name"]
        
        order = {
            "order_id": order_id,
            "user_id": str(user_id),
            "user_name": user_name,
            "game_id": game_id,
            "game_name": game_name,
            "duration": duration,
            "amount": amount,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "payment_screenshot": None,
            "key": None
        }
        
        self.orders[order_id] = order
        self.save_all()
        return order_id
    
    def update_payment_screenshot(self, order_id, screenshot_path):
        """Update order with payment screenshot"""
        if order_id in self.orders:
            self.orders[order_id]["payment_screenshot"] = screenshot_path
            self.orders[order_id]["status"] = "waiting_verification"
            self.save_all()
            return True
        return False
    
    def get_user_keys(self, user_id):
        """Get all keys for a user"""
        if str(user_id) in self.users_data:
            return self.users_data[str(user_id)]["keys"]
        return []
    
    def get_user_orders(self, user_id):
        """Get all orders for a user"""
        user_orders = []
        for order_id, order in self.orders.items():
            if order["user_id"] == str(user_id):
                user_orders.append(order)
        return sorted(user_orders, key=lambda x: x["created_at"], reverse=True)
    
    def delete_user_key(self, user_id, key):
        """Delete a key for user"""
        if str(user_id) in self.users_data:
            keys = self.users_data[str(user_id)]["keys"]
            for i, k in enumerate(keys):
                if k["key"] == key:
                    del keys[i]
                    self.save_all()
                    return True
        return False
    
    # Owner Functions
    def get_all_orders(self, status=None):
        """Get all orders with optional status filter"""
        if status:
            return {k: v for k, v in self.orders.items() if v["status"] == status}
        return self.orders
    
    def get_all_keys(self):
        """Get all owner keys"""
        return self.owner_keys
    
    def get_stats(self):
        """Get bot statistics"""
        total_orders = len(self.orders)
        completed_orders = len([o for o in self.orders.values() if o["status"] == "completed"])
        pending_orders = len([o for o in self.orders.values() if o["status"] in ["pending", "waiting_verification"]])
        
        total_keys = len(self.owner_keys)
        available_keys = len([k for k in self.owner_keys.values() if k["status"] == "available"])
        sold_keys = len([k for k in self.owner_keys.values() if k["status"] == "sold"])
        
        total_revenue = sum([o["amount"] for o in self.orders.values() if o["status"] == "completed"])
        
        return {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "pending_orders": pending_orders,
            "total_keys": total_keys,
            "available_keys": available_keys,
            "sold_keys": sold_keys,
            "total_revenue": total_revenue,
            "total_users": len(self.users_data)
        }

bot_manager = LicenseKeyBot()

# Keyboard Markups
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🛒 Purchase Keys", callback_data="purchase")],
        [InlineKeyboardButton("🔑 My Keys", callback_data="my_keys")],
        [InlineKeyboardButton("📜 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton("🗑 Delete Key", callback_data="delete_key")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_game_menu():
    keyboard = []
    for game_id, game_data in GAMES.items():
        keyboard.append([InlineKeyboardButton(
            f"{game_data['emoji']} {game_data['name']}", 
            callback_data=f"game_{game_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_duration_menu(game_id):
    keyboard = []
    game_data = GAMES[game_id]
    duration_names = {
        "1day": "1 Day",
        "3day": "3 Days", 
        "7day": "7 Days",
        "15day": "15 Days",
        "30day": "30 Days",
        "60day": "60 Days"
    }
    
    for duration_key, price in game_data["prices"].items():
        keyboard.append([InlineKeyboardButton(
            f"{duration_names[duration_key]} - ₹{price}", 
            callback_data=f"duration_{game_id}_{duration_key}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Back to Games", callback_data="back_to_games")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")],
        [InlineKeyboardButton("🔑 Add New Keys", callback_data="admin_add_keys")],
        [InlineKeyboardButton("📋 View All Keys", callback_data="admin_view_keys")],
        [InlineKeyboardButton("✅ Verify Payments", callback_data="admin_verify_payments")],
        [InlineKeyboardButton("📦 All Orders", callback_data="admin_orders")],
        [InlineKeyboardButton("💰 Revenue Stats", callback_data="admin_revenue")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = (
        f"🎮 *Welcome to License Key Bot* 🎮\n\n"
        f"Hello {user.first_name}!\n\n"
        f"📌 *Available Games:*\n"
    )
    
    for game_id, game_data in GAMES.items():
        welcome_message += f"{game_data['emoji']} *{game_data['name']}* - Starting from ₹{min(game_data['prices'].values())}\n"
    
    welcome_message += f"\nUse the buttons below to get started:"
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    if data == "main_menu":
        await query.edit_message_text(
            "🎮 *Main Menu* 🎮\n\nChoose an option:",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
    
    elif data == "help":
        help_text = (
            "ℹ️ *How to Use This Bot* ℹ️\n\n"
            "1️⃣ *Purchase Keys*\n"
            "   - Select a game and duration\n"
            "   - Make payment to given UPI ID\n"
            "   - Upload payment screenshot\n"
            "   - Wait for admin verification\n\n"
            "2️⃣ *My Keys*\n"
            "   - View all your active license keys\n\n"
            "3️⃣ *My Orders*\n"
            "   - Track your order status\n\n"
            "4️⃣ *Delete Key*\n"
            "   - Remove a key from your account\n\n"
            "📞 *Support:* Contact @admin for any issues"
        )
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]]),
            parse_mode="Markdown"
        )
    
    elif data == "purchase":
        await query.edit_message_text(
            "🛒 *Purchase Keys* 🛒\n\nSelect a game:",
            reply_markup=get_game_menu(),
            parse_mode="Markdown"
        )
    
    elif data.startswith("game_"):
        game_id = data.replace("game_", "")
        context.user_data["selected_game"] = game_id
        await query.edit_message_text(
            f"🎮 *Game: {GAMES[game_id]['name']}* 🎮\n\nSelect key duration:",
            reply_markup=get_duration_menu(game_id),
            parse_mode="Markdown"
        )
    
    elif data.startswith("duration_"):
        _, game_id, duration_key = data.split("_")
        price = GAMES[game_id]["prices"][duration_key]
        
        # Check if keys available
        game_name = GAMES[game_id]["name"]
        available_keys = bot_manager.get_available_keys(game_name, duration_key)
        
        if not available_keys:
            await query.edit_message_text(
                f"❌ *Sorry!* ❌\n\n"
                f"{GAMES[game_id]['emoji']} *{game_name}* - *{duration_key}*\n\n"
                f"Currently no keys available for this duration.\n\n"
                f"Please contact admin for availability.\n\n"
                f"📞 Support: Contact @admin",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Games", callback_data="back_to_games")
                ]]),
                parse_mode="Markdown"
            )
            return
        
        context.user_data["payment_data"] = {
            "game_id": game_id,
            "duration_key": duration_key,
            "price": price
        }
        
        # Create order
        order_id = bot_manager.create_order(
            user.id,
            user.first_name,
            game_id,
            duration_key,
            price
        )
        
        context.user_data["current_order"] = order_id
        
        # UPI Payment Details
        upi_id = "your_upi_id@okhdfcbank"  # Change to your UPI ID
        
        payment_message = (
            f"💳 *Payment Details* 💳\n\n"
            f"🆔 *Order ID:* `{order_id}`\n"
            f"🎮 *Game:* {GAMES[game_id]['name']}\n"
            f"⏱️ *Duration:* {duration_key.replace('day', ' Day')}\n"
            f"💰 *Amount:* ₹{price}\n\n"
            f"📱 *UPI ID:* `{upi_id}`\n\n"
            f"*Instructions:*\n"
            f"1️⃣ Send ₹{price} to the UPI ID above\n"
            f"2️⃣ Use Order ID as payment reference\n"
            f"3️⃣ Take a screenshot of successful payment\n"
            f"4️⃣ Click below and upload screenshot\n\n"
            f"⚠️ *Note:* Key will be assigned after verification!"
        )
        
        keyboard = [
            [InlineKeyboardButton("📸 Upload Payment Screenshot", callback_data=f"upload_{order_id}")],
            [InlineKeyboardButton("🔙 Cancel", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            payment_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("upload_"):
        order_id = data.replace("upload_", "")
        context.user_data["pending_screenshot"] = order_id
        
        await query.edit_message_text(
            f"📸 *Upload Payment Screenshot* 📸\n\n"
            f"🆔 *Order ID:* `{order_id}`\n\n"
            f"Please send the payment confirmation screenshot.\n\n"
            f"*Screenshot should show:*\n"
            f"✅ Transaction ID\n"
            f"✅ Amount: ₹{bot_manager.orders[order_id]['amount']}\n"
            f"✅ Payment Status: Success\n\n"
            f"Send the screenshot as a photo.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Cancel", callback_data="main_menu")
            ]]),
            parse_mode="Markdown"
        )
    
    elif data == "my_keys":
        user_keys = bot_manager.get_user_keys(user.id)
        
        if user_keys:
            message = "🔑 *Your Active Keys:* 🔑\n\n"
            for key_data in user_keys:
                expiry = datetime.fromisoformat(key_data["expiry"]).strftime("%Y-%m-%d")
                message += f"🎮 *{key_data['game']}*\n"
                message += f"🔐 Key: `{key_data['key']}`\n"
                message += f"📅 Expires: {expiry}\n"
                message += "─" * 20 + "\n"
        else:
            message = "📭 *You don't have any active keys.*"
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]]),
            parse_mode="Markdown"
        )
    
    elif data == "my_orders":
        user_orders = bot_manager.get_user_orders(user.id)
        
        if user_orders:
            message = "📜 *Your Orders:* 📜\n\n"
            for order in user_orders[:10]:
                created = datetime.fromisoformat(order["created_at"]).strftime("%Y-%m-%d %H:%M")
                status_emoji = "✅" if order["status"] == "completed" else "⏳"
                
                message += f"{status_emoji} *{order['order_id']}*\n"
                message += f"🎮 {order['game_name']} - ₹{order['amount']}\n"
                message += f"📅 {created}\n"
                message += f"Status: {order['status'].upper()}\n"
                
                if order.get("key"):
                    message += f"🔑 Key: `{order['key']}`\n"
                
                message += "─" * 20 + "\n"
        else:
            message = "📭 *You don't have any orders.*"
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]]),
            parse_mode="Markdown"
        )
    
    elif data == "delete_key":
        context.user_data["action"] = "delete"
        await query.edit_message_text(
            "🗑 *Delete Key* 🗑\n\n"
            "Please enter the license key you want to delete:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Cancel", callback_data="main_menu")
            ]]),
            parse_mode="Markdown"
        )
    
    elif data == "back_to_games":
        await query.edit_message_text(
            "🛒 *Select Game:*\n\nChoose a game to generate key for:",
            reply_markup=get_game_menu(),
            parse_mode="Markdown"
        )
    
    # Admin Panel Handlers
    elif user.id == OWNER_ID:
        if data == "admin_menu":
            await query.edit_message_text(
                "👑 *Admin Panel* 👑\n\nSelect an option:",
                reply_markup=get_admin_menu(),
                parse_mode="Markdown"
            )
        
        elif data == "admin_dashboard":
            stats = bot_manager.get_stats()
            
            dashboard = (
                "📊 *Dashboard* 📊\n\n"
                f"📦 *Orders*\n"
                f"├ Total: {stats['total_orders']}\n"
                f"├ Completed: {stats['completed_orders']}\n"
                f"└ Pending: {stats['pending_orders']}\n\n"
                f"🔑 *Keys*\n"
                f"├ Total: {stats['total_keys']}\n"
                f"├ Available: {stats['available_keys']}\n"
                f"└ Sold: {stats['sold_keys']}\n\n"
                f"💰 *Revenue*: ₹{stats['total_revenue']}\n"
                f"👥 *Users*: {stats['total_users']}"
            )
            
            await query.edit_message_text(
                dashboard,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Refresh", callback_data="admin_dashboard"),
                    InlineKeyboardButton("🔙 Back", callback_data="admin_menu")
                ]]),
                parse_mode="Markdown"
            )
        
        elif data == "admin_add_keys":
            context.user_data["admin_action"] = "add_keys"
            await query.edit_message_text(
                "🔑 *Add New Keys* 🔑\n\n"
                "Send keys in this format:\n\n"
                "`game|duration|key|expiry_date`\n\n"
                "*Example:*\n"
                "`MARS LOADER|30day|ABC123XYZ|2025-12-31`\n"
                "`ELIMINATOR|7day|XYZ789ABC|2025-06-15`\n\n"
                "You can send multiple keys, one per line.\n\n"
                "*Durations:* 1day, 3day, 7day, 15day, 30day, 60day\n\n"
                "Send /cancel to stop.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancel", callback_data="admin_menu")
                ]]),
                parse_mode="Markdown"
            )
        
        elif data == "admin_view_keys":
            keys = bot_manager.get_all_keys()
            
            if keys:
                message = "🔑 *All Keys* 🔑\n\n"
                for key_id, key_data in list(keys.items())[:20]:  # Show last 20
                    status_emoji = "✅" if key_data["status"] == "available" else "❌"
                    message += f"{status_emoji} *{key_data['key']}*\n"
                    message += f"   🎮 {key_data['game']} - {key_data['duration']}\n"
                    message += f"   📅 Expires: {key_data['expiry']}\n"
                    if key_data["status"] == "sold":
                        message += f"   👤 Sold to: {key_data['sold_to']}\n"
                    message += "─" * 20 + "\n"
                
                keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="admin_view_keys")],
                           [InlineKeyboardButton("🔙 Back", callback_data="admin_menu")]]
                
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "📭 No keys added yet.\n\nUse 'Add New Keys' to add keys.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_menu")
                    ]]),
                    parse_mode="Markdown"
                )
        
        elif data == "admin_verify_payments":
            pending_orders = bot_manager.get_all_orders("waiting_verification")
            
            if pending_orders:
                keyboard = []
                for order_id, order in pending_orders.items():
                    keyboard.append([InlineKeyboardButton(
                        f"📸 {order_id} - {order['user_name']} - ₹{order['amount']}",
                        callback_data=f"verify_order_{order_id}"
                    )])
                keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_menu")])
                
                await query.edit_message_text(
                    "📸 *Pending Verifications* 📸\n\nSelect order to verify:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "✅ No pending verifications.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_menu")
                    ]]),
                    parse_mode="Markdown"
                )
        
        elif data.startswith("verify_order_"):
            order_id = data.replace("verify_order_", "")
            order = bot_manager.orders.get(order_id)
            
            if order:
                game_name = order["game_name"]
                duration = order["duration"]
                
                # Check if keys available
                available_keys = bot_manager.get_available_keys(game_name, duration)
                
                if available_keys:
                    keyboard = []
                    for key_id in available_keys[:10]:  # Show first 10 keys
                        key_data = bot_manager.owner_keys[key_id]
                        keyboard.append([InlineKeyboardButton(
                            f"🔑 {key_data['key']} (Expires: {key_data['expiry']})",
                            callback_data=f"assign_key_{order_id}_{key_id}"
                        )])
                    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_verify_payments")])
                    
                    verification_message = (
                        f"🔍 *Verify Order* 🔍\n\n"
                        f"🆔 Order ID: `{order_id}`\n"
                        f"👤 User: {order['user_name']} (ID: {order['user_id']})\n"
                        f"🎮 Game: {game_name}\n"
                        f"⏱️ Duration: {duration}\n"
                        f"💰 Amount: ₹{order['amount']}\n\n"
                        f"📸 Screenshot received!\n\n"
                        f"Select a key to assign to this user:"
                    )
                    
                    # Send screenshot if available
                    if order.get("payment_screenshot") and os.path.exists(order["payment_screenshot"]):
                        try:
                            with open(order["payment_screenshot"], 'rb') as f:
                                await query.message.reply_photo(
                                    InputFile(f),
                                    caption=verification_message,
                                    reply_markup=InlineKeyboardMarkup(keyboard),
                                    parse_mode="Markdown"
                                )
                            await query.delete_message()
                        except Exception as e:
                            logger.error(f"Error sending screenshot: {e}")
                            await query.edit_message_text(
                                verification_message,
                                reply_markup=InlineKeyboardMarkup(keyboard),
                                parse_mode="Markdown"
                            )
                    else:
                        await query.edit_message_text(
                            verification_message,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode="Markdown"
                        )
                else:
                    await query.edit_message_text(
                        f"❌ No keys available for {game_name} - {duration}\n\n"
                        f"Please add keys first using 'Add New Keys' option.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("➕ Add Keys", callback_data="admin_add_keys"),
                            InlineKeyboardButton("🔙 Back", callback_data="admin_verify_payments")
                        ]]),
                        parse_mode="Markdown"
                    )
        
        elif data.startswith("assign_key_"):
            _, order_id, key_id = data.split("_", 2)
            order = bot_manager.orders.get(order_id)
            
            if order:
                # Assign key to user
                success, key, expiry = bot_manager.assign_key_to_user(key_id, int(order["user_id"]), order_id)
                
                if success:
                    # Notify user
                    try:
                        await context.bot.send_message(
                            chat_id=int(order["user_id"]),
                            text=(
                                f"✅ *Payment Verified! Key Assigned!* ✅\n\n"
                                f"🎮 *Game:* {order['game_name']}\n"
                                f"🔑 *Your License Key:* `{key}`\n"
                                f"📅 *Expires:* {expiry}\n"
                                f"🆔 *Order ID:* `{order_id}`\n\n"
                                f"Use this key to activate your game. Keep it safe!"
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Error notifying user: {e}")
                    
                    await query.edit_message_text(
                        f"✅ Order {order_id} verified!\n\n"
                        f"Key `{key}` assigned to {order['user_name']}\n"
                        f"User has been notified.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_menu")
                        ]]),
                        parse_mode="Markdown"
                    )
                else:
                    await query.edit_message_text(
                        "❌ Failed to assign key. Key may already be sold.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back", callback_data="admin_verify_payments")
                        ]]),
                        parse_mode="Markdown"
                    )
        
        elif data == "admin_orders":
            orders = bot_manager.get_all_orders()
            
            if orders:
                message = "📦 *All Orders* 📦\n\n"
                for order_id, order in list(orders.items())[:20]:
                    created = datetime.fromisoformat(order["created_at"]).strftime("%Y-%m-%d")
                    status_emoji = "✅" if order["status"] == "completed" else "⏳"
                    message += f"{status_emoji} *{order_id}*\n"
                    message += f"   👤 {order['user_name']}\n"
                    message += f"   🎮 {order['game_name']} - ₹{order['amount']}\n"
                    message += f"   📅 {created} - {order['status']}\n"
                    if order.get("key"):
                        message += f"   🔑 `{order['key']}`\n"
                    message += "─" * 20 + "\n"
                
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Refresh", callback_data="admin_orders"),
                        InlineKeyboardButton("🔙 Back", callback_data="admin_menu")
                    ]]),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "📭 No orders yet.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="admin_menu")
                    ]]),
                    parse_mode="Markdown"
                )
        
        elif data == "admin_revenue":
            stats = bot_manager.get_stats()
            
            # Calculate revenue by game
            revenue_by_game = {}
            for order in bot_manager.orders.values():
                if order["status"] == "completed":
                    game = order["game_name"]
                    revenue_by_game[game] = revenue_by_game.get(game, 0) + order["amount"]
            
            revenue_message = (
                "💰 *Revenue Report* 💰\n\n"
                f"📊 *Total Revenue:* ₹{stats['total_revenue']}\n\n"
                f"🎮 *Revenue by Game:*\n"
            )
            
            for game, revenue in revenue_by_game.items():
                revenue_message += f"   {game}: ₹{revenue}\n"
            
            revenue_message += f"\n📦 *Completed Orders:* {stats['completed_orders']}\n"
            revenue_message += f"🔑 *Keys Sold:* {stats['sold_keys']}"
            
            await query.edit_message_text(
                revenue_message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Refresh", callback_data="admin_revenue"),
                    InlineKeyboardButton("🔙 Back", callback_data="admin_menu")
                ]]),
                parse_mode="Markdown"
            )

# Message Handlers
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Handle admin adding keys
    if user_id == OWNER_ID and context.user_data.get("admin_action") == "add_keys":
        if message_text.lower() == "/cancel":
            context.user_data.pop("admin_action", None)
            await update.message.reply_text(
                "❌ Cancelled adding keys.",
                reply_markup=get_admin_menu()
            )
            return
        
        # Parse keys
        lines = message_text.strip().split('\n')
        added_count = 0
        failed_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('|')
            if len(parts) == 4:
                game_name, duration, key, expiry = [p.strip() for p in parts]
                
                # Validate game name
                game_found = False
                for game_id, game_data in GAMES.items():
                    if game_data["name"].lower() == game_name.lower():
                        game_found = True
                        break
                
                if game_found and duration in ["1day", "3day", "7day", "15day", "30day", "60day"]:
                    bot_manager.add_owner_key(game_name, duration, key, expiry)
                    added_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
        
        await update.message.reply_text(
            f"✅ *Keys Added*\n\n"
            f"✅ Successfully added: {added_count}\n"
            f"❌ Failed: {failed_count}\n\n"
            f"Use /admin to go back to admin panel.",
            parse_mode="Markdown"
        )
        
        context.user_data.pop("admin_action", None)
        return
    
    # Handle delete key
    if "action" in context.user_data and context.user_data["action"] == "delete":
        result = bot_manager.delete_user_key(user_id, message_text)
        if result:
            await update.message.reply_text(
                f"✅ Key `{message_text}` deleted successfully!",
                parse_mode="Markdown",
                reply_markup=get_main_menu()
            )
        else:
            await update.message.reply_text(
                f"❌ Key not found or you don't own this key",
                parse_mode="Markdown",
                reply_markup=get_main_menu()
            )
        context.user_data.pop("action")
        return
    
    # Handle screenshot upload
    if "pending_screenshot" in context.user_data:
        order_id = context.user_data["pending_screenshot"]
        
        if update.message.photo:
            # Save screenshot
            photo_file = await update.message.photo[-1].get_file()
            os.makedirs("screenshots", exist_ok=True)
            screenshot_path = f"screenshots/{order_id}.jpg"
            await photo_file.download_to_drive(screenshot_path)
            
            # Update order
            bot_manager.update_payment_screenshot(order_id, screenshot_path)
            
            # Notify admin
            try:
                order = bot_manager.orders.get(order_id)
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=(
                        f"📸 *New Payment Screenshot!*\n\n"
                        f"🆔 Order: {order_id}\n"
                        f"👤 User: {order['user_name']}\n"
                        f"🎮 Game: {order['game_name']}\n"
                        f"💰 Amount: ₹{order['amount']}\n\n"
                        f"Check admin panel to verify."
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error notifying admin: {e}")
            
            await update.message.reply_text(
                f"✅ *Screenshot Received!* ✅\n\n"
                f"🆔 Order ID: `{order_id}`\n\n"
                f"Your payment screenshot has been submitted.\n"
                f"Admin will verify and assign your key shortly.\n\n"
                f"You'll receive a notification once verified.",
                parse_mode="Markdown",
                reply_markup=get_main_menu()
            )
            
            context.user_data.pop("pending_screenshot")
            context.user_data.pop("payment_data", None)
        
        else:
            await update.message.reply_text(
                "❌ Please send a photo (screenshot) of your payment confirmation.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancel", callback_data="main_menu")
                ]])
            )
        
        return
    
    await update.message.reply_text(
        "Please use the buttons below to interact with the bot.",
        reply_markup=get_main_menu()
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command handler"""
    if update.effective_user.id == OWNER_ID:
        await update.message.reply_text(
            "👑 *Admin Panel* 👑\n\nWelcome to admin panel!",
            reply_markup=get_admin_menu(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ You are not authorized to use this command.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 License Key Bot is starting...")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"🎮 Games: {len(GAMES)}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()