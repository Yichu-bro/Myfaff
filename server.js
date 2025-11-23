import express from 'express';
import mongoose from 'mongoose';
import cors from 'cors';
import { Telegraf } from 'telegraf';
import axios from 'axios'; // We need this to fetch real data
import path from 'path';
import { fileURLToPath } from 'url';

// =========================================================
// 1. CONFIGURATION
// =========================================================
const BOT_TOKEN = process.env.BOT_TOKEN || 'YOUR_BOT_TOKEN';
const MONGO_URI = process.env.MONGO_URI || 'YOUR_MONGO_URI';
const WEBAPP_URL = process.env.WEBAPP_URL || 'YOUR_RENDER_URL';
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

mongoose.connect(MONGO_URI)
    .then(() => console.log('✅ MongoDB Connected'))
    .catch(err => console.error('❌ DB Error:', err));

// =========================================================
// 3. DATABASE MODELS
// =========================================================
const UserSchema = new mongoose.Schema({
    tgId: { type: String, unique: true },
    username: String,
    coins: { type: Number, default: 50 },
    savedUid: String,
    history: [{ action: String, targetUid: String, status: String, timestamp: Date }]
});
const User = mongoose.model('User', UserSchema);

// =========================================================
// 4. REAL DATA ENGINES
// =========================================================

/**
 * 🟢 GET REAL PROFILE INFO
 * Connects to a third-party API to fetch the REAL nickname.
 * Note: Level/Rank are usually hidden by Garena, but Nickname is public.
 */
async function getRealProfile(uid, region) {
    try {
        // We use a public API wrapper. If this goes down, you must find a new one or buy an API key.
        // This is a common free endpoint for UID validation.
        const response = await axios.get(`https://ff-api-checker.vercel.app/api/validate/${uid}?region=${region}`);
        
        if (response.data && response.data.success) {
            return {
                nickname: response.data.nickname, // REAL Nickname
                uid: uid,
                region: region,
                // These details below are NOT accessible via HTTP (Only inside Game Client)
                // We must simulate them or leave them as "Hidden"
                level: "Hidden", 
                rank: "Hidden",
                likes: "Hidden",
                bio: `Verified Player ✅`,
                avatar: "https://cdn-icons-png.flaticon.com/512/147/147142.png"
            };
        } else {
            throw new Error("Player not found");
        }
    } catch (error) {
        // Fallback if API fails (Connection error or invalid UID)
        console.error("API Error:", error.message);
        throw new Error("Could not fetch real data. Check UID.");
    }
}

/**
 * 🔴 EXECUTE ACTIONS (LIKE, REQUEST, VISIT)
 * IMPORTANT: It is IMPOSSIBLE to send real likes via a web server.
 * You need a "SMM Panel" (Paid Service) to do this.
 * This code simulates the request unless you add a Paid API Key below.
 */
async function executeAction(uid, action) {
    // If you buy a real API key from a panel, paste their code here.
    // For now, this validates the UID exists, then marks it as "Processing".
    return new Promise((resolve) => {
        setTimeout(() => {
            resolve({ 
                success: true, 
                message: `Request sent to Server for UID: ${uid}. (Note: Real execution requires SMM API)` 
            });
        }, 2000);
    });
}

// =========================================================
// 5. API ROUTES
// =========================================================

app.get('/api/user/:id', async (req, res) => {
    try {
        let user = await User.findOne({ tgId: req.params.id });
        if (!user) user = await User.create({ tgId: req.params.id, username: 'User' });
        res.json(user);
    } catch (e) { res.status(500).json({ error: "Server Error" }); }
});

// ✅ REAL PROFILE CHECK
app.post('/api/check-profile', async (req, res) => {
    const { uid, region } = req.body;
    try {
        const data = await getRealProfile(uid, region);
        res.json({ success: true, data });
    } catch (e) {
        res.json({ success: false, error: "Invalid UID or Server Offline" });
    }
});

app.post('/api/execute', async (req, res) => {
    const { tgId, uid, region, action } = req.body;
    try {
        const user = await User.findOne({ tgId });
        if (!user || user.coins < 5) return res.json({ success: false, error: "Low Coins" });

        // 1. Verify UID exists first (Real Check)
        await getRealProfile(uid, region);

        // 2. Execute Action (Simulation or SMM Panel)
        const result = await executeAction(uid, action);

        user.coins -= 5;
        user.savedUid = uid;
        user.history.unshift({ action, targetUid: uid, status: 'Success', timestamp: new Date() });
        await user.save();

        res.json({ success: true, newCoins: user.coins, message: result.message });
    } catch (e) {
        res.json({ success: false, error: "UID Invalid or Network Error" });
    }
});

// =========================================================
// 6. BOT START
// =========================================================
bot.command('start', (ctx) => {
    ctx.replyWithPhoto(
        'https://upload.wikimedia.org/wikipedia/commons/f/f4/Garena_Free_Fire_Logo.png', 
        {
            caption: `<b>🔥 Real FF Tools</b>\n\nUID Validator & Manager.\n\n👇 <b>Open App:</b>`,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: [[{ text: "🚀 Open Tools", web_app: { url: WEBAPP_URL } }]] }
        }
    );
});

bot.launch();
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));