from app.database import engine
from sqlalchemy import text
import asyncio

async def test():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("Connected.")
    except Exception as e:
        print("Failed:", e)

asyncio.run(test())
