#!/usr/bin/env python
"""
Module for collecting VM-related data from vCenter.
"""
import re
import os
from pyVmomi import vim


class VMCollector:
    """
    Class to collect VM data from vCenter.
    """
    
    def __init__(self, service_instance, content, container):
        """
        Initialize the VM collector.
        
        Args:
            service_instance: The vCenter service instance
            content: vCenter service instance content
            container: vCenter service instance container
        """
        self.service_instance = service_instance
        self.content = content
        self.container = container
        self.seen_uuids = set()
        self.duplicate_uuids = {}
        self.vm_skip_list = self._load_vm_skip_list("vm-skip-list.txt")
        self.dvs_uuid_to_name = self._build_dvs_mapping()
    
    def _load_vm_skip_list(self, filename):
        """
        Load VM name patterns to skip from a file.
        
        Args:
            filename (str): Path to the file containing VM name patterns to skip
            
        Returns:
            list: List of VM name patterns to skip
        """
        try:
            skip_list = []
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith('#'):
                            skip_list.append(line)
                return skip_list
            return []
        except Exception as e:
            print(f"Error loading VM skip list from {filename}: {str(e)}")
            return []
    
    def _build_dvs_mapping(self):
        """
        Build a mapping of DVS UUIDs to names.
        
        Returns:
            dict: Mapping of DVS UUID to name
        """
        dvs_uuid_to_name = {}
        dvs_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.DistributedVirtualSwitch], True
        )
        try:
            for dvs in dvs_view.view:
                if hasattr(dvs, "uuid") and hasattr(dvs, "name"):
                    dvs_uuid_to_name[dvs.uuid] = dvs.name
        finally:
            dvs_view.Destroy()
        return dvs_uuid_to_name
    
    def _should_skip_vm(self, vm):
        """
        Check if a VM should be skipped based on skip list patterns.
        
        Args:
            vm: The VM object
            
        Returns:
            bool: True if VM should be skipped
        """
        for pattern in self.vm_skip_list:
            # Check if pattern contains any regex special characters
            if any(c in pattern for c in '*?[](){}|^$+\\'):
                try:
                    # Use regex matching with proper escaping
                    if re.search(re.escape(pattern).replace('\\*', '.*'), vm.name):
                        print(f"Skipping VM {vm.name} (matches pattern {pattern})")
                        return True
                except re.error:
                    # Fall back to simple wildcard matching if regex fails
                    if pattern.replace("*", "") in vm.name:
                        print(f"Skipping VM {vm.name} (matches wildcard {pattern})")
                        return True
            else:
                # Use exact matching for entries without regex characters
                if vm.name == pattern:
                    print(f"Skipping VM {vm.name} (exact match)")
                    return True
        return False
    
    def _is_duplicate_uuid(self, vm_properties):
        """
        Check if VM has a duplicate UUID and track it.
        
        Args:
            vm_properties (dict): VM properties dictionary
            
        Returns:
            bool: True if VM has duplicate UUID
        """
        uuid = vm_properties.get("VM UUID", "")
        if uuid and uuid in self.seen_uuids:
            print(f"Skipping VM {vm_properties['VM']} (duplicate UUID: {uuid})")
            if uuid not in self.duplicate_uuids:
                self.duplicate_uuids[uuid] = []
            self.duplicate_uuids[uuid].append(vm_properties['VM'])
            return True
        if uuid:
            self.seen_uuids.add(uuid)
        return False
    
    def get_vm_properties(self, vm):
        """
        Extract required properties from a VM object.
        
        Args:
            vm: The VM object
            
        Returns:
            dict: VM properties or None if VM should be skipped
        """
        # Get content for service instance info
        about_info = self.content.about
        
        # Initialize properties with default values
        properties = {
            "VM": vm.name,
            "Powerstate": "",
            "Template": "",
            "DNS Name": "",
            "CPUs": "",
            "Memory": "",
            "Total disk capacity MiB": "",
            "NICs": "",
            "Disks": "",
            "Host": "",
            "OS according to the configuration file": "",
            "OS according to the VMware Tools": "",
            "VI SDK API Version": about_info.apiVersion,
            "Primary IP Address": "",
            "VM ID": str(vm._moId),
            "VM UUID": "",
            "VI SDK Server type": about_info.name,
            "VI SDK Server": about_info.fullName,
            "VI SDK UUID": about_info.instanceUuid
        }
        
        # Get power state
        properties["Powerstate"] = str(vm.runtime.powerState)
        
        # Skip powered off VMs or VMs with guest state notRunning
        if properties["Powerstate"] == "poweredOff" or (hasattr(vm.guest, "guestState") and vm.guest.guestState == "notRunning"):
            return None
        
        # Check if VM is a template
        properties["Template"] = str(vm.config.template)
        
        # Get DNS name (FQDN)
        self._set_dns_name(vm, properties)
        
        # Get CPU count
        if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "numCPU"):
            properties["CPUs"] = str(vm.config.hardware.numCPU)
        
        # Get memory (raw value)
        if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "memoryMB"):
            properties["Memory"] = str(vm.config.hardware.memoryMB)
        
        # Get NIC count
        if hasattr(vm, "network"):
            properties["NICs"] = str(len(vm.network))
        
        # Get disk count and total capacity
        self._set_disk_info(vm, properties)
        
        # Get host name
        if hasattr(vm, "runtime") and hasattr(vm.runtime, "host") and vm.runtime.host:
            properties["Host"] = vm.runtime.host.name
        
        # Get OS according to config
        if hasattr(vm.config, "guestFullName"):
            properties["OS according to the configuration file"] = vm.config.guestFullName
        
        # Get OS according to VMware Tools
        if hasattr(vm.guest, "guestFullName"):
            properties["OS according to the VMware Tools"] = vm.guest.guestFullName
        
        # Get primary IP address
        if hasattr(vm.guest, "ipAddress") and vm.guest.ipAddress:
            properties["Primary IP Address"] = vm.guest.ipAddress
        
        # Get VM UUID
        if hasattr(vm.config, "uuid"):
            properties["VM UUID"] = vm.config.uuid
        
        return properties
    
    def _set_dns_name(self, vm, properties):
        """Set DNS name for VM properties."""
        # Try to get FQDN from guest info
        if hasattr(vm.guest, "ipStack") and vm.guest.ipStack:
            for ip_stack in vm.guest.ipStack:
                if hasattr(ip_stack, "dnsConfig") and ip_stack.dnsConfig:
                    if hasattr(ip_stack.dnsConfig, "domainName") and ip_stack.dnsConfig.domainName:
                        if hasattr(vm.guest, "hostName") and vm.guest.hostName:
                            properties["DNS Name"] = f"{vm.guest.hostName}.{ip_stack.dnsConfig.domainName}"
                            return
        
        # Fallback if we couldn't get FQDN from ipStack
        if hasattr(vm.guest, "hostName") and vm.guest.hostName:
            hostname = vm.guest.hostName
            # Check if hostname already contains domain parts (has dots)
            if "." in hostname:
                properties["DNS Name"] = hostname
            elif hasattr(vm.guest, "domainName") and vm.guest.domainName:
                properties["DNS Name"] = f"{hostname}.{vm.guest.domainName}"
            else:
                # Use VM name + default domain as last resort
                properties["DNS Name"] = f"{vm.name}.local"
    
    def _set_disk_info(self, vm, properties):
        """Set disk information for VM properties."""
        if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "device"):
            disk_count = 0
            total_capacity_mib = 0
            for device in vm.config.hardware.device:
                if hasattr(device, "capacityInKB"):
                    disk_count += 1
                    # Convert KB to MiB
                    total_capacity_mib += device.capacityInKB / 1024
            
            if disk_count > 0:
                properties["Disks"] = str(disk_count)
                properties["Total disk capacity MiB"] = str(int(total_capacity_mib))
    
    def get_vm_network_properties(self, vm):
        """
        Extract network properties from a VM object.
        
        Args:
            vm: The VM object
            
        Returns:
            list: List of dictionaries with network properties for each NIC
        """
        network_properties_list = []
        
        # Check if VM has network adapters
        if hasattr(vm.guest, "net") and vm.guest.net:
            for nic in vm.guest.net:
                network_properties = {
                    "VM": vm.name,
                    "Network": "",
                    "IPv4 Address": "",
                    "IPv6 Address": "",
                    "Switch": "",
                    "Mac Address": ""
                }
                
                # Get network name
                if hasattr(nic, "network"):
                    network_properties["Network"] = nic.network
                
                # Get IPv4 address
                if hasattr(nic, "ipAddress"):
                    ipv4_addresses = [ip for ip in nic.ipAddress if ":" not in ip]
                    if ipv4_addresses:
                        network_properties["IPv4 Address"] = ipv4_addresses[0]
                
                # Get IPv6 address
                if hasattr(nic, "ipAddress"):
                    ipv6_addresses = [ip for ip in nic.ipAddress if ":" in ip]
                    if ipv6_addresses:
                        network_properties["IPv6 Address"] = ipv6_addresses[0]
                
                # Get MAC address
                if hasattr(nic, "macAddress"):
                    network_properties["Mac Address"] = nic.macAddress
                
                # Get switch information
                self._set_switch_info(vm, nic, network_properties)
                
                network_properties_list.append(network_properties)
        
        # If no NICs were found, add a single entry with just the VM name
        if not network_properties_list:
            network_properties_list.append({
                "VM": vm.name,
                "Network": "",
                "IPv4 Address": "",
                "IPv6 Address": "",
                "Switch": "",
                "Mac Address": ""
            })
        
        return network_properties_list
    
    def _set_switch_info(self, vm, nic, network_properties):
        """Set switch information for network properties."""
        if hasattr(nic, "deviceConfigId"):
            # Find the matching device in the VM's hardware
            if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "device"):
                for device in vm.config.hardware.device:
                    if hasattr(device, "key") and device.key == nic.deviceConfigId:
                        # Standard vSwitch
                        if hasattr(device, "backing") and isinstance(device.backing, vim.vm.device.VirtualEthernetCard.NetworkBackingInfo):
                            if hasattr(device.backing, "deviceName"):
                                network_properties["Switch"] = device.backing.deviceName
                                break
                        # Distributed vSwitch
                        elif hasattr(device, "backing") and isinstance(device.backing, vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
                            if hasattr(device.backing, "port") and hasattr(device.backing.port, "switchUuid"):
                                # Use the dictionary to look up the DVS name from UUID
                                switch_uuid = device.backing.port.switchUuid
                                if switch_uuid in self.dvs_uuid_to_name:
                                    network_properties["Switch"] = self.dvs_uuid_to_name[switch_uuid]
                                break
    
    def get_vm_cpu_properties(self, vm):
        """Extract CPU properties from a VM object."""
        cpu_properties = {
            "VM": vm.name,
            "CPUs": "",
            "Sockets": "",
            "Reservation": ""
        }
        
        # Get CPU count
        if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "numCPU"):
            cpu_properties["CPUs"] = str(vm.config.hardware.numCPU)
        
        # Get socket count
        if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "numCoresPerSocket"):
            cores_per_socket = vm.config.hardware.numCoresPerSocket
            if cores_per_socket > 0 and cpu_properties["CPUs"]:
                sockets = int(cpu_properties["CPUs"]) // cores_per_socket
                cpu_properties["Sockets"] = str(sockets)
        
        # Get CPU reservation
        if hasattr(vm.config, "cpuAllocation") and hasattr(vm.config.cpuAllocation, "reservation"):
            cpu_properties["Reservation"] = str(vm.config.cpuAllocation.reservation)
        
        return cpu_properties
    
    def get_vm_memory_properties(self, vm):
        """Extract memory properties from a VM object."""
        memory_properties = {
            "VM": vm.name,
            "Size MiB": "",
            "Reservation": ""
        }
        
        # Get memory size
        if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "memoryMB"):
            memory_properties["Size MiB"] = str(vm.config.hardware.memoryMB)
        
        # Get memory reservation
        if hasattr(vm.config, "memoryAllocation") and hasattr(vm.config.memoryAllocation, "reservation"):
            memory_properties["Reservation"] = str(vm.config.memoryAllocation.reservation)
        
        return memory_properties
    
    def get_vm_disk_properties(self, vm):
        """Extract disk properties from a VM object."""
        disk_properties_list = []
        
        # Check if VM has disks
        if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "device"):
            disk_number = 0
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualDisk):
                    disk_number += 1
                    disk_properties = {
                        "VM": vm.name,
                        "Disk": str(disk_number),
                        "Disk Key": str(device.key),
                        "Disk Path": "",
                        "Capacity MiB": ""
                    }
                    
                    # Get disk path
                    if hasattr(device.backing, "fileName"):
                        disk_properties["Disk Path"] = device.backing.fileName
                    
                    # Get disk capacity in MiB
                    if hasattr(device, "capacityInKB"):
                        # Convert KB to MiB
                        capacity_mib = device.capacityInKB / 1024
                        disk_properties["Capacity MiB"] = str(int(capacity_mib))
                    
                    disk_properties_list.append(disk_properties)
        
        # If no disks were found, add a single entry with just the VM name
        if not disk_properties_list:
            disk_properties_list.append({
                "VM": vm.name,
                "Disk": "",
                "Disk Key": "",
                "Disk Path": "",
                "Capacity MiB": ""
            })
        
        return disk_properties_list
    
    def get_vm_partition_properties(self, vm):
        """Extract partition properties from a VM object."""
        partition_properties_list = []
        
        # Check if VM has disks
        if hasattr(vm.config, "hardware") and hasattr(vm.config.hardware, "device"):
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualDisk):
                    partition_properties = {
                        "VM": vm.name,
                        "Disk Key": str(device.key),
                        "Disk": "",
                        "Capacity MiB": "",
                        "Free MiB": ""
                    }
                    
                    # Get disk number
                    if hasattr(device, "unitNumber"):
                        partition_properties["Disk"] = str(device.unitNumber)
                    
                    # Get disk capacity in MiB
                    if hasattr(device, "capacityInKB"):
                        # Convert KB to MiB
                        capacity_mib = device.capacityInKB / 1024
                        partition_properties["Capacity MiB"] = str(int(capacity_mib))
                        
                        # Set free space (this would normally come from guest OS, using placeholder)
                        partition_properties["Free MiB"] = ""
                        if hasattr(vm, "guest") and hasattr(vm.guest, "disk"):
                            for disk in vm.guest.disk:
                                if hasattr(disk, "diskPath") and hasattr(device.backing, "fileName"):
                                    if disk.diskPath in device.backing.fileName:
                                        free_mib = disk.freeSpace / (1024 * 1024)
                                        partition_properties["Free MiB"] = str(int(free_mib))
                                        break
                    
                    partition_properties_list.append(partition_properties)
        
        # If no partitions were found, add a single entry with just the VM name
        if not partition_properties_list:
            partition_properties_list.append({
                "VM": vm.name,
                "Disk Key": "",
                "Disk": "",
                "Capacity MiB": "",
                "Free MiB": ""
            })
        
        return partition_properties_list
    
    def get_vm_tools_properties(self, vm):
        """Extract VMware Tools properties from a VM object."""
        tools_properties = {
            "VM": vm.name,
            "Tools": ""
        }
        
        # Get VMware Tools status
        if hasattr(vm.guest, "toolsStatus"):
            tools_properties["Tools"] = str(vm.guest.toolsStatus)
        
        return tools_properties
    
    def print_duplicate_uuids_summary(self):
        """Print information about duplicate UUIDs if any were found."""
        if self.duplicate_uuids:
            print("\nThe following UUIDs were skipped as duplicates, and only the first VM with each UUID was exported:")
            for uuid, vm_names in self.duplicate_uuids.items():
                print(f"  UUID: {uuid}")
                print(f"    Skipped VMs: {', '.join(vm_names)}")