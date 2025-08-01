#!/usr/bin/env python
"""
Module for collecting host-related data from vCenter.
"""
from pyVmomi import vim


class HostCollector:
    """
    Class to collect host data from vCenter.
    """
    
    def __init__(self, content, container):
        """
        Initialize the host collector.
        
        Args:
            content: vCenter service instance content
            container: vCenter service instance container
        """
        self.content = content
        self.container = container
    
    def get_host_properties(self):
        """
        Extract host properties from the service instance.
        
        Returns:
            list: List of dictionaries with host properties
        """
        host_properties_list = []
        host_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.HostSystem], True
        )
        
        try:
            for host in host_view.view:
                model = host.hardware.systemInfo.model if hasattr(host, "hardware") and hasattr(host.hardware, "systemInfo") else ""
                if model != "VMware Mobility Platform":
                    host_properties = {
                        "Host": host.name if hasattr(host, "name") else "",
                        "# CPU": str(host.hardware.cpuInfo.numCpuPackages) if hasattr(host, "hardware") and hasattr(host.hardware, "cpuInfo") else "",
                        "# Cores": str(host.hardware.cpuInfo.numCpuCores) if hasattr(host, "hardware") and hasattr(host.hardware, "cpuInfo") else "",
                        "# Memory": str(host.hardware.memorySize // (1024 * 1024)) if hasattr(host, "hardware") and hasattr(host.hardware, "memorySize") else "",
                        "# NICs": str(len(host.config.network.pnic)) if hasattr(host, "config") and hasattr(host.config, "network") else "",
                        "Vendor": host.hardware.systemInfo.vendor if hasattr(host, "hardware") and hasattr(host.hardware, "systemInfo") else "",
                        "Model": model,
                        "Object ID": str(host._moId) if hasattr(host, "_moId") else "",
                        "UUID": host.hardware.systemInfo.uuid if hasattr(host, "hardware") and hasattr(host.hardware, "systemInfo") else "",
                        "VI SDK UUID": self.content.about.instanceUuid if hasattr(self.content, "about") and hasattr(self.content.about, "instanceUuid") else ""
                    }
                    host_properties_list.append(host_properties)
        finally:
            if host_view:
                host_view.Destroy()
        
        return host_properties_list
    
    def get_host_nic_properties(self):
        """
        Extract NIC properties from hosts.
        
        Returns:
            list: List of dictionaries with host NIC properties
        """
        nic_properties_list = []
        host_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.HostSystem], True
        )
        
        try:
            for host in host_view.view:
                if hasattr(host, "config") and hasattr(host.config, "network") and hasattr(host.config.network, "pnic"):
                    for pnic in host.config.network.pnic:
                        nic_properties = {
                            "Host": host.name if hasattr(host, "name") else "",
                            "Network Device": pnic.device if hasattr(pnic, "device") else "",
                            "MAC": pnic.mac if hasattr(pnic, "mac") else "",
                            "Switch": ""
                        }
                        
                        # Try to get switch information
                        if hasattr(host.config.network, "vswitch"):
                            for vswitch in host.config.network.vswitch:
                                if hasattr(vswitch, "pnic") and pnic.key in vswitch.pnic:
                                    nic_properties["Switch"] = vswitch.name
                                    break
                        
                        nic_properties_list.append(nic_properties)
        finally:
            if host_view:
                host_view.Destroy()
        
        return nic_properties_list
    
    def get_host_vmk_properties(self):
        """
        Extract VMkernel properties from hosts.
        
        Returns:
            list: List of dictionaries with host VMkernel properties
        """
        vmk_properties_list = []
        
        host_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.HostSystem], True
        )
        
        try:
            for host in host_view.view:
                if hasattr(host, "config") and hasattr(host.config, "network") and hasattr(host.config.network, "vnic"):
                    for vnic in host.config.network.vnic:
                        vmk_properties = {
                            "Host": host.name if hasattr(host, "name") else "",
                            "Mac Address": vnic.spec.mac if hasattr(vnic, "spec") and hasattr(vnic.spec, "mac") else "",
                            "IP Address": vnic.spec.ip.ipAddress if (hasattr(vnic, "spec") and 
                                                                hasattr(vnic.spec, "ip") and 
                                                                hasattr(vnic.spec.ip, "ipAddress") and 
                                                                vnic.spec.ip.ipAddress is not None) else "",
                            "IP 6 Address": "",
                            "Subnet mask": vnic.spec.ip.subnetMask if (hasattr(vnic, "spec") and 
                                                                    hasattr(vnic.spec, "ip") and 
                                                                    hasattr(vnic.spec.ip, "subnetMask") and 
                                                                    vnic.spec.ip.subnetMask is not None) else ""
                        }
                        
                        # Try to get IPv6 address
                        if (hasattr(vnic.spec, "ip") and 
                            hasattr(vnic.spec.ip, "ipV6Config") and 
                            hasattr(vnic.spec.ip.ipV6Config, "ipV6Address") and 
                            vnic.spec.ip.ipV6Config.ipV6Address):
                            vmk_properties["IP 6 Address"] = vnic.spec.ip.ipV6Config.ipV6Address[0].ipAddress
                        
                        vmk_properties_list.append(vmk_properties)
        finally:
            if host_view:
                host_view.Destroy()
        
        return vmk_properties_list