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

# === 发帖目标社区 ===
SUBREDDITS = ["running", "C25K", "getdisciplined", "selfimprovement"]
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
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        text = response["choices"][0]["message"]["content"]
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

# === 发帖函数 ===
def post_to_subreddit(subreddit_name):
    log(f"🚀 Attempting to post to r/{subreddit_name}...")
    try:
        title, body = generate_post(subreddit_name)
        subreddit = reddit.subreddit(subreddit_name)
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

# === 主循环 ===
log("🚀 Patrick GPT Poster started!")

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
