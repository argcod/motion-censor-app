import logging
from utils.paths import ensure_dir, log_path, path_str


def setup_logger():
    # Keep log files under the project root, not the process cwd
    ensure_dir(log_path())

    logger = logging.getLogger("SmartSecure")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        file_handler = logging.FileHandler(path_str(log_path("application.log")))
        file_handler.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()
