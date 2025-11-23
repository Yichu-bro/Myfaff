import express from 'express';
import mongoose from 'mongoose';
import cors from 'cors';
import { Telegraf } from 'telegraf';
import path from 'path';
import { fileURLToPath } from 'url';

// =========================================================
// 1. CONFIGURATION (EDIT THESE)
// =========================================================
const BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_HERE'; // Get from @BotFather
const MONGO_URI = 'mongodb://localhost:27017/ff_tools'; // Or your MongoDB Atlas URL
const WEBAPP_URL = 'https://your-domain.com'; // Your HTTPS URL where this is hosted
const PORT = process.env.PORT || 3000;

// =========================================================
// 2. SERVER SETUP
// =========================================================
const app = express();
const bot = new Telegraf(BOT_TOKEN);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public')); // Serves your index.html

// Database Connection
mongoose.connect(MONGO_URI)
    .then(() => console.log('✅ MongoDB Connected Successfully'))
    .catch(err => console.error('❌ MongoDB Connection Error:', err));

// =========================================================
// 3. DATABASE MODELS
// =========================================================
const UserSchema = new mongoose.Schema({
    tgId: { type: String, required: true, unique: true },
    username: String,
    coins: { type: Number, default: 50 }, // Starting Balance
    region: { type: String, default: 'ETHIOPIA' },
    savedUid: String,
    joinedAt: { type: Date, default: Date.now },
    history: [{
        action: String,
        targetUid: String,
        timestamp: { type: Date, default: Date.now },
        status: String
    }]
});

const User = mongoose.model('User', UserSchema);

// =========================================================
// 4. SIMULATION ENGINES
// =========================================================

/**
 * Simulates sending data to Garena servers.
 * Since there is no public API, this simulates latency and responses.
 */
async function simulateFFAction(uid, action) {
    return new Promise((resolve, reject) => {
        // Basic Validation
        if (!/^\d{8,12}$/.test(uid)) {
            return reject("Invalid UID Format. Must be 8-12 digits.");
        }

        // Simulate Network Latency (1.5s to 3s)
        const delay = Math.floor(Math.random() * 1500) + 1500;

        setTimeout(() => {
            // 95% Success Rate simulation
            const isSuccess = Math.random() > 0.05;
            
            if (isSuccess) {
                resolve({ 
                    success: true, 
                    message: `Successfully sent ${action} to UID: ${uid}` 
                });
            } else {
                reject("Server Timeout: Target player offline or server busy.");
            }
        }, delay);
    });
}

/**
 * Simulates fetching profile data.
 * Returns consistent mock data based on UID to look real.
 */
async function simulateProfileFetch(uid, region) {
    return new Promise((resolve) => {
        setTimeout(() => {
            // Generate deterministic but random-looking data based on UID
            const lastThree = uid.substring(uid.length - 3);
            const levels = Math.floor(parseInt(lastThree) / 10) + 40; // Level 40-100ish
            
            const ranks = ['Platinum III', 'Diamond IV', 'Heroic', 'Grandmaster'];
            const rankIndex = parseInt(uid) % ranks.length;
            
            const likes = parseInt(uid.substring(0, 4)) + Math.floor(Math.random() * 1000);

            resolve({
                nickname: `Killer_ET${lastThree}`, // Ethiopia style name
                uid: uid,
                region: region,
                level: levels > 100 ? 99 : levels,
                rank: ranks[rankIndex],
                likes: likes,
                bio: "Respect for all! 🇪🇹🔥",
                avatar: "https://cdn-icons-png.flaticon.com/512/147/147142.png" 
            });
        }, 2000);
    });
}

// =========================================================
// 5. API ROUTES
// =========================================================

// GET: Fetch User Data (Auto-create if not exists)
app.get('/api/user/:id', async (req, res) => {
    try {
        let user = await User.findOne({ tgId: req.params.id });
        
        if (!user) {
            // Create new user if they don't exist
            user = await User.create({ 
                tgId: req.params.id, 
                username: 'New User' 
            });
            console.log(`New user registered: ${req.params.id}`);
        }
        res.json(user);
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "Server Error" });
    }
});

// POST: Check Profile Info
app.post('/api/check-profile', async (req, res) => {
    const { uid, region } = req.body;
    
    if(!uid) return res.json({ success: false, error: "UID Required" });

    try {
        const profileData = await simulateProfileFetch(uid, region);
        res.json({ success: true, data: profileData });
    } catch (e) {
        res.json({ success: false, error: "Failed to fetch profile" });
    }
});

// POST: Execute Action (Like, Request, etc.)
app.post('/api/execute', async (req, res) => {
    const { tgId, uid, region, action } = req.body;
    const COST = 5;

    try {
        const user = await User.findOne({ tgId });
        if (!user) return res.status(404).json({ error: "User not found" });

        // Check Balance
        if (user.coins < COST) {
            return res.json({ success: false, error: "Insufficient Coins! You need 5 coins." });
        }

        // Execute Simulation
        const result = await simulateFFAction(uid, action);

        // Deduct Coins & Save Data
        user.coins -= COST;
        user.savedUid = uid;
        user.region = region;
        
        // Add to History
        user.history.unshift({
            action: action,
            targetUid: uid,
            status: 'Success'
        });

        // Keep history size manageable (last 50 items)
        if(user.history.length > 50) user.history.pop();

        await user.save();

        res.json({ 
            success: true, 
            newCoins: user.coins, 
            message: result.message 
        });

    } catch (e) {
        // Log failed attempt in DB (optional, but good for debugging)
        res.json({ success: false, error: e.toString() });
    }
});

// =========================================================
// 6. TELEGRAM BOT LOGIC
// =========================================================

bot.command('start', (ctx) => {
    ctx.replyWithPhoto(
        'https://wallpapers.com/images/hd/free-fire-logo-on-black-background-8w194-2.jpg', // Placeholder image
        {
            caption: `<b>🔥 Welcome to FF Master Tools!</b>\n\nManage your Free Fire interactions seamlessly.\n\n👇 <b>Click below to open the app:</b>`,
            parse_mode: 'HTML',
            reply_markup: {
                inline_keyboard: [[
                    { text: "🚀 Open Tools App", web_app: { url: WEBAPP_URL } }
                ]]
            }
        }
    );
});

// Start the bot
bot.launch().then(() => {
    console.log('🤖 Telegram Bot Started');
});

// Enable graceful stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));

// =========================================================
// 7. START EXPRESS SERVER
// =========================================================
app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
    console.log(`🌍 WebApp URL configured as: ${WEBAPP_URL}`);
});