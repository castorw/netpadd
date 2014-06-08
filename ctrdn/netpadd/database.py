import logging
import sqlalchemy
from ConfigParser import NoOptionError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.session import sessionmaker

DeclarativeBase = declarative_base()

__author__ = 'Lubomir Kaplan <castor@castor.sk>'


class DatabaseException(Exception):
    pass


class NetPadDatabase():
    _db_handle = None
    _logger = logging.getLogger("database")

    def __init__(self, config):
        config = config

        try:
            driver = config.get("database", "driver")
            if driver == "sqlite":
                sqlalchemy_string = "sqlite:///"
                sqlite_file = config.get("database", "sqlite-file")
                sqlalchemy_string += sqlite_file
            elif driver == "mysql":
                sqlalchemy_string = "mysql://"
                mysql_host = config.get("database", "mysql-host")
                mysql_port = config.getint("database", "mysql-port")
                mysql_user = config.get("database", "mysql-user")
                mysql_pass = config.get("database", "mysql-password")
                mysql_schema = config.get("database", "mysql-schema")

                sqlalchemy_string += mysql_user + ":" + mysql_pass + "@" + mysql_host + \
                                                  ":" + str(mysql_port) + "/" + mysql_schema
            else:
                raise DatabaseException("Unknown database driver " + driver)
        except NoOptionError as ex:
            raise DatabaseException("Invalid configuration: " + ex.message)

        self._db_handle = sqlalchemy.create_engine(sqlalchemy_string)
        try:
            db_debug = config.getboolean("database", "database-debug")
            if db_debug is True:
                self._logger.debug("database debugging is enabled")
                self._db_handle.echo = True
        except NoOptionError:
            self._logger.debug("database debugging is disabled")
            self._db_handle.echo = False
        if driver == "sqlite":
            self._logger.info("opened sqlite database from file %s", sqlite_file)
        elif driver == "mysql":
            self._logger.info("connected to mysql database at %s:%d", mysql_host, mysql_port)

        self._initialize_tables()

    def _initialize_tables(self):
        DeclarativeBase.metadata.create_all(bind=self._db_handle, checkfirst=True)

    def get_session_maker(self):
        return sessionmaker(bind=self._db_handle, autocommit=False)
