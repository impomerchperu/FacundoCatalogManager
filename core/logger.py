import logging

from config.settings import LOG_PATH


def setup_logger():

    LOG_PATH.parent.mkdir(exist_ok=True)

    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    return logging.getLogger("FCM")
