from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

engine = create_async_engine(settings.DATABASE_URL)
async_session_factory = async_sessionmaker(engine, expire_on_commit=True)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_async_session():
    async with async_session_factory() as session:
        yield session
