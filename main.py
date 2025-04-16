import os
import openai
import praw
import random
import time
import sys
import traceback
from datetime import datetime, timedelta

# === 配置日志 ===
def log(message, error=False):
    """增强的日志记录，带时间戳和流刷新"""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    log_message = f"[{timestamp}] {message}"
    
    if error:
        print(log_message, file=sys.stderr)
    else:
        print(log_message)
    
    # 强制刷新以确保日志立即显示
    sys.stdout.flush()
    sys.stderr.flush()

# 以清晰的状态消息开始
log("👋 脚本启动中...")

# === 检查环境变量 ===
required_env_vars = [
    "OPENAI_API_KEY", 
    "CLIENT_ID", 
    "CLIENT_SECRET", 
    "REFRESH_TOKEN", 
    "USER_AGENT"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    log(f"❌ 错误: 缺少必要的环境变量: {', '.join(missing_vars)}", error=True)
    log("⛔ 脚本因配置缺失而退出", error=True)
    sys.exit(1)

# 记录环境变量加载成功
for var in required_env_vars:
    value = os.getenv(var)
    masked_value = f"{value[:3]}...{value[-3:]}" if value else "未设置"
    log(f"✅ {var} 已加载: {masked_value}")

# === 配置信息 ===
openai.api_key = os.getenv("OPENAI_API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
USER_AGENT = os.getenv("USER_AGENT")

# === 发帖目标社区配置 ===
TARGET_SUBREDDIT = "C25K"  # 只在C25K社区发帖
SUBREDDITS_CONFIG = {
    TARGET_SUBREDDIT: {"flair_id": None, "flair_text": None}  # 如果C25K需要flair，则更新此处
}

# === 帖子历史记录 ===
post_history = [
    {
        "day": 1,
        "title": "Day 1: Every marathon journey starts with a single step!",  # 假设标题
        "body": """This is Patrick here, your humble running coach and newbie marathon trainee. So, today is DAY 1 of my grand 100-day marathon training challenge, and guess what? I've successfully run a grand total of... 0 km. Yep, you read that right! I know some of you are thinking, "Oh, that's not a great start, Patrick." But hey, every journey, even a 42.195 km one, starts with a single step, right?

I've got to admit, the toughest part was not the run itself, but getting out of bed in the pre-dawn darkness. Trust me, the struggle is real! But the post-run exhilaration, wow, it's worth every sleepy-eyed curse word I muttered this morning.

I'd love to hear how you guys deal with the early morning hustle. Do you have any tricks up your sleeve to make waking up less of a battle? Any funny stories to share?

Here's to the next 99 days and beyond! Let's hit the track, metaphorically or otherwise, and support each other on this journey.

Keep running, keep smiling!

Patrick"""
    }
]

# 更新历史记录函数
def update_post_history(day, title, body):
    """将新帖子添加到历史记录中"""
    post_history.append({
        "day": day,
        "title": title,
        "body": body
    })
    # 保持历史记录不超过7天（最近一周）
    if len(post_history) > 7:
        post_history.pop(0)
    
    # 同时保存到永久存储
    try:
        with open("post_history.txt", "a", encoding="utf-8") as f:
            f.write(f"\n\n===== DAY {day} =====\n")
            f.write(f"Title: {title}\n\n")
            f.write(body)
            f.write("\n\n----------\n")
    except Exception as e:
        log(f"⚠️ 警告: 无法保存帖子历史到文件: {str(e)}", error=True)

# === 发帖追踪 ===
# 设置最后发帖日期为2025年4月17日
last_post_date = datetime(2025, 4, 16).date()  # 指定最后一次发帖的日期
log_file = "patrick_post_log.txt"

# === 初始化 Reddit ===
try:
    log("🔄 初始化Reddit API连接...")
    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        refresh_token=REFRESH_TOKEN,
        user_agent=USER_AGENT,
    )
    # 通过检查用户名验证凭据
    username = reddit.user.me().name
    log(f"✅ 成功认证为用户: {username}")
except Exception as e:
    log(f"❌ Reddit API初始化失败: {str(e)}", error=True)
    log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
    log("⛔ 脚本因Reddit API失败而退出", error=True)
    sys.exit(1)

# === Patrick 的当前状态（用作上下文保持） ===
patrick_state = {
    "day": 2,  # 从第2天开始，因为第1天已经发过了
    "total_km": 5,  # 假设第一天跑了5公里
    "mood": "determined",  # 第二天的心情
    "struggles": ["muscle soreness"],  # 第二天的挑战
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

# === 获取当前UK时间 ===
def get_uk_time():
    """返回英国当前时间（基于UTC+1，适用于British Summer Time）"""
    # 英国夏令时UTC+1，冬令时UTC+0
    # 这里假设我们在夏令时，根据需要可调整
    utc_time = datetime.utcnow()
    uk_time = utc_time + timedelta(hours=1)  # BST (UTC+1)
    return uk_time

# === 检查今天是否已发帖 ===
def should_post_today():
    """检查今天（按英国时区）是否需要发帖"""
    uk_now = get_uk_time()
    uk_today = uk_now.date()
    
    if last_post_date is None:
        log(f"🗓️ 尚未发过帖子，今天需要发帖")
        return True
        
    # 如果最后发帖日期不是今天，则需要发帖
    if last_post_date != uk_today:
        log(f"🗓️ 最后发帖日期是 {last_post_date}，今天是 {uk_today}，需要发帖")
        return True
    
    log(f"🗓️ 今天已经发过帖子了 ({uk_today})")
    return False

# === 检查是否在发帖时间窗口内 ===
def is_posting_time():
    """检查当前时间是否在发帖时间窗口内（英国时间11点到20点）"""
    uk_now = get_uk_time()
    hour = uk_now.hour
    
    if 11 <= hour < 20:
        return True
    else:
        log(f"⏰ 当前UK时间 {uk_now.strftime('%H:%M')} 超出发帖时间窗口 (11:00-20:00)")
        return False

# === 根据发帖时间确定训练时段 ===
def get_training_time_context():
    """根据当前UK时间确定合适的训练时段描述"""
    uk_now = get_uk_time()
    hour = uk_now.hour
    
    if 11 <= hour < 13:
        # 上午11点到下午1点 - 假设是晨跑
        return {
            "when": "early morning",
            "time_desc": "dawn", 
            "details": "I set my alarm early and dragged myself out of bed while most people were still sleeping. The streets were quiet, and the morning air was crisp."
        }
    elif 13 <= hour < 16:
        # 下午1点到4点 - 假设是早上跑步
        return {
            "when": "this morning",
            "time_desc": "morning", 
            "details": "I decided to start my day with a run. The morning was bright, and there were already people commuting to work when I hit the pavement."
        }
    elif 16 <= hour < 18:
        # 下午4点到6点 - 假设是午餐时间跑步
        return {
            "when": "during my lunch break",
            "time_desc": "midday", 
            "details": "I squeezed in a quick run during my lunch break today. It was a perfect way to break up the day and refresh my mind."
        }
    else:  # 18-20点
        # 晚上6点到8点 - 假设是下班后跑步
        return {
            "when": "after work",
            "time_desc": "evening", 
            "details": "I went for a run after finishing work today. The sunset was beautiful, and there were lots of other runners out enjoying the evening."
        }

# === GPT 生成发帖内容 ===
def generate_post():
    log(f"🧠 为r/{TARGET_SUBREDDIT}生成帖子内容...")
    
    # 获取与当前时间相符的训练情境
    time_context = get_training_time_context()
    
    # 准备最近帖子的摘要
    recent_posts_summary = ""
    if post_history:
        # 最多包含最近3天的历史
        for recent_post in post_history[-3:]:
            day = recent_post["day"]
            # 摘取帖子正文的前100个字符作为摘要
            body_snippet = recent_post["body"][:100].replace("\n", " ") + "..."
            recent_posts_summary += f"- Day {day}: {body_snippet}\n"
    
    prompt = f"""
You are Patrick — a positive, slightly humorous, energetic running coach currently on day {patrick_state['day']} of a 100-day marathon training challenge.
You've currently run about {patrick_state['total_km']} km total.
You're feeling {patrick_state['mood']}, and struggling with things like {', '.join(patrick_state['struggles'])}.
You're sharing your reflections and thoughts on Reddit in r/{TARGET_SUBREDDIT}.

Based on the current time of day, your latest run was {time_context["when"]} in the {time_context["time_desc"]}. 
Details about your run timing: {time_context["details"]}

Here are summaries of your most recent posts to maintain continuity:
{recent_posts_summary}

Full text of your most recent post (Day {post_history[-1]['day']}):
{post_history[-1]['body']}

Write a Reddit post for Day {patrick_state['day']} that:
- Is from Patrick, staying consistent with his background
- Has a title and a body (formatted clearly)
- Feels personal and real
- References your most recent run which happened {time_context["when"]}
- References things mentioned in your previous posts for continuity
- Shows progression in your running journey
- Invites interaction
- Avoids promotion and links
- Is 100–200 words
- For C25K community, shows understanding of beginner runners facing the couch-to-5k challenge, while still maintaining your marathon training journey
- Offers encouragement that relates to both your journey and theirs

Output format:
Title: ...
Body: ...
"""
    try:
        # 使用OpenAI API v1.0.0+
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
        log(f"✅ 帖子内容已生成: '{title}'")
        
        # 更新帖子历史
        update_post_history(patrick_state["day"], title, body)
        
        return title, body
    except Exception as e:
        log(f"❌ OpenAI API错误: {str(e)}", error=True)
        log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
        raise

# === 保存日志 ===
def log_post(title, body):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            uk_time = get_uk_time().isoformat()
            f.write(f"[{uk_time}] r/{TARGET_SUBREDDIT}\nTitle: {title}\nBody:\n{body}\n\n---\n\n")
        log(f"📝 帖子已记录到 {log_file}")
    except Exception as e:
        log(f"⚠️ 警告: 写入日志文件失败: {str(e)}", error=True)

# === 获取子版块的可用 flair ===
def get_available_flairs():
    """尝试获取subreddit的可用flairs并记录"""
    try:
        subreddit = reddit.subreddit(TARGET_SUBREDDIT)
        flairs = list(subreddit.flair.link_templates.user_selectable())
        log(f"📋 r/{TARGET_SUBREDDIT}的可用flairs: 找到{len(flairs)}个")
        
        # 记录可用的flairs以供参考
        for flair in flairs[:5]:  # 限制为前5个以避免日志过多
            flair_id = flair["id"] if "id" in flair else "未知"
            flair_text = flair["text"] if "text" in flair else "未知"
            log(f"   - Flair: '{flair_text}' (ID: {flair_id})")
        
        if len(flairs) > 5:
            log(f"   - ... 以及另外 {len(flairs) - 5} 个flairs")
            
        return flairs
    except Exception as e:
        log(f"⚠️ 警告: 无法获取r/{TARGET_SUBREDDIT}的flairs: {str(e)}", error=True)
        # 如果获得403错误，说明我们没有权限获取flairs
        if "403" in str(e):
            log(f"ℹ️ 将为r/{TARGET_SUBREDDIT}使用直接flair分配")
        return []

# === 发帖函数 ===
def post_to_subreddit():
    log(f"🚀 尝试在r/{TARGET_SUBREDDIT}发帖...")
    try:
        # 获取当前时间上下文
        time_context = get_training_time_context()
        log(f"⏰ 当前时间段上下文: 跑步时间为{time_context['when']}")
        
        title, body = generate_post()
        subreddit = reddit.subreddit(TARGET_SUBREDDIT)
        
        # 获取flair配置
        flair_config = SUBREDDITS_CONFIG.get(TARGET_SUBREDDIT, {})
        flair_id = flair_config.get("flair_id")
        flair_text = flair_config.get("flair_text")
        
        # 如果没有配置flair但可能需要，尝试获取可用的flairs
        if not flair_id and not flair_text:
            flairs = get_available_flairs()
            if flairs:
                flair = flairs[0]
                flair_id = flair.get("id")
                flair_text = flair.get("text")
                log(f"📌 自动选择flair: '{flair_text}'")
        
        # 如果有flair则使用
        if flair_id or flair_text:
            log(f"📌 使用flair: ID={flair_id}, Text='{flair_text}'")
            submission = subreddit.submit(title, selftext=body, flair_id=flair_id, flair_text=flair_text)
        else:
            log(f"ℹ️ 没有flair配置，发帖时不使用flair")
            submission = subreddit.submit(title, selftext=body)
            
        log(f"✅ 成功发帖到r/{TARGET_SUBREDDIT}: {submission.url}")
        log_post(title, body)
        
        # 更新最后发帖日期为今天（英国时区）
        global last_post_date
        last_post_date = get_uk_time().date()
        
        return submission
    except Exception as e:
        log(f"❌ 发帖到r/{TARGET_SUBREDDIT}出错: {str(e)}", error=True)
        log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
        raise

# === 健康检查 ===
def health_check():
    """执行定期健康检查以确认脚本仍在正常运行"""
    try:
        # 检查Reddit连接
        username = reddit.user.me().name
        uk_time = get_uk_time().strftime("%H:%M:%S")
        log(f"💓 健康检查: Reddit API连接正常 (用户: {username}), 英国当前时间: {uk_time}")
        
        # 记录Patrick的当前状态
        log(f"💓 健康: Patrick在第{patrick_state['day']}天, 已跑{patrick_state['total_km']}公里, 感觉{patrick_state['mood']}")
        
        return True
    except Exception as e:
        log(f"⚠️ 健康检查失败: {str(e)}", error=True)
        return False

# === 启动时获取子版块信息 ===
def initialize_subreddit_info():
    log("🔍 获取subreddit信息...")
    try:
        # 验证我们可以访问subreddit
        subreddit = reddit.subreddit(TARGET_SUBREDDIT)
        
        # 获取subreddit规则以检查发帖要求
        try:
            rules = list(subreddit.rules)
            log(f"📋 r/{TARGET_SUBREDDIT}: 找到{len(rules)}条规则")
            
            # 检查规则中是否提到flair要求
            flair_required = any("flair" in rule.description.lower() for rule in rules if hasattr(rule, 'description'))
            if flair_required:
                log(f"⚠️ r/{TARGET_SUBREDDIT}可能需要flair（根据规则）")
        except Exception as e:
            log(f"⚠️ 无法获取r/{TARGET_SUBREDDIT}的规则: {str(e)}", error=True)
        
        # 尝试获取flairs
        get_available_flairs()
        
    except Exception as e:
        log(f"⚠️ 无法初始化r/{TARGET_SUBREDDIT}的信息: {str(e)}", error=True)

# === 主循环 ===
def main_loop():
    """主应用循环，提取为函数以便更好地处理错误"""
    health_check_interval = 60 * 30  # 每30分钟检查一次健康状况
    post_check_interval = 60 * 15    # 每15分钟检查一次是否需要发帖
    last_health_check = get_uk_time()
    last_post_check = get_uk_time()
    
    while True:
        try:
            now = get_uk_time()
            
            # 定期健康检查
            if (now - last_health_check).total_seconds() >= health_check_interval:
                health_check()
                last_health_check = now
            
            # 检查是否需要发帖
            if (now - last_post_check).total_seconds() >= post_check_interval:
                log("🔍 检查是否需要发帖...")
                last_post_check = now
                
                # 检查今天是否已经发过帖子
                if should_post_today():
                    # 检查当前是否在发帖时间窗口内
                    if is_posting_time():
                        try:
                            # 尝试发帖
                            post_to_subreddit()
                            
                            # 更新Patrick状态
                            km_run = random.randint(4, 10)
                            patrick_state["day"] += 1
                            patrick_state["total_km"] += km_run
                            log(f"🏃 Patrick前进到第{patrick_state['day']}天并跑了+{km_run}公里")
                            
                            # 每7天切换一次情绪和挑战
                            mood_index = ((patrick_state["day"] - 1) // 7) % len(mood_cycle)
                            patrick_state["mood"], patrick_state["struggles"] = mood_cycle[mood_index]
                            log(f"😊 Patrick的情绪更新为: {patrick_state['mood']}")
                        except Exception as e:
                            log(f"❌ 发帖到r/{TARGET_SUBREDDIT}失败: {str(e)}", error=True)
                            log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
                            # 将在下次检查时再次尝试
                    else:
                        log("⏰ 当前不在发帖时间窗口内 (UK 11:00-20:00)，等待合适时间")
            
            # 计算状态信息
            uk_now = get_uk_time()
            
            # 计算到下一个发帖窗口的时间
            next_window_time = None
            if uk_now.hour < 11:
                # 当前时间早于11点，等到今天11点
                next_window_time = uk_now.replace(hour=11, minute=0, second=0, microsecond=0)
            elif uk_now.hour >= 20:
                # 当前时间晚于20点，等到明天11点
                next_window_time = (uk_now + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
            
            # 如果今天已发帖，计算到明天11点的时间
            if last_post_date == uk_now.date():
                next_window_time = (uk_now + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
                wait_seconds = (next_window_time - uk_now).total_seconds()
                wait_hours = wait_seconds / 3600
                log(f"⏳ 今天已完成发帖。距离下一个发帖窗口（明天UK 11:00）还有{wait_hours:.1f}小时")
            elif next_window_time:
                # 如果不在发帖窗口内，显示到下一个窗口的时间
                wait_seconds = (next_window_time - uk_now).total_seconds()
                wait_hours = wait_seconds / 3600
                log(f"⏳ 距离下一个发帖窗口（UK {next_window_time.strftime('%H:%M')}）还有{wait_hours:.1f}小时")
            else:
                # 在发帖窗口内但尚未发帖
                window_end = uk_now.replace(hour=20, minute=0, second=0, microsecond=0)
                remaining_seconds = (window_end - uk_now).total_seconds()
                remaining_hours = remaining_seconds / 3600
                log(f"⏳ 当前在发帖窗口内，尚未完成今日发帖。发帖窗口还剩{remaining_hours:.1f}小时结束")
            
            # 睡眠适当时间
            time.sleep(60 * 5)  # 5分钟
                
        except KeyboardInterrupt:
            log("👋 脚本被手动停止（键盘中断）")
            break
        except Exception as e:
            log(f"‼️ 主循环中意外错误: {str(e)}", error=True)
            log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
            log("🔄 错误后继续主循环")
            time.sleep(60 * 5)  # 错误后等待5分钟再继续

# === 脚本启动入口 ===
log("🚀 Patrick GPT发帖器启动！")
log(f"🌐 当前配置: 仅发布到r/{TARGET_SUBREDDIT}, 英国时区, 每天一帖")
log(f"⏰ 发帖时间窗口: 英国时间 11:00-20:00")
log(f"📊 Patrick当前状态: 第{patrick_state['day']}天, 已跑{patrick_state['total_km']}公里")
log(f"🧠 已加载历史帖子记录: {len(post_history)}个")

# 在启动时初始化subreddit信息
try:
    initialize_subreddit_info()
    
    # 开始主循环
    main_loop()
except Exception as e:
    log(f"💥 致命错误: {str(e)}", error=True)
    log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
    log("⛔ 脚本因不可恢复的错误而终止")
