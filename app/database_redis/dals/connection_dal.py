from app.database_redis.dals.base import BaseDAL


class ConnectionDAL(BaseDAL):
    def __init__(self, client, connection_id, user_id=None):
        super().__init__(client)
        self.id = connection_id
        self.type_ = f"connection:{connection_id}"
        self.path = f"/audio/{connection_id}.webm"
        self.start_timestamp = None
        self.end_timestamp = None
        self.user_id = user_id

    async def update_redis(self):
        if self.start_timestamp is not None:
            await self.redis.hset(self.type_, "start_timestamp", self.start_timestamp)
        if self.user_id is not None:
            await self.redis.hset(self.type_, "user_id", self.user_id)

    async def load_from_redis(self):
        data = await self.redis.hgetall(self.type_)
        self.start_timestamp = data.get("start_timestamp")
        self.user_id = data.get("user_id")

    def delete_connection_data(self):
        self.redis.delete(self.type_)

    async def update_timestamps(self, segment_start_timestamp, end_timestamp):
        await self.load_from_redis()
        self.start_timestamp = segment_start_timestamp if not self.start_timestamp else self.start_timestamp
        self.end_timestamp = end_timestamp
        await self.update_redis()
