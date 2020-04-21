import logging
import os
from datetime import datetime

from flask_script import Manager
from peewee import SqliteDatabase
from dotenv import load_dotenv

from app import create_app
from migrations import init_db

# Import environment file variables
from seeds import init_seed

load_dotenv()

# Log configuration
log_dirname = 'logs/'
log_filename = '{}.log'.format(datetime.utcnow().strftime('%Y%m%d'))
log_fullpath = '{}{}'.format(log_dirname, log_filename)

if not os.path.exists(log_dirname):
    os.mkdir(log_dirname)

FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(filename=log_fullpath, format=FORMAT, level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Database
dbname = '%s.db' % os.getenv('DATABASE_NAME', 'prod.db')
database = SqliteDatabase(dbname)

# App
app = create_app(os.getenv('FLASK_CONFIG', 'config.DevConfig'))
manager = Manager(app)


# This hook ensures that a connection is opened to handle any queries
# generated by the request.
@app.before_request
def _db_connect():
    database.connect(reuse_if_open=True)


# This hook ensures that the connection is closed when we've finished
# processing the request.
@app.teardown_request
def _db_close(exc):
    if not database.is_closed():
        database.close()


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    response.headers.add('Cache-Control', 'no-cache')
    return response


@manager.command
def migrate():
    init_db()


@manager.command
def seed():
    init_seed()


if __name__ == '__main__':
    manager.run()
