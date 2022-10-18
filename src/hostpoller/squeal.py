"""
Interface to SQLAlchemy for creating tables, inserting records and running queries
"""
import logging
from typing import List

from sqlalchemy import MetaData, Table, create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import Insert


class Squeal:
    """
    Main interface to SQLAlchemy to initialize the engine
    """

    def __init__(self, engine_meta: dict) -> None:
        self.logger = logging.getLogger(__name__)

        if engine_meta["type"] == "sqlite":
            self.sqlite_filepath = engine_meta["file_path"]
            self.engine = create_engine(f"sqlite:///{self.sqlite_filepath}")

        self.session = Session(self.engine, future=True)
        self.meta_data = MetaData(bind=self.engine)
        MetaData.reflect(self.meta_data)
        self.inspector = inspect(self.engine)

    def insert(self, table: Table, record: dict) -> bool:
        """
        Function to manage inserting records
        """
        statement = Insert(table, values=record)
        self.logger.debug("Executing: %s", statement)

        self.engine.execute(statement)
        self.logger.debug("Executed")
        return True

    def select_all(self, table: Table) -> List:
        """
        Select all reccords from all columns for a given table
        """
        results = []
        for result in self.session.query(table):
            results.append(result)

        return results

    def describe_table(self, table: Table) -> None:
        """
        Describe given table
        """
        print(table)
