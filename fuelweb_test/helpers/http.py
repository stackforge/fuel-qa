from __future__ import absolute_import

from traceback import print_stack
from warnings import warn

from fuelweb_test import logger

from core.helpers.http import HTTPClientZabbix

msg = (
    'fuelweb_test.helpers.http is deprecated and will be dropped '
    'on 14.09.2016. Please use core.models.collector_client instead'
)
warn(msg)
print_stack()
logger.critical(msg)

__all__ = ['HTTPClientZabbix']
