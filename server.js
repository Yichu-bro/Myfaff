import express from 'express';
import mongoose from 'mongoose';
import cors from 'cors';
import { Telegraf } from 'telegraf';
import path from 'path';
import { fileURLToPath } from 'url';

// =========================================================
// 1. CONFIGURATION
// =========================================================
// These use values from Render's "Environment Variables"
// If testing locally, you can replace the process.env part with your strings.
const BOT_TOKEN = process.env.BOT_TOKEN || 'YOUR_BOT_TOKEN_HERE'; 
const MONGO_URI = process.env.MONGO_URI || 'YOUR_MONGO_URI_HERE';
const WEBAPP_URL = process.env.WEBAPP_URL || 'https://your-app-name.onrender.com'; 
const PORT = process.env.PORT || 3000;

// =========================================================
// 2. SERVER SETUP
// =========================================================
const app = express();
const bot = new Telegraf(BOT_TOKEN);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Connect to MongoDB
mongoose.connect(MONGO_URI)
    .then(() => console.log('✅ MongoDB Connected Successfully'))
    .catch(err => console.error('❌ MongoDB Connection Error:', err));

// =========================================================
// 3. DATABASE MODELS
// =========================================================
const UserSchema = new mongoose.Schema({
    tgId: { type: String, required: true, unique: true },
    username: String,
    coins: { type: Number, default: 50 }, 
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

// Simulate Action (Like, Visit, etc.)
async function simulateFFAction(uid, action) {
    return new Promise((resolve, reject) => {
        if (!/^\d{8,12}$/.test(uid)) return reject("Invalid UID Format");
        
        // 1.5 - 3 second delay to look real
        const delay = Math.floor(Math.random() * 1500) + 1500;

        setTimeout(() => {
            resolve({ 
                success: true, 
                message: `${action} sent successfully to UID: ${uid}` 
            });
        }, delay);
    });
}

// Simulate Profile Fetch (Consistent Fake Data)
async function simulateProfileFetch(uid, region) {
    return new Promise((resolve) => {
        setTimeout(() => {
            const lastThree = uid.substring(uid.length - 3);
            const levels = Math.floor(parseInt(lastThree || "50") / 10) + 40;
            
            resolve({
                nickname: `Killer_ET${lastThree}`,
                uid: uid,
                region: region,
                level: levels > 100 ? 99 : levels,
                rank: 'Heroic',
                likes: 1200 + Math.floor(Math.random() * 500),
                bio: "Respect for all! 🇪🇹🔥",
                avatar: "https://cdn-icons-png.flaticon.com/512/147/147142.png" 
            });
        }, 2000);
    });
}

// =========================================================
// 5. API ROUTES
// =========================================================

// Get User Info
app.get('/api/user/:id', async (req, res) => {
    try {
        let user = await User.findOne({ tgId: req.params.id });
        if (!user) {
            user = await User.create({ tgId: req.params.id, username: 'New User' });
        }
        res.json(user);
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "Server Error" });
    }
});

// Check Profile
app.post('/api/check-profile', async (req, res) => {
    const { uid, region } = req.body;
    try {
        const data = await simulateProfileFetch(uid, region);
        res.json({ success: true, data });
    } catch (e) {
        res.json({ success: false, error: "Failed to fetch profile" });
    }
});

// Execute Action
app.post('/api/execute', async (req, res) => {
    const { tgId, uid, region, action } = req.body;
    try {
        const user = await User.findOne({ tgId });
        if (!user) return res.status(404).json({ error: "User not found" });

        if (user.coins < 5) {
            return res.json({ success: false, error: "Insufficient Coins" });
        }

        const result = await simulateFFAction(uid, action);

        user.coins -= 5;
        user.savedUid = uid;
        user.region = region;
        user.history.unshift({
            action: action,
            targetUid: uid,
            status: 'Success'
        });
        
        if(user.history.length > 50) user.history.pop();
        await user.save();

        res.json({ success: true, newCoins: user.coins, message: result.message });
    } catch (e) {
        res.json({ success: false, error: e.toString() });
    }
});

// =========================================================
// 6. TELEGRAM BOT LOGIC (FIXED IMAGE)
// =========================================================

bot.command('start', async (ctx) => {
    try {
        // We use a Wikimedia URL which is safe and reliable
        await ctx.replyWithPhoto(
            'https://upload.wikimedia.org/wikipedia/commons/f/f4/Garena_Free_Fire_Logo.png', 
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
    } catch (error) {
        // Fallback: If image fails, send text only so bot doesn't crash
        console.log("Image failed, sending text fallback.");
        await ctx.reply(`<b>🔥 Welcome to FF Master Tools!</b>\n\n👇 <b>Click below to open:</b>`, {
            parse_mode: 'HTML',
            reply_markup: {
                inline_keyboard: [[
                    { text: "🚀 Open Tools App", web_app: { url: WEBAPP_URL } }
                ]]
            }
        });
    }
});

// Graceful Stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));

// =========================================================
// 7. START SERVER
// =========================================================
// Start Bot
bot.launch().then(() => console.log('🤖 Telegram Bot Started'));

// Start Express
app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
});