import sys, asyncio
sys.path.insert(0, r'c:\Users\Samandar\sherali aka bot')
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'


async def debug():
    from app.services.sheets import sheets_service
    from app.bot.dispatcher import create_bot_and_dispatcher
    from aiogram.types import Update, Message
    from unittest.mock import AsyncMock, patch, MagicMock

    bot, dp = create_bot_and_dispatcher()

    update_data = {
        'update_id': 88888888,
        'message': {
            'message_id': 12345,
            'from': {'id': 777888999, 'is_bot': False, 'first_name': 'YeniUser'},
            'chat': {'id': 777888999, 'type': 'private'},
            'date': 1700000001,
            'text': '/start'
        }
    }
    update = Update.model_validate(update_data, context={'bot': bot})

    async def mock_get_agent(tid):
        print(f"[mock] get_agent_by_id({tid}) -> None")
        return None

    answers = []

    async def mock_answer(*a, **kw):
        text = kw.get('text') or (a[0] if a else '')
        print(f"[mock] message.answer called! text={str(text)[:80]}")
        answers.append(text)
        m = MagicMock()
        m.message_id = 1
        return m

    with patch.object(sheets_service, 'get_agent_by_id', side_effect=mock_get_agent):
        with patch.object(Message, 'answer', side_effect=mock_answer):
            try:
                await dp.feed_update(bot=bot, update=update)
                print(f"feed_update completed. Answers sent: {len(answers)}")
            except Exception as e:
                print(f"Error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()


asyncio.run(debug())
