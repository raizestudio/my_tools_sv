import logging

import aio_pika

from config import Settings

settings = Settings()

logger = logging.getLogger(__name__)


class RabbitMQ:
    def __init__(self, url: str):
        self.url = url
        self.connection: aio_pika.RobustConnection = None
        self.channel: aio_pika.RobustChannel = None

    async def connect(self):
        """Establish connection and channel."""
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        # Ensure the queue exists
        await self.channel.declare_queue(settings.rabbitmq_queue_name, durable=True)
        logging.info("RabbitMQ connection and channel established.")

    async def close(self):
        """Close channel and connection."""
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logging.info("RabbitMQ connection closed.")

    async def publish_message(self, message_body: str):
        """Publish a message to the specified queue."""
        if not self.channel:
            raise Exception("RabbitMQ channel is not available.")

        message = aio_pika.Message(body=message_body.encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT)

        await self.channel.default_exchange.publish(message, routing_key=settings.rabbitmq_queue_name)
        logging.info(f" [x] Sent '{message_body}'")
