
import praw
import openai
import random
import time
from datetime import datetime, timedelta
import os


# === 配置信息（请替换为你自己的） ===
CLIENT_ID = "xGCk3lxmH9nJFh8aygMW-Q"
CLIENT_SECRET = "dIFbNaKIK5n8oZPDCxjO1V30wB5ohQ"
REFRESH_TOKEN = "791695964020-Z6cyMcvhb-kw8_bHjyEeZpL6f_5nbQ"
USER_AGENT = "marathon-bot by u/Minimum_Impression92"
openai.api_key = os.getenv("OPENAI_API_KEY")

# === 发帖目标社区 ===
SUBREDDITS = ["running", "C25K", "getdisciplined", "selfimprovement"]
POST_INTERVAL_HOURS = 6  # 每6小时检查一次是否需要发帖
MIN_INTERVAL_BETWEEN_POSTS = 1  # 最小间隔（小时）

# === 初始化 Reddit 和 OpenAI ===
openai.api_key = OPENAI_API_KEY
reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    refresh_token=REFRESH_TOKEN,
    user_agent=USER_AGENT,
)

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
    prompt = f"""
You are Patrick — a positive, slightly humorous, energetic running coach currently on day {patrick_state['day']} of a 100-day marathon training challenge.
You’ve currently run about {patrick_state['total_km']} km total.
You’re feeling {patrick_state['mood']}, and struggling with things like {', '.join(patrick_state['struggles'])}.
You’re sharing your reflections and thoughts on Reddit in r/{subreddit_name}.

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
    return title, body

# === 保存日志 ===
def log_post(subreddit_name, title, body):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.utcnow().isoformat()}] r/{subreddit_name}\nTitle: {title}\nBody:\n{body}\n\n---\n\n")

# === 发帖函数 ===
def post_to_subreddit(subreddit_name):
    title, body = generate_post(subreddit_name)
    subreddit = reddit.subreddit(subreddit_name)
    submission = subreddit.submit(title, selftext=body)
    print(f"✅ Posted to r/{subreddit_name}: {title}")
    log_post(subreddit_name, title, body)
    return submission

# === 主循环 ===
print("🚀 Patrick GPT Poster started!")
while True:
    now = datetime.utcnow()

    if last_global_post_time and (now - last_global_post_time).total_seconds() < MIN_INTERVAL_BETWEEN_POSTS * 3600:
        print("⏳ Waiting for 1h interval between posts...")
        time.sleep(300)
        continue

    for sub in SUBREDDITS:
        last_time = last_post_time.get(sub)
        should_post = not last_time or (now - last_time).total_seconds() >= 60 * 60 * 24
        if should_post:
            try:
                post_to_subreddit(sub)
                last_post_time[sub] = now
                last_global_post_time = now
                # 更新 Patrick 状态
                patrick_state["day"] += 1
                patrick_state["total_km"] += random.randint(4, 10)
                # 每 7 天切换一次情绪和挑战
                mood_index = ((patrick_state["day"] - 1) // 7) % len(mood_cycle)
                patrick_state["mood"], patrick_state["struggles"] = mood_cycle[mood_index]
            except Exception as e:
                print(f"❌ Error posting to r/{sub}: {e}")
    print("⏳ Sleeping before next post check...")
    time.sleep(POST_INTERVAL_HOURS * 3600)
