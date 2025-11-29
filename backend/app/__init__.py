import os
from flask import Flask
from flask_cors import CORS

from .config import Config
from .services.gemini import gemini_client
from .startup_checks import run_startup_checks


def create_app(testing: bool = False) -> Flask:
    """Application factory: configures Flask and registers blueprints."""
    if not testing:
        run_startup_checks()
    app = Flask(__name__)

    # Enable CORS for frontend
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Ensure upload directory exists and is configured
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Register blueprints with /api prefix
    from .routes.ingest import bp as ingest_bp
    from .routes.search import bp as search_bp
    from .routes.documents import bp as documents_bp
    from .routes.auth import bp as auth_bp
    app.register_blueprint(ingest_bp, url_prefix="/api")
    app.register_blueprint(search_bp, url_prefix="/api")
    app.register_blueprint(documents_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")

    # Health check endpoint
    @app.route("/api/health")
    def health():
        return {
            "status": "healthy",
            "service": "Lexivion API",
            "gemini_enabled": gemini_client.enabled,
            "model": Config.GEMINI_MODEL if gemini_client.enabled else None,
        }

    return app


# For direct imports in server.py
# Only create app if not in testing mode or CI environment
def _is_ci_environment() -> bool:
    """Detect if running in a CI environment."""
    ci_indicators = [
        "CI", "GITHUB_ACTIONS", "TRAVIS", "JENKINS_URL", 
        "GITLAB_CI", "CIRCLECI", "APPVEYOR", "TEAMCITY_VERSION"
    ]
    return any(os.getenv(indicator) for indicator in ci_indicators)

if not os.getenv("TESTING") and not _is_ci_environment():
    app = create_app()
else:
    app = None

