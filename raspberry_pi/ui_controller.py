import logging
from .ui_state import UIState
from .display_controller import DisplayController, DisplayWorker

LOG = logging.getLogger("inklite.pi")


class UIController:
    def __init__(self, config, worker=None):
        self.config = config
        self.state = UIState(config.pages, config.timer_minutes)
        self.worker = worker or DisplayWorker(DisplayController(config))

    def start(self):
        self.worker.start()
        LOG.info("[UI] %s", self.state.snapshot().page.title())
        self.worker.submit(self.state.snapshot())

    def on_command(self, command):
        previous = self.state.snapshot()
        snapshot = self.state.apply(command)
        if command.value == "TAP":
            LOG.info("[UI] %s %s", "Confirm" if previous.entered else "Enter", snapshot.page.title())
        LOG.info("[UI] Current Page: %s / %s", snapshot.page.title(), "Entered" if snapshot.entered else "Browse")
        self.worker.submit(snapshot)

    def tick(self):
        snapshot = self.state.tick()
        if snapshot is not None:
            self.worker.submit(snapshot)

    def close(self):
        self.worker.close()
