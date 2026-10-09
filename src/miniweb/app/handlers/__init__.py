"""Import all handler modules so their @on() decorators run at import time."""
from . import banking_handler  # noqa
from . import email_handler  # noqa
from . import calendar_handler  # noqa
from . import im_handler  # noqa
from . import cloud_storage_handler  # noqa
from . import password_handler  # noqa
