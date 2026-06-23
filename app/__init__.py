from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config.from_prefixed_env("SWIMCHI")

    from .models import get_db, init_db
    conn = get_db()
    init_db(conn)
    conn.close()

    from . import routes
    app.register_blueprint(routes.bp)

    return app
