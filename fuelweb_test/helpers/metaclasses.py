#    Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from warnings import warn

warn(
    'fuelweb_test.helpers.metaclasses.SingletonMeta is deprected:'
    'class is moved to devops.helpers.metaclasses.\n'
    'Due to it was single metaclass in file, this file will be deleted in'
    'short time!',
    DeprecationWarning
)


class SingletonMeta(type):
    """Metaclass for Singleton

    Main goals: not need to implement __new__ in singleton classes
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
