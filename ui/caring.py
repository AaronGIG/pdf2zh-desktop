"""人文关怀系统 — 全天候关怀、翻译里程碑、节日问候、名言语录"""

from datetime import datetime, date
import random

from ui.quotes import (
    CHINESE_INSPIRATIONAL, ENGLISH_INSPIRATIONAL,
    LATE_NIGHT_QUOTES, MORNING_QUOTES,
    NOON_QUOTES, EVENING_QUOTES,
)


def get_caring_message():
    """
    根据当前时间和日期返回关怀消息，没有则返回 None。
    为避免过于频繁，非深夜/节日时段有概率不显示（~40% 触发）。
    返回格式: (emoji, 标题, 正文) 或 None
    """
    now = datetime.now()
    hour = now.hour
    today = now.date()
    month_day = (today.month, today.day)

    # ── 节日优先（100% 触发）──
    holidays = {
        (1, 1):   ("🎆", "新年快乐", "新的一年，愿你的论文全部被接收！🥳"),
        (2, 14):  ("💝", "情人节快乐", "学术之路虽苦，但你并不孤单 💕"),
        (3, 8):   ("🌷", "女神节快乐", "致敬每一位在科研路上闪光的你 ✨"),
        (3, 12):  ("🌳", "植树节快乐", "种下知识的种子，终会长成大树 🌿"),
        (4, 1):   ("🤡", "愚人节快乐", "今天可以皮一下，但论文还是要认真写哦 😜"),
        (5, 1):   ("🎊", "劳动节快乐", "科研工作者也要好好放个假 🏖️"),
        (5, 4):   ("💫", "青年节快乐", "年轻的科研人，你的未来无限 🚀"),
        (5, 20):  ("🥰", "520 快乐", "今天记得对自己说一句：我爱你 💗"),
        (6, 1):   ("🎈", "六一快乐", "保持好奇心，像孩子一样探索世界 🌈"),
        (6, 18):  ("🎁", "618 快乐", "买书也算学习投资吧 📚"),
        (9, 1):   ("📝", "开学季", "新学期新气象，加油冲鸭 🦆"),
        (9, 10):  ("🍎", "教师节快乐", "致敬每一位传道授业的学者 📖"),
        (10, 1):  ("🇨🇳", "国庆快乐", "祝祖国繁荣昌盛，科研蒸蒸日上！🎉"),
        (10, 24): ("💻", "程序员节快乐", "1024! 今天 bug 全消，代码全过 🎯"),
        (10, 31): ("🎃", "万圣节快乐", "今晚不搞科研，搞点 trick or treat 🍬"),
        (11, 11): ("🛍️", "双十一快乐", "论文通过的快乐，比购物车清空还爽 🎉"),
        (12, 25): ("🎄", "Merry Christmas", "愿你的圣诞有好论文和好心情相伴 🎅"),
        (12, 31): ("🥂", "跨年夜", "这一年辛苦了，明年我们继续 🌟"),
    }
    # ── 确定触发概率 ──
    weekday = now.weekday()  # 0=Mon ... 6=Sun
    if month_day in holidays:
        prob = 0.20          # 节假日 20%
    elif 2 <= hour < 5:
        prob = 0.50          # 凌晨 2:00-4:59  50%
    elif weekday < 5:
        prob = 0.10          # 周一至周五 10%
    else:
        prob = 0.05          # 周六日 5%

    if random.random() > prob:
        return None

    # ── 节日消息 ──
    if month_day in holidays:
        return holidays[month_day]

    # ── 深夜（23:00 - 01:59）──
    if hour >= 23 or hour < 2:
        q = random.choice(LATE_NIGHT_QUOTES)
        icons = ["🌙", "✨", "💫", "🌃", "🌌", "☕", "🪐", "🫧", "🧸"]
        return random.choice(icons), "深夜陪伴", q

    # ── 凌晨（02:00 - 04:59）──
    if 2 <= hour < 5:
        q = random.choice(LATE_NIGHT_QUOTES)
        return "😴", "真的该休息了", q

    # ── 清晨 & 上午（05:00 - 11:29）── 简短 + 星期感知 ──
    if 5 <= hour < 11 or (hour == 11 and now.minute < 30):
        # 星期特别问候
        weekday_greetings = {
            0: ["新的一周，元气满满 💪", "周一好！新的开始 🚀", "Monday！冲鸭 🦆"],
            4: ["周五啦！再坚持一下 🎉", "TGIF！快到周末了 ✨", "周五好！胜利在望 🏁"],
            5: ["周末愉快 🎈 今天可以慢一点", "周六好！适合充电 📚", "周末的时光最珍贵 ☀️"],
            6: ["周日好！好好休息 🧸", "周日适合放空自己 🌈", "明天又是新的一周，养精蓄锐 💫"],
        }
        if weekday in weekday_greetings and random.random() < 0.5:
            q = random.choice(weekday_greetings[weekday])
        elif 5 <= hour < 9:
            short_morning = [
                "早安 ☀️ 元气满满！",
                "早上好 🌸 新的一天加油！",
                "起床啦 🐰 今天也要加油哦",
                "早安 ✨ 你是最棒的！",
                "早 🌻 开启美好的一天",
                "早上好 🌅 阳光正好",
                "早安 💫 今天也是充满希望的一天",
                "起来啦 🐦 世界等你去探索",
            ]
            q = random.choice(short_morning)
        else:
            q = random.choice([
                "上午好 ☕ 状态拉满！",
                "上午效率最高，冲 💪",
                "认真工作的你 ✨ 最棒了",
                "上午好 🎯 继续加油",
                "进度条在动了 📊 保持节奏",
            ])
        icons = ["☀️", "🌸", "🌻", "✨", "💫", "🐰"]
        return random.choice(icons), "早安" if hour < 9 else "上午好", q

    # ── 中午（11:30 - 13:59）──
    if (hour == 11 and now.minute >= 30) or 12 <= hour < 14:
        q = random.choice(NOON_QUOTES)
        icons = ["🍱", "🧋", "☕", "🍜", "🌤️", "😊"]
        return random.choice(icons), "午间提醒", q

    # ── 下午（14:00 - 17:29）──
    if 14 <= hour < 17 or (hour == 17 and now.minute < 30):
        q = random.choice(NOON_QUOTES)
        icons = ["☕", "🧋", "🍵", "🌻", "💪", "📚"]
        return random.choice(icons), "下午好", q

    # ── 傍晚（17:30 - 19:59）──
    if (hour == 17 and now.minute >= 30) or 18 <= hour < 20:
        q = random.choice(EVENING_QUOTES)
        icons = ["🌇", "🌅", "🍲", "🏠", "🍃", "✨"]
        return random.choice(icons), "傍晚啦", q

    # ── 晚上（20:00 - 22:59）──
    if 20 <= hour < 23:
        tips = [
            "晚上好 🌙 今天又是收获满满的一天。",
            "夜晚适合安静地翻阅文献 📖 享受知识的宁静。",
            "吃完晚饭了吗？来杯热牛奶暖暖胃 🥛",
            "晚上别太拼了，早点休息明天更高效 😊",
            "今晚的月色真美，就像你的论文一样迷人 🌕",
            "追剧还是看论文？都是快乐的选择 📺",
            "泡个热水脚，边泡边看文献，舒服 🛁",
            "今天辛苦了，晚上好好犒劳自己 🍰",
        ]
        icons = ["🌙", "🌕", "🌆", "📖", "🧸", "💫"]
        return random.choice(icons), "晚上好", random.choice(tips)

    return None


def get_milestone_message(total_pages):
    """翻译页数里程碑消息"""
    milestones = {
        10:   ("🎯", "首个 10 页！", "学术翻译之旅正式开始 🚀"),
        50:   ("📚", "50 页达成！", "你已经翻译了一篇完整论文的量 💪"),
        100:  ("💯", "100 页里程碑！", "你是认真的科研人 ✨"),
        200:  ("🔥", "200 页！", "翻译达人就是你！继续冲 🏃"),
        500:  ("🏆", "500 页！", "半千页！你是翻译大户 👑"),
        1000: ("👑", "1000 页传奇！", "千页翻译王者，致敬你的学术热情！🌟"),
        2000: ("💎", "2000 页！", "你已经是 pdf2zh 的资深用户了 🫡"),
        5000: ("🌟", "5000 页神话！", "你是 pdf2zh-desktop 的传奇用户 🏅"),
    }
    return milestones.get(total_pages)


def get_session_tip():
    """随机小贴士 + 温暖鼓励 + 名言"""
    # 25% 英文名言，25% 中文励志，50% 操作贴士+鼓励
    r = random.random()
    if r < 0.25:
        return random.choice(ENGLISH_INSPIRATIONAL)
    elif r < 0.50:
        return random.choice(CHINESE_INSPIRATIONAL)
    else:
        tips = [
            "💡 Ctrl+滚轮快速缩放 · 左右键翻页 · 输入页码跳转",
            "📖 Side by Side 模式适合对照阅读",
            "📝 术语库可以保证专业术语翻译一致",
            "📄 分块翻译适合 50 页以上的长文档",
            "🖐️ 触摸板双指缩放，阅读更自由",
            "💧 记得喝水哦，保持水灵灵的",
            "🧘 累了就站起来走走，灵感常在放松时出现",
            "🌍 知识没有国界，而你正在打破语言的墙",
            "📚 今天读到的每一页，都在为明天的你铺路",
            "🎯 上下键也能翻页哦，试试看",
            "⌨️ 在页码框输入数字回车可以直接跳转",
            "🔍 试试不同的翻译服务，找到最适合你的那个",
            "☕ 来杯咖啡，边喝边看翻译结果",
            "🌟 你正在做一件很酷的事情",
            "🐱 你今天也很努力呢，喵~",
            "🎵 听着音乐看论文，效率翻倍",
            "🌈 每翻译一页，你就离目标更近一步",
        ]
        return random.choice(tips)
