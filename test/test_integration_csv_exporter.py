#!/usr/bin/env python
"""
Integration tests for csv_exporter.py module.
Tests the CSVExporter class with real file operations and temporary directories.
"""

import pytest
import os
import csv
import zipfile
import tempfile
import shutil
from src.exporters.csv_exporter import CSVExporter


class TestCSVExporterIntegration:
    """Integration test class for CSVExporter"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup after test
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def csv_exporter(self, temp_dir):
        """Create CSVExporter instance with temporary directory"""
        return CSVExporter(output_dir=temp_dir)
    
    @pytest.fixture
    def comprehensive_test_data(self):
        """Comprehensive test data covering all export types"""
        return {
            "vm_info": [
                {
                    "VM": "test-vm-1",
                    "Powerstate": "poweredOn",
                    "Template": "False",
                    "DNS Name": "test-vm-1.example.com",
                    "CPUs": "2",
                    "Memory": "4096",
                    "Total disk capacity MiB": "20480",
                    "NICs": "1",
                    "Disks": "1",
                    "Host": "test-host-1",
                    "OS according to the configuration file": "ubuntu64Guest",
                    "OS according to the VMware Tools": "Ubuntu Linux (64-bit)",
                    "VI SDK API Version": "7.0",
                    "Primary IP Address": "192.168.1.100",
                    "VM ID": "vm-123",
                    "VM UUID": "test-uuid-123",
                    "VI SDK Server type": "VirtualCenter",
                    "VI SDK Server": "vcenter.example.com",
                    "VI SDK UUID": "vcenter-uuid-123"
                },
                {
                    "VM": "test-vm-2",
                    "Powerstate": "poweredOn",
                    "Template": "False",
                    "DNS Name": "test-vm-2.example.com",
                    "CPUs": "4",
                    "Memory": "8192",
                    "Total disk capacity MiB": "40960",
                    "NICs": "2",
                    "Disks": "2",
                    "Host": "test-host-2",
                    "OS according to the configuration file": "windows9Server64Guest",
                    "OS according to the VMware Tools": "Microsoft Windows Server 2019 (64-bit)",
                    "VI SDK API Version": "7.0",
                    "Primary IP Address": "192.168.1.101",
                    "VM ID": "vm-456",
                    "VM UUID": "test-uuid-456",
                    "VI SDK Server type": "VirtualCenter",
                    "VI SDK Server": "vcenter.example.com",
                    "VI SDK UUID": "vcenter-uuid-123"
                }
            ],
            "vm_network": [
                {
                    "VM": "test-vm-1",
                    "Network": "VM Network",
                    "IPv4 Address": "192.168.1.100",
                    "IPv6 Address": "",
                    "Switch": "vSwitch0",
                    "Mac Address": "00:50:56:12:34:56"
                },
                {
                    "VM": "test-vm-2",
                    "Network": "Production Network",
                    "IPv4 Address": "192.168.1.101",
                    "IPv6 Address": "2001:db8::1",
                    "Switch": "dvSwitch-1",
                    "Mac Address": "00:50:56:78:90:ab"
                }
            ],
            "vm_cpu": [
                {"VM": "test-vm-1", "CPUs": "2", "Sockets": "1", "Reservation": "0"},
                {"VM": "test-vm-2", "CPUs": "4", "Sockets": "2", "Reservation": "1000"}
            ],
            "vm_memory": [
                {"VM": "test-vm-1", "Size MiB": "4096", "Reservation": "0"},
                {"VM": "test-vm-2", "Size MiB": "8192", "Reservation": "2048"}
            ],
            "vm_disk": [
                {"VM": "test-vm-1", "Disk": "Hard disk 1", "Disk Key": "2000", "Disk Path": "[datastore1] test-vm-1/test-vm-1.vmdk", "Capacity MiB": "20480"},
                {"VM": "test-vm-2", "Disk": "Hard disk 1", "Disk Key": "2000", "Disk Path": "[datastore2] test-vm-2/test-vm-2.vmdk", "Capacity MiB": "40960"}
            ],
            "vm_partition": [
                {"VM": "test-vm-1", "Disk Key": "2000", "Disk": "Hard disk 1", "Capacity MiB": "20480", "Free MiB": "15000"},
                {"VM": "test-vm-2", "Disk Key": "2000", "Disk": "Hard disk 1", "Capacity MiB": "40960", "Free MiB": "30000"}
            ],
            "source": {
                "Name": "vcenter.example.com",
                "API version": "7.0",
                "Vendor": "VMware, Inc.",
                "VI SDK UUID": "vcenter-uuid-123"
            },
            "vm_tools": [
                {"VM": "test-vm-1", "Tools": "toolsOk"},
                {"VM": "test-vm-2", "Tools": "toolsOld"}
            ],
            "host": [
                {
                    "Host": "test-host-1",
                    "# CPU": "16",
                    "# Cores": "8",
                    "# Memory": "65536",
                    "# NICs": "4",
                    "Vendor": "Dell Inc.",
                    "Model": "PowerEdge R640",
                    "Object ID": "host-123",
                    "UUID": "host-uuid-123",
                    "VI SDK UUID": "vcenter-uuid-123"
                }
            ],
            "host_nic": [
                {"Host": "test-host-1", "Network Device": "vmnic0", "MAC": "aa:bb:cc:dd:ee:ff", "Switch": "vSwitch0"}
            ],
            "host_vmk": [
                {"Host": "test-host-1", "Mac Address": "aa:bb:cc:dd:ee:01", "IP Address": "192.168.1.10", "IP 6 Address": "", "Subnet mask": "255.255.255.0"}
            ],
            "vswitch": [
                {
                    "Host": "test-host-1",
                    "Datacenter": "Datacenter1",
                    "Cluster": "Cluster1",
                    "Switch": "vSwitch0",
                    "# Ports": "128",
                    "Free Ports": "120",
                    "Promiscuous Mode": "False",
                    "Mac Changes": "True",
                    "Forged Transmits": "True",
                    "Traffic Shaping": "False",
                    "Width": "",
                    "Peak": "",
                    "Burst": "",
                    "Policy": "loadbalance_srcid",
                    "Reverse Policy": "True",
                    "Notify Switch": "True",
                    "Rolling Order": "False",
                    "Offload": "True",
                    "TSO": "True",
                    "Zero Copy Xmit": "True",
                    "MTU": "1500",
                    "VI SDK Server": "vcenter.example.com",
                    "VI SDK UUID": "vcenter-uuid-123"
                }
            ],
            "dvswitch": [
                {
                    "Switch": "dvSwitch-1",
                    "Datacenter": "Datacenter1",
                    "Name": "dvSwitch-1",
                    "Vendor": "VMware, Inc.",
                    "Version": "7.0.0",
                    "Description": "Distributed Switch",
                    "Created": "2024-01-01T00:00:00Z",
                    "Host members": "2",
                    "Max Ports": "1024",
                    "# Ports": "512",
                    "# VMs": "10",
                    "In Traffic Shaping": "False",
                    "In Avg": "",
                    "In Peak": "",
                    "In Burst": "",
                    "Out Traffic Shaping": "False",
                    "Out Avg": "",
                    "Out Peak": "",
                    "Out Burst": "",
                    "CDP Type": "lldp",
                    "CDP Operation": "listen",
                    "LACP Name": "",
                    "LACP Mode": "",
                    "LACP Load Balance Alg.": "",
                    "Max MTU": "9000",
                    "Contact": "admin@example.com",
                    "Admin Name": "Administrator",
                    "Object ID": "dvs-123",
                    "com.vrlcm.snapshot": "",
                    "Datastore": "",
                    "Tier": "",
                    "VI SDK Server": "vcenter.example.com",
                    "VI SDK UUID": "vcenter-uuid-123"
                }
            ],
            "vport": [
                {"Port Group": "VM Network", "Switch": "vSwitch0", "VLAN": "0"}
            ],
            "dvport": [
                {"Port": "Production Network", "Switch": "dvSwitch-1", "VLAN": "100"}
            ],
            "performance": [
                {
                    "VM Name": "test-vm-1",
                    "VM UUID": "test-uuid-123",
                    "Timestamp": "2024-01-01T12:00:00Z",
                    "maxCpuUsagePctDec": "0.75",
                    "avgCpuUsagePctDec": "0.45",
                    "maxRamUsagePctDec": "0.80",
                    "avgRamUtlPctDec": "0.60"
                },
                {
                    "VM Name": "test-vm-2",
                    "VM UUID": "test-uuid-456",
                    "Timestamp": "2024-01-01T12:00:00Z",
                    "maxCpuUsagePctDec": "0.65",
                    "avgCpuUsagePctDec": "0.35",
                    "maxRamUsagePctDec": "0.70",
                    "avgRamUtlPctDec": "0.50"
                }
            ]
        }
    
    @pytest.fixture
    def mock_perf_collector(self):
        """Mock performance collector for integration testing"""
        class MockPerfCollector:
            def get_metric_headers(self):
                return [
                    "VM Name", "VM UUID", "Timestamp", 
                    "maxCpuUsagePctDec", "avgCpuUsagePctDec",
                    "maxRamUsagePctDec", "avgRamUtlPctDec"
                ]
        return MockPerfCollector()

    def test_write_csv_file_creates_real_file(self, csv_exporter, temp_dir):
        """Test that write_csv_file creates a real CSV file with correct content"""
        filename = os.path.join(temp_dir, "test_vm_info.csv")
        headers = ["VM", "Powerstate", "CPUs"]
        data = [
            {"VM": "test-vm-1", "Powerstate": "poweredOn", "CPUs": "2"},
            {"VM": "test-vm-2", "Powerstate": "poweredOff", "CPUs": "4"}
        ]
        
        result = csv_exporter.write_csv_file(filename, headers, data)
        
        assert result is True
        assert os.path.exists(filename)
        assert filename in csv_exporter.csv_files
        
        # Verify file content
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        assert len(rows) == 2
        assert rows[0]["VM"] == "test-vm-1"
        assert rows[0]["Powerstate"] == "poweredOn"
        assert rows[0]["CPUs"] == "2"
        assert rows[1]["VM"] == "test-vm-2"
        assert rows[1]["Powerstate"] == "poweredOff"
        assert rows[1]["CPUs"] == "4"
    
    def test_write_csv_file_creates_nested_directories(self, csv_exporter, temp_dir):
        """Test that write_csv_file creates nested directories"""
        nested_path = os.path.join(temp_dir, "subdir", "nested", "test.csv")
        headers = ["VM", "Powerstate"]
        data = [{"VM": "test-vm", "Powerstate": "poweredOn"}]
        
        result = csv_exporter.write_csv_file(nested_path, headers, data)
        
        assert result is True
        assert os.path.exists(nested_path)
        assert os.path.exists(os.path.dirname(nested_path))
    
    def test_write_source_csv_creates_real_file(self, csv_exporter, temp_dir):
        """Test that write_source_csv creates a real CSV file with single row"""
        filename = os.path.join(temp_dir, "test_source.csv")
        headers = ["Name", "API version", "Vendor", "VI SDK UUID"]
        source_data = {
            "Name": "vcenter.example.com",
            "API version": "7.0",
            "Vendor": "VMware, Inc.",
            "VI SDK UUID": "vcenter-uuid-123"
        }
        
        result = csv_exporter.write_source_csv(filename, headers, source_data)
        
        assert result is True
        assert os.path.exists(filename)
        assert filename in csv_exporter.csv_files
        
        # Verify file content
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        assert len(rows) == 1
        assert rows[0]["Name"] == "vcenter.example.com"
        assert rows[0]["API version"] == "7.0"
        assert rows[0]["Vendor"] == "VMware, Inc."
        assert rows[0]["VI SDK UUID"] == "vcenter-uuid-123"
    
    def test_create_zip_archive_real_zip(self, csv_exporter, temp_dir):
        """Test creating a real zip archive with multiple CSV files"""
        # Create some test CSV files
        file1 = os.path.join(temp_dir, "file1.csv")
        file2 = os.path.join(temp_dir, "file2.csv")
        
        csv_exporter.write_csv_file(file1, ["VM"], [{"VM": "test-vm-1"}])
        csv_exporter.write_csv_file(file2, ["Host"], [{"Host": "test-host-1"}])
        
        zip_path = os.path.join(temp_dir, "test_export.zip")
        result = csv_exporter.create_zip_archive(zip_path, purge_csv=False)
        
        assert result == zip_path
        assert os.path.exists(zip_path)
        
        # Verify zip contents
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            file_list = zipf.namelist()
            assert "file1.csv" in file_list
            assert "file2.csv" in file_list
            
            # Verify file content in zip
            with zipf.open("file1.csv") as f:
                content = f.read().decode('utf-8')
                assert "VM" in content
                assert "test-vm-1" in content
    
    def test_create_zip_archive_with_purge(self, csv_exporter, temp_dir):
        """Test creating zip archive and purging original CSV files"""
        # Create test CSV files
        file1 = os.path.join(temp_dir, "file1.csv")
        file2 = os.path.join(temp_dir, "file2.csv")
        
        csv_exporter.write_csv_file(file1, ["VM"], [{"VM": "test-vm-1"}])
        csv_exporter.write_csv_file(file2, ["Host"], [{"Host": "test-host-1"}])
        
        # Verify files exist before zipping
        assert os.path.exists(file1)
        assert os.path.exists(file2)
        
        zip_path = os.path.join(temp_dir, "test_export.zip")
        result = csv_exporter.create_zip_archive(zip_path, purge_csv=True)
        
        assert result == zip_path
        assert os.path.exists(zip_path)
        
        # Verify original files were deleted
        assert not os.path.exists(file1)
        assert not os.path.exists(file2)
    
    def test_export_all_data_creates_all_files(self, temp_dir, comprehensive_test_data, mock_perf_collector):
        """Test that export_all_data creates all expected CSV files"""
        # Change to temp directory so files are created there
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            csv_exporter = CSVExporter()  # Use default output_dir
            created_files = csv_exporter.export_all_data(
                comprehensive_test_data,
                export_statistics=True,
                perf_collector=mock_perf_collector
            )
            
            # Verify all expected files were created
            expected_files = [
                "RVTools_tabvInfo.csv",
                "RVTools_tabvNetwork.csv",
                "RVTools_tabvCPU.csv",
                "RVTools_tabvMemory.csv",
                "RVTools_tabvDisk.csv",
                "RVTools_tabvPartition.csv",
                "RVTools_tabvSource.csv",
                "RVTools_tabvTools.csv",
                "RVTools_tabvHost.csv",
                "RVTools_tabvNIC.csv",
                "RVTools_tabvSC_VMK.csv",
                "RVTools_tabvSwitch.csv",
                "RVTools_tabdvSwitch.csv",
                "RVTools_tabvPort.csv",
                "RVTools_tabdvPort.csv",
                "vcexport_tabvPerformance.csv"
            ]
            
            for filename in expected_files:
                file_path = os.path.join(temp_dir, filename)
                assert os.path.exists(file_path), f"File {filename} was not created"
                assert filename in csv_exporter.csv_files
        finally:
            os.chdir(original_cwd)
    
    def test_export_all_data_file_contents(self, temp_dir, comprehensive_test_data, mock_perf_collector):
        """Test that exported files contain correct data"""
        # Change to temp directory so files are created there
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            csv_exporter = CSVExporter()
            csv_exporter.export_all_data(
                comprehensive_test_data,
                export_statistics=True,
                perf_collector=mock_perf_collector
            )
            
            # Test VM info file
            vm_info_path = os.path.join(temp_dir, "RVTools_tabvInfo.csv")
            with open(vm_info_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 2
            assert rows[0]["VM"] == "test-vm-1"
            assert rows[0]["CPUs"] == "2"
            assert rows[1]["VM"] == "test-vm-2"
            assert rows[1]["CPUs"] == "4"
            
            # Test source file (single row)
            source_path = os.path.join(temp_dir, "RVTools_tabvSource.csv")
            with open(source_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 1
            assert rows[0]["Name"] == "vcenter.example.com"
            assert rows[0]["API version"] == "7.0"
            
            # Test performance file with custom headers
            perf_path = os.path.join(temp_dir, "vcexport_tabvPerformance.csv")
            with open(perf_path, 'r') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                rows = list(reader)
            
            # Verify custom headers from mock performance collector
            expected_headers = mock_perf_collector.get_metric_headers()
            assert headers == expected_headers
            assert len(rows) == 2
            assert rows[0]["VM Name"] == "test-vm-1"
            assert rows[0]["maxCpuUsagePctDec"] == "0.75"
        finally:
            os.chdir(original_cwd)
    
    def test_export_all_data_empty_lists(self, temp_dir):
        """Test export with empty data lists creates empty files"""
        empty_data = {
            "vm_info": [],
            "vm_network": [],
            "source": {"Name": "test", "API version": "7.0", "Vendor": "VMware", "VI SDK UUID": "test-uuid"}
        }
        
        # Change to temp directory so files are created there
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            csv_exporter = CSVExporter()
            csv_exporter.export_all_data(empty_data, export_statistics=False)
            
            # Files should exist but be empty (except headers)
            vm_info_path = os.path.join(temp_dir, "RVTools_tabvInfo.csv")
            assert os.path.exists(vm_info_path)
            
            with open(vm_info_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 0  # No data rows, only headers
            
            # Source file should have one row
            source_path = os.path.join(temp_dir, "RVTools_tabvSource.csv")
            with open(source_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 1
        finally:
            os.chdir(original_cwd)
    
    def test_full_workflow_with_zip(self, csv_exporter, temp_dir, comprehensive_test_data, mock_perf_collector):
        """Test complete workflow: export data, create zip, verify contents"""
        # Export all data
        created_files = csv_exporter.export_all_data(
            comprehensive_test_data,
            export_statistics=True,
            perf_collector=mock_perf_collector
        )
        
        # Create zip archive
        zip_path = os.path.join(temp_dir, "vcexport.zip")
        result = csv_exporter.create_zip_archive(zip_path, purge_csv=True)
        
        assert result == zip_path
        assert os.path.exists(zip_path)
        
        # Verify all CSV files were deleted after zipping
        for filename in csv_exporter.get_default_filenames().values():
            file_path = os.path.join(temp_dir, filename)
            assert not os.path.exists(file_path), f"File {filename} should have been deleted"
        
        # Verify zip contains all expected files
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zip_contents = zipf.namelist()
            
            for filename in csv_exporter.get_default_filenames().values():
                assert filename in zip_contents, f"File {filename} missing from zip"
            
            # Verify content of a file in the zip
            with zipf.open("RVTools_tabvInfo.csv") as f:
                content = f.read().decode('utf-8')
                assert "test-vm-1" in content
                assert "test-vm-2" in content
    
    def test_unicode_and_special_characters(self, temp_dir):
        """Test handling of unicode and special characters in data"""
        unicode_data = {
            "vm_info": [
                {
                    "VM": "test-vm-ñáéíóú",
                    "Powerstate": "poweredOn",
                    "Template": "False",
                    "DNS Name": "test-vm-ñáéíóú.example.com",
                    "CPUs": "2",
                    "Memory": "4096",
                    "Total disk capacity MiB": "20480",
                    "NICs": "1",
                    "Disks": "1",
                    "Host": "test-host-中文",
                    "OS according to the configuration file": "ubuntu64Guest",
                    "OS according to the VMware Tools": "Ubuntu Linux (64-bit) - 特殊字符",
                    "VI SDK API Version": "7.0",
                    "Primary IP Address": "192.168.1.100",
                    "VM ID": "vm-123",
                    "VM UUID": "test-uuid-123",
                    "VI SDK Server type": "VirtualCenter",
                    "VI SDK Server": "vcenter.example.com",
                    "VI SDK UUID": "vcenter-uuid-123"
                }
            ],
            "source": {
                "Name": "vcenter-ñáéíóú.example.com",
                "API version": "7.0",
                "Vendor": "VMware, Inc. - 特殊字符",
                "VI SDK UUID": "vcenter-uuid-123"
            }
        }
        
        # Change to temp directory so files are created there
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            csv_exporter = CSVExporter()
            csv_exporter.export_all_data(unicode_data, export_statistics=False)
            
            # Verify unicode characters are preserved
            vm_info_path = os.path.join(temp_dir, "RVTools_tabvInfo.csv")
            with open(vm_info_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "test-vm-ñáéíóú" in content
                assert "test-host-中文" in content
                assert "特殊字符" in content
            
            source_path = os.path.join(temp_dir, "RVTools_tabvSource.csv")
            with open(source_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "vcenter-ñáéíóú.example.com" in content
                assert "VMware, Inc. - 特殊字符" in content
        finally:
            os.chdir(original_cwd)
    
    def test_large_dataset_performance(self, temp_dir):
        """Test performance with a larger dataset"""
        # Create a larger dataset
        large_vm_data = []
        for i in range(1000):
            large_vm_data.append({
                "VM": f"test-vm-{i:04d}",
                "Powerstate": "poweredOn" if i % 2 == 0 else "poweredOff",
                "Template": "False",
                "DNS Name": f"test-vm-{i:04d}.example.com",
                "CPUs": str((i % 8) + 1),
                "Memory": str((i % 16 + 1) * 1024),
                "Total disk capacity MiB": str((i % 10 + 1) * 10240),
                "NICs": "1",
                "Disks": "1",
                "Host": f"test-host-{i % 10}",
                "OS according to the configuration file": "ubuntu64Guest",
                "OS according to the VMware Tools": "Ubuntu Linux (64-bit)",
                "VI SDK API Version": "7.0",
                "Primary IP Address": f"192.168.{i // 256}.{i % 256}",
                "VM ID": f"vm-{i}",
                "VM UUID": f"test-uuid-{i:04d}",
                "VI SDK Server type": "VirtualCenter",
                "VI SDK Server": "vcenter.example.com",
                "VI SDK UUID": "vcenter-uuid-123"
            })
        
        large_data = {
            "vm_info": large_vm_data,
            "source": {
                "Name": "vcenter.example.com",
                "API version": "7.0",
                "Vendor": "VMware, Inc.",
                "VI SDK UUID": "vcenter-uuid-123"
            }
        }
        
        # Change to temp directory so files are created there
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            csv_exporter = CSVExporter()
            # This should complete without timeout or memory issues
            csv_exporter.export_all_data(large_data, export_statistics=False)
            
            # Verify the large file was created correctly
            vm_info_path = os.path.join(temp_dir, "RVTools_tabvInfo.csv")
            assert os.path.exists(vm_info_path)
            
            with open(vm_info_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 1000
            assert rows[0]["VM"] == "test-vm-0000"
            assert rows[999]["VM"] == "test-vm-0999"
        finally:
            os.chdir(original_cwd)
