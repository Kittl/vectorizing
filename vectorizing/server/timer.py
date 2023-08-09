import time

class Timer:
    def __init__(self):
        self.entries = {}
        self.actions_stack = []
        self.time_stack = []

    def start_timer(self, action_name):
        self.time_stack.append(time.time())
        self.actions_stack.append(action_name)
    
    def end_timer(self):
        self.entries[self.actions_stack.pop()] = time.time() - self.time_stack.pop()

    def timelog(self):
        log = ''

        for action_name in self.entries:
            time = self.entries[action_name]
            log += f'{action_name}: {time} / '
        
        return log