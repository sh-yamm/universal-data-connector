import logging


def configure_logging():
    # Simple stdout logging: timestamp + level + message
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
