import pytest

from backend.common.db import create_pool
from backend.common.settings import get_settings


@pytest.fixture
async def databases():
    settings = get_settings()
    try:
        owner = await create_pool(settings, owner=True)
        runtime = await create_pool(settings)
    except (OSError, ConnectionError) as error:
        pytest.fail(
            f"Real Postgres is required. Run scripts/dev-up.ps1 -App. {type(error).__name__}"
        )
    try:
        yield owner, runtime
    finally:
        await runtime.close()
        await owner.close()
