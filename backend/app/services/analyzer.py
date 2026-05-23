from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from app.core.config import get_settings


TEXT_EXTENSIONS = {
    ".c",
    ".cfg",
    ".cmake",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".env",
    ".go",
    ".gradle",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".lock",
    ".md",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

SKIPPED_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "venv",
}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("API key or token", re.compile(r"(?i)(api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
    ("Password-like value", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^'\"\s]{8,}")),
    ("JWT secret", re.compile(r"(?i)(jwt[_-]?secret|secret[_-]?key)\s*[:=]\s*['\"]?[^'\"\s]{12,}")),
    ("Database URL", re.compile(r"(?i)(postgresql|postgres|mysql|mongodb|redis)://[^\\s'\"]+")),
    ("Private key block", re.compile(r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b|github_pat_[A-Za-z0-9_]{20,}")),
]

SECRET_EXAMPLE_MARKERS = ("example", "placeholder", "your_", "changeme", "dummy")
SECRET_TEST_MARKER_PATTERN = re.compile(r"(?i)(?:^|[^a-z0-9_])(test|sample|fixture)(?:[^a-z0-9_]|$)")
SECRET_REAL_CONTEXT_PATTERN = re.compile(r"(?i)(?:^|[^a-z0-9_])(prod|production|live|real)(?:[^a-z0-9_]|$)")


@dataclass(frozen=True)
class FileRecord:
    path: str
    absolute_path: Path
    size: int
    is_text: bool


@dataclass(frozen=True)
class FindingDraft:
    category: str
    severity: str
    title: str
    description: str
    recommendation: str
    file_path: str | None = None
    line_number: int | None = None
    priority: str | None = None
    why_it_matters: str | None = None


@dataclass(frozen=True)
class TechnologyDraft:
    name: str
    category: str
    evidence_file: str | None = None
    reason: str | None = None
    confidence: str = "high"


@dataclass(frozen=True)
class FileSummaryDraft:
    total_files: int
    scanned_files: int
    skipped_files: int
    total_size_bytes: int


@dataclass(frozen=True)
class AnalysisDraft:
    project_name: str
    project_type: str
    technologies: list[TechnologyDraft]
    findings: list[FindingDraft]
    file_summary: FileSummaryDraft
    scores: dict[str, int]
    score_explanations: dict[str, dict[str, list[str] | str]]


def analyze_project(root: Path, project_name: str) -> AnalysisDraft:
    files = collect_files(root)
    path_set = {record.path for record in files}
    lower_path_set = {record.path.lower() for record in files}
    technologies = detect_technologies(root, files)
    project_type = detect_project_type(technologies, path_set)
    findings = run_checks(root, files, path_set, lower_path_set, technologies, project_type)
    findings = finalize_findings(findings)
    scores, explanations = calculate_scores(findings, path_set, technologies, project_type)
    summary = FileSummaryDraft(
        total_files=len(files),
        scanned_files=sum(1 for record in files if record.is_text and record.size <= get_settings().max_scan_file_size_bytes),
        skipped_files=sum(1 for record in files if not record.is_text or record.size > get_settings().max_scan_file_size_bytes),
        total_size_bytes=sum(record.size for record in files),
    )

    return AnalysisDraft(
        project_name=project_name,
        project_type=project_type,
        technologies=technologies,
        findings=findings,
        file_summary=summary,
        scores=scores,
        score_explanations=explanations,
    )


def collect_files(root: Path) -> list[FileRecord]:
    records: list[FileRecord] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIPPED_DIRS for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        records.append(
            FileRecord(
                path=relative,
                absolute_path=path,
                size=size,
                is_text=is_probably_text(path),
            )
        )
    return sorted(records, key=lambda item: item.path)


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS or path.name in {
        ".dockerignore",
        ".env",
        ".gitignore",
        "Dockerfile",
        "Makefile",
        "README",
    }:
        try:
            chunk = path.read_bytes()[:2048]
        except OSError:
            return False
        return b"\x00" not in chunk
    return False


def detect_technologies(root: Path, files: list[FileRecord]) -> list[TechnologyDraft]:
    path_set = {record.path for record in files}
    lower_path_set = {record.path.lower() for record in files}
    techs: dict[str, TechnologyDraft] = {}

    def add(
        name: str,
        category: str,
        evidence_file: str | None,
        reason: str,
        confidence: str = "high",
    ) -> None:
        current = techs.get(name)
        candidate = TechnologyDraft(
            name=name,
            category=category,
            evidence_file=evidence_file,
            reason=reason,
            confidence=confidence,
        )
        if current is None or confidence_rank(candidate.confidence) > confidence_rank(current.confidence):
            techs[name] = candidate

    package_path = find_named_path(path_set, "package.json")
    package_data = load_json_file(root, package_path) if package_path else {}
    deps = package_dependencies(package_data)

    if package_path:
        add("Node.js", "runtime", package_path, "package.json was found.")
        if "react" in deps:
            add("React", "frontend", package_path, "React dependency was found in package.json.")
        if "typescript" in deps:
            add("TypeScript", "language", package_path, "TypeScript dependency was found in package.json.")
        elif any(path.endswith((".ts", ".tsx")) for path in lower_path_set):
            ts_path = find_by_suffix(lower_path_set, (".ts", ".tsx"))
            add("TypeScript", "language", ts_path, "TypeScript source files were found.", "medium")
        vite_path = find_name_startswith(path_set, "vite.config")
        if "vite" in deps:
            add("Vite", "frontend", package_path, "Vite dependency was found in package.json.")
        elif vite_path:
            add("Vite", "frontend", vite_path, "Vite configuration file was found.", "high")
        next_path = find_name_startswith(path_set, "next.config")
        if "next" in deps:
            add("Next.js", "frontend", package_path, "Next.js dependency was found in package.json.")
        elif next_path:
            add("Next.js", "frontend", next_path, "Next.js configuration file was found.", "high")
        if "express" in deps:
            add("Express", "backend", package_path, "Express dependency was found in package.json.")
        elif find_named_path(path_set, "server.js"):
            add("Express", "backend", "server.js", "server.js was found; Express is possible but not confirmed.", "low")
        if "jest" in deps:
            add("Jest", "testing", package_path, "Jest dependency was found in package.json.")
        if "vitest" in deps:
            add("Vitest", "testing", package_path, "Vitest dependency was found in package.json.")

    requirements_path = find_named_path(path_set, "requirements.txt")
    pyproject_path = find_named_path(path_set, "pyproject.toml")
    python_source_path = find_by_suffix(lower_path_set, (".py",))
    if requirements_path:
        add("Python", "language", requirements_path, "Python dependency file requirements.txt was found.")
    elif pyproject_path:
        add("Python", "language", pyproject_path, "Python project file pyproject.toml was found.")
    elif python_source_path:
        add("Python", "language", python_source_path, "Python source files were found.", "medium")

    python_candidates = [path for path in [requirements_path, pyproject_path, find_named_path(path_set, "main.py"), "app/main.py" if "app/main.py" in path_set else None] if path]
    python_text = read_selected_text(root, python_candidates)
    if re.search(r"(?i)\bfastapi\b", python_text):
        add("FastAPI", "backend", first_matching_text_file(root, python_candidates, r"(?i)\bfastapi\b"), "FastAPI dependency or import was detected.")
    if re.search(r"(?i)\bflask\b", python_text):
        add("Flask", "backend", first_matching_text_file(root, python_candidates, r"(?i)\bflask\b"), "Flask dependency or import was detected.")
    pytest_path = find_named_path(path_set, "pytest.ini")
    if pytest_path:
        add("Pytest", "testing", pytest_path, "pytest.ini configuration file was found.")
    elif re.search(r"(?i)\bpytest\b", python_text):
        add("Pytest", "testing", first_matching_text_file(root, python_candidates, r"(?i)\bpytest\b"), "Pytest dependency or reference was detected.")

    pom_path = find_named_path(path_set, "pom.xml")
    if pom_path:
        add("Java", "language", pom_path, "Maven project file pom.xml was found.")
        add("Maven", "build", pom_path, "pom.xml was found.")
    gradle_path = find_named_path(path_set, "build.gradle") or find_named_path(path_set, "build.gradle.kts")
    if gradle_path:
        add("Java", "language", gradle_path, "Gradle build file was found.")
        add("Gradle", "build", gradle_path, "Gradle build file was found.")

    cmake_path = find_named_path(path_set, "CMakeLists.txt")
    if cmake_path:
        add("CMake", "build", cmake_path, "CMakeLists.txt was found.")
    cpp_path = find_by_suffix(lower_path_set, (".cpp", ".h", ".hpp", ".c"))
    if cpp_path:
        add("C/C++", "language", cpp_path, "C or C++ source/header files were found.", "medium")
    makefile_path = find_named_path(path_set, "Makefile")
    if makefile_path:
        add("Make", "build", makefile_path, "Makefile was found.")

    dockerfile_path = find_named_path(path_set, "Dockerfile")
    if dockerfile_path:
        add("Docker", "deployment", dockerfile_path, "Dockerfile was found.")
    compose_path = find_first_present(path_set, ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"])
    if compose_path:
        add("Docker Compose", "deployment", compose_path, f"{Path(compose_path).name} was found.")
    workflow_path = next((path for path in path_set if path.startswith(".github/workflows/")), None)
    if workflow_path:
        add("GitHub Actions", "ci", workflow_path, "A workflow file was found under .github/workflows.")
    if any(name in deps for name in {"pg", "postgres", "sequelize"}):
        add("PostgreSQL", "database", package_path, "PostgreSQL-related JavaScript dependency was found in package.json.")
    elif re.search(r"(?i)psycopg|sqlalchemy|postgres", python_text):
        add("PostgreSQL", "database", first_matching_text_file(root, python_candidates, r"(?i)psycopg|sqlalchemy|postgres"), "PostgreSQL-related Python dependency or reference was detected.", "medium")

    return sorted(techs.values(), key=lambda technology: technology.name)


def detect_project_type(technologies: list[TechnologyDraft], path_set: set[str]) -> str:
    categories = {tech.category for tech in technologies}
    names = {tech.name for tech in technologies}
    has_frontend = bool({"React", "Vite", "Next.js"} & names) or "src" in {Path(path).parts[0] for path in path_set}
    has_backend = bool({"FastAPI", "Flask", "Express"} & names) or "backend" in {Path(path).parts[0] for path in path_set}

    if has_frontend and has_backend:
        return "Full-stack web app"
    if has_frontend:
        return "Frontend web app"
    if has_backend:
        return "Backend API/service"
    if "Java" in names:
        return "Java application"
    if "C/C++" in names:
        return "C/C++ project"
    if "deployment" in categories:
        return "Containerized project"
    return "Software project"


def run_checks(
    root: Path,
    files: list[FileRecord],
    path_set: set[str],
    lower_path_set: set[str],
    technologies: list[TechnologyDraft],
    project_type: str,
) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    names = {tech.name for tech in technologies}
    backend_detected = bool({"FastAPI", "Flask", "Express", "Python", "Node.js"} & names)
    docker_detected = bool({"Docker", "Docker Compose"} & names)

    findings.extend(security_findings(root, files, path_set))
    findings.extend(documentation_findings(root, path_set, backend_detected, docker_detected))
    findings.extend(testing_findings(root, path_set, lower_path_set))
    findings.extend(docker_findings(root, path_set, project_type, technologies))
    findings.extend(github_findings(root, path_set))
    findings.extend(dependency_findings(root, path_set))
    findings.extend(structure_findings(root, path_set, files))

    return findings


def security_findings(root: Path, files: list[FileRecord], path_set: set[str]) -> list[FindingDraft]:
    findings: list[FindingDraft] = []

    env_files = [path for path in path_set if Path(path).name == ".env" or path.endswith("/.env")]
    for env_file in env_files:
        findings.append(
            FindingDraft(
                category="security",
                severity="critical",
                title="Potential secret detected in .env",
                description=".env files commonly contain credentials or environment-specific secrets and should not be committed.",
                recommendation="Remove .env from the repository, rotate exposed secrets, and add .env to .gitignore.",
                file_path=env_file,
            )
        )

    private_key_files = [
        path
        for path in path_set
        if path.endswith((".pem", ".key", ".p12", ".pfx")) or "id_rsa" in Path(path).name.lower()
    ]
    for private_key in private_key_files:
        findings.append(
            FindingDraft(
                category="security",
                severity="critical",
                title="Private key file included",
                description="A private key-like file was found in the archive.",
                recommendation="Remove private keys from the repository and rotate any exposed credentials.",
                file_path=private_key,
            )
        )

    for record in files:
        if not record.is_text or record.size > get_settings().max_scan_file_size_bytes:
            continue
        text = read_text_safely(record.absolute_path)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if should_skip_secret_line(line):
                continue
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    severity = "critical" if record.path in env_files or "private key" in label.lower() else "warning"
                    findings.append(
                        FindingDraft(
                            category="security",
                            severity=severity,
                            title=f"Potential {label.lower()} detected",
                            description="A secret-like value was found using deterministic pattern matching.",
                            recommendation="Move secrets to environment variables or a secret manager, rotate exposed values, and avoid committing credentials.",
                            file_path=record.path,
                            line_number=line_number,
                        )
                    )
                    break

    if not any(f.category == "security" and f.severity in {"critical", "warning"} for f in findings):
        findings.append(
            FindingDraft(
                category="security",
                severity="passed",
                title="No obvious committed secrets detected",
                description="The MVP scanner did not find common secret-like strings in text files.",
                recommendation="Continue using secret scanning in CI for deeper coverage.",
            )
        )

    return findings


def documentation_findings(root: Path, path_set: set[str], backend_detected: bool, docker_detected: bool) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    readme_path = find_case_insensitive(path_set, "README.md")
    if not readme_path:
        return [
            FindingDraft(
                category="documentation",
                severity="warning",
                title="README.md is missing",
                description="A README is important for setup, usage, and project evaluation.",
                recommendation="Add a README.md with installation, run, testing, architecture, and API notes.",
            )
        ]

    findings.append(
        FindingDraft(
            category="documentation",
            severity="passed",
            title="README.md exists",
            description="The project includes a README file.",
            recommendation="Keep README instructions current as the project evolves.",
            file_path=readme_path,
        )
    )
    text = read_text_safely(root / readme_path) or ""
    checks = [
        (
            "README has setup/run instructions",
            re.search(r"(?i)(install|setup|getting started|run|docker compose|npm|pip)", text),
            "Add clear installation and run instructions.",
        ),
        (
            "README has tech stack section",
            re.search(r"(?i)(tech stack|technologies|built with|stack)", text),
            "Add a concise tech stack section.",
        ),
        (
            "README has screenshots or image links",
            re.search(r"(?i)(screenshots?|!\[.*\]\(|\.png|\.jpg|\.jpeg|\.gif)", text),
            "Add a screenshots section or image links that show the application.",
        ),
        (
            "README has testing instructions",
            re.search(r"(?i)(test|testing|pytest|jest|vitest|npm\s+test|python\s+-m\s+pytest)", text),
            "Document how to run the project test suite.",
        ),
    ]
    if backend_detected:
        checks.append(
            (
                "README has API documentation section",
                re.search(r"(?i)(api|endpoint|openapi|swagger|docs)", text),
                "Document key API endpoints and how to open the generated API docs.",
            )
        )
    if docker_detected:
        checks.append(
            (
                "README has Docker instructions",
                re.search(r"(?i)(docker|compose|container)", text),
                "Document Docker or Docker Compose setup instructions because container files were detected.",
            )
        )

    for title, passed, recommendation in checks:
        findings.append(
            FindingDraft(
                category="documentation",
                severity="passed" if passed else "warning",
                title=title if passed else title.replace("has", "is missing"),
                description="README content check passed." if passed else "The README does not appear to include this expected section.",
                recommendation="Good. Keep this section accurate." if passed else recommendation,
                file_path=readme_path,
            )
        )

    return findings


def testing_findings(root: Path, path_set: set[str], lower_path_set: set[str]) -> list[FindingDraft]:
    has_tests_dir = any(Path(path).parts and Path(path).parts[0].lower() == "tests" for path in path_set)
    has_test_files = any(
        re.search(r"(\.test\.|\.spec\.|test_).*", Path(path).name.lower()) for path in lower_path_set
    )
    has_backend_tests = any(
        path.endswith(".py") and ("tests/" in path or path.startswith("test_") or "/test_" in path)
        for path in lower_path_set
    )
    has_frontend_tests = any(
        path.endswith((".test.ts", ".test.tsx", ".test.js", ".test.jsx", ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx"))
        for path in lower_path_set
    )
    has_test_config = any(
        path in lower_path_set
        for path in {
            "pytest.ini",
            "vitest.config.ts",
            "vitest.config.js",
            "jest.config.js",
            "jest.config.ts",
            "jest.config.mjs",
        }
    )
    package_path = find_named_path(path_set, "package.json")
    package_data = load_json_file(root, package_path)
    scripts = package_data.get("scripts", {}) if isinstance(package_data, dict) else {}
    has_test_script = isinstance(scripts, dict) and "test" in scripts
    has_js_project = package_path is not None

    findings = [
        FindingDraft(
            category="testing",
            severity="passed" if has_tests_dir else "warning",
            title="Tests folder exists" if has_tests_dir else "Tests folder is missing",
            description="A tests directory was found." if has_tests_dir else "No top-level tests directory was found.",
            recommendation="Good. Keep tests organized by feature." if has_tests_dir else "Add a tests directory with focused unit or API tests.",
        ),
        FindingDraft(
            category="testing",
            severity="passed" if has_test_files else "warning",
            title="Test files detected" if has_test_files else "No test files detected",
            description="Test file naming patterns were found." if has_test_files else "No common test file names were found.",
            recommendation="Good. Keep test naming consistent." if has_test_files else "Add files named like test_*.py, *.test.ts, or *.spec.ts.",
        ),
        FindingDraft(
            category="testing",
            severity="passed" if has_test_config else "info",
            title="Test runner configuration detected" if has_test_config else "No explicit test runner configuration detected",
            description="A pytest, Jest, or Vitest config was found." if has_test_config else "The scanner did not find a dedicated test runner config.",
            recommendation="Good. CI can use this test configuration." if has_test_config else "Add pytest.ini, jest.config.*, or vitest.config.* when test settings become non-trivial.",
        ),
        FindingDraft(
            category="testing",
            severity="passed" if has_backend_tests else "info",
            title="Backend tests detected" if has_backend_tests else "Backend tests not detected",
            description="Python backend test files were found." if has_backend_tests else "No Python backend test files were found.",
            recommendation="Good. Backend tests improve API confidence." if has_backend_tests else "Add backend tests if the project includes backend logic.",
        ),
    ]
    if has_js_project:
        findings.append(
            FindingDraft(
                category="testing",
                severity="passed" if has_test_script else "warning",
                title="package.json test script exists" if has_test_script else "package.json test script is missing",
                description="A test script was found in package.json." if has_test_script else "The JavaScript project does not expose an npm test script.",
                recommendation="Good. Test scripts make local and CI checks discoverable." if has_test_script else "Add a package.json test script that runs Jest, Vitest, or the selected test runner.",
                file_path=package_path,
            )
        )
        findings.append(
            FindingDraft(
                category="testing",
                severity="passed" if has_frontend_tests else "warning",
                title="Frontend tests detected" if has_frontend_tests else "Frontend tests are missing",
                description="Frontend test files were found." if has_frontend_tests else "No Jest/Vitest-style frontend test files were found.",
                recommendation="Good. Frontend tests improve UI confidence." if has_frontend_tests else "Add frontend tests for critical UI flows or document why the project is backend-only.",
            )
        )
    return findings


def docker_findings(root: Path, path_set: set[str], project_type: str, technologies: list[TechnologyDraft]) -> list[FindingDraft]:
    compose_path = next(
        (path for path in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"] if path in path_set),
        None,
    )
    dockerfile_exists = "Dockerfile" in path_set
    dockerignore_exists = ".dockerignore" in path_set
    findings = [
        FindingDraft(
            category="docker",
            severity="passed" if dockerfile_exists else "warning",
            title="Dockerfile exists" if dockerfile_exists else "Dockerfile is missing",
            description="A Dockerfile was found." if dockerfile_exists else "No Dockerfile was detected.",
            recommendation="Good. Container builds improve deployment repeatability." if dockerfile_exists else "Add a Dockerfile for reproducible builds.",
            file_path="Dockerfile" if dockerfile_exists else None,
        ),
        FindingDraft(
            category="docker",
            severity="passed" if compose_path else "warning",
            title="Docker Compose detected" if compose_path else "Docker Compose file is missing",
            description="A Compose file was found." if compose_path else "No Docker Compose file was detected.",
            recommendation="Good. Docker Compose improves reproducibility." if compose_path else "Add docker-compose.yml for local multi-service development.",
            file_path=compose_path,
        ),
        FindingDraft(
            category="docker",
            severity="passed" if dockerignore_exists else "warning",
            title=".dockerignore exists" if dockerignore_exists else ".dockerignore is missing",
            description=".dockerignore was found." if dockerignore_exists else "No .dockerignore was detected.",
            recommendation="Good. This keeps builds smaller and cleaner." if dockerignore_exists else "Add .dockerignore to avoid copying local caches, dependencies, and secrets into images.",
            file_path=".dockerignore" if dockerignore_exists else None,
        ),
    ]

    if dockerfile_exists:
        dockerfile = read_text_safely(root / "Dockerfile") or ""
        exposed = re.findall(r"(?im)^EXPOSE\s+(.+)$", dockerfile)
        healthcheck = re.search(r"(?im)^HEALTHCHECK\b", dockerfile)
        findings.append(
            FindingDraft(
                category="docker",
                severity="info" if exposed else "warning",
                title="Dockerfile exposes ports" if exposed else "Dockerfile does not expose ports",
                description=f"Exposed ports: {', '.join(exposed)}" if exposed else "No EXPOSE instruction was found.",
                recommendation="Document exposed ports in the README." if exposed else "Add EXPOSE for service ports when useful for operators.",
                file_path="Dockerfile",
            )
        )
        findings.append(
            FindingDraft(
                category="docker",
                severity="passed" if healthcheck else "warning",
                title="Docker healthcheck exists" if healthcheck else "Docker healthcheck is missing",
                description="A HEALTHCHECK instruction was found." if healthcheck else "No Dockerfile HEALTHCHECK instruction was found.",
                recommendation="Good. Healthchecks improve deployment observability." if healthcheck else "Add HEALTHCHECK or define service healthchecks in Compose for production-like services.",
                file_path="Dockerfile",
            )
        )
        dev_server = re.search(r"(?i)(npm\s+run\s+dev|vite\s+--host|uvicorn\s+.*--reload|flask\s+run)", dockerfile)
        if dev_server:
            findings.append(
                FindingDraft(
                    category="docker",
                    severity="warning",
                    title="Dockerfile appears to run a development server",
                    description="The Dockerfile command references a development server or reload mode.",
                    recommendation="Use production server commands for deployable images and keep development commands in Compose overrides.",
                    file_path="Dockerfile",
                )
            )
        unsafe_env = find_unsafe_dockerfile_environment(dockerfile)
        if unsafe_env:
            findings.append(
                FindingDraft(
                    category="docker",
                    severity="warning",
                    title="Potential hardcoded secret in Dockerfile environment",
                    description=f"ENV instruction appears to contain a literal credential: {unsafe_env}",
                    recommendation="Use runtime environment variables or secret managers instead of baking credentials into container images.",
                    file_path="Dockerfile",
                )
            )

    if compose_path:
        compose_text = read_text_safely(root / compose_path) or ""
        compose_services = parse_compose_services(compose_text)
        service_count = len(compose_services) if compose_services is not None else len(re.findall(r"(?m)^  [A-Za-z0-9_.-]+:\s*$", compose_text))
        compose_roles = detect_compose_roles(compose_text, compose_services)
        if project_type == "Full-stack web app":
            findings.append(
                FindingDraft(
                    category="docker",
                    severity="passed" if service_count >= 2 else "warning",
                    title="Docker Compose defines multiple services" if service_count >= 2 else "Docker Compose may be incomplete for full-stack app",
                    description=f"Detected approximately {service_count} Compose service(s).",
                    recommendation="Good. Full-stack projects usually need multiple services." if service_count >= 2 else "Define frontend, backend, and database services as appropriate.",
                    file_path=compose_path,
                )
            )
            for role, label in [("frontend", "frontend-like service"), ("backend", "backend/API-like service")]:
                found = compose_roles[role]
                findings.append(
                    FindingDraft(
                        category="docker",
                        severity="passed" if found else "warning",
                        title=f"Docker Compose includes {label}" if found else f"Docker Compose is missing {label}",
                        description=f"A {label} was detected in Compose." if found else f"No obvious {label} was detected in Compose service names, images, or build context.",
                        recommendation="Good. Compose reflects the project architecture." if found else f"Add or rename a {label} in Compose so local setup matches the app architecture.",
                        file_path=compose_path,
                    )
                )
        names = {technology.name for technology in technologies}
        if "PostgreSQL" in names or re.search(r"(?i)postgres|psql|database", compose_text):
            findings.append(
                FindingDraft(
                    category="docker",
                    severity="passed" if compose_roles["postgres"] else "warning",
                    title="Docker Compose includes PostgreSQL-like service" if compose_roles["postgres"] else "Docker Compose is missing PostgreSQL-like service",
                    description="A PostgreSQL/database service was detected in Compose." if compose_roles["postgres"] else "PostgreSQL was detected in the project but no obvious database service was found in Compose.",
                    recommendation="Good. Database dependencies are reproducible locally." if compose_roles["postgres"] else "Add a postgres or database service to Compose when local development depends on PostgreSQL.",
                    file_path=compose_path,
                )
            )
        unsafe_env = find_unsafe_compose_environment(compose_text, compose_services)
        if unsafe_env:
            findings.append(
                FindingDraft(
                    category="docker",
                    severity="warning",
                    title="Potential hardcoded secret in Docker Compose environment",
                    description=f"Environment value appears to contain a literal credential: {unsafe_env}",
                    recommendation="Use environment variable references such as ${DATABASE_PASSWORD} instead of hardcoded secrets in Compose.",
                    file_path=compose_path,
                )
            )

    return findings


def parse_compose_services(compose_text: str) -> dict[str, object] | None:
    try:
        parsed = yaml.safe_load(compose_text)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    services = parsed.get("services")
    if not isinstance(services, dict):
        return None
    return services


def detect_compose_roles(compose_text: str, compose_services: dict[str, object] | None = None) -> dict[str, bool]:
    if compose_services is None:
        lowered = compose_text.lower()
        return {
            "frontend": bool(re.search(r"\b(frontend|front-end|web|client|ui|vite|react)\b", lowered)),
            "backend": bool(re.search(r"\b(backend|back-end|api|server|fastapi|flask|express)\b", lowered)),
            "postgres": bool(re.search(r"\b(postgres|postgresql|db|database)\b", lowered)),
        }

    role_text_parts: list[str] = []
    for name, definition in compose_services.items():
        role_text_parts.append(str(name))
        if not isinstance(definition, dict):
            continue
        for field in ("image", "build", "container_name", "command"):
            value = definition.get(field)
            if isinstance(value, str):
                role_text_parts.append(value)
            elif isinstance(value, dict):
                context = value.get("context")
                dockerfile = value.get("dockerfile")
                if isinstance(context, str):
                    role_text_parts.append(context)
                if isinstance(dockerfile, str):
                    role_text_parts.append(dockerfile)
    lowered = " ".join(role_text_parts).lower()
    return {
        "frontend": bool(re.search(r"\b(frontend|front-end|web|client|ui|vite|react)\b", lowered)),
        "backend": bool(re.search(r"\b(backend|back-end|api|server|fastapi|flask|express)\b", lowered)),
        "postgres": bool(re.search(r"\b(postgres|postgresql|db|database)\b", lowered)),
    }


def find_unsafe_dockerfile_environment(dockerfile: str) -> str | None:
    for line in dockerfile.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("ENV "):
            continue
        if re.search(r"(?i)(password|secret|token|api[_-]?key)", stripped) and not re.search(r"\$\{?[A-Z0-9_]+\}?", stripped):
            return stripped[:120]
    return None


def find_unsafe_compose_environment(compose_text: str, compose_services: dict[str, object] | None = None) -> str | None:
    if compose_services is not None:
        for service_name, definition in compose_services.items():
            if not isinstance(definition, dict):
                continue
            environment = definition.get("environment")
            found = find_unsafe_environment_value(environment)
            if found:
                return f"{service_name}: {found}"[:120]

    for line in compose_text.splitlines():
        stripped = line.strip()
        if not re.search(r"(?i)(password|secret|token|api[_-]?key)", stripped):
            continue
        if "${" in stripped:
            continue
        if re.search(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[^'\"\s{}]+", stripped):
            return stripped[:120]
    return None


def find_unsafe_environment_value(environment: object) -> str | None:
    items: list[tuple[str, object]] = []
    if isinstance(environment, dict):
        items.extend((str(key), value) for key, value in environment.items())
    elif isinstance(environment, list):
        for item in environment:
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                items.append((key, value))

    for key, value in items:
        if not re.search(r"(?i)(password|secret|token|api[_-]?key)", key):
            continue
        if value is None:
            continue
        value_text = str(value).strip()
        if not value_text or "${" in value_text:
            continue
        return f"{key}={value_text}"[:120]
    return None


def github_findings(root: Path, path_set: set[str]) -> list[FindingDraft]:
    has_ci = any(path.startswith(".github/workflows/") for path in path_set)
    has_screenshots = any(Path(path).parts and Path(path).parts[0].lower() in {"screenshots", "assets"} for path in path_set)
    license_path = next((path for path in path_set if Path(path).name.lower() in {"license", "license.md", "license.txt"}), None)
    checks = [
        (".gitignore exists", ".gitignore" in path_set, "Add .gitignore to prevent generated files and secrets from being committed.", ".gitignore"),
        ("README exists", any(Path(path).name.lower() == "readme.md" for path in path_set), "Add README.md for project visitors.", "README.md"),
        ("Screenshots folder exists", has_screenshots, "Add screenshots or assets that show the project in use.", None),
        ("License file exists", bool(license_path), "Add a license file if the project is intended to be shared.", license_path),
        ("CI workflow exists", has_ci, "Add a GitHub Actions workflow to run tests and builds.", ".github/workflows"),
    ]
    findings: list[FindingDraft] = []
    for title, passed, recommendation, file_path in checks:
        findings.append(
            FindingDraft(
                category="github",
                severity="passed" if passed else "warning",
                title=title if passed else title.replace("exists", "is missing"),
                description="GitHub readiness check passed." if passed else "Expected GitHub readiness artifact was not found.",
                recommendation="Good. This improves repository readiness." if passed else recommendation,
                file_path=file_path if passed else None,
            )
        )
    gitignore_path = ".gitignore" if ".gitignore" in path_set else None
    if gitignore_path:
        gitignore_text = read_text_safely(root / gitignore_path) or ""
        ignore_checks = [
            ("node_modules", r"(^|/|\n)node_modules/?(\n|$)", "Add node_modules to .gitignore for JavaScript dependency folders."),
            ("dist", r"(^|/|\n)dist/?(\n|$)", "Add dist to .gitignore for frontend build output."),
            ("__pycache__", r"__pycache__/?", "Add __pycache__ to .gitignore for Python bytecode folders."),
            (".env", r"(^|\n)\.env(\n|$)", "Add .env to .gitignore to reduce accidental secret commits."),
            ("virtual environments", r"(^|\n)(\.venv|venv)/?(\n|$)", "Add .venv or venv to .gitignore for local Python environments."),
            ("*.pyc", r"\*\.pyc", "Add *.pyc to .gitignore for Python bytecode files."),
        ]
        for label, pattern, recommendation in ignore_checks:
            passed = bool(re.search(pattern, gitignore_text))
            findings.append(
                FindingDraft(
                    category="github",
                    severity="passed" if passed else "warning",
                    title=f".gitignore excludes {label}" if passed else f".gitignore does not exclude {label}",
                    description=f".gitignore includes a pattern for {label}." if passed else f".gitignore does not appear to include a pattern for {label}.",
                    recommendation="Good. This reduces repository noise and accidental commits." if passed else recommendation,
                    file_path=gitignore_path,
                )
            )
    return findings


def dependency_findings(root: Path, path_set: set[str]) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    package_path = find_named_path(path_set, "package.json")
    package_data = load_json_file(root, package_path)

    if package_path:
        scripts = package_data.get("scripts", {}) if isinstance(package_data, dict) else {}
        findings.append(
            FindingDraft(
                category="dependencies",
                severity="passed" if scripts else "warning",
                title="package.json scripts detected" if scripts else "package.json has no scripts",
                description="package.json includes executable scripts." if scripts else "No scripts block was found in package.json.",
                recommendation="Good. Scripts make builds and tests discoverable." if scripts else "Add scripts such as dev, build, and test.",
                file_path=package_path,
            )
        )
        has_lock = any(path in path_set for path in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"})
        findings.append(
            FindingDraft(
                category="dependencies",
                severity="passed" if has_lock else "warning",
                title="JavaScript lockfile exists" if has_lock else "JavaScript lockfile is missing",
                description="A package manager lockfile was found." if has_lock else "No npm, pnpm, or yarn lockfile was detected.",
                recommendation="Good. Lockfiles improve reproducible installs." if has_lock else "Commit a lockfile to make installs deterministic.",
            )
        )
        broad_versions = broad_dependency_versions(package_data)
        for dep_name, version in broad_versions[:10]:
            findings.append(
                FindingDraft(
                    category="dependencies",
                    severity="info",
                    title="Broad dependency version detected",
                    description=f"{dep_name} uses a broad version constraint: {version}",
                    recommendation="Pin dependency versions where reproducibility matters.",
                    file_path=package_path,
                )
            )

    if "requirements.txt" in path_set:
        text = read_text_safely(root / "requirements.txt") or ""
        unpinned = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#") and "==" not in line and not line.startswith("-")
        ]
        findings.append(
            FindingDraft(
                category="dependencies",
                severity="passed" if not unpinned else "info",
                title="Python dependencies are pinned" if not unpinned else "Some Python dependencies are not pinned",
                description="requirements.txt dependencies use exact pins." if not unpinned else "Some requirements do not use exact == pins.",
                recommendation="Good. Exact pins improve reproducibility." if not unpinned else "Pin dependency versions for production deployments.",
                file_path="requirements.txt",
            )
        )

    if not findings:
        findings.append(
            FindingDraft(
                category="dependencies",
                severity="info",
                title="Dependency manifests not checked",
                description="No package.json or requirements.txt file was found.",
                recommendation="Add dependency manifests for supported ecosystems when applicable.",
            )
        )
    return findings


def structure_findings(root: Path, path_set: set[str], files: list[FileRecord]) -> list[FindingDraft]:
    skipped_binary = sum(1 for record in files if not record.is_text)
    top_level_dirs = {Path(path).parts[0] for path in path_set if len(Path(path).parts) > 1}
    source_dirs = {"src", "app", "backend", "frontend", "tests"} & {directory.lower() for directory in top_level_dirs}
    dependency_files = [
        path
        for path in path_set
        if Path(path).name in {"package.json", "requirements.txt", "pyproject.toml", "pom.xml", "build.gradle", "build.gradle.kts"}
    ]
    generated_dirs = sorted(
        {
            path.name
            for path in root.rglob("*")
            if path.is_dir() and path.name in {"node_modules", "dist", "build", ".pytest_cache", "__pycache__", "coverage"}
        }
    )
    findings = [
        FindingDraft(
            category="structure",
            severity="info",
            title="File inventory completed",
            description=f"Indexed {len(files)} files for high-level analysis.",
            recommendation="Review skipped files if the project relies on generated or binary assets.",
        )
    ]
    findings.append(
        FindingDraft(
            category="structure",
            severity="passed" if source_dirs else "info",
            title="Clear project folders detected" if source_dirs else "Clear project folders not checked",
            description=f"Detected project folders: {', '.join(sorted(source_dirs))}." if source_dirs else "No conventional top-level source, app, backend, frontend, or tests folder was found.",
            recommendation="Good. Clear folders improve maintainability." if source_dirs else "Use conventional folders such as src, app, backend, frontend, or tests as the project grows.",
        )
    )
    findings.append(
        FindingDraft(
            category="structure",
            severity="passed" if dependency_files else "info",
            title="Dependency files detected" if dependency_files else "Dependency files not checked",
            description=f"Detected dependency files: {', '.join(dependency_files[:6])}." if dependency_files else "No supported dependency manifest was found.",
            recommendation="Good. Dependency manifests make setup and review easier." if dependency_files else "Add dependency manifests for the project ecosystem when applicable.",
        )
    )
    if generated_dirs:
        findings.append(
            FindingDraft(
                category="structure",
                severity="warning",
                title="Generated folders included in archive",
                description=f"Generated folders were present in the upload: {', '.join(generated_dirs[:8])}.",
                recommendation="Exclude generated folders such as node_modules, dist, build, caches, and coverage from project archives.",
            )
        )
    if skipped_binary:
        findings.append(
            FindingDraft(
                category="structure",
                severity="info",
                title="Binary files skipped",
                description=f"Skipped {skipped_binary} binary or unsupported files from content scanning.",
                recommendation="This MVP intentionally avoids deep binary scanning.",
            )
        )
    if "src" in {Path(path).parts[0] for path in path_set} or "app" in {Path(path).parts[0] for path in path_set}:
        findings.append(
            FindingDraft(
                category="structure",
                severity="passed",
                title="Source directory detected",
                description="A conventional src or app directory was found.",
                recommendation="Good. Keep source files organized by feature or module.",
            )
        )
    return findings


def finalize_findings(findings: list[FindingDraft]) -> list[FindingDraft]:
    finalized = [
        replace(
            finding,
            priority=finding.priority or priority_for(finding),
            why_it_matters=finding.why_it_matters or why_it_matters_for(finding),
        )
        for finding in findings
    ]
    return sorted(finalized, key=finding_sort_key)


def priority_for(finding: FindingDraft) -> str:
    title = finding.title.lower()
    if finding.severity == "critical":
        return "P0"
    if finding.category == "security" and finding.severity == "warning":
        return "P1"
    if finding.category == "docker" and finding.severity == "warning":
        return "P1"
    if finding.category == "testing" and finding.severity == "warning":
        return "P2"
    if "readme" in title and finding.severity == "warning":
        return "P2"
    if finding.severity == "warning":
        return "P2"
    if finding.severity == "info":
        return "P3"
    return "P3"


def why_it_matters_for(finding: FindingDraft) -> str:
    if finding.category == "security":
        return "Security hygiene issues can expose credentials, weaken deployment safety, or require emergency secret rotation."
    if finding.category == "documentation":
        return "Documentation quality affects whether reviewers and operators can install, run, test, and evaluate the project."
    if finding.category == "testing":
        return "Testing signals show whether changes can be validated reliably before release."
    if finding.category == "docker":
        return "Docker and deployment checks affect reproducibility, runtime safety, and production readiness."
    if finding.category == "github":
        return "GitHub readiness affects repository professionalism, collaboration, and CI visibility."
    if finding.category == "dependencies":
        return "Dependency metadata affects reproducible installs and maintainability."
    if finding.category == "structure":
        return "Project structure affects reviewability, onboarding, and long-term maintenance."
    return "This finding affects the project audit score and readiness assessment."


def finding_sort_key(finding: FindingDraft) -> tuple[int, int, str]:
    priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(finding.priority or "P3", 3)
    severity_rank = {"critical": 0, "warning": 1, "info": 2, "passed": 3}.get(finding.severity, 4)
    return priority_rank, severity_rank, finding.title


def calculate_scores(
    findings: list[FindingDraft], path_set: set[str], technologies: list[TechnologyDraft], project_type: str
) -> tuple[dict[str, int], dict[str, dict[str, list[str] | str]]]:
    categories = {
        "security": "security_score",
        "documentation": "documentation_score",
        "testing": "testing_score",
        "docker": "docker_score",
        "github": "github_score",
        "dependencies": "maintainability_score",
        "structure": "maintainability_score",
    }
    scores = {
        "security_score": 100,
        "documentation_score": 100,
        "testing_score": 100,
        "docker_score": 100,
        "github_score": 100,
        "deployment_score": 100,
        "maintainability_score": 100,
    }
    deductions: dict[str, list[str]] = {key: [] for key in scores}
    positives: dict[str, list[str]] = {key: [] for key in scores}

    penalties = {"critical": 20, "warning": 8, "info": 0, "passed": 0}
    for finding in findings:
        score_key = categories.get(finding.category)
        if not score_key:
            continue
        penalty = penalties[finding.severity]
        if penalty:
            scores[score_key] -= penalty
            deductions[score_key].append(f"-{penalty}: {finding.title}")
        elif finding.severity == "passed":
            positives[score_key].append(finding.title)

        if finding.category in {"docker", "dependencies"} and finding.severity == "warning":
            scores["deployment_score"] -= 6
            deductions["deployment_score"].append(f"-6: {finding.title}")
        if finding.category in {"testing", "structure"} and finding.severity == "warning":
            scores["maintainability_score"] -= 5
            deductions["maintainability_score"].append(f"-5: {finding.title}")
        if finding.category == "security" and finding.severity == "critical":
            scores["deployment_score"] -= 10
            deductions["deployment_score"].append(f"-10: {finding.title}")

    names = {tech.name for tech in technologies}
    if "Docker" in names:
        scores["deployment_score"] += 5
        positives["deployment_score"].append("+5: Dockerfile detected")
    if "Docker Compose" in names:
        scores["deployment_score"] += 5
        positives["deployment_score"].append("+5: Docker Compose detected")
    if any(path.startswith(".github/workflows/") for path in path_set):
        scores["github_score"] += 5
        positives["github_score"].append("+5: CI workflow detected")
    if project_type == "Full-stack web app" and "Docker Compose" not in names:
        scores["deployment_score"] -= 8
        deductions["deployment_score"].append("-8: Full-stack project without Docker Compose")

    for key in scores:
        scores[key] = clamp(scores[key])

    component_keys = [
        "security_score",
        "documentation_score",
        "testing_score",
        "docker_score",
        "github_score",
        "deployment_score",
        "maintainability_score",
    ]
    scores["overall_score"] = clamp(round(sum(scores[key] for key in component_keys) / len(component_keys)))

    explanations = {
        "security": explanation_for("Security", scores["security_score"], positives["security_score"], deductions["security_score"], "Move secrets to environment variables, rotate exposed credentials, and keep sensitive files out of the repository."),
        "documentation": explanation_for("Documentation", scores["documentation_score"], positives["documentation_score"], deductions["documentation_score"], "Add missing README sections for setup, testing, API, Docker, screenshots, and stack details."),
        "testing": explanation_for("Testing", scores["testing_score"], positives["testing_score"], deductions["testing_score"], "Add or document backend and frontend tests, then expose repeatable test commands."),
        "docker": explanation_for("Docker", scores["docker_score"], positives["docker_score"], deductions["docker_score"], "Add Dockerfile, Compose, .dockerignore, healthchecks, and production-oriented container commands."),
        "github": explanation_for("GitHub readiness", scores["github_score"], positives["github_score"], deductions["github_score"], "Improve repository readiness with .gitignore coverage, license, screenshots, and CI workflow."),
        "deployment": explanation_for("Deployment readiness", scores["deployment_score"], positives["deployment_score"], deductions["deployment_score"], "Close deployment gaps around containers, service definitions, secrets, and runtime health checks."),
        "maintainability": explanation_for("Maintainability", scores["maintainability_score"], positives["maintainability_score"], deductions["maintainability_score"], "Keep source folders clear, generated files out of archives, and dependency manifests reproducible."),
    }
    overall_deductions = [
        f"{key.replace('_score', '').replace('_', ' ').title()}: {item}"
        for key in component_keys
        for item in deductions[key][:2]
    ]
    overall_positives = [
        f"{key.replace('_score', '').replace('_', ' ').title()}: {item}"
        for key in component_keys
        for item in positives[key][:2]
    ]
    explanations["overall"] = {
        "status": score_status(scores["overall_score"]),
        "explanation": "Overall score is the average of security, documentation, testing, Docker, GitHub, deployment, and maintainability scores.",
        "positives": overall_positives[:6],
        "deductions": overall_deductions[:6],
        "recommendation": "Start with P0/P1 findings, then address warnings in the lowest scoring categories.",
    }
    return scores, explanations


def load_package_json(root: Path) -> dict:
    return load_json_file(root, "package.json")


def load_json_file(root: Path, file_path: str | None) -> dict:
    if not file_path:
        return {}
    path = root / file_path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def package_dependencies(package_data: dict) -> dict[str, str]:
    deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = package_data.get(key, {})
        if isinstance(value, dict):
            deps.update({str(name).lower(): str(version) for name, version in value.items()})
    return deps


def broad_dependency_versions(package_data: dict) -> list[tuple[str, str]]:
    broad: list[tuple[str, str]] = []
    for name, version in package_dependencies(package_data).items():
        if version in {"*", "latest"} or version.startswith((">", ">=", "x", "X")):
            broad.append((name, version))
    return broad


def read_selected_text(root: Path, candidates: list[str]) -> str:
    chunks: list[str] = []
    for candidate in candidates:
        path = root / candidate
        if path.exists() and path.is_file():
            text = read_text_safely(path)
            if text:
                chunks.append(text[:20_000])
    return "\n".join(chunks)


def first_matching_text_file(root: Path, candidates: list[str], pattern: str) -> str | None:
    regex = re.compile(pattern)
    for candidate in candidates:
        path = root / candidate
        if path.exists() and path.is_file():
            text = read_text_safely(path) or ""
            if regex.search(text):
                return candidate
    return candidates[0] if candidates else None


def find_named_path(paths: set[str], name: str) -> str | None:
    target = name.lower()
    return next((path for path in sorted(paths) if Path(path).name.lower() == target), None)


def find_name_startswith(paths: set[str], prefix: str) -> str | None:
    target = prefix.lower()
    return next((path for path in sorted(paths) if Path(path).name.lower().startswith(target)), None)


def find_by_suffix(paths: set[str], suffixes: tuple[str, ...]) -> str | None:
    return next((path for path in sorted(paths) if path.lower().endswith(suffixes)), None)


def find_first_present(paths: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in paths:
            return candidate
    candidate_names = {candidate.lower() for candidate in candidates}
    return next((path for path in sorted(paths) if Path(path).name.lower() in candidate_names), None)


def confidence_rank(confidence: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(confidence, 0)


def read_text_safely(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def should_skip_secret_line(line: str) -> bool:
    lowered = line.lower()
    if any(token in lowered for token in SECRET_EXAMPLE_MARKERS):
        return True
    if SECRET_TEST_MARKER_PATTERN.search(line) and not SECRET_REAL_CONTEXT_PATTERN.search(line):
        return not any(pattern.search(line) for _, pattern in SECRET_PATTERNS)
    return False


def find_case_insensitive(paths: set[str], target: str) -> str | None:
    target_lower = target.lower()
    return next((path for path in paths if Path(path).name.lower() == target_lower), None)


def explanation_for(label: str, score: int, positives: list[str], deductions: list[str], recommendation: str) -> dict[str, list[str] | str]:
    if deductions:
        cleaned = [deduction.split(": ", 1)[-1] for deduction in deductions[:3]]
        explanation = f"{label} score was reduced because {', '.join(cleaned)}."
    else:
        explanation = f"{label} score started at 100 and no scoring penalties were applied."
    return {
        "status": score_status(score),
        "explanation": explanation,
        "positives": positives[:5],
        "deductions": deductions[:5],
        "recommendation": recommendation,
    }


def score_status(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Needs work"
    if score >= 40:
        return "Risky"
    return "Critical"


def clamp(value: int) -> int:
    return max(0, min(100, value))
