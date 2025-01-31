# local imports
# 3rd-party imports
import pytest

from quicknxs.config import Settings


class TestConfiguration(object):
    def test_init(self):
        settings = Settings()

    def test_singleton(self):
        settings1 = Settings()
        settings2 = Settings()
        assert id(settings1) == id(settings2)

    def test_defaults(self):
        settings = Settings()
        assert settings["OpenSum"]["LogNames"][-1] == "S3Vheight"
        assert settings["OpenSum"]["Tolerances"][-1] == 0.01


if __name__ == "__main__":
    pytest.main([__file__])
