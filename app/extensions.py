from flask import Flask
from flask_mail import Mail
from flask_marshmallow import Marshmallow
from flask_security import Security
from flask_swagger_ui import get_swaggerui_blueprint
from playhouse.flask_utils import FlaskDB

from app.celery import MyCelery

db_wrapper = FlaskDB()
security = Security()
mail = Mail()
celery = MyCelery()
ma = Marshmallow()


def init_app(app: Flask) -> None:
    from app.models.user import user_datastore

    db_wrapper.init_app(app)
    security.init_app(app, datastore=user_datastore, register_blueprint=False)
    mail.init_app(app)
    ma.init_app(app)

    swagger_blueprint = get_swaggerui_blueprint(
        app.config.get('SWAGGER_URL'),  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
        app.config.get('SWAGGER_API_URL'),
        config={  # Swagger UI config overrides
            'app_name': 'Flask-api application'
        },
        # oauth_config={  # OAuth config. See https://github.com/swagger-api/swagger-ui#oauth2-configuration .
        #    'clientId': "your-client-id",
        #    'clientSecret': "your-client-secret-if-required",
        #    'realm': "your-realms",
        #    'appName': "your-app-name",
        #    'scopeSeparator': " ",
        #    'additionalQueryStringParams': {'test': "hello"}
        # }
    )

    app.register_blueprint(swagger_blueprint, url_prefix=app.config.get('SWAGGER_URL'))

    # This hook ensures that a connection is opened to handle any queries
    # generated by the request.
    @app.before_request
    def db_connect() -> None:
        db_wrapper.database.connect(reuse_if_open=True)

    # This hook ensures that the connection is closed when we've finished
    # processing the request.
    @app.teardown_request
    def db_close(exc) -> None:
        if not db_wrapper.database.is_closed():
            db_wrapper.database.close()
