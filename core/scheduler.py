from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, Coroutine, Any

class WorkflowScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        
    async def add_job(
        self, 
        func: Callable[..., Coroutine[Any, Any, None]], 
        cron_expr: str,
        *args: Any
    ) -> None:
        """Fügt einen zeitgesteuerten Job hinzu"""
        trigger = CronTrigger.from_crontab(cron_expr)
        self.scheduler.add_job(func, trigger, args=args)
        
    async def start(self) -> None:
        """Startet den Scheduler"""
        self.scheduler.start()
        
    async def shutdown(self) -> None:
        """Stoppt den Scheduler"""
        self.scheduler.shutdown()
