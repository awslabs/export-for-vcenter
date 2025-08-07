#!/usr/bin/env python
"""
Main orchestrator module for vCenter data export.
"""
from pyVmomi import vim
from connection import VCenterConnection
from collectors import VMCollector, HostCollector, NetworkCollector, PerformanceCollector
from exporters import CSVExporter


class VCenterOrchestrator:
    """
    Main class to orchestrate vCenter data collection and export.
    """
    
    def __init__(self, host, user, password, port=443, disable_ssl_verification=False):
        """
        Initialize the vCenter exporter.
        
        Args:
            host (str): The vCenter server hostname or IP address
            user (str): The username to authenticate with
            password (str): The password to authenticate with
            port (int): The port to connect on (default: 443)
            disable_ssl_verification (bool): Whether to disable SSL certificate verification
        """
        self.connection = VCenterConnection(host, user, password, port, disable_ssl_verification)
        self.service_instance = None
        self.content = None
        self.container = None
        
        # Collectors
        self.vm_collector = None
        self.host_collector = None
        self.network_collector = None
        self.performance_collector = None
        self.csv_exporter = CSVExporter()
    
    def connect(self):
        """
        Connect to vCenter and initialize collectors.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        self.service_instance = self.connection.connect()
        if not self.service_instance:
            return False
        
        self.content = self.connection.get_content()
        self.container = self.connection.get_container()
        
        # Initialize collectors
        self.vm_collector = VMCollector(self.service_instance, self.content, self.container)
        self.host_collector = HostCollector(self.content, self.container)
        self.network_collector = NetworkCollector(self.content, self.container)
        self.performance_collector = PerformanceCollector(self.service_instance)
        
        return True
    
    def get_source_properties(self):
        """
        Extract source properties from the service instance.
        
        Returns:
            dict: Dictionary with source properties
        """
        about_info = self.content.about
        
        return {
            "Name": about_info.name if hasattr(about_info, "name") else "",
            "API version": about_info.apiVersion if hasattr(about_info, "apiVersion") else "",
            "Vendor": about_info.vendor if hasattr(about_info, "vendor") else "",
            "VI SDK UUID": about_info.instanceUuid if hasattr(about_info, "instanceUuid") else ""
        }
    
    def collect_vm_data(self, max_count=None):
        """
        Collect all VM-related data.
        
        Args:
            max_count (int, optional): Maximum number of VMs to process
            
        Returns:
            dict: Dictionary containing all VM data
        """
        # Get all VMs
        container_view = self.content.viewManager.CreateContainerView(
            self.container, [vim.VirtualMachine], True
        )
        
        vm_data = {
            "vm_info": [],
            "vm_network": [],
            "vm_cpu": [],
            "vm_memory": [],
            "vm_disk": [],
            "vm_partition": [],
            "vm_tools": []
        }
        
        try:
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
            
            # Process VMs
            for i, vm in enumerate(vms_to_process):
                # Skip VMs that match patterns in skip list
                if self.vm_collector._should_skip_vm(vm):
                    continue
                
                print(f"Processing VM {i+1} of {total_vms}: {vm.name}")
                
                # Get VM info properties
                vm_properties = self.vm_collector.get_vm_properties(vm)
                if vm_properties:  # Skip if None (powered off VM)
                    # Skip VMs without a primary IP address
                    if not vm_properties.get("Primary IP Address"):
                        print(f"Skipping VM {vm.name} (no primary IP address)")
                        continue

                    # Check for duplicate UUID
                    if self.vm_collector._is_duplicate_uuid(vm_properties):
                        continue
                    
                    # Get VM network properties
                    vm_network_properties = self.vm_collector.get_vm_network_properties(vm)
                    if vm_network_properties is None:
                        print(f"Skipping VM {vm.name} (no network properties found)")
                        continue

                    vm_data["vm_network"].extend(vm_network_properties)

                    # Moved this below vm_network_properties, if the properties returns nothing we want to skip the VM
                    vm_data["vm_info"].append(vm_properties)
                    
                    # Get VM CPU properties
                    vm_cpu_properties = self.vm_collector.get_vm_cpu_properties(vm)
                    vm_data["vm_cpu"].append(vm_cpu_properties)
                    
                    # Get VM memory properties
                    vm_memory_properties = self.vm_collector.get_vm_memory_properties(vm)
                    vm_data["vm_memory"].append(vm_memory_properties)
                    
                    # Get VM disk properties
                    vm_disk_properties = self.vm_collector.get_vm_disk_properties(vm)
                    vm_data["vm_disk"].extend(vm_disk_properties)
                    
                    # Get VM partition properties
                    vm_partition_properties = self.vm_collector.get_vm_partition_properties(vm)
                    vm_data["vm_partition"].extend(vm_partition_properties)
                    
                    # Get VM tools properties
                    vm_tools_properties = self.vm_collector.get_vm_tools_properties(vm)
                    vm_data["vm_tools"].append(vm_tools_properties)
                else:
                    print(f"Skipping VM {vm.name}, powered off or invalid state.")
            
            # Print duplicate UUIDs summary
            self.vm_collector.print_duplicate_uuids_summary()
            
        finally:
            # Always clean up the container view
            if container_view:
                container_view.Destroy()
        
        return vm_data
    
    def collect_all_data(self, max_count=None, export_statistics=True, perf_interval=60):
        """
        Collect all data from vCenter.
        
        Args:
            max_count (int, optional): Maximum number of VMs to process
            export_statistics (bool): Whether to collect performance statistics
            perf_interval (int): Performance collection time interval in minutes
            
        Returns:
            dict: Dictionary containing all collected data
        """
        print("Starting data collection...")
        
        # Collect source properties
        print("Getting source properties...")
        source_properties = self.get_source_properties()
        
        # Collect host properties
        print("Getting host properties...")
        host_properties_list = self.host_collector.get_host_properties()
        
        # Collect host NIC properties
        print("Getting host NIC properties...")
        host_nic_properties_list = self.host_collector.get_host_nic_properties()
        
        # Collect host VMkernel properties
        print("Getting host VMKernel properties...")
        host_vmk_properties_list = self.host_collector.get_host_vmk_properties()
        
        # Collect virtual switch properties
        print("Getting virtual switch properties...")
        vswitch_properties_list = self.network_collector.get_vm_vswitch_properties()
        
        # Collect distributed virtual switch properties
        print("Getting distributed virtual switch properties...")
        dvswitch_properties_list = self.network_collector.get_vm_dvswitch_properties()
        
        # Collect port group properties
        print("Getting port group properties...")
        port_properties_list = self.network_collector.get_vm_port_properties()
        
        # Collect distributed virtual port properties
        print("Getting distributed port group properties...")
        dvport_properties_list = self.network_collector.get_vm_dvport_properties()
        
        # Collect performance metrics
        if export_statistics:
            print("Getting performance metric properties...")
            performance_properties_list = self.performance_collector.get_performance_properties(
                self.content, 
                self.container, 
                interval_mins=perf_interval
            )
        else:
            print("Skipping performance statistics collection (--no-statistics specified)")
            performance_properties_list = []
        
        # Collect VM data
        vm_data = self.collect_vm_data(max_count)
        
        # Combine all data
        all_data = {
            "source": source_properties,
            "host": host_properties_list,
            "host_nic": host_nic_properties_list,
            "host_vmk": host_vmk_properties_list,
            "vswitch": vswitch_properties_list,
            "dvswitch": dvswitch_properties_list,
            "vport": port_properties_list,
            "dvport": dvport_properties_list,
            "performance": performance_properties_list,
            **vm_data  # Unpack VM data
        }
        
        return all_data
    
    def export_data(self, max_count=None, purge_csv=True, export_statistics=True, perf_interval=60):
        """
        Export all data to CSV files and create zip archive.
        
        Args:
            max_count (int, optional): Maximum number of VMs to process
            purge_csv (bool): Whether to delete CSV files after zipping
            export_statistics (bool): Whether to collect performance statistics
            perf_interval (int): Performance collection time interval in minutes
            
        Returns:
            str: Path to the created zip file
        """
        if not self.service_instance:
            print("No valid vCenter connection")
            return None
        
        # Collect all data
        all_data = self.collect_all_data(max_count, export_statistics, perf_interval)
        
        # Export to CSV files
        print("Exporting data to CSV files...")
        created_files = self.csv_exporter.export_all_data(
            all_data, 
            export_statistics, 
            self.performance_collector if export_statistics else None
        )
        
        # Create zip archive
        zip_file = self.csv_exporter.create_zip_archive(purge_csv=purge_csv)
        
        return zip_file
    
    def disconnect(self):
        """Disconnect from vCenter server."""
        if self.connection:
            self.connection.disconnect()