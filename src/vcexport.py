#!/usr/bin/env python
"""
Script to export virtual machine and related config info from vCenter to a CSV file.
"""
import argparse
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

from collectors.performance_collector import PerformanceCollector

def write_csv_file(filename, headers, data_list):
    """
    Write data to a CSV file.
    
    Args:
        filename (str): Path to the output CSV file
        headers (list): List of column headers
        data_list (list): List of dictionaries containing the data
        
    Returns:
        bool: True on success, False on fail
    """
    try:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            for data in data_list:
                writer.writerow(data)

            return True

    except Exception as e:
        print(f"Error writing CSV file: {str(e.Message)}")
        return False


def collect_performance_metrics(service_instance, vms, output_dir, interval_mins=60, samples=12):
    """
    Collect and export performance metrics for VMs.
    
    Args:
        service_instance: The vCenter service instance
        vms (list): List of VM objects to collect metrics for
        output_dir (str): Directory to save the performance metrics CSV file
        interval_mins (int): Time interval in minutes for metrics collection
        samples (int): Number of samples to collect
        
    Returns:
        str: Path to the generated CSV file, or None if collection failed
    """
    try:
        # Create performance collector
        perf_collector = PerformanceCollector(service_instance)
        
        # Filter for powered on VMs
        powered_on_vms = [vm for vm in vms if vm.runtime.powerState == 'poweredOn']
        
        print(f"Collecting performance metrics for {len(powered_on_vms)} powered on VMs")
        print(f"Time interval: {interval_mins} minutes, Samples: {samples}")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export VM metrics to CSV
        csv_filename = f"{output_dir}/detailed_vm_metrics_{timestamp}.csv"
        print(f"Exporting detailed VM metrics to {csv_filename}")
        
        success = perf_collector.export_detailed_vm_metrics_to_csv(powered_on_vms, csv_filename, interval_mins, samples)
        
        if success:
            print(f"Successfully exported detailed VM metrics to {csv_filename}")
            return csv_filename
        else:
            print("Failed to export detailed VM metrics")
            return None
            
    except Exception as e:
        print(f"Error collecting performance metrics: {str(e)}")
        return None

def load_vm_skip_list(filename):
    """
    Load VM name patterns to skip from a file.
    
    Args:
        filename (str): Path to the file containing VM name patterns to skip
        
    Returns:
        list: List of VM name patterns to skip, or None if file doesn't exist
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
        return None
    except Exception as e:
        print(f"Error loading VM skip list from {filename}: {str(e.message)}")
        return None

def connect_to_vcenter(host, user, password, port=443, disable_ssl_verification=False):
    """
    Connect to vCenter server and return the service instance object.
    
    Args:
        host (str): The vCenter server hostname or IP address
        user (str): The username to authenticate with
        password (str): The password to authenticate with
        port (int): The port to connect on (default: 443)
        disable_ssl_verification (bool): Whether to disable SSL certificate verification
        
    Returns:
        ServiceInstance: The vCenter service instance
    """
    context = None
    
    # Create SSL context if SSL verification is disabled
    if disable_ssl_verification:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    
    try:
        # Connect to vCenter server
        service_instance = connect.SmartConnect(
            host=host,
            user=user,
            pwd=password,
            port=port,
            disableSslCertValidation=disable_ssl_verification,
            sslContext=context
        )
        
        # Register disconnect function to be called when script exits
        atexit.register(connect.Disconnect, service_instance)
        
        print(f"Successfully connected to vCenter Server: {host}")
        return service_instance
    
    except vim.fault.InvalidLogin:
        print("Invalid login credentials")
        return None
    except Exception as e:
        print(f"Failed to connect to vCenter Server: {str(e)}")
        return None

def get_vm_properties(vm, content, container):
    """
    Extract required properties from a VM object.
    
    Args:
        vm: The VM object
        service_instance: The vCenter service instance
        
    Returns:
        dict: VM properties
    """
    # Get content for service instance info
    about_info = content.about
    
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
    # Try to get FQDN from guest info
    if hasattr(vm.guest, "ipStack") and vm.guest.ipStack:
        for ip_stack in vm.guest.ipStack:
            if hasattr(ip_stack, "dnsConfig") and ip_stack.dnsConfig:
                if hasattr(ip_stack.dnsConfig, "domainName") and ip_stack.dnsConfig.domainName:
                    if hasattr(vm.guest, "hostName") and vm.guest.hostName:
                        properties["DNS Name"] = f"{vm.guest.hostName}.{ip_stack.dnsConfig.domainName}"
                        break
    
    # Fallback if we couldn't get FQDN from ipStack
    if not properties["DNS Name"] and hasattr(vm.guest, "hostName") and vm.guest.hostName:
        hostname = vm.guest.hostName
        # Check if hostname already contains domain parts (has dots)
        if "." in hostname:
            properties["DNS Name"] = hostname
        elif hasattr(vm.guest, "domainName") and vm.guest.domainName:
            properties["DNS Name"] = f"{hostname}.{vm.guest.domainName}"
        else:
            # Use VM name + default domain as last resort
            properties["DNS Name"] = f"{vm.name}.local"
    
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


def get_vm_network_properties(vm, dvs_uuid_to_name:dict):
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
                                    if switch_uuid in dvs_uuid_to_name:
                                        network_properties["Switch"] = dvs_uuid_to_name[switch_uuid]
                                    break                                    
            
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


def get_vm_cpu_properties(vm):
    """
    Extract CPU properties from a VM object.
    
    Args:
        vm: The VM object
        
    Returns:
        dict: Dictionary with CPU properties
    """
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


def get_vm_memory_properties(vm):
    """
    Extract memory properties from a VM object.
    
    Args:
        vm: The VM object
        
    Returns:
        dict: Dictionary with memory properties
    """
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


def get_vm_disk_properties(vm):
    """
    Extract disk properties from a VM object.
    
    Args:
        vm: The VM object
        
    Returns:
        list: List of dictionaries with disk properties for each disk
    """
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


def get_vm_partition_properties(vm):
    """
    Extract partition properties from a VM object.
    
    Args:
        vm: The VM object
        
    Returns:
        list: List of dictionaries with partition properties for each disk
    """
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
                    # In a real implementation, you would get this from vm.guest.disk if available
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


def get_vm_tools_properties(vm):
    """
    Extract VMware Tools properties from a VM object.
    
    Args:
        vm: The VM object
        
    Returns:
        dict: Dictionary with VMware Tools properties
    """
    tools_properties = {
        "VM": vm.name,
        "Tools": ""
    }
    
    # Get VMware Tools status
    if hasattr(vm.guest, "toolsStatus"):
        tools_properties["Tools"] = str(vm.guest.toolsStatus)
    
    return tools_properties


def get_host_properties(content, container):
    """
    Extract host properties from the service instance.
    
    Args:
        content: vCenter service instance content
        container: vCenter service instance container
        
    Returns:
        list: List of dictionaries with host properties
    """
    host_properties_list = []
    host_view = content.viewManager.CreateContainerView(container, [vim.HostSystem], True)
    
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
                    "VI SDK UUID": content.about.instanceUuid if hasattr(content, "about") and hasattr(content.about, "instanceUuid") else ""
                }
                host_properties_list.append(host_properties)
    finally:
        if host_view:
            host_view.Destroy()
    
    return host_properties_list


def get_host_nic_properties(content, container):
    """
    Extract NIC properties from hosts.
    
    Args:
        content: vCenter service instance content
        container: vCenter service instance container
        
    Returns:
        list: List of dictionaries with host NIC properties
    """
    nic_properties_list = []
    host_view = content.viewManager.CreateContainerView(container, [vim.HostSystem], True)
    
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


def get_host_vmk_properties(content, container):
    """
    Extract VMkernel properties from hosts.
    
    Args:
        content: vCenter service instance content
        container: vCenter service instance container
        
    Returns:
        list: List of dictionaries with host VMkernel properties
    """
    vmk_properties_list = []
    
    host_view = content.viewManager.CreateContainerView(container, [vim.HostSystem], True)
    
    try:
        for host in host_view.view:
            if hasattr(host, "config") and hasattr(host.config, "network") and hasattr(host.config.network, "vnic"):
                for vnic in host.config.network.vnic:
                    vmk_properties = {
                        "Host": host.name if hasattr(host, "name") else "",
                        "Mac Address": vnic.spec.mac if hasattr(vnic, "spec") and hasattr(vnic.spec, "mac") else "",
                        "IP Address": vnic.spec.ip.ipAddress if hasattr(vnic, "spec") and hasattr(vnic.spec, "ip") else "",
                        "IP 6 Address": "",
                        "Subnet mask": vnic.spec.ip.subnetMask if hasattr(vnic, "spec") and hasattr(vnic.spec, "ip") else ""
                    }
                    
                    # Try to get IPv6 address
                    if hasattr(vnic.spec, "ip") and hasattr(vnic.spec.ip, "ipV6Config") and hasattr(vnic.spec.ip.ipV6Config, "ipV6Address"):
                        if vnic.spec.ip.ipV6Config.ipV6Address:
                            vmk_properties["IP 6 Address"] = vnic.spec.ip.ipV6Config.ipV6Address[0].ipAddress
                    
                    vmk_properties_list.append(vmk_properties)
    finally:
        if host_view:
            host_view.Destroy()
    
    return vmk_properties_list


def get_vm_dvport_properties(content, container):
    """
    Extract distributed virtual port properties.
    
    Args:
        content: vCenter service instance content
        container: vCenter service instance container
        
    Returns:
        list: List of dictionaries with distributed virtual port properties
    """
    dvport_properties_list = []
       
    # Get all distributed virtual switches
    dvs_view = content.viewManager.CreateContainerView(container, [vim.DistributedVirtualSwitch], True)
    
    try:
        for dvs in dvs_view.view:
            # Get all port groups in this DVS
            if hasattr(dvs, "portgroup"):
                for pg in dvs.portgroup:
                    # Get VLAN info
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


def get_vm_port_properties(content, container):
    """
    Extract port group properties from standard virtual switches.
    
    Args:
        content: vCenter service instance content
        container: vCenter service instance container
        
    Returns:
        list: List of dictionaries with port group properties
    """
    port_properties_list = []
    
    # Get standard port groups from hosts
    host_view = content.viewManager.CreateContainerView(container, [vim.HostSystem], True)
    
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



def get_vm_dvswitch_properties(content, container):
    """
    Extract distributed virtual switch properties.
    
    Args:
        content: vCenter service instance content
        container: vCenter service instance container
        
    Returns:
        list: List of dictionaries with distributed virtual switch properties
    """
    dvswitch_properties_list = []
      
    # Get all distributed virtual switches
    dvs_view = content.viewManager.CreateContainerView(container, [vim.DistributedVirtualSwitch], True)
    
    try:
        for dvs in dvs_view.view:
            # Get datacenter info
            datacenter = ""
            parent = dvs.parent
            while parent:
                if isinstance(parent, vim.Datacenter):
                    datacenter = parent.name
                    break
                parent = parent.parent
            
            # Get host members
            host_members = ""
            if hasattr(dvs, "summary") and hasattr(dvs.summary, "hostMember"):
                host_members = ", ".join([host.name for host in dvs.summary.hostMember]) if dvs.summary.hostMember else ""
            
            # Get VM count
            vm_count = ""
            if hasattr(dvs, "vm"):
                vm_count = str(len(dvs.vm)) if dvs.vm else "0"
            
            # Get creation date
            created = ""
            if hasattr(dvs, "config") and hasattr(dvs.config, "createTime"):
                created = str(dvs.config.createTime)
            
            # Get custom attributes
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
            
            dvswitch_props = {
                "Switch": dvs.name if hasattr(dvs, "name") else "",
                "Datacenter": datacenter,
                "Name": dvs.name if hasattr(dvs, "name") else "",
                "Vendor": dvs.config.vendor if hasattr(dvs, "config") and hasattr(dvs.config, "vendor") else "",
                "Version": dvs.config.version if hasattr(dvs, "config") and hasattr(dvs.config, "version") else "",
                "Description": dvs.config.description if hasattr(dvs, "config") and hasattr(dvs.config, "description") else "",
                "Created": created,
                "Host members": host_members,
                "Max Ports": str(dvs.config.maxPorts) if hasattr(dvs, "config") and hasattr(dvs.config, "maxPorts") else "",
                "# Ports": str(dvs.summary.numPorts) if hasattr(dvs, "summary") and hasattr(dvs.summary, "numPorts") else "",
                "# VMs": vm_count,
                "In Traffic Shaping": str(dvs.config.defaultPortConfig.inShapingPolicy.enabled.value) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig.inShapingPolicy, "enabled") and hasattr(dvs.config.defaultPortConfig.inShapingPolicy.enabled, "value") else "",
                "In Avg": str(int(dvs.config.defaultPortConfig.inShapingPolicy.averageBandwidth.value / 1000)) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig.inShapingPolicy, "averageBandwidth") and hasattr(dvs.config.defaultPortConfig.inShapingPolicy.averageBandwidth, "value") else "",
                "In Peak": str(int(dvs.config.defaultPortConfig.inShapingPolicy.peakBandwidth.value / 1000)) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig.inShapingPolicy, "peakBandwidth") and hasattr(dvs.config.defaultPortConfig.inShapingPolicy.peakBandwidth, "value") else "",
                "In Burst": str(int(dvs.config.defaultPortConfig.inShapingPolicy.burstSize.value / 1024)) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig.inShapingPolicy, "burstSize") and hasattr(dvs.config.defaultPortConfig.inShapingPolicy.burstSize, "value") else "",
                "Out Traffic Shaping": str(dvs.config.defaultPortConfig.outShapingPolicy.enabled.value) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig.outShapingPolicy, "enabled") and hasattr(dvs.config.defaultPortConfig.outShapingPolicy.enabled, "value") else "",
                "Out Avg": str(int(dvs.config.defaultPortConfig.outShapingPolicy.averageBandwidth.value / 1000)) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig.outShapingPolicy, "averageBandwidth") and hasattr(dvs.config.defaultPortConfig.outShapingPolicy.averageBandwidth, "value") else "",
                "Out Peak": str(int(dvs.config.defaultPortConfig.outShapingPolicy.peakBandwidth.value / 1000)) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig.outShapingPolicy, "peakBandwidth") and hasattr(dvs.config.defaultPortConfig.outShapingPolicy.peakBandwidth, "value") else "",
                "Out Burst": str(int(dvs.config.defaultPortConfig.outShapingPolicy.burstSize.value / 1024)) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig.outShapingPolicy, "burstSize") and hasattr(dvs.config.defaultPortConfig.outShapingPolicy.burstSize, "value") else "",
                "CDP Type": str(dvs.config.linkDiscoveryProtocolConfig.protocol) if hasattr(dvs, "config") and hasattr(dvs.config, "linkDiscoveryProtocolConfig") else "",
                "CDP Operation": str(dvs.config.linkDiscoveryProtocolConfig.operation) if hasattr(dvs, "config") and hasattr(dvs.config, "linkDiscoveryProtocolConfig") else "",
                "LACP Name": str(dvs.config.lacpApiVersion) if hasattr(dvs, "config") and hasattr(dvs.config, "lacpApiVersion") else "",
                "LACP Mode": str(dvs.config.defaultPortConfig.lacpPolicy.enable.value) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig, "lacpPolicy") and hasattr(dvs.config.defaultPortConfig.lacpPolicy, "enable") and hasattr(dvs.config.defaultPortConfig.lacpPolicy.enable, "value") else "",
                "LACP Load Balance Alg.": str(dvs.config.defaultPortConfig.lacpPolicy.mode.value) if hasattr(dvs, "config") and hasattr(dvs.config, "defaultPortConfig") and hasattr(dvs.config.defaultPortConfig, "lacpPolicy") and hasattr(dvs.config.defaultPortConfig.lacpPolicy, "mode") and hasattr(dvs.config.defaultPortConfig.lacpPolicy.mode, "value") else "",
                "Max MTU": str(dvs.config.maxMtu) if hasattr(dvs, "config") and hasattr(dvs.config, "maxMtu") else "",
                "Contact": dvs.config.contact.name if hasattr(dvs, "config") and hasattr(dvs.config, "contact") else "",
                "Admin Name": dvs.config.contact.contact if hasattr(dvs, "config") and hasattr(dvs.config, "contact") else "",
                "Object ID": str(dvs._moId) if hasattr(dvs, "_moId") else "",
                "com.vrlcm.snapshot": snapshot,
                "Datastore": datastore,
                "Tier": tier,
                "VI SDK Server": content.about.fullName if hasattr(content, "about") else "",
                "VI SDK UUID": content.about.instanceUuid if hasattr(content, "about") else ""
            }
            
            # Just add one entry per dvSwitch
            dvswitch_properties_list.append(dvswitch_props)
    finally:
        if dvs_view:
            dvs_view.Destroy()
    
    return dvswitch_properties_list


def get_vm_vswitch_properties(content, container):
    """
    Extract virtual switch properties from hosts.
    
    Args:
        content: vCenter service instance content
        container: vCenter service instance container
        
    Returns:
        list: List of dictionaries with virtual switch properties
    """
    vswitch_properties_list = []
    
    host_view = content.viewManager.CreateContainerView(container, [vim.HostSystem], True)
    
    try:
        for host in host_view.view:
            if hasattr(host, "config") and hasattr(host.config, "network"):
                # Get datacenter and cluster info
                datacenter = ""
                cluster = ""
                parent = host.parent
                while parent:
                    if isinstance(parent, vim.ClusterComputeResource):
                        cluster = parent.name
                    elif isinstance(parent, vim.Datacenter):
                        datacenter = parent.name
                        break
                    parent = parent.parent

                # Process each virtual switch
                if hasattr(host.config.network, "vswitch"):
                    for vswitch in host.config.network.vswitch:
                        switch_props = {
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
                            "VI SDK Server": content.about.fullName if hasattr(content, "about") else "",
                            "VI SDK UUID": content.about.instanceUuid if hasattr(content, "about") else ""
                        }
                        vswitch_properties_list.append(switch_props)
    finally:
        if host_view:
            host_view.Destroy()
    
    return vswitch_properties_list


def get_source_properties(content):
    """
    Extract source properties from the service instance.
    
    Args:
        content: vCenter service instance content
        container: vCenter service instance container
        
    Returns:
        dict: Dictionary with source properties
    """
    about_info = content.about
    
    source_properties = {
        "Name": about_info.name if hasattr(about_info, "name") else "",
        "API version": about_info.apiVersion if hasattr(about_info, "apiVersion") else "",
        "Vendor": about_info.vendor if hasattr(about_info, "vendor") else "",
        "VI SDK UUID": about_info.instanceUuid if hasattr(about_info, "instanceUuid") else ""
    }
    
    return source_properties


def export_vm_data(service_instance, info_file="RVTools_tabvInfo.csv", network_file="RVTools_tabvNetwork.csv", 
                  vcpu_file="RVTools_tabvCPU.csv", memory_file="RVTools_tabvMemory.csv", disk_file="RVTools_tabvDisk.csv", 
                  partition_file="RVTools_tabvPartition.csv", vsource_file="RVTools_tabvSource.csv", 
                  vtools_file="RVTools_tabvTools.csv", vhost_file="RVTools_tabvHost.csv", vnic_file="RVTools_tabvNIC.csv",
                  sc_vmk_file="RVTools_tabvSC_VMK.csv", vswitch_file="RVTools_tabvSwitch.csv", 
                  dvswitch_file="RVTools_tabdvSwitch.csv", vport_file="RVTools_tabvPort.csv", 
                  dvport_file="RVTools_tabdvPort.csv", performance_file="vcexport_tabvPerformance.csv", max_count=None, purge_csv=True, 
                  export_statistics=True, perf_interval=60):
    """
    Export VM data to CSV files.
    
    Args:
        service_instance: The vCenter service instance
        info_file (str): Path to the VM info output CSV file
        network_file (str): Path to the VM network output CSV file
        vcpu_file (str): Path to the VM CPU output CSV file
        memory_file (str): Path to the VM memory output CSV file
        disk_file (str): Path to the VM disk output CSV file
        partition_file (str): Path to the VM partition output CSV file
        vsource_file (str): Path to the source info output CSV file
        vtools_file (str): Path to the VMware Tools output CSV file
        vhost_file (str): Path to the host info output CSV file
        vnic_file (str): Path to the VM NIC output CSV file
        dvswitch_file (str): Path to the distributed virtual switch output CSV file
        vport_file (str): Path to the standard virtual switch ports output CSV file
        dvport_file (str): Path to the distributed virtual switch ports output CSV file
        performance_file (str): Path to the performance metrics from vCenter using performance statistics
        max_count (int, optional): Maximum number of VMs to process
        purge_csv (bool, optional): If true, individual CSV files are deleted after zipping
        export_statistics (bool, optional): If true, collect performance statistics (default: True)
        perf_interval (int, optional): Performance collection time interval in minutes (default: 60). Sampling period is automatically determined.
        
    Returns:
        tuple: Paths to the created CSV files
    """
    if not service_instance:
        print("No valid vCenter connection")
        return None, None, None, None, None, None, None, None, None, None, None, None, None, None, None
    
    # Ensure the directories exist
    # This is overkill, but leaving in place in case we need different paths at some point
    os.makedirs(os.path.dirname(os.path.abspath(info_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(network_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(vcpu_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(memory_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(disk_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(partition_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(vsource_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(vtools_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(vhost_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(vnic_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(sc_vmk_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(vswitch_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(dvswitch_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(vport_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(dvport_file)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(performance_file)), exist_ok=True)
    

    # Get content and container view
    content = service_instance.RetrieveContent()
    container = content.rootFolder

    # Get source properties
    print("Getting source properties...")
    source_properties = get_source_properties(content)
    
    # Get host properties
    print("Getting host properties...")
    host_properties_list = get_host_properties(content, container)
    
    # Get host NIC properties
    print("Getting host NIC properties...")
    host_nic_properties_list = get_host_nic_properties(content, container)
    
    # Get host VMkernel properties
    print("Getting host VMKernel properties...")
    host_vmk_properties_list = get_host_vmk_properties(content, container)
    
    # Get virtual switch properties
    print("Getting virtual switch properties...")
    vswitch_properties_list = get_vm_vswitch_properties(content, container)
    
    # Get distributed virtual switch properties
    print("Getting distributed virtual switch properties...")
    dvswitch_properties_list = get_vm_dvswitch_properties(content, container)
    
    # Get port group properties
    print("Getting port group properties...")
    port_properties_list = get_vm_port_properties(content, container)
    
    # Get distributed virtual port properties
    print("Getting distributed port group properties...")
    dvport_properties_list = get_vm_dvport_properties(content, container)
    
    # Get performance metric properties
    if export_statistics:
        print("Getting performance metric properties...")
        perf_collector = PerformanceCollector(service_instance) # Create performance collector
        performance_properties_list =  perf_collector.get_performance_properties(
            content, 
            container, 
            interval_mins=perf_interval
        )
    else:
        print("Skipping performance statistics collection (--no-statistics specified)")
        performance_properties_list = []
        perf_collector = None
    
    # Get content and container view
    #content = service_instance.RetrieveContent()
    #container = content.rootFolder
    container_view = content.viewManager.CreateContainerView(container, [vim.VirtualMachine], True)
    
    try:
        # Get all VMs
        all_vms = list(container_view.view)
        
        # Apply max_count limit if specified
        if max_count is not None and isinstance(max_count, int) and max_count > 0:
            vms_to_process = all_vms[:max_count]
            total_vms = min(len(all_vms), max_count)
            print(f"Found {len(all_vms)} VMs, processing {total_vms} (limited by max_count={max_count})")
        else:
            vms_to_process = all_vms
            total_vms = len(all_vms)
            print(f"Found {len(all_vms)} VMs, processing all")
        
        # Lists to store VM data
        vm_info_list = []
        vm_network_list = []
        vm_cpu_list = []
        vm_memory_list = []
        vm_disk_list = []
        vm_partition_list = []
        vm_tools_list = []
        
        # Track VM UUIDs to detect duplicates
        seen_uuids = set()
        duplicate_uuids = {}  # Will store UUID -> list of skipped VM names

        # Load VM name patterns to skip from file or use defaults
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        skip_list_path = os.path.join(script_dir, "vm-skip-list.txt")
        vm_skip_list = load_vm_skip_list(skip_list_path)

        # Used to map VMs to a specific DVS 
        dvs_view = content.viewManager.CreateContainerView(container, [vim.DistributedVirtualSwitch], True)
        dvs_uuid_to_name = {}
        try:
            for dvs in dvs_view.view:
                if hasattr(dvs, "uuid") and hasattr(dvs, "name"):
                    dvs_uuid_to_name[dvs.uuid] = dvs.name
        finally:
            dvs_view.Destroy()

        # Process VMs
        for i, vm in enumerate(vms_to_process):
            # Skip VMs that match patterns in vm_skip_list
            skip_vm = False
            for pattern in vm_skip_list:
                # Check if pattern contains any regex special characters
                if any(c in pattern for c in '*?[](){}|^$+\\'):
                    try:
                        # Use regex matching with proper escaping
                        if re.search(re.escape(pattern).replace('\\*', '.*'), vm.name):
                            print(f"Skipping VM {vm.name} (matches pattern {pattern})")
                            skip_vm = True
                            break
                    except re.error:
                        # Fall back to simple wildcard matching if regex fails
                        if pattern.replace("*", "") in vm.name:
                            print(f"Skipping VM {vm.name} (matches wildcard {pattern})")
                            skip_vm = True
                            break
                else:
                    # Use exact matching for entries without regex characters
                    if vm.name == pattern:
                        print(f"Skipping VM {vm.name} (exact match)")
                        skip_vm = True
                        break
            if skip_vm:
                continue
                
            print(f"Processing VM {i+1} of {total_vms}: {vm.name}")
            
            # Get VM info properties
            vm_properties = get_vm_properties(vm, content, container)
            if vm_properties:  # Skip if None (powered off VM)
                # Skip VMs without a primary IP address
                if not vm_properties.get("Primary IP Address"):
                    print(f"Skipping VM {vm.name} (no primary IP address)")
                    continue

                # Check for duplicate UUID
                uuid = vm_properties.get("VM UUID", "")
                if uuid and uuid in seen_uuids:
                    print(f"Skipping VM {vm.name} (duplicate UUID: {uuid})")
                    if uuid not in duplicate_uuids:
                        duplicate_uuids[uuid] = []
                    duplicate_uuids[uuid].append(vm.name)
                    continue
                if uuid:
                    seen_uuids.add(uuid)
                vm_info_list.append(vm_properties)
            
                # Get VM network properties
                vm_network_properties = get_vm_network_properties(vm, dvs_uuid_to_name)
                vm_network_list.extend(vm_network_properties)
                
                # Get VM CPU properties
                vm_cpu_properties = get_vm_cpu_properties(vm)
                vm_cpu_list.append(vm_cpu_properties)
                
                # Get VM memory properties
                vm_memory_properties = get_vm_memory_properties(vm)
                vm_memory_list.append(vm_memory_properties)
                
                # Get VM disk properties
                vm_disk_properties = get_vm_disk_properties(vm)
                vm_disk_list.extend(vm_disk_properties)
                
                # Get VM partition properties
                vm_partition_properties = get_vm_partition_properties(vm)
                vm_partition_list.extend(vm_partition_properties)
                
                # Get VM tools properties
                vm_tools_properties = get_vm_tools_properties(vm)
                vm_tools_list.append(vm_tools_properties)
            else:
                print(f"Skipping VM {vm.name}, powered off or invalid state.")
        
        # Define headers for VM info
        info_headers = [
            "VM", "Powerstate", "Template", "DNS Name", "CPUs", "Memory", "Total disk capacity MiB", "NICs", "Disks", 
            "Host", "OS according to the configuration file", "OS according to the VMware Tools", 
            "VI SDK API Version", "Primary IP Address", "VM ID", "VM UUID", 
            "VI SDK Server type", "VI SDK Server", "VI SDK UUID"
        ]
        
        # Define headers for VM network
        network_headers = ["VM", "Network", "IPv4 Address", "IPv6 Address", "Switch", "Mac Address"]
        
        # Define headers for VM CPU
        cpu_headers = ["VM", "CPUs", "Sockets", "Reservation"]
        
        # Define headers for VM memory
        memory_headers = ["VM", "Size MiB", "Reservation"]
        
        # Define headers for VM disk
        disk_headers = ["VM", "Disk", "Disk Key", "Disk Path", "Capacity MiB"]
        
        # Define headers for VM partition
        partition_headers = ["VM", "Disk Key", "Disk", "Capacity MiB", "Free MiB"]
        
        # Define headers for source
        source_headers = ["Name", "API version", "Vendor", "VI SDK UUID"]
        
        # Print information about duplicate UUIDs if any were found
        if duplicate_uuids:
            print("\nThe following UUIDs were skipped as duplicates, and only the first VM with each UUID was exported:")
            for uuid, vm_names in duplicate_uuids.items():
                print(f"  UUID: {uuid}")
                print(f"    Skipped VMs: {', '.join(vm_names)}")
        
        # Define headers for VM tools
        tools_headers = ["VM", "Tools"]
        
        # Define headers for host
        host_headers = ["Host", "# CPU", "# Cores", "# Memory", "# NICs", "Vendor", "Model", "Object ID", "UUID", "VI SDK UUID"]
        
        # Define headers for host NIC
        nic_headers = ["Host", "Network Device", "MAC", "Switch"]
        
        # Define headers for host VMkernel
        vmk_headers = ["Host", "Mac Address", "IP Address", "IP 6 Address", "Subnet mask"]
        
        # Define headers for virtual switch
        vswitch_headers = ["Host", "Datacenter", "Cluster", "Switch", "# Ports", "Free Ports", 
                          "Promiscuous Mode", "Mac Changes", "Forged Transmits", "Traffic Shaping", 
                          "Width", "Peak", "Burst", "Policy", "Reverse Policy", "Notify Switch", 
                          "Rolling Order", "Offload", "TSO", "Zero Copy Xmit", "MTU", 
                          "VI SDK Server", "VI SDK UUID"]
        
        # Define headers for distributed virtual switch
        dvswitch_headers = ["Switch", "Datacenter", "Name", "Vendor", "Version", "Description", 
                           "Created", "Host members", "Max Ports", "# Ports", "# VMs", 
                           "In Traffic Shaping", "In Avg", "In Peak", "In Burst", 
                           "Out Traffic Shaping", "Out Avg", "Out Peak", "Out Burst", 
                           "CDP Type", "CDP Operation", "LACP Name", "LACP Mode", 
                           "LACP Load Balance Alg.", "Max MTU", "Contact", "Admin Name", 
                           "Object ID", "com.vrlcm.snapshot", "Datastore", "Tier", 
                           "VI SDK Server", "VI SDK UUID"]
                           
        # Define headers for port groups
        port_headers = ["Port Group", "Switch", "VLAN"]
        
        # Define headers for distributed virtual ports
        dvport_headers = ["Port", "Switch", "VLAN"]
        
        # Define headers for performance metrics
        if export_statistics and perf_collector:
            performance_headers = perf_collector.get_metric_headers()
        else:
            performance_headers = ["VM Name", "VM UUID", "Timestamp"]  # Minimal headers for empty file
        
        # Write VM info to CSV
        success = write_csv_file(info_file, info_headers, vm_info_list)
        if success:
            print(f"Exported {len(vm_info_list)} VMs to {info_file}")
        
        # Write VM network data to CSV
        success = write_csv_file(network_file, network_headers, vm_network_list)
        if success:
            print(f"Exported network data for {len(vm_network_list)} VM NICs to {network_file}")
      
        # Write VM CPU data to CSV
        success = write_csv_file(vcpu_file, cpu_headers, vm_cpu_list)
        if success:
            print(f"Exported CPU data for {len(vm_cpu_list)} VMs to {vcpu_file}")
        
        # Write VM memory data to CSV
        success = write_csv_file(memory_file, memory_headers, vm_memory_list)
        if success:
            print(f"Exported memory data for {len(vm_memory_list)} VMs to {memory_file}")

        # Write VM disk data to CSV
        success = write_csv_file(disk_file, disk_headers, vm_disk_list)
        if success:
            print(f"Exported disk data for {len(vm_disk_list)} VM disks to {disk_file}")
     
        # Write VM partition data to CSV
        success = write_csv_file(partition_file, partition_headers, vm_partition_list)
        if success:
            print(f"Exported partition data for {len(vm_partition_list)} VM partitions to {partition_file}")

        # Write source data to CSV
        with open(vsource_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=source_headers)
            writer.writeheader()
            writer.writerow(source_properties)
        print(f"Exported source data to {vsource_file}")
        
        # Write VM tools data to CSV
        success = write_csv_file(vtools_file, tools_headers, vm_tools_list)
        if success:
            print(f"Exported tools data for {len(vm_tools_list)} VMs to {vtools_file}")

        # Write host data to CSV
        success = write_csv_file(vhost_file, host_headers, host_properties_list)
        if success:
            print(f"Exported host data for {len(host_properties_list)} hosts to {vhost_file}")

        # Write host NIC data to CSV
        success = write_csv_file(vnic_file, nic_headers, host_nic_properties_list)
        if success:
            print(f"Exported NIC data for {len(host_nic_properties_list)} host NICs to {vnic_file}")
 
        # Write host VMkernel data to CSV
        success = write_csv_file(sc_vmk_file, vmk_headers, host_vmk_properties_list)
        if success:
            print(f"Exported VMkernel data for {len(host_vmk_properties_list)} host VMKs to {sc_vmk_file}")

        # Write virtual switch data to CSV
        success = write_csv_file(vswitch_file, vswitch_headers, vswitch_properties_list)
        if success:
            print(f"Exported virtual switch data for {len(vswitch_properties_list)} virtual switches to {vswitch_file}")

        # Write distributed virtual switch data to CSV
        success = write_csv_file(dvswitch_file, dvswitch_headers, dvswitch_properties_list)
        if success:
            print(f"Exported distributed virtual switch data for {len(dvswitch_properties_list)} distributed virtual switches to {dvswitch_file}")

        # Write port group data to CSV
        success = write_csv_file(vport_file, port_headers, port_properties_list)
        if success:
            print(f"Exported port group data for {len(port_properties_list)} port groups to {vport_file}")

        # Write distributed virtual port data to CSV
        success = write_csv_file(dvport_file, dvport_headers, dvport_properties_list)
        if success:
            print(f"Exported distributed virtual port data for {len(dvport_properties_list)} port groups to {dvport_file}")
        
        # Write performance metrics data to CSV
        success = write_csv_file(performance_file, performance_headers, performance_properties_list)
        if success:
            if export_statistics:
                print(f"Exported performance metrics data for {len(performance_properties_list)} VMs to {performance_file}")
            else:
                print(f"Created empty performance file (statistics collection disabled): {performance_file}")
        
        # Create a zip file containing all CSV files
        zip_filename = "vcexport.zip"
        csv_files = [info_file, network_file, vcpu_file, memory_file, disk_file, 
                    partition_file, vsource_file, vtools_file, vhost_file, vnic_file, 
                    sc_vmk_file, vswitch_file, dvswitch_file, vport_file, dvport_file, 
                    performance_file]
        
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for file in csv_files:
                zipf.write(file, os.path.basename(file))  # Add file to zip root, not in folder
        
        print(f"All CSV files have been zipped to {zip_filename}")

        if purge_csv is True:
            print("Purging CSV files, leaving only the ZIP.")
            for file in csv_files:
                os.remove(file)
        
        return info_file, network_file, vcpu_file, memory_file, disk_file, partition_file, vsource_file, vtools_file, vhost_file, vnic_file, sc_vmk_file, vswitch_file, dvswitch_file, vport_file, dvport_file
    
    finally:
        # Always clean up the container view
        if container_view:
            container_view.Destroy()


if __name__ == "__main__":

    # Minimum Python version check
    if sys.version_info < (3, 10):
        print("Python 3.10 or higher is required to run this script.")
        print(f"Current Python version: {sys.version}")
        sys.exit(1)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Export VM data from vCenter to CSV files in RVTools format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Environment Variables Required:
    EXP_VCENTER_HOST      vCenter FQDN (do not include https://)
    EXP_VCENTER_USER      vCenter username
    EXP_VCENTER_PASSWORD  vCenter password

    Performance Collection Examples:
    python vcexport.py                          # Default: 60 minutes
    python vcexport.py --perf-interval 240     # 4 hours of data
    python vcexport.py --perf-interval 1440    # 24 hours of data
    python vcexport.py --no-statistics         # Skip performance collection
        """
    )
    
    parser.add_argument(
        "--no-statistics",
        action="store_false",
        dest="export_statistics",
        default=True,
        help="Skip performance statistics collection"
    )
    
    parser.add_argument(
        "--perf-interval",
        type=int,
        default=60,
        help="Performance collection time interval in minutes (default: 60). Sampling period is automatically determined."
    )
    
    args = parser.parse_args()
    
    # Get vCenter details from environment variables
    vcenter_host = os.environ.get("EXP_VCENTER_HOST")
    vcenter_user = os.environ.get("EXP_VCENTER_USER")
    vcenter_password = os.environ.get("EXP_VCENTER_PASSWORD")
    disable_ssl_verification = os.environ.get("EXP_DISABLE_SSL_VERIFICATION", "false").lower() == "true"

    # Validate environment variables
    if not all([vcenter_host, vcenter_user, vcenter_password]):
        print("Error: Please set EXP_VCENTER_HOST, EXP_VCENTER_USER, and EXP_VCENTER_PASSWORD environment variables")
        exit(1)

    # Connect to vCenter
    si = connect_to_vcenter(
        host=vcenter_host,
        user=vcenter_user,
        password=vcenter_password,
        disable_ssl_verification=disable_ssl_verification
    )
    
    # Export VM data to CSV
    if si:
        print("Starting export process, this will take some time...")
        export_vm_data(
            si, 
            max_count=None, 
            purge_csv=True,
            export_statistics=args.export_statistics,
            perf_interval=args.perf_interval
        )