from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read_project_file(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(
        encoding="utf-8"
    )


def test_dockerfile_uses_pinned_non_root_single_worker_runtime():
    dockerfile = read_project_file("Dockerfile")

    assert "python:3.10.19-slim-bookworm" in dockerfile
    assert "USER app" in dockerfile
    assert '"--workers", "1"' in dockerfile
    assert "--reload" not in dockerfile
    assert "requirements-dev.txt" not in dockerfile


def test_dockerfile_initializes_database_and_has_readiness_healthcheck():
    dockerfile = read_project_file("Dockerfile")
    entrypoint = read_project_file(
        "scripts/docker-entrypoint.sh"
    )

    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/ready" in dockerfile
    assert "python -m src.app.db" in entrypoint
    assert entrypoint.index(
        "python -m src.app.db"
    ) < entrypoint.index('exec "$@"')


def test_compose_persists_all_runtime_state_in_named_volumes():
    compose = read_project_file("docker-compose.yml")

    expected_mounts = {
        "chat_api_data:/app/data",
        "chat_api_runs:/app/runs",
        "chat_api_kb:/app/kb",
    }
    assert all(mount in compose for mount in expected_mounts)
    assert "./data:/app/data" not in compose
    assert "./runs:/app/runs" not in compose
    assert "sqlite:////app/data/chat_api.db" in compose


def test_compose_maps_ollama_to_host_gateway():
    compose = read_project_file("docker-compose.yml")
    env_example = read_project_file(".env.example")

    assert (
        "host.docker.internal:host-gateway"
        in compose
    )
    assert (
        "OLLAMA_DOCKER_BASE_URL:-"
        "http://host.docker.internal:11434"
        in compose
    )
    assert (
        "OLLAMA_DOCKER_BASE_URL="
        "http://host.docker.internal:11434"
        in env_example
    )


def test_dockerignore_excludes_secrets_and_runtime_data():
    dockerignore = read_project_file(".dockerignore")

    for pattern in (
        ".env",
        "data/",
        "runs/",
        "kb/chroma/",
        "kb/docs/",
        "benchmarks/results/",
    ):
        assert pattern in dockerignore

    assert "!.env.example" in dockerignore


def test_one_click_start_and_ci_use_release_smoke_test():
    start_script = read_project_file(
        "scripts/docker_start.sh"
    )
    workflow = read_project_file(
        ".github/workflows/ci.yml"
    )

    assert "docker compose up --build --detach" in start_script
    assert "scripts/docker_smoke_test.py" in start_script
    assert "docker-smoke:" in workflow
    assert "--wait-timeout 180" in workflow
    assert "scripts/docker_smoke_test.py" in workflow
    assert ".State.Health.Status" in workflow
