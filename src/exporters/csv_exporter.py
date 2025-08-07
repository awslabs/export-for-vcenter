#!/usr/bin/env python
"""
Module for handling CSV file operations and data export.
"""
import csv
import os
import zipfile
from datetime import datetime


class CSVExporter:
    """
    Class to handle CSV file creation and export operations.
    """
    
    def __init__(self, output_dir="."):
        """
        Initialize the CSV exporter.
        
        Args:
            output_dir (str): Directory to save CSV files
        """
        self.output_dir = output_dir
        self.csv_files = []
    
    def write_csv_file(self, filename, headers, data_list):
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
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                for data in data_list:
                    writer.writerow(data)
            
            # Track created files for zipping
            self.csv_files.append(filename)
            return True

        except Exception as e:
            print(f"Error writing CSV file {filename}: {str(e)}")
            return False
    
    def write_source_csv(self, filename, headers, source_properties):
        """
        Write source data to CSV file (single row).
        
        Args:
            filename (str): Path to the output CSV file
            headers (list): List of column headers
            source_properties (dict): Dictionary containing source data
            
        Returns:
            bool: True on success, False on fail
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                writer.writerow(source_properties)
            
            # Track created files for zipping
            self.csv_files.append(filename)
            return True

        except Exception as e:
            print(f"Error writing source CSV file {filename}: {str(e)}")
            return False
    
    def create_zip_archive(self, zip_filename="vcexport.zip", purge_csv=True):
        """
        Create a zip file containing all CSV files.
        
        Args:
            zip_filename (str): Name of the zip file to create
            purge_csv (bool): Whether to delete CSV files after zipping
            
        Returns:
            str: Path to the created zip file
        """
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in self.csv_files:
                    if os.path.exists(file):
                        zipf.write(file, os.path.basename(file))  # Add file to zip root
            
            print(f"All CSV files have been zipped to {zip_filename}")

            if purge_csv:
                print("Purging CSV files, leaving only the ZIP.")
                for file in self.csv_files:
                    if os.path.exists(file):
                        os.remove(file)
            
            return zip_filename
        
        except Exception as e:
            print(f"Error creating zip archive: {str(e)}")
            return None
    
    def get_default_filenames(self):
        """
        Get default filenames for all CSV exports.
        
        Returns:
            dict: Dictionary of export types to filenames
        """
        return {
            "info": "RVTools_tabvInfo.csv",
            "network": "RVTools_tabvNetwork.csv",
            "vcpu": "RVTools_tabvCPU.csv",
            "memory": "RVTools_tabvMemory.csv",
            "disk": "RVTools_tabvDisk.csv",
            "partition": "RVTools_tabvPartition.csv",
            "vsource": "RVTools_tabvSource.csv",
            "vtools": "RVTools_tabvTools.csv",
            "vhost": "RVTools_tabvHost.csv",
            "vnic": "RVTools_tabvNIC.csv",
            "sc_vmk": "RVTools_tabvSC_VMK.csv",
            "vswitch": "RVTools_tabvSwitch.csv",
            "dvswitch": "RVTools_tabdvSwitch.csv",
            "vport": "RVTools_tabvPort.csv",
            "dvport": "RVTools_tabdvPort.csv",
            "performance": "vcexport_tabvPerformance.csv"
        }
    
    def get_csv_headers(self):
        """
        Get predefined CSV headers for all export types.
        
        Returns:
            dict: Dictionary of export types to header lists
        """
        return {
            "info": [
                "VM", "Powerstate", "Template", "DNS Name", "CPUs", "Memory", "Total disk capacity MiB", 
                "NICs", "Disks", "Host", "OS according to the configuration file", 
                "OS according to the VMware Tools", "VI SDK API Version", "Primary IP Address", 
                "VM ID", "VM UUID", "VI SDK Server type", "VI SDK Server", "VI SDK UUID"
            ],
            "network": ["VM", "Network", "IPv4 Address", "IPv6 Address", "Switch", "Mac Address"],
            "vcpu": ["VM", "CPUs", "Sockets", "Reservation"],
            "memory": ["VM", "Size MiB", "Reservation"],
            "disk": ["VM", "Disk", "Disk Key", "Disk Path", "Capacity MiB"],
            "partition": ["VM", "Disk Key", "Disk", "Capacity MiB", "Free MiB"],
            "vsource": ["Name", "API version", "Vendor", "VI SDK UUID"],
            "vtools": ["VM", "Tools"],
            "vhost": ["Host", "# CPU", "# Cores", "# Memory", "# NICs", "Vendor", "Model", "Object ID", "UUID", "VI SDK UUID"],
            "vnic": ["Host", "Network Device", "MAC", "Switch"],
            "sc_vmk": ["Host", "Mac Address", "IP Address", "IP 6 Address", "Subnet mask"],
            "vswitch": [
                "Host", "Datacenter", "Cluster", "Switch", "# Ports", "Free Ports", 
                "Promiscuous Mode", "Mac Changes", "Forged Transmits", "Traffic Shaping", 
                "Width", "Peak", "Burst", "Policy", "Reverse Policy", "Notify Switch", 
                "Rolling Order", "Offload", "TSO", "Zero Copy Xmit", "MTU", 
                "VI SDK Server", "VI SDK UUID"
            ],
            "dvswitch": [
                "Switch", "Datacenter", "Name", "Vendor", "Version", "Description", 
                "Created", "Host members", "Max Ports", "# Ports", "# VMs", 
                "In Traffic Shaping", "In Avg", "In Peak", "In Burst", 
                "Out Traffic Shaping", "Out Avg", "Out Peak", "Out Burst", 
                "CDP Type", "CDP Operation", "LACP Name", "LACP Mode", 
                "LACP Load Balance Alg.", "Max MTU", "Contact", "Admin Name", 
                "Object ID", "com.vrlcm.snapshot", "Datastore", "Tier", 
                "VI SDK Server", "VI SDK UUID"
            ],
            "vport": ["Port Group", "Switch", "VLAN"],
            "dvport": ["Port", "Switch", "VLAN"],
            "performance": ["VM Name", "VM UUID", "Timestamp"]  # Default minimal headers
        }
    
    def export_all_data(self, data_dict, export_statistics=True, perf_collector=None):
        """
        Export all collected data to CSV files.
        
        Args:
            data_dict (dict): Dictionary containing all collected data
            export_statistics (bool): Whether to export performance statistics
            perf_collector: Performance collector instance for headers
            
        Returns:
            list: List of created CSV file paths
        """
        filenames = self.get_default_filenames()
        headers = self.get_csv_headers()
        
        # Update performance headers if collector is available
        if export_statistics and perf_collector:
            headers["performance"] = perf_collector.get_metric_headers()
        
        created_files = []
        
        # Export VM info
        if self.write_csv_file(filenames["info"], headers["info"], data_dict.get("vm_info", [])):
            print(f"Exported {len(data_dict.get('vm_info', []))} VMs to {filenames['info']}")
            created_files.append(filenames["info"])
        
        # Export VM network data
        if self.write_csv_file(filenames["network"], headers["network"], data_dict.get("vm_network", [])):
            print(f"Exported network data for {len(data_dict.get('vm_network', []))} VM NICs to {filenames['network']}")
            created_files.append(filenames["network"])
        
        # Export VM CPU data
        if self.write_csv_file(filenames["vcpu"], headers["vcpu"], data_dict.get("vm_cpu", [])):
            print(f"Exported CPU data for {len(data_dict.get('vm_cpu', []))} VMs to {filenames['vcpu']}")
            created_files.append(filenames["vcpu"])
        
        # Export VM memory data
        if self.write_csv_file(filenames["memory"], headers["memory"], data_dict.get("vm_memory", [])):
            print(f"Exported memory data for {len(data_dict.get('vm_memory', []))} VMs to {filenames['memory']}")
            created_files.append(filenames["memory"])
        
        # Export VM disk data
        if self.write_csv_file(filenames["disk"], headers["disk"], data_dict.get("vm_disk", [])):
            print(f"Exported disk data for {len(data_dict.get('vm_disk', []))} VM disks to {filenames['disk']}")
            created_files.append(filenames["disk"])
        
        # Export VM partition data
        if self.write_csv_file(filenames["partition"], headers["partition"], data_dict.get("vm_partition", [])):
            print(f"Exported partition data for {len(data_dict.get('vm_partition', []))} VM partitions to {filenames['partition']}")
            created_files.append(filenames["partition"])
        
        # Export source data
        if self.write_source_csv(filenames["vsource"], headers["vsource"], data_dict.get("source", {})):
            print(f"Exported source data to {filenames['vsource']}")
            created_files.append(filenames["vsource"])
        
        # Export VM tools data
        if self.write_csv_file(filenames["vtools"], headers["vtools"], data_dict.get("vm_tools", [])):
            print(f"Exported tools data for {len(data_dict.get('vm_tools', []))} VMs to {filenames['vtools']}")
            created_files.append(filenames["vtools"])
        
        # Export host data
        if self.write_csv_file(filenames["vhost"], headers["vhost"], data_dict.get("host", [])):
            print(f"Exported host data for {len(data_dict.get('host', []))} hosts to {filenames['vhost']}")
            created_files.append(filenames["vhost"])
        
        # Export host NIC data
        if self.write_csv_file(filenames["vnic"], headers["vnic"], data_dict.get("host_nic", [])):
            print(f"Exported NIC data for {len(data_dict.get('host_nic', []))} host NICs to {filenames['vnic']}")
            created_files.append(filenames["vnic"])
        
        # Export host VMkernel data
        if self.write_csv_file(filenames["sc_vmk"], headers["sc_vmk"], data_dict.get("host_vmk", [])):
            print(f"Exported VMkernel data for {len(data_dict.get('host_vmk', []))} host VMKs to {filenames['sc_vmk']}")
            created_files.append(filenames["sc_vmk"])
        
        # Export virtual switch data
        if self.write_csv_file(filenames["vswitch"], headers["vswitch"], data_dict.get("vswitch", [])):
            print(f"Exported virtual switch data for {len(data_dict.get('vswitch', []))} virtual switches to {filenames['vswitch']}")
            created_files.append(filenames["vswitch"])
        
        # Export distributed virtual switch data
        if self.write_csv_file(filenames["dvswitch"], headers["dvswitch"], data_dict.get("dvswitch", [])):
            print(f"Exported distributed virtual switch data for {len(data_dict.get('dvswitch', []))} distributed virtual switches to {filenames['dvswitch']}")
            created_files.append(filenames["dvswitch"])
        
        # Export port group data
        if self.write_csv_file(filenames["vport"], headers["vport"], data_dict.get("vport", [])):
            print(f"Exported port group data for {len(data_dict.get('vport', []))} port groups to {filenames['vport']}")
            created_files.append(filenames["vport"])
        
        # Export distributed virtual port data
        if self.write_csv_file(filenames["dvport"], headers["dvport"], data_dict.get("dvport", [])):
            print(f"Exported distributed virtual port data for {len(data_dict.get('dvport', []))} port groups to {filenames['dvport']}")
            created_files.append(filenames["dvport"])
        
        # Export performance metrics data
        if self.write_csv_file(filenames["performance"], headers["performance"], data_dict.get("performance", [])):
            if export_statistics:
                print(f"Exported performance metrics data for {len(data_dict.get('performance', []))} VMs to {filenames['performance']}")
            else:
                print(f"Created empty performance file (statistics collection disabled): {filenames['performance']}")
            created_files.append(filenames["performance"])
        
        return created_files