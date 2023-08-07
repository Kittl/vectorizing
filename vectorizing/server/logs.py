from logging.config import dictConfig

def setup_logs():
    # Set up Flask logging to STDOUT
    dictConfig({
        'version': 1,
        'formatters': 
            {
            'default': 
                {
                'format': '[%(levelname)s] %(message)s'
                }
            },
        'handlers': 
            {
            'stdout': 
                {
                'class': 'logging.StreamHandler',
                'formatter': 'default', 
                'stream': 'ext://sys.stdout'
                }
            }, 
        'loggers': 
            {
            '': 
                {                  
                'handlers': ['stdout'],    
                'level': 'INFO',    
                'propagate': True 
                }
            }
        }
    )