# This script is useful if you need to manually explore the VMware API model
# You can execute this code in a Python terminal, then access object properties

import vcexport
import csv
import os
import zipfile
import re
from datetime import datetime
import atexit
import ssl
import sys

from pyVim import connect
from pyVmomi import vim

vcenter_host = os.environ.get("EXP_VCENTER_HOST")
vcenter_user = os.environ.get("EXP_VCENTER_USER")
vcenter_password = os.environ.get("EXP_VCENTER_PASSWORD")
disable_ssl_verification = os.environ.get("EXP_DISABLE_SSL_VERIFICATION", "false").lower() == "true"

si = vcexport.connect_to_vcenter(
    host=vcenter_host,
    user=vcenter_user,
    password=vcenter_password,
    disable_ssl_verification=disable_ssl_verification
)

dvport_properties_list = []

content = si.RetrieveContent()
container = content.rootFolder

# Get all distributed virtual switches
dvs_view = content.viewManager.CreateContainerView(container, [vim.DistributedVirtualSwitch], True)