# This file is used by Gunicorn to find and run your application.
# It imports the 'app' instance from your main application file (app.py).

from app import app as application

if __name__ == '__main__':
    application.run()