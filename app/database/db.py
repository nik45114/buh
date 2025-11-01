"""
Подключение к базе данных
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.database.models import Base
import logging

logger = logging.getLogger(__name__)

# Создание движка БД
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Фабрика сессий
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Alias для удобства
async_session = async_session_maker


async def get_session() -> AsyncSession:
    """
    Получить сессию базы данных
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Инициализация базы данных - создание таблиц
    """
    try:
        async with engine.begin() as conn:
            # Создание всех таблиц
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")

        # Создание начальных данных
        await create_initial_data()

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


async def create_initial_data():
    """
    Создание начальных данных (категории)
    """
    from app.database.models import Category

    async with async_session_maker() as session:
        # Проверяем, есть ли уже категории
        from sqlalchemy import select
        result = await session.execute(select(Category))
        if result.scalars().first():
            logger.info("Categories already exist, skipping initial data creation")
            return

        # Категории расходов (учитываемые в УСН)
        expense_categories = [
            ('Материальные расходы', 'expense', True, 1),
            ('Товары для перепродажи', 'expense', True, 2),
            ('Оплата труда', 'expense', True, 3),
            ('Страховые взносы', 'expense', True, 4),
            ('Аренда помещений', 'expense', True, 5),
            ('Коммунальные услуги', 'expense', True, 6),
            ('Услуги связи и интернет', 'expense', True, 7),
            ('Транспортные расходы', 'expense', True, 8),
            ('Канцелярские товары', 'expense', True, 9),
            ('Программное обеспечение', 'expense', True, 10),
            ('Ремонт и обслуживание', 'expense', True, 11),
            ('Реклама и маркетинг', 'expense', True, 12),
            ('Банковские услуги', 'expense', True, 13),
            ('Налоги и сборы', 'expense', True, 14),
            ('Прочие расходы', 'expense', True, 15),
            # Расходы НЕ учитываемые в УСН
            ('Штрафы и пени', 'expense', False, 16),
            ('Представительские расходы', 'expense', False, 17),
            ('Личные расходы', 'expense', False, 18),
        ]

        # Категории доходов
        income_categories = [
            ('Услуги компьютерного клуба', 'income', True, 1),
            ('Аренда помещений', 'income', True, 2),
            ('Прочие доходы', 'income', True, 3),
        ]

        # Создаем категории
        for name, type_, tax_deductible, sort_order in expense_categories + income_categories:
            category = Category(
                name=name,
                type=type_,
                tax_deductible=tax_deductible,
                sort_order=sort_order,
                is_active=True
            )
            session.add(category)

        await session.commit()
        logger.info("Initial categories created successfully")


async def close_db():
    """
    Закрытие соединения с БД
    """
    await engine.dispose()
    logger.info("Database connection closed")
