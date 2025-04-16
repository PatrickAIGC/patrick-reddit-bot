import os
import openai
import praw
import random
import time
import sys
import traceback
from datetime import datetime, timedelta

# === Configure Logging ===
def log(message, error=False):
    """Enhanced logging with timestamps and stream flushing"""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    log_message = f"[{timestamp}] {message}"
    
    if error:
        print(log_message, file=sys.stderr)
    else:
        print(log_message)
    
    # Force flush to ensure logs appear immediately
    sys.stdout.flush()
    sys.stderr.flush()

# Start with clear status messages
log("👋 Script booting...")

# === Check Environment Variables ===
required_env_vars = [
    "OPENAI_API_KEY", 
    "CLIENT_ID", 
    "CLIENT_SECRET", 
    "REFRESH_TOKEN", 
    "USER_AGENT"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    log(f"❌ ERROR: Missing required environment variables: {', '.join(missing_vars)}", error=True)
    log("⛔ Exiting script due to missing configuration", error=True)
    sys.exit(1)

# Log successful env var loading
for var in required_env_vars:
    value = os.getenv(var)
    masked_value = f"{value[:3]}...{value[-3:]}" if value else "NOT SET"
    log(f"✅ {var} loaded: {masked_value}")

# === 配置信息 ===
openai.api_key = os.getenv("OPENAI_API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
USER_AGENT = os.getenv("USER_AGENT")

# === 发帖目标社区及对应的 flair ===
SUBREDDITS_CONFIG = {
    "running": {"flair_id": None, "flair_text": "Training"},  # We're using "Training" flair for r/running
    "C25K": {"flair_id": None, "flair_text": None},  # Update with appropriate flair if required
    "getdisciplined": {"flair_id": None, "flair_text": None},  # Update with appropriate flair if required
    "selfimprovement": {"flair_id": None, "flair_text": None},  # Update with appropriate flair if required
}

# Additional flair options for r/running if "Training" isn't available or appropriate
RUNNING_FLAIRS = [
    "Training", 
    "Article", 
    "Weekly Thread", 
    "Monthly Thread", 
    "Nutrition", 
    "Race Report", 
    "Review", 
    "PSA", 
    "Safety"
]
SUBREDDITS = list(SUBREDDITS_CONFIG.keys())
POST_INTERVAL_HOURS = 6  # 每6小时检查一次是否需要发帖
MIN_INTERVAL_BETWEEN_POSTS = 1  # 最小间隔（小时）

# === 初始化 Reddit ===
try:
    log("🔄 Initializing Reddit API connection...")
    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        refresh_token=REFRESH_TOKEN,
        user_agent=USER_AGENT,
    )
    # Verify credentials by checking username
    username = reddit.user.me().name
    log(f"✅ Successfully authenticated as: {username}")
except Exception as e:
    log(f"❌ Reddit API initialization failed: {str(e)}", error=True)
    log(f"Stack trace: {traceback.format_exc()}", error=True)
    log("⛔ Exiting script due to Reddit API failure", error=True)
    sys.exit(1)

# === 发帖追踪 ===
last_post_time = {}
last_global_post_time = None
log_file = "patrick_post_log.txt"

# === Patrick 的当前状态（用作上下文保持） ===
patrick_state = {
    "day": 1,
    "total_km": 0,
    "mood": "optimistic",
    "struggles": ["early mornings"],
}

# === 情绪变化日历（每7天切换一次） ===
mood_cycle = [
    ("optimistic", ["early mornings"]),
    ("determined", ["muscle soreness"]),
    ("tired but focused", ["motivation dips"]),
    ("energized", ["balancing work and training"]),
    ("reflective", ["self-doubt", "weather"]),
    ("confident", ["nothing specific"]),
    ("grateful", ["the long journey"]),
]

# === GPT 生成发帖内容 ===
def generate_post(subreddit_name):
    log(f"🧠 Generating post content for r/{subreddit_name}...")
    
    prompt = f"""
You are Patrick — a positive, slightly humorous, energetic running coach currently on day {patrick_state['day']} of a 100-day marathon training challenge.
You've currently run about {patrick_state['total_km']} km total.
You're feeling {patrick_state['mood']}, and struggling with things like {', '.join(patrick_state['struggles'])}.
You're sharing your reflections and thoughts on Reddit in r/{subreddit_name}.

Write a Reddit post that:
- Is from Patrick, staying consistent with his background
- Has a title and a body (formatted clearly)
- Feels personal and real
- Invites interaction
- Avoids promotion and links
- Is 100–200 words

Output format:
Title: ...
Body: ...
"""
    try:
        # Updated for OpenAI API v1.0.0+
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        text = response.choices[0].message.content
        lines = text.strip().split("\n")
        title = ""
        body_lines = []
        for line in lines:
            if line.lower().startswith("title:"):
                title = line.replace("Title:", "").strip()
            elif line.lower().startswith("body:"):
                continue
            else:
                body_lines.append(line)
        body = "\n".join(body_lines)
        log(f"✅ Post content generated: '{title}'")
        return title, body
    except Exception as e:
        log(f"❌ OpenAI API error: {str(e)}", error=True)
        log(f"Stack trace: {traceback.format_exc()}", error=True)
        raise

# === 保存日志 ===
def log_post(subreddit_name, title, body):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] r/{subreddit_name}\nTitle: {title}\nBody:\n{body}\n\n---\n\n")
        log(f"📝 Post logged to {log_file}")
    except Exception as e:
        log(f"⚠️ Warning: Failed to write to log file: {str(e)}", error=True)

# === 获取子版块的可用 flair ===
def get_available_flairs(subreddit_name):
    """Retrieves available flairs for a subreddit and logs them"""
    try:
        subreddit = reddit.subreddit(subreddit_name)
        flairs = list(subreddit.flair.link_templates.user_selectable())
        log(f"📋 Available flairs for r/{subreddit_name}: {len(flairs)} flairs found")
        
        # Log the available flairs for reference
        for flair in flairs[:5]:  # Limit to first 5 to avoid excessive logging
            flair_id = flair["id"] if "id" in flair else "Unknown"
            flair_text = flair["text"] if "text" in flair else "Unknown"
            log(f"   - Flair: '{flair_text}' (ID: {flair_id})")
        
        if len(flairs) > 5:
            log(f"   - ... and {len(flairs) - 5} more flairs")
            
        return flairs
    except Exception as e:
        log(f"⚠️ Warning: Failed to get flairs for r/{subreddit_name}: {str(e)}", error=True)
        return []

# === 发帖函数 ===
def post_to_subreddit(subreddit_name):
    log(f"🚀 Attempting to post to r/{subreddit_name}...")
    try:
        title, body = generate_post(subreddit_name)
        subreddit = reddit.subreddit(subreddit_name)
        
        # Get flair configuration
        flair_config = SUBREDDITS_CONFIG.get(subreddit_name, {})
        flair_id = flair_config.get("flair_id")
        flair_text = flair_config.get("flair_text")
        
        # Special handling for r/running based on extracted flair options
        if subreddit_name == "running":
            # Try using "Training" flair first
            if "Training" in RUNNING_FLAIRS:
                flair_text = "Training"
                log(f"📌 Using 'Training' flair for post in r/running")
        
        # If no flair is configured but the subreddit might require it,
        # try to get available flairs and find a matching one
        if not flair_id and (not flair_text or subreddit_name == "running"):
            flairs = get_available_flairs(subreddit_name)
            if flairs:
                # For r/running, try to match one of our known flairs
                if subreddit_name == "running":
                    for flair in flairs:
                        if "text" in flair and flair["text"] in RUNNING_FLAIRS:
                            flair_id = flair.get("id")
                            flair_text = flair.get("text")
                            log(f"📌 Found matching flair: '{flair_text}' for r/{subreddit_name}")
                            break
                
                # If still no match, just use the first available flair
                if not flair_id and not flair_text:
                    flair = flairs[0]
                    flair_id = flair.get("id")
                    flair_text = flair.get("text")
                    log(f"📌 Auto-selected flair: '{flair_text}' for r/{subreddit_name}")
        
        # Submit post with flair if available
        if flair_id or flair_text:
            log(f"📌 Using flair: ID={flair_id}, Text='{flair_text}' for post in r/{subreddit_name}")
            submission = subreddit.submit(title, selftext=body, flair_id=flair_id, flair_text=flair_text)
        else:
            log(f"⚠️ No flair configured for r/{subreddit_name}, attempting to post without flair")
            submission = subreddit.submit(title, selftext=body)
            
        log(f"✅ Successfully posted to r/{subreddit_name}: {submission.url}")
        log_post(subreddit_name, title, body)
        return submission
    except Exception as e:
        log(f"❌ Error posting to r/{subreddit_name}: {str(e)}", error=True)
        log(f"Stack trace: {traceback.format_exc()}", error=True)
        raise

# === 健康检查 ===
def health_check():
    """Perform periodic health checks to confirm script is still running properly"""
    try:
        # Check Reddit connection
        username = reddit.user.me().name
        log(f"💓 Health check: Reddit API connection OK (user: {username})")
        
        # Log Patrick's current state
        log(f"💓 Health: Patrick on day {patrick_state['day']}, {patrick_state['total_km']} km run, feeling {patrick_state['mood']}")
        
        return True
    except Exception as e:
        log(f"⚠️ Health check failed: {str(e)}", error=True)
        return False

# === 启动时获取子版块信息 ===
def initialize_subreddit_info():
    log("🔍 Retrieving subreddit information and available flairs...")
    for sub in SUBREDDITS:
        try:
            # Verify we can access the subreddit
            subreddit = reddit.subreddit(sub)
            # Get subreddit rules to check posting requirements
            rules = list(subreddit.rules)
            log(f"📋 r/{sub}: Found {len(rules)} rules")
            
            # Check for flair requirement mentions in the rules
            flair_required = any("flair" in rule.description.lower() for rule in rules if hasattr(rule, 'description'))
            if flair_required:
                log(f"⚠️ r/{sub} likely requires flair based on rules")
            
            # Get available flairs
            get_available_flairs(sub)
            
            # Wait a bit between API calls to avoid rate limiting
            time.sleep(2)
        except Exception as e:
            log(f"⚠️ Could not initialize info for r/{sub}: {str(e)}", error=True)

# === 主循环 ===
log("🚀 Patrick GPT Poster started!")

# Initialize subreddit information at startup
initialize_subreddit_info()

health_check_interval = 60 * 60  # Check health every hour
last_health_check = datetime.utcnow()

while True:
    try:
        now = datetime.utcnow()
        
        # Periodic health check
        if (now - last_health_check).total_seconds() >= health_check_interval:
            health_check()
            last_health_check = now
        
        # Check if we need to wait for the minimum interval
        if last_global_post_time and (now - last_global_post_time).total_seconds() < MIN_INTERVAL_BETWEEN_POSTS * 3600:
            wait_time_mins = (MIN_INTERVAL_BETWEEN_POSTS * 3600 - (now - last_global_post_time).total_seconds()) / 60
            log(f"⏳ Waiting for minimum posting interval ({wait_time_mins:.1f} minutes remaining)")
            time.sleep(300)  # Sleep for 5 minutes before checking again
            continue
        
        # Check each subreddit
        for sub in SUBREDDITS:
            last_time = last_post_time.get(sub)
            # Post once per day to each subreddit
            should_post = not last_time or (now - last_time).total_seconds() >= 60 * 60 * 24
            
            if should_post:
                try:
                    # Update flair information before posting if needed
                    if not SUBREDDITS_CONFIG[sub]["flair_id"] and not SUBREDDITS_CONFIG[sub]["flair_text"]:
                        flairs = get_available_flairs(sub)
                        if flairs:
                            SUBREDDITS_CONFIG[sub]["flair_id"] = flairs[0].get("id")
                            SUBREDDITS_CONFIG[sub]["flair_text"] = flairs[0].get("text")
                    
                    post_to_subreddit(sub)
                    last_post_time[sub] = now
                    last_global_post_time = now
                    
                    # 更新 Patrick 状态
                    km_run = random.randint(4, 10)
                    patrick_state["day"] += 1
                    patrick_state["total_km"] += km_run
                    log(f"🏃 Patrick progressed to day {patrick_state['day']} and ran +{km_run}km")
                    
                    # 每 7 天切换一次情绪和挑战
                    mood_index = ((patrick_state["day"] - 1) // 7) % len(mood_cycle)
                    patrick_state["mood"], patrick_state["struggles"] = mood_cycle[mood_index]
                    log(f"😊 Patrick's mood updated to: {patrick_state['mood']}")
                    
                    # Success, now sleep before next subreddit to avoid rate limits
                    time.sleep(60 * 5)  # Sleep 5 minutes between posts
                except Exception as e:
                    log(f"❌ Failed to post to r/{sub}: {str(e)}", error=True)
                    # Sleep for a bit to avoid hammering APIs in case of failure
                    time.sleep(60 * 15)  # Sleep 15 minutes after failure
        
        log(f"⏳ Sleeping for {POST_INTERVAL_HOURS} hours before next post check...")
        # Sleep in smaller chunks so we can perform health checks
        for _ in range(POST_INTERVAL_HOURS * 12):  # 12 checks per hour
            time.sleep(300)  # 5 minutes
            health_check()
            
    except KeyboardInterrupt:
        log("👋 Script manually stopped via keyboard interrupt")
        break
    except Exception as e:
        log(f"‼️ Unexpected error in main loop: {str(e)}", error=True)
        log(f"Stack trace: {traceback.format_exc()}", error=True)
        log("🔄 Continuing main loop after error")
        time.sleep(300)  # Sleep for 5 minutes before continuing
