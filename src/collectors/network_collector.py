#!/usr/bin/env python
"""
Module for collecting network-related data from vCenter.
"""
from pyVmomi import vim


class NetworkCollector:
    """
    Class to collect network data from vCenter.
    """
    
    def __init__(self, content, container):
        """
        Initialize the network collector.
        
        Args:
            content: vCenter service instance content
            container: vCenter service instance container
        """
        self.content = content
        self.container = container
    
    def get_vm_dvport_properties(self):
        """
        Extract distributed virtual port properties.
        
        Returns:
            list: List of dictionaries with distributed virtual port properties
        """
        dvport_properties_list = []
           
        # Get all distributed virtual switches
        dvs_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.DistributedVirtualSwitch], True
        )
        
        try:
            for dvs in dvs_view.view:
                # Get all port groups in this DVS
                if hasattr(dvs, "portgroup"):
                    for pg in dvs.portgroup:
                        # Get VLAN info
                        vlan_info = self._get_vlan_info(pg)

                        # Create an entry for each port group
                        port_props = {
                            "Port": pg.key if hasattr(pg, "key") else "",
                            "Switch": dvs.name if hasattr(dvs, "name") else "",
                            "VLAN": vlan_info
                        }
                        dvport_properties_list.append(port_props)
        finally:
            if dvs_view:
                dvs_view.Destroy()
        
        return dvport_properties_list
    
    def _get_vlan_info(self, pg):
        """Extract VLAN information from a port group."""
        vlan_info = ""
        if hasattr(pg, "config") and hasattr(pg.config, "defaultPortConfig") and hasattr(pg.config.defaultPortConfig, "vlan"):
            vlan_config = pg.config.defaultPortConfig.vlan
            if hasattr(vlan_config, "vlanId"):
                # Check if vlanId is a NumericRange object
                if isinstance(vlan_config.vlanId, int):
                    vlan_info = str(vlan_config.vlanId)
                elif isinstance(vlan_config.vlanId, list) and len(vlan_config.vlanId) > 0:
                    # Handle NumericRange in a list
                    vlan_range = vlan_config.vlanId[0]
                    if hasattr(vlan_range, "start") and hasattr(vlan_range, "end"):
                        vlan_info = f"{vlan_range.start}-{vlan_range.end}"
        return vlan_info
    
    def get_vm_port_properties(self):
        """
        Extract port group properties from standard virtual switches.
        
        Returns:
            list: List of dictionaries with port group properties
        """
        port_properties_list = []
        
        # Get standard port groups from hosts
        host_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.HostSystem], True
        )
        
        try:
            for host in host_view.view:
                if hasattr(host, "config") and hasattr(host.config, "network") and hasattr(host.config.network, "portgroup"):
                    for pg in host.config.network.portgroup:
                        # Skip if this is a distributed port group
                        if hasattr(pg, "spec") and hasattr(pg.spec, "distributedVirtualSwitch"):
                            continue
                        
                        port_props = {
                            "Port Group": pg.spec.name if hasattr(pg, "spec") and hasattr(pg.spec, "name") else "",
                            "Switch": pg.spec.vswitchName if hasattr(pg, "spec") and hasattr(pg.spec, "vswitchName") else "",
                            "VLAN": str(pg.spec.vlanId) if hasattr(pg, "spec") and hasattr(pg.spec, "vlanId") else ""
                        }
                        
                        # Only add if not already in the list (avoid duplicates)
                        if port_props not in port_properties_list:
                            port_properties_list.append(port_props)
        finally:
            if host_view:
                host_view.Destroy()
        
        return port_properties_list
    
    def get_vm_dvswitch_properties(self):
        """
        Extract distributed virtual switch properties.
        
        Returns:
            list: List of dictionaries with distributed virtual switch properties
        """
        dvswitch_properties_list = []
          
        # Get all distributed virtual switches
        dvs_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.DistributedVirtualSwitch], True
        )
        
        try:
            for dvs in dvs_view.view:
                # Get datacenter info
                datacenter = self._get_datacenter_name(dvs)
                
                # Get host members
                host_members = self._get_host_members(dvs)
                
                # Get VM count
                vm_count = str(len(dvs.vm)) if hasattr(dvs, "vm") and dvs.vm else "0"
                
                # Get creation date
                created = str(dvs.config.createTime) if hasattr(dvs, "config") and hasattr(dvs.config, "createTime") else ""
                
                # Get custom attributes
                snapshot, datastore, tier = self._get_custom_attributes(dvs)
                
                dvswitch_props = self._build_dvswitch_properties(dvs, datacenter, host_members, vm_count, created, snapshot, datastore, tier)
                dvswitch_properties_list.append(dvswitch_props)
        finally:
            if dvs_view:
                dvs_view.Destroy()
        
        return dvswitch_properties_list
    
    def _get_datacenter_name(self, dvs):
        """Get datacenter name for a DVS."""
        if not dvs:
            return ""
        datacenter = ""
        parent = getattr(dvs, 'parent', None)
        while parent:
            if isinstance(parent, vim.Datacenter):
                datacenter = parent.name
                break
            parent = getattr(parent, 'parent', None)
        return datacenter
    
    def _get_host_members(self, dvs):
        """Get host members for a DVS."""
        host_members = ""
        if hasattr(dvs, "summary") and hasattr(dvs.summary, "hostMember"):
            host_members = ", ".join([host.name for host in dvs.summary.hostMember]) if dvs.summary.hostMember else ""
        return host_members
    
    def _get_custom_attributes(self, dvs):
        """Get custom attributes for a DVS."""
        snapshot = ""
        datastore = ""
        tier = ""
        
        if hasattr(dvs, "customValue") and dvs.customValue:
            for value in dvs.customValue:
                if hasattr(value, "key") and hasattr(value, "value"):
                    if value.key == "com.vrlcm.snapshot":
                        snapshot = value.value
                    elif value.key == "Datastore":
                        datastore = value.value
                    elif value.key == "Tier":
                        tier = value.value
        
        return snapshot, datastore, tier
    
    def _build_dvswitch_properties(self, dvs, datacenter, host_members, vm_count, created, snapshot, datastore, tier):
        """Build DVS properties dictionary."""
        return {
            "Switch": str(dvs.name) if hasattr(dvs, "name") and dvs.name else "",
            "Datacenter": str(datacenter) if datacenter else "",
            "Name": str(dvs.name) if hasattr(dvs, "name") and dvs.name else "",
            "Vendor": str(dvs.config.vendor) if hasattr(dvs, "config") and hasattr(dvs.config, "vendor") and dvs.config.vendor else "",
            "Version": str(dvs.config.version) if hasattr(dvs, "config") and hasattr(dvs.config, "version") and dvs.config.version else "",
            "Description": str(dvs.config.description) if hasattr(dvs, "config") and hasattr(dvs.config, "description") and dvs.config.description else "",
            "Created": str(created) if created else "",
            "Host members": str(host_members) if host_members else "",
            "Max Ports": str(dvs.config.maxPorts) if hasattr(dvs, "config") and hasattr(dvs.config, "maxPorts") and dvs.config.maxPorts else "",
            "# Ports": str(dvs.summary.numPorts) if hasattr(dvs, "summary") and hasattr(dvs.summary, "numPorts") and dvs.summary.numPorts else "",
            "# VMs": str(vm_count) if vm_count else "",
            "In Traffic Shaping": self._get_traffic_shaping_value(dvs, "inShapingPolicy", "enabled"),
            "In Avg": self._get_traffic_shaping_value(dvs, "inShapingPolicy", "averageBandwidth", divide_by=1000),
            "In Peak": self._get_traffic_shaping_value(dvs, "inShapingPolicy", "peakBandwidth", divide_by=1000),
            "In Burst": self._get_traffic_shaping_value(dvs, "inShapingPolicy", "burstSize", divide_by=1024),
            "Out Traffic Shaping": self._get_traffic_shaping_value(dvs, "outShapingPolicy", "enabled"),
            "Out Avg": self._get_traffic_shaping_value(dvs, "outShapingPolicy", "averageBandwidth", divide_by=1000),
            "Out Peak": self._get_traffic_shaping_value(dvs, "outShapingPolicy", "peakBandwidth", divide_by=1000),
            "Out Burst": self._get_traffic_shaping_value(dvs, "outShapingPolicy", "burstSize", divide_by=1024),
            "CDP Type": str(dvs.config.linkDiscoveryProtocolConfig.protocol) if hasattr(dvs, "config") and hasattr(dvs.config, "linkDiscoveryProtocolConfig") and dvs.config.linkDiscoveryProtocolConfig and hasattr(dvs.config.linkDiscoveryProtocolConfig, "protocol") else "",
            "CDP Operation": str(dvs.config.linkDiscoveryProtocolConfig.operation) if hasattr(dvs, "config") and hasattr(dvs.config, "linkDiscoveryProtocolConfig") and dvs.config.linkDiscoveryProtocolConfig and hasattr(dvs.config.linkDiscoveryProtocolConfig, "operation") else "",
            "LACP Name": str(dvs.config.lacpApiVersion) if hasattr(dvs, "config") and hasattr(dvs.config, "lacpApiVersion") and dvs.config.lacpApiVersion else "",
            "LACP Mode": self._get_lacp_value(dvs, "enable"),
            "LACP Load Balance Alg.": self._get_lacp_value(dvs, "mode"),
            "Max MTU": str(dvs.config.maxMtu) if hasattr(dvs, "config") and hasattr(dvs.config, "maxMtu") and dvs.config.maxMtu else "",
            "Contact": str(dvs.config.contact.name) if hasattr(dvs, "config") and hasattr(dvs.config, "contact") and dvs.config.contact and hasattr(dvs.config.contact, "name") and dvs.config.contact.name else "",
            "Admin Name": str(dvs.config.contact.contact) if hasattr(dvs, "config") and hasattr(dvs.config, "contact") and dvs.config.contact and hasattr(dvs.config.contact, "contact") and dvs.config.contact.contact else "",
            "Object ID": str(dvs._moId) if hasattr(dvs, "_moId") and dvs._moId else "",
            "com.vrlcm.snapshot": str(snapshot) if snapshot else "",
            "Datastore": str(datastore) if datastore else "",
            "Tier": str(tier) if tier else "",
            "VI SDK Server": str(self.content.about.fullName) if hasattr(self.content, "about") and hasattr(self.content.about, "fullName") and self.content.about.fullName else "",
            "VI SDK UUID": str(self.content.about.instanceUuid) if hasattr(self.content, "about") and hasattr(self.content.about, "instanceUuid") and self.content.about.instanceUuid else ""
        }
    
    def _get_traffic_shaping_value(self, dvs, policy_type, attribute, divide_by=None):
        """Get traffic shaping values from DVS configuration."""
        try:
            if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig"):
                policy = getattr(dvs.config.defaultPortConfig, policy_type, None)
                if policy and hasattr(policy, attribute):
                    attr_obj = getattr(policy, attribute)
                    if hasattr(attr_obj, "value"):
                        value = attr_obj.value
                        if divide_by:
                            return str(int(value / divide_by))
                        return str(value)
        except AttributeError:
            pass
        return ""
    
    def _get_lacp_value(self, dvs, attribute):
        """Get LACP values from DVS configuration."""
        try:
            if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig, "lacpPolicy"):
                lacp_policy = dvs.config.defaultPortConfig.lacpPolicy
                if hasattr(lacp_policy, attribute):
                    attr_obj = getattr(lacp_policy, attribute)
                    if hasattr(attr_obj, "value"):
                        return str(attr_obj.value)
        except AttributeError:
            pass
        return ""
    
    def get_vm_vswitch_properties(self):
        """
        Extract virtual switch properties from hosts.
        
        Returns:
            list: List of dictionaries with virtual switch properties
        """
        vswitch_properties_list = []
        
        host_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.HostSystem], True
        )
        
        try:
            for host in host_view.view:
                if hasattr(host, "config") and hasattr(host.config, "network"):
                    # Get datacenter and cluster info
                    datacenter, cluster = self._get_host_location_info(host)

                    # Process each virtual switch
                    if hasattr(host.config.network, "vswitch"):
                        for vswitch in host.config.network.vswitch:
                            switch_props = self._build_vswitch_properties(host, vswitch, datacenter, cluster)
                            vswitch_properties_list.append(switch_props)
        finally:
            if host_view:
                host_view.Destroy()
        
        return vswitch_properties_list
    
    def _get_host_location_info(self, host):
        """Get datacenter and cluster information for a host."""
        if not host:
            return "", ""
        datacenter = ""
        cluster = ""
        parent = getattr(host, 'parent', None)
        while parent:
            if isinstance(parent, vim.ClusterComputeResource):
                cluster = parent.name
            elif isinstance(parent, vim.Datacenter):
                datacenter = parent.name
                break
            parent = getattr(parent, 'parent', None)
        return datacenter, cluster
    
    def _build_vswitch_properties(self, host, vswitch, datacenter, cluster):
        """Build vSwitch properties dictionary."""
        return {
            "Host": host.name,
            "Datacenter": datacenter,
            "Cluster": cluster,
            "Switch": vswitch.name,
            "# Ports": str(vswitch.numPorts) if hasattr(vswitch, "numPorts") else "",
            "Free Ports": str(vswitch.numPortsAvailable) if hasattr(vswitch, "numPortsAvailable") else "",
            "Promiscuous Mode": str(vswitch.spec.policy.security.allowPromiscuous) if hasattr(vswitch, "spec") else "",
            "Mac Changes": str(vswitch.spec.policy.security.macChanges) if hasattr(vswitch, "spec") else "",
            "Forged Transmits": str(vswitch.spec.policy.security.forgedTransmits) if hasattr(vswitch, "spec") else "",
            "Traffic Shaping": str(vswitch.spec.policy.shapingPolicy.enabled) if hasattr(vswitch, "spec") else "",
            "Width": str(vswitch.spec.policy.shapingPolicy.averageBandwidth) if hasattr(vswitch, "spec") else "",
            "Peak": str(vswitch.spec.policy.shapingPolicy.peakBandwidth) if hasattr(vswitch, "spec") else "",
            "Burst": str(vswitch.spec.policy.shapingPolicy.burstSize) if hasattr(vswitch, "spec") else "",
            "Policy": str(vswitch.spec.policy.nicTeaming.policy) if hasattr(vswitch, "spec") else "",
            "Reverse Policy": str(vswitch.spec.policy.nicTeaming.reversePolicy) if hasattr(vswitch, "spec") else "",
            "Notify Switch": str(vswitch.spec.policy.nicTeaming.notifySwitches) if hasattr(vswitch, "spec") else "",
            "Rolling Order": str(vswitch.spec.policy.nicTeaming.rollingOrder) if hasattr(vswitch, "spec") else "",
            "Offload": "True" if hasattr(host.config, "netOffloadCapabilities") else "",
            "TSO": str(host.config.netOffloadCapabilities.csOffload) if hasattr(host.config, "netOffloadCapabilities") and hasattr(host.config.netOffloadCapabilities, "csOffload") else "",
            "Zero Copy Xmit": str(host.config.netOffloadCapabilities.tcpSegmentation) if hasattr(host.config, "netOffloadCapabilities") and hasattr(host.config.netOffloadCapabilities, "tcpSegmentation") else "",
            "MTU": str(vswitch.mtu) if hasattr(vswitch, "mtu") else "",
            "VI SDK Server": str(self.content.about.fullName) if hasattr(self.content, "about") and hasattr(self.content.about, "fullName") and self.content.about.fullName else "",
            "VI SDK UUID": str(self.content.about.instanceUuid) if hasattr(self.content, "about") and hasattr(self.content.about, "instanceUuid") and self.content.about.instanceUuid else ""
        }