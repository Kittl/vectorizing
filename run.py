import argparse
import subprocess

actions = [
    'build',
    'start',
    'test',
    'test-custom'
]

commands = {
    # action
    # or
    # [action, build]
    'build': 'docker-compose build',
    ('start', True): 'docker-compose up --build',
    ('start', False): 'docker-compose up',
    ('test', True): 'docker compose run --build test',
    ('test', False): 'docker-compose run test',
    ('test-custom', True): 'docker-compose run --build test-custom',
    ('test-custom', False): 'docker-compose run test-custom'
}

parser = argparse.ArgumentParser()

parser.add_argument(
    'action', 
    type = str, 
    choices = 
    actions, 
    default = None, 
    help = 'Action to perform', 
    metavar = 'ACTION'
)

parser.add_argument(
    '--nobuild', 
    action = 'store_true', 
    default = False, 
    help = 'Do not build the image before starting the container'
)

args = parser.parse_args()
action = args.action
nobuild = args.nobuild
command = commands.get(action if action == 'build' else (action, not nobuild))
subprocess.run([command], shell = True)
