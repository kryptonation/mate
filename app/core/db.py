# app/core/db.py

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings
from app.utils.logger import get_logger

# --- Configure logging ---
logger = get_logger(__name__)

# --- Create database engine ---
engine = create_engine(settings.db_url)

# --- Create sessionmaker ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Create declarative base ---
Base = declarative_base()

# --- Synchronous database session ---

def get_db():
    """
    Method for obtaining database session object
    """
    db = SessionLocal()
    try:
        yield db
        logger.info("Committing DB transaction")
        db.commit()
    finally:
        db.close()


def generate_schema_description() -> str:
    """
    Generate a schema description for the database
    """
    try:
        meta = MetaData()
        meta.reflect(bind=engine)

        table_descriptions = []

        for table in meta.sorted_tables:
            column_descriptions = []
            for col in table.columns:
                col_desc = f"{col.name} {col.type}"
                if col.foreign_keys:
                    fk = list(col.foreign_keys)[0]
                    col_desc += f" → {fk.column.table.name}.{fk.column.name}"
                column_descriptions.append(col_desc)

            table_description = f"Table: {table.name} ({', '.join(column_descriptions)})"
            table_descriptions.append(table_description)

        return "\n".join(table_descriptions)
    except Exception as e:
        logger.error("Error generating schema description", error_message=str(e))
        raise e

# --- Asynchronous database setup ---
async_engine = create_async_engine(settings.async_db_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_async_db():
    """
    Async method for obtaining database session object
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            logger.info("Committing async DB transaction")
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Error in async DB transaction", error_message=str(e))
            raise e
        finally:
            await session.close()