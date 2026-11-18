from backend.app.config import Settings, get_settings


def test_settings_load_defaults():
    settings = get_settings()
    assert settings.APP_NAME == "OpsSage AI"
    assert settings.PORT == 8000
    assert settings.API_V1_STR == "/api/v1"
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert len(settings.ALLOWED_ORIGINS) > 0


def test_cors_origins_parsing():
    settings = Settings(
        ALLOWED_ORIGINS="http://localhost:3000, https://app.opssage.ai",
        MONGODB_URI="mongodb://localhost:27017"
    )
    assert settings.ALLOWED_ORIGINS == ["http://localhost:3000", "https://app.opssage.ai"]
