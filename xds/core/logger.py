from loguru import logger
import sys


class Logger:
    def __init__(self):
        self.configure_logger()

    def configure_logger(self):
        logger.remove()
        logger.add(
            sys.stderr,
            level='INFO',
            format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}',
        )
        logger.add(
            'logs/xds.log',
            level='DEBUG',
            format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}',
        )

    def info(self, message: str) -> None:
        logger.info(message)

    def debug(self, message: str) -> None:
        logger.debug(message)

    def error(self, message: str) -> None:
        logger.error(message)


log = Logger()
