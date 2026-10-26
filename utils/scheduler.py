from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from utils.broker import broker  # Adjust import path based on your folder structure

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)
