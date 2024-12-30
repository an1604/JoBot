from dataclasses import dataclass


@dataclass
class User:
    def __init__(self, user_id, user_name):
        self.current_answer = None
        self.llm = None
        self.attack = None
        self.attack_type = None
        self.user_id = user_id
        self.user_name = user_name
        self.is_in_attack = False
        self.transcript = None

        self.tries_counter = 0  # This counter is for handling attack initialization problems in the chat itself.
        # It keeps track the tries of the user to generate new attack without any success
        # if some error occurs on the server side and session restart needed.

    def is_restart_session(self):
        self.tries_counter += 1
        if self.tries_counter >= 3:
            self.tries_counter = 0
            return True
        return False
