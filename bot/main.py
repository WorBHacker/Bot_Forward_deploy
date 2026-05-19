"""
Entry point.  Wire up all components and start the bot.
"""
import asyncio
import logging
import sys
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings
from bot.database.db import init_db
from bot.handlers import (
    admin_router,
    chat_member_router,
    control_panel_router,
    master_router,
)
from bot.handlers import admin_panel, control_panel, master_channel
from bot.middlewares.i18n import I18nMiddleware
from bot.middlewares.rbac import RBACMiddleware
from bot.services.analytics import AnalyticsService
from bot.services.broadcaster import BroadcastQueue
from bot.services.censorship import CensorshipService
from bot.services.media_collector import MediaGroupCollector
from bot.utils.backup import run_backup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # ---------------------------------------------------------------- #
    #  Bot & Dispatcher                                                  #
    # ---------------------------------------------------------------- #
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # ---------------------------------------------------------------- #
    #  Database                                                          #
    # ---------------------------------------------------------------- #
    await init_db()

    # ---------------------------------------------------------------- #
    #  Services                                                          #
    # ---------------------------------------------------------------- #
    collector = MediaGroupCollector(delay=settings.media_group_delay)
    censor = CensorshipService()
    broadcaster = BroadcastQueue(bot, rate_limit=settings.broadcast_rate_limit)
    analytics = AnalyticsService(bot)

    await broadcaster.start()
    logger.info("BroadcastQueue started")

    # Eagerly load detoxify model in background so first post isn't slow
    asyncio.create_task(_warm_up_censor(censor))

    # ---------------------------------------------------------------- #
    #  Inject dependencies into handlers                                 #
    # ---------------------------------------------------------------- #
    master_channel.setup(collector, censor, broadcaster)
    control_panel.setup(broadcaster)
    admin_panel.setup(broadcaster, analytics)

    # ---------------------------------------------------------------- #
    #  Middleware                                                        #
    # ---------------------------------------------------------------- #
    dp.message.middleware(RBACMiddleware())
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(RBACMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    # ---------------------------------------------------------------- #
    #  Routers                                                           #
    # ---------------------------------------------------------------- #
    dp.include_router(chat_member_router)   # must be first (no RBAC needed)
    dp.include_router(master_router)        # channel posts bypass RBAC
    dp.include_router(control_panel_router)
    dp.include_router(admin_router)

    # ---------------------------------------------------------------- #
    #  Scheduler (APScheduler)                                           #
    # ---------------------------------------------------------------- #
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Daily summary text
    scheduler.add_job(
        analytics.send_daily_summary,
        CronTrigger(
            hour=settings.daily_report_hour,
            minute=settings.daily_report_minute,
        ),
        id="daily_summary",
        replace_existing=True,
    )

    # Daily Excel report (sent right after the summary)
    scheduler.add_job(
        analytics.send_excel_report,
        CronTrigger(
            hour=settings.daily_report_hour,
            minute=settings.daily_report_minute + 1 if settings.daily_report_minute < 59 else 0,
        ),
        id="daily_excel",
        replace_existing=True,
    )

    # Hub-channel view sync every 30 minutes
    scheduler.add_job(
        analytics.sync_hub_views,
        "interval",
        minutes=30,
        id="hub_view_sync",
        replace_existing=True,
    )

    # Weekly backup (owner only)
    scheduler.add_job(
        run_backup,
        CronTrigger(day_of_week=settings.backup_day_of_week, hour=3, minute=0),
        id="weekly_backup",
        replace_existing=True,
        kwargs={"bot": bot},
    )

    scheduler.start()
    logger.info("Scheduler started")

    # ---------------------------------------------------------------- #
    #  Start polling                                                     #
    # ---------------------------------------------------------------- #
    logger.info("Bot starting — owner_id=%s master_channel=%s", settings.owner_id, settings.master_channel_id)

    try:
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "edited_message",
                "channel_post",
                "edited_channel_post",
                "callback_query",   
                "my_chat_member",
            ],
            drop_pending_updates=True,
        )
    finally:
        await broadcaster.stop()
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot stopped cleanly")


async def _warm_up_censor(censor: CensorshipService) -> None:
    try:
        await censor.check_text("warm up")
        logger.info("detoxify model warm-up complete")
    except Exception as exc:
        logger.warning("detoxify warm-up failed: %s", exc)


if __name__ == "__main__":
    asyncio.run(main())
