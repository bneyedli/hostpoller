"""
Interface to argparse
"""
import argparse


class ParseArgs:  # pylint: disable=too-few-public-methods
    """
    Ingest list of dicts to construct command line switches and parse runtime directives
    """

    def __init__(self, name: str, description: str, argument_map: list) -> None:
        self.name = name
        self.description = description
        self.argument_map = argument_map
        self.parse_args()

    def parse_args(self) -> None:
        """Parse args and return collection"""
        self.parser = argparse.ArgumentParser(description=self.description)
        for argument in self.argument_map:
            self.parser.add_argument(
                argument["switch"],
                type=argument["type"],
                default=argument["default"],
                help=argument["help"],
            )
        self.args_parsed = self.parser.parse_args()
