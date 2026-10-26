# utils/broker.py
from taskiq import TaskiqEvents, TaskiqState
from taskiq_aio_pika import AioPikaBroker

from config import Settings
from utils.cache import ValkeyCache
from utils.db import Database

settings = Settings()
db = Database()

broker = AioPikaBroker(
    settings.rabbitmq_url,
    queue_name="jmpt_tasks",
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState):
    await db.init_standalone()
    await ValkeyCache.init()
    print("Worker started and ready.")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState):
    await ValkeyCache.close()
    await db.close()
    print("Worker shutting down.")


import tasks.maintenance  # noqa: F401
