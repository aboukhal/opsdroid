from .base import Base


class Users(Base):
    endpoint = "/users"

    async def get_user(self, user_id):
        return await self.get(self.endpoint + "/" + user_id)
