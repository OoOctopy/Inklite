from enum import Enum
import logging

LOG = logging.getLogger("inklite.pi")


class Command(str, Enum):
    TAP = "TAP"
    CW = "CW"
    CCW = "CCW"


def parse_command(payload):
    if not isinstance(payload, (bytes, bytearray)) or not 2 <= len(payload) <= 3:
        raise ValueError("Expected one 2–3 byte command")
    try:
        return Command(bytes(payload).decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as error:
        raise ValueError("Expected exactly TAP, CW or CCW in UTF-8") from error


class CommandHandler:
    def __init__(self, on_command=None):
        self.on_command = on_command

    def receive(self, payload):
        command = parse_command(payload)
        LOG.info("[BLE] Received: %s", command.value)
        self.handle(command)
        return command

    def handle(self, command):
        if not isinstance(command, Command):
            raise ValueError("CommandHandler requires a parsed Command")
        action = {Command.TAP: "Confirm / Enter", Command.CW: "Next", Command.CCW: "Back"}[command]
        LOG.info("[COMMAND] %s", action)
        if self.on_command is not None:
            self.on_command(command)
        return action
