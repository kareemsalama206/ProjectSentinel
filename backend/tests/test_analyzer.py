from pathlib import Path

from app.services.analyzer import analyze_project


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_detects_common_project_files(tmp_path):
    write(tmp_path / "package.json", '{"scripts":{"test":"vitest"},"dependencies":{"react":"19.0.0","vite":"6.0.5"},"devDependencies":{"typescript":"5.6.3"}}')
    write(tmp_path / "requirements.txt", "fastapi==0.115.6\npytest==8.3.4\n")
    write(tmp_path / "Dockerfile", "FROM python:3.12-slim\nEXPOSE 8000\n")
    write(tmp_path / "docker-compose.yml", "services:\n  backend:\n    build: .\n  db:\n    image: postgres\n")
    write(tmp_path / "README.md", "# App\n\n## Setup\nRun it.\n\n## Tech Stack\nReact FastAPI\n\n## API\nDocs.\n\n## Screenshots\n![x](x.png)\n")
    write(tmp_path / ".gitignore", ".env\n")
    write(tmp_path / "tests" / "test_app.py", "def test_ok(): assert True\n")

    result = analyze_project(tmp_path, "sample")
    technologies = {technology.name for technology in result.technologies}
    tech_by_name = {technology.name: technology for technology in result.technologies}

    assert {"React", "TypeScript", "FastAPI", "Docker", "Docker Compose", "Pytest"}.issubset(technologies)
    assert tech_by_name["Docker Compose"].evidence_file == "docker-compose.yml"
    assert tech_by_name["Docker Compose"].confidence == "high"
    assert tech_by_name["React"].evidence_file == "package.json"
    assert tech_by_name["Python"].evidence_file == "requirements.txt"
    assert "FastAPI" in tech_by_name["FastAPI"].reason
    assert result.project_type == "Full-stack web app"
    assert any(finding.title == "README.md exists" for finding in result.findings)
    assert any(finding.title == "Tests folder exists" for finding in result.findings)
    assert any(finding.title == "Docker Compose detected" for finding in result.findings)
    assert result.score_explanations["security"]["explanation"]
    assert result.score_explanations["security"]["status"] == "Excellent"
    assert result.score_explanations["github"]["deductions"]


def test_detects_env_file_and_secret_like_string(tmp_path):
    write(tmp_path / ".env", "API_KEY=abc12345678901234567890\nJWT_SECRET=supersecretjwtvalue\n")
    write(tmp_path / "README.md", "# App\n")

    result = analyze_project(tmp_path, "unsafe")

    assert any(finding.title == "Potential secret detected in .env" for finding in result.findings)
    assert any("api key" in finding.title.lower() for finding in result.findings)
    critical = next(finding for finding in result.findings if finding.severity == "critical")
    assert critical.priority == "P0"
    assert critical.why_it_matters
    assert critical.recommendation
    assert result.scores["security_score"] < 80


def test_missing_readme_and_gitignore_warnings(tmp_path):
    write(tmp_path / "main.py", "print('hello')\n")

    result = analyze_project(tmp_path, "minimal")

    assert any(finding.title == "README.md is missing" for finding in result.findings)
    assert any(finding.title == ".gitignore is missing" for finding in result.findings)


def test_scores_are_between_zero_and_one_hundred(tmp_path):
    write(tmp_path / ".env", "PASSWORD=hardcodedpassword\n")

    result = analyze_project(tmp_path, "scores")

    for score in result.scores.values():
        assert 0 <= score <= 100


def test_docker_files_improve_deployment_score(tmp_path):
    write(tmp_path / "Dockerfile", "FROM python:3.12-slim\nHEALTHCHECK CMD python -V\n")
    write(tmp_path / "docker-compose.yml", "services:\n  app:\n    build: .\n")
    write(tmp_path / ".dockerignore", "__pycache__\n")

    result = analyze_project(tmp_path, "docker-ready")

    assert result.scores["deployment_score"] >= 90


def test_readme_quality_checks_include_testing_and_docker(tmp_path):
    write(tmp_path / "README.md", "# App\n\n## Setup\nRun it.\n\n## Tech Stack\nPython\n")
    write(tmp_path / "Dockerfile", "FROM python:3.12-slim\n")
    write(tmp_path / "requirements.txt", "fastapi==0.115.6\n")

    result = analyze_project(tmp_path, "docs")
    titles = {finding.title for finding in result.findings}

    assert "README is missing testing instructions" in titles
    assert "README is missing Docker instructions" in titles


def test_gitignore_quality_checks(tmp_path):
    write(tmp_path / ".gitignore", "node_modules\n.env\n*.pyc\n")
    write(tmp_path / "README.md", "# App\n")

    result = analyze_project(tmp_path, "ignore")
    titles = {finding.title for finding in result.findings}

    assert ".gitignore excludes node_modules" in titles
    assert ".gitignore excludes .env" in titles
    assert ".gitignore does not exclude dist" in titles
    assert ".gitignore does not exclude virtual environments" in titles


def test_docker_quality_checks_for_roles_and_secrets(tmp_path):
    write(tmp_path / "package.json", '{"scripts":{"test":"vitest"},"dependencies":{"react":"19.0.0"}}')
    write(tmp_path / "requirements.txt", "fastapi==0.115.6\npsycopg2==2.9.10\n")
    write(tmp_path / "Dockerfile", "FROM python:3.12-slim\nENV API_SECRET=literal-secret\n")
    write(tmp_path / "docker-compose.yml", "services:\n  backend:\n    build: .\n    environment:\n      POSTGRES_PASSWORD: hardcoded\n")

    result = analyze_project(tmp_path, "docker-risk")
    titles = {finding.title for finding in result.findings}

    assert "Docker Compose is missing frontend-like service" in titles
    assert "Docker Compose is missing PostgreSQL-like service" in titles
    assert "Potential hardcoded secret in Dockerfile environment" in titles
    assert "Potential hardcoded secret in Docker Compose environment" in titles


def test_docker_compose_yaml_parser_counts_services_and_roles(tmp_path):
    write(tmp_path / "package.json", '{"scripts":{"test":"vitest"},"dependencies":{"react":"19.0.0"}}')
    write(tmp_path / "requirements.txt", "fastapi==0.115.6\npsycopg2==2.9.10\n")
    write(
        tmp_path / "compose.yml",
        """
services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
  ui:
    build:
      context: ./frontend
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
""",
    )

    result = analyze_project(tmp_path, "compose-yaml")
    titles = {finding.title for finding in result.findings}

    assert "Docker Compose defines multiple services" in titles
    assert "Docker Compose includes frontend-like service" in titles
    assert "Docker Compose includes backend/API-like service" in titles
    assert "Docker Compose includes PostgreSQL-like service" in titles
    assert "Potential hardcoded secret in Docker Compose environment" not in titles


def test_testing_quality_checks_backend_frontend_and_package_script(tmp_path):
    write(tmp_path / "package.json", '{"scripts":{"build":"vite build"},"dependencies":{"react":"19.0.0"}}')
    write(tmp_path / "backend" / "tests" / "test_api.py", "def test_ok(): assert True\n")
    write(tmp_path / "pytest.ini", "[pytest]\n")

    result = analyze_project(tmp_path, "tests")
    titles = {finding.title for finding in result.findings}

    assert "Backend tests detected" in titles
    assert "Frontend tests are missing" in titles
    assert "package.json test script is missing" in titles
    assert "Test runner configuration detected" in titles


def test_token_like_patterns_and_lockfile_detection(tmp_path):
    write(tmp_path / "package.json", '{"scripts":{"test":"vitest"},"dependencies":{"react":"latest"}}')
    write(tmp_path / "config.txt", "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456\nAWS_KEY=AKIA1234567890ABCDEF\n")

    result = analyze_project(tmp_path, "tokens")
    titles = {finding.title for finding in result.findings}

    assert "Potential github token detected" in titles
    assert "Potential aws access key detected" in titles
    assert "JavaScript lockfile is missing" in titles
    assert "Broad dependency version detected" in titles


def test_secret_scanner_skips_obvious_example_lines(tmp_path):
    write(tmp_path / "README.md", "# App\n")
    write(tmp_path / "examples.env", "API_KEY=example_abcdefghijklmnopqrstuvwxyz\nJWT_SECRET=placeholder_secret_value\n")

    result = analyze_project(tmp_path, "samples")
    titles = {finding.title for finding in result.findings}

    assert "Potential api key or token detected" not in titles
    assert "Potential jwt secret detected" not in titles


def test_secret_scanner_does_not_skip_test_sample_or_fixture_secret_values(tmp_path):
    write(tmp_path / "README.md", "# App\n")
    write(
        tmp_path / "config.txt",
        "\n".join(
            [
                "API_KEY=testABCDEF1234567890",
                "# sample API_KEY=sampleABCDEF1234567890",
                "# fixture JWT_SECRET=fixturejwtsecretvalue123",
                "# test GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456",
            ]
        ),
    )

    result = analyze_project(tmp_path, "test-prefixed-secret")
    findings_by_title = {}
    for finding in result.findings:
        findings_by_title.setdefault(finding.title, []).append(finding)

    assert len(findings_by_title["Potential api key or token detected"]) >= 2
    assert any(finding.line_number == 3 for finding in findings_by_title["Potential jwt secret detected"])
    assert any(finding.line_number == 4 for finding in findings_by_title["Potential github token detected"])
