from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.services.sheets import sheets_service


def get_tashkent_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Tashkent"))


def generate_progress_bar(current: int, total: int, length: int = 10) -> str:
    if total <= 0:
        ratio = 0.0
    else:
        ratio = min(1.0, max(0.0, current / total))
    filled_len = int(round(length * ratio))
    bar = "▓" * filled_len + "░" * (length - filled_len)
    return bar


async def get_agent_stats(agent_id: int, daily_plan: int = 20) -> dict[str, Any]:
    """Calculate today, week, month, total counts for a specific agent."""
    now = get_tashkent_now()
    today_str = now.strftime("%Y-%m-%d")

    # Start of this week (Monday 00:00:00)
    monday = now - timedelta(days=now.weekday())
    monday_str = monday.strftime("%Y-%m-%d")

    # Start of this month (1st day)
    month_start_str = now.strftime("%Y-%m-01")

    stores = await sheets_service.get_stores(include_deleted=False)
    visits = await sheets_service.get_visits()

    today_count = 0
    week_count = 0
    month_count = 0
    total_count = 0

    for s in stores:
        if s.agent_id == agent_id:
            total_count += 1
            if s.date == today_str:
                today_count += 1
            if s.date >= monday_str:
                week_count += 1
            if s.date >= month_start_str:
                month_count += 1

    agent_visits = sum(1 for v in visits if v.agent_id == agent_id)

    percent = int((today_count / daily_plan) * 100) if daily_plan > 0 else 0
    progress_bar = generate_progress_bar(today_count, daily_plan, length=10)

    return {
        "today": today_count,
        "week": week_count,
        "month": month_count,
        "total": total_count,
        "visits": agent_visits,
        "daily_plan": daily_plan,
        "percent": percent,
        "progress_bar": progress_bar,
    }


async def get_top_ranking(period: str = "day", my_agent_id: int = 0) -> dict[str, Any]:
    """Calculate ranking by active store count for period: day, week, month."""
    now = get_tashkent_now()
    today_str = now.strftime("%Y-%m-%d")
    monday = now - timedelta(days=now.weekday())
    monday_str = monday.strftime("%Y-%m-%d")
    month_start_str = now.strftime("%Y-%m-01")

    stores = await sheets_service.get_stores(include_deleted=False)
    agents = await sheets_service.get_agents()

    # Agent ID -> count
    counts: dict[int, int] = {}
    names: dict[int, str] = {}

    for s in stores:
        if period == "day" and s.date != today_str:
            continue
        elif period == "week" and s.date < monday_str:
            continue
        elif period == "month" and s.date < month_start_str:
            continue

        counts[s.agent_id] = counts.get(s.agent_id, 0) + 1
        if s.agent_id not in names and s.agent_name:
            names[s.agent_id] = s.agent_name

    for aid, ag in agents.items():
        if aid not in names:
            names[aid] = ag.name
        if aid not in counts:
            counts[aid] = 0

    # Sort descending
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    ranking_list = []
    my_rank = None
    my_count = 0

    medals = ["🥇", "🥈", "🥉"]

    for idx, (aid, count) in enumerate(sorted_items, start=1):
        if aid == my_agent_id:
            my_rank = idx
            my_count = count

        if idx <= 10:
            medal = medals[idx - 1] if idx <= 3 else f"{idx}."
            name = names.get(aid, f"Agent #{aid}")
            ranking_list.append(f"{medal} {name}: {count} ta")

    if my_rank is None:
        my_rank = len(sorted_items) + 1
        my_count = counts.get(my_agent_id, 0)

    period_names = {
        "day": "Bugun",
        "week": "Shu hafta",
        "month": "Shu oy",
    }

    return {
        "period": period_names.get(period, period),
        "ranking_text": "\n".join(ranking_list) if ranking_list else "Hozircha ma'lumot yo'q.",
        "my_rank": my_rank,
        "my_count": my_count,
    }
