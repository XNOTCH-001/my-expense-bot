# This file is used by Gunicorn to find and run your application.
# It imports the 'app' instance from your main application file.

# We need to import the Flask app instance from your main file.
# Since your main file is named 'add.py', we import 'app' from 'add'.
from add import app as application

# The code below is not needed for Gunicorn, but it's good practice
# for local testing. We will keep it here.
if __name__ == '__main__':
    application.run()