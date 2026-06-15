import uuid
from sqlalchemy import select
from db.models import ProviderConfig, AppSetting, GeneralChatSession


async def test_provider_config_persists(db_session):
    row = ProviderConfig(
        id=str(uuid.uuid4()),
        provider="openai",
        label="My OpenAI",
        enabled=True,
        is_default=True,
        config_encrypted="enc-blob",
    )
    db_session.add(row)
    await db_session.commit()
    got = (await db_session.execute(select(ProviderConfig))).scalar_one()
    assert got.provider == "openai"
    assert got.is_default is True
    assert got.config_encrypted == "enc-blob"


async def test_app_setting_persists(db_session):
    db_session.add(AppSetting(key="default_model", value="pid::gpt-4o"))
    await db_session.commit()
    got = (await db_session.execute(select(AppSetting).where(AppSetting.key == "default_model"))).scalar_one()
    assert got.value == "pid::gpt-4o"


async def test_general_chat_has_model_provider_id(db_session):
    chat = GeneralChatSession(id=str(uuid.uuid4()), title="c", model="gpt-4o", model_provider_id="pid-1")
    db_session.add(chat)
    await db_session.commit()
    got = (await db_session.execute(select(GeneralChatSession))).scalar_one()
    assert got.model == "gpt-4o"
    assert got.model_provider_id == "pid-1"
