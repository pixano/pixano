# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de la configuration du worker."""

import pytest
from pixano_worker.config import (
    DEFAULT_CHUNK_TIMEOUT_S,
    DEFAULT_CONCURRENCY,
    MissingConfigurationError,
    WorkerConfig,
    heartbeat_path,
    redact_dsn,
)


REQUIRED_ENV = {
    "PIXANO_DATABASE_URL": "postgresql://pixano:s3cret@postgres:5432/pixano",
    "PIXANO_INFERENCE_URL": "http://pixano-inference:7463",
    "PIXANO_LIBRARY_DIR": "/data/library",
    "PIXANO_MEDIA_ROOT": "/medias",
    "PIXANO_INFERENCE_MEDIA_ROOT": "/mnt/partage/medias",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poser un environnement complet et effacer les variables optionnelles."""
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    for name in (
        "PIXANO_INFERENCE_API_KEY",
        "PIXANO_WORKER_HEARTBEAT",
        "PIXANO_WORKER_CONCURRENCY",
        "PIXANO_WORKER_CHUNK_TIMEOUT_S",
    ):
        monkeypatch.delenv(name, raising=False)


class TestRedactDsn:
    """La chaîne de connexion est loguée au démarrage : elle ne doit jamais porter le mot de passe."""

    def test_masks_the_password_of_a_url(self) -> None:
        assert redact_dsn("postgresql://pixano:s3cret@db:5432/pixano") == "postgresql://pixano:***@db:5432/pixano"

    def test_masks_the_password_of_a_libpq_keyword_string(self) -> None:
        redacted = redact_dsn("host=db user=pixano password=s3cret dbname=pixano")
        assert "s3cret" not in redacted
        assert redacted == "host=db user=pixano password=*** dbname=pixano"

    def test_masks_a_quoted_keyword_password(self) -> None:
        assert "s3 cret" not in redact_dsn("host=db password='s3 cret' dbname=pixano")

    def test_leaves_a_passwordless_url_untouched(self) -> None:
        assert redact_dsn("postgresql://pixano@db:5432/pixano") == "postgresql://pixano@db:5432/pixano"

    def test_keeps_the_host_readable(self) -> None:
        """Le but du log est de montrer où l'on se connecte : l'hôte doit survivre."""
        assert "db.interne:5432" in redact_dsn("postgresql://pixano:s3cret@db.interne:5432/pixano")


class TestWorkerConfig:
    """Une configuration incomplète doit échouer au démarrage, pas trois couches plus loin."""

    def test_reads_every_field_from_the_environment(self, env: None) -> None:
        config = WorkerConfig.from_env()

        assert config.database_url == REQUIRED_ENV["PIXANO_DATABASE_URL"]
        assert config.inference_url == REQUIRED_ENV["PIXANO_INFERENCE_URL"]
        assert config.library_dir == REQUIRED_ENV["PIXANO_LIBRARY_DIR"]
        assert config.media_root == "/medias"
        assert config.inference_media_root == "/mnt/partage/medias"

    @pytest.mark.parametrize("missing", sorted(REQUIRED_ENV))
    def test_rejects_a_missing_variable(self, env: None, monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
        monkeypatch.delenv(missing)

        with pytest.raises(MissingConfigurationError, match=missing):
            WorkerConfig.from_env()

    @pytest.mark.parametrize("missing", sorted(REQUIRED_ENV))
    def test_rejects_a_blank_variable(self, env: None, monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
        """Une variable vide est le symptôme habituel d'un .env absent : même traitement."""
        monkeypatch.setenv(missing, "   ")

        with pytest.raises(MissingConfigurationError, match=missing):
            WorkerConfig.from_env()

    def test_the_inference_api_key_is_optional(self, env: None) -> None:
        assert WorkerConfig.from_env().inference_api_key == ""

    def test_concurrency_has_a_default(self, env: None) -> None:
        assert WorkerConfig.from_env().concurrency == DEFAULT_CONCURRENCY

    def test_concurrency_follows_the_environment(self, env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIXANO_WORKER_CONCURRENCY", "12")

        assert WorkerConfig.from_env().concurrency == 12

    @pytest.mark.parametrize("value", ["0", "-2", "quatre"])
    def test_rejects_a_concurrency_that_would_do_no_work(
        self, env: None, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """Zéro chunk à la fois ferait un worker vivant qui ne travaille jamais, sans erreur."""
        monkeypatch.setenv("PIXANO_WORKER_CONCURRENCY", value)

        with pytest.raises(MissingConfigurationError, match="PIXANO_WORKER_CONCURRENCY"):
            WorkerConfig.from_env()

    def test_the_chunk_time_limit_has_a_default(self, env: None) -> None:
        assert WorkerConfig.from_env().chunk_timeout_s == DEFAULT_CHUNK_TIMEOUT_S

    def test_the_chunk_time_limit_follows_the_environment(self, env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIXANO_WORKER_CHUNK_TIMEOUT_S", "90.5")

        assert WorkerConfig.from_env().chunk_timeout_s == 90.5

    @pytest.mark.parametrize("value", ["0", "-1", "une heure"])
    def test_rejects_a_chunk_time_limit_that_would_send_everything_back(
        self, env: None, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("PIXANO_WORKER_CHUNK_TIMEOUT_S", value)

        with pytest.raises(MissingConfigurationError, match="PIXANO_WORKER_CHUNK_TIMEOUT_S"):
            WorkerConfig.from_env()

    def test_the_two_media_roots_stay_independent(self, env: None) -> None:
        """Les deux côtés ne voient pas nécessairement le stockage au même endroit."""
        config = WorkerConfig.from_env()

        assert config.media_root != config.inference_media_root

    def test_describe_never_leaks_the_password(self, env: None) -> None:
        described = WorkerConfig.from_env().describe()

        assert "s3cret" not in described
        assert "postgres:5432" in described

    def test_describe_says_whether_the_inference_is_authenticated(
        self, env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert "sans clé d'API" in WorkerConfig.from_env().describe()

        monkeypatch.setenv("PIXANO_INFERENCE_API_KEY", "jeton")
        assert "authentifiée" in WorkerConfig.from_env().describe()

    def test_describe_never_leaks_the_inference_key(self, env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIXANO_INFERENCE_API_KEY", "jeton-secret")

        assert "jeton-secret" not in WorkerConfig.from_env().describe()


class TestHeartbeatPath:
    """Le worker et sa sonde doivent viser le même fichier."""

    def test_defaults_to_the_container_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PIXANO_WORKER_HEARTBEAT", raising=False)

        assert heartbeat_path() == "/tmp/pixano-worker.heartbeat"

    def test_follows_the_environment(self, env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIXANO_WORKER_HEARTBEAT", "/var/run/battement")

        assert heartbeat_path() == "/var/run/battement"
        assert WorkerConfig.from_env().heartbeat_path == "/var/run/battement"
