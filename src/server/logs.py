from logging.config import dictConfig

def setup_logs():
    # Set up Flask logging to STDOUT
    dictConfig({
        'version': 1,
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })