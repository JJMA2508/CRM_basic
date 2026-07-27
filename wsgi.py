import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

application = create_app()
app = application

if __name__ == '__main__':
    application.run(
        host=application.config.get('HOST', '0.0.0.0'),
        port=application.config.get('PORT', 5000),
        debug=application.config.get('DEBUG', False)
    )
