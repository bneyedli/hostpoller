"""
Interface to signal for handling common signals
"""
import logging
from signal import SIGHUP, SIGINT, SIGQUIT, SIGTERM, signal


class Trapper:  # pylint: disable=too-few-public-methods
    """
    Catch given kill signals and run handler
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.signal = signal
        self.signal(SIGINT, self.trap_handler)
        self.signal(SIGQUIT, self.trap_handler)
        self.signal(SIGTERM, self.trap_handler)
        self.signal(SIGHUP, self.trap_handler)

    def trap_handler(self, signal_code: int, frame: object) -> None:
        """
        Function to trap kill signals and cleanup on exit
        """
        if signal_code == 2:
            print()
            self.logger.info("Signal interrupt caught")
        else:
            self.logger.info("Unhandled signal: %s caught", signal_code)
            self.logger.info("Frame: %s", frame)

        raise SystemExit
