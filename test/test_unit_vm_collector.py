#!/usr/bin/env python
"""
Unit tests for vm_collector.py module.
Tests the VMCollector class and its methods using mocks.
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from src.collectors.vm_collector import VMCollector
from pyVmomi import vim


class TestVMCollector:
    """Test class for VMCollector"""
    
    @pytest.fixture
    def mock_service_instance(self):
        """Create a mock service instance for testing"""
        mock_si = Mock()
        mock_content = Mock()
        mock_container = Mock()
        
        # Setup about info
        mock_about = Mock()
        mock_about.apiVersion = "7.0"
        mock_about.name = "VMware vCenter Server"
        mock_about.fullName = "VMware vCenter Server 7.0.0 build-12345"
        mock_about.instanceUuid = "test-instance-uuid"
        mock_content.about = mock_about
        
        # Setup view manager for DVS mapping
        mock_view_manager = Mock()
        mock_content.viewManager = mock_view_manager
        
        return mock_si, mock_content, mock_container
    
    @pytest.fixture
    def vm_collector(self, mock_service_instance):
        """Create VMCollector instance with mocked dependencies"""
        mock_si, mock_content, mock_container = mock_service_instance
        
        # Mock DVS view
        mock_dvs_view = Mock()
        mock_dvs = Mock()
        mock_dvs.uuid = "dvs-uuid-123"
        mock_dvs.name = "Test-DVS"
        mock_dvs_view.view = [mock_dvs]
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        
        with patch('os.path.exists', return_value=False):
            collector = VMCollector(mock_si, mock_content, mock_container)
        
        return collector
    
    @pytest.fixture
    def mock_vm_powered_on(self):
        """Create a mock VM that is powered on"""
        mock_vm = Mock()
        mock_vm.name = "test-vm-01"
        mock_vm._moId = "vm-123"
        
        # Runtime properties
        mock_runtime = Mock()
        mock_runtime.powerState = "poweredOn"
        mock_host = Mock()
        mock_host.name = "test-host-01"
        mock_runtime.host = mock_host
        mock_vm.runtime = mock_runtime
        
        # Config properties
        mock_config = Mock()
        mock_config.template = False
        mock_config.uuid = "vm-uuid-123"
        mock_config.guestFullName = "Ubuntu Linux (64-bit)"
        
        # Hardware config
        mock_hardware = Mock()
        mock_hardware.numCPU = 4
        mock_hardware.memoryMB = 8192
        mock_hardware.numCoresPerSocket = 2
        mock_hardware.device = []  # Empty device list
        mock_config.hardware = mock_hardware
        
        # CPU and memory allocation
        mock_cpu_allocation = Mock()
        mock_cpu_allocation.reservation = 1000
        mock_config.cpuAllocation = mock_cpu_allocation
        
        mock_memory_allocation = Mock()
        mock_memory_allocation.reservation = 4096
        mock_config.memoryAllocation = mock_memory_allocation
        
        mock_vm.config = mock_config
        
        # Guest properties
        mock_guest = Mock()
        mock_guest.guestState = "running"
        mock_guest.ipAddress = "192.168.1.100"
        mock_guest.hostName = "test-vm-01"
        mock_guest.domainName = "example.com"
        mock_guest.guestFullName = "Ubuntu Linux (64-bit)"
        mock_guest.toolsStatus = "toolsOk"
        mock_guest.ipStack = []  # Empty list for ipStack
        mock_vm.guest = mock_guest
        
        # Network properties
        mock_vm.network = ["network1", "network2"]
        
        return mock_vm
    
    @pytest.fixture
    def mock_vm_powered_off(self):
        """Create a mock VM that is powered off"""
        mock_vm = Mock()
        mock_vm.name = "test-vm-off"
        mock_runtime = Mock()
        mock_runtime.powerState = "poweredOff"
        mock_vm.runtime = mock_runtime
        return mock_vm
    
    def test_init_with_skip_list_file(self, mock_service_instance):
        """Test VMCollector initialization with skip list file"""
        mock_si, mock_content, mock_container = mock_service_instance
        
        # Mock DVS view
        mock_dvs_view = Mock()
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        mock_dvs_view.view = []
        
        skip_list_content = "test-vm-skip\n# This is a comment\n\nvm-pattern-*\n"
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=skip_list_content)):
            collector = VMCollector(mock_si, mock_content, mock_container)
            
            assert len(collector.vm_skip_list) == 2
            assert "test-vm-skip" in collector.vm_skip_list
            assert "vm-pattern-*" in collector.vm_skip_list
    
    def test_init_without_skip_list_file(self, mock_service_instance):
        """Test VMCollector initialization without skip list file"""
        mock_si, mock_content, mock_container = mock_service_instance
        
        # Mock DVS view
        mock_dvs_view = Mock()
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        mock_dvs_view.view = []
        
        with patch('os.path.exists', return_value=False):
            collector = VMCollector(mock_si, mock_content, mock_container)
            assert collector.vm_skip_list == []
    
    def test_build_dvs_mapping(self, mock_service_instance):
        """Test DVS UUID to name mapping"""
        mock_si, mock_content, mock_container = mock_service_instance
        
        # Mock DVS view with multiple DVS switches
        mock_dvs_view = Mock()
        mock_dvs1 = Mock()
        mock_dvs1.uuid = "dvs-uuid-1"
        mock_dvs1.name = "Production-DVS"
        
        mock_dvs2 = Mock()
        mock_dvs2.uuid = "dvs-uuid-2"
        mock_dvs2.name = "Management-DVS"
        
        mock_dvs_view.view = [mock_dvs1, mock_dvs2]
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        
        with patch('os.path.exists', return_value=False):
            collector = VMCollector(mock_si, mock_content, mock_container)
            
            assert collector.dvs_uuid_to_name["dvs-uuid-1"] == "Production-DVS"
            assert collector.dvs_uuid_to_name["dvs-uuid-2"] == "Management-DVS"
    
    def test_should_skip_vm_exact_match(self, vm_collector):
        """Test VM skip logic with exact name match"""
        vm_collector.vm_skip_list = ["test-vm-skip", "another-vm"]
        
        mock_vm = Mock()
        mock_vm.name = "test-vm-skip"
        
        assert vm_collector._should_skip_vm(mock_vm) is True
    
    def test_should_skip_vm_wildcard_match(self, vm_collector):
        """Test VM skip logic with wildcard pattern"""
        vm_collector.vm_skip_list = ["test-*", "prod-vm-*"]
        
        mock_vm = Mock()
        mock_vm.name = "test-vm-01"
        
        assert vm_collector._should_skip_vm(mock_vm) is True
    
    def test_should_skip_vm_no_match(self, vm_collector):
        """Test VM skip logic when VM should not be skipped"""
        vm_collector.vm_skip_list = ["skip-vm", "test-*"]
        
        mock_vm = Mock()
        mock_vm.name = "production-vm-01"
        
        assert vm_collector._should_skip_vm(mock_vm) is False
    
    def test_is_duplicate_uuid_first_occurrence(self, vm_collector):
        """Test duplicate UUID detection for first occurrence"""
        vm_properties = {
            "VM": "test-vm-01",
            "VM UUID": "unique-uuid-123"
        }
        
        assert vm_collector._is_duplicate_uuid(vm_properties) is False
        assert "unique-uuid-123" in vm_collector.seen_uuids
    
    def test_is_duplicate_uuid_duplicate_occurrence(self, vm_collector):
        """Test duplicate UUID detection for duplicate occurrence"""
        # First VM with UUID
        vm_properties1 = {
            "VM": "test-vm-01",
            "VM UUID": "duplicate-uuid-123"
        }
        vm_collector._is_duplicate_uuid(vm_properties1)
        
        # Second VM with same UUID
        vm_properties2 = {
            "VM": "test-vm-02",
            "VM UUID": "duplicate-uuid-123"
        }
        
        assert vm_collector._is_duplicate_uuid(vm_properties2) is True
        assert "duplicate-uuid-123" in vm_collector.duplicate_uuids
        assert "test-vm-02" in vm_collector.duplicate_uuids["duplicate-uuid-123"]
    
    def test_get_vm_properties_powered_on(self, vm_collector, mock_vm_powered_on):
        """Test getting properties from a powered-on VM"""
        properties = vm_collector.get_vm_properties(mock_vm_powered_on)
        
        assert properties is not None
        assert properties["VM"] == "test-vm-01"
        assert properties["Powerstate"] == "poweredOn"
        assert properties["Template"] == "False"
        assert properties["CPUs"] == "4"
        assert properties["Memory"] == "8192"
        assert properties["Host"] == "test-host-01"
        assert properties["Primary IP Address"] == "192.168.1.100"
        assert properties["VM UUID"] == "vm-uuid-123"
        assert properties["VM ID"] == "vm-123"
        assert properties["NICs"] == "2"
    
    def test_get_vm_properties_powered_off(self, vm_collector, mock_vm_powered_off):
        """Test getting properties from a powered-off VM (should return None)"""
        properties = vm_collector.get_vm_properties(mock_vm_powered_off)
        assert properties is None
    
    def test_get_vm_properties_guest_not_running(self, vm_collector):
        """Test getting properties from VM with guest not running"""
        mock_vm = Mock()
        mock_vm.name = "test-vm"
        mock_runtime = Mock()
        mock_runtime.powerState = "poweredOn"
        mock_vm.runtime = mock_runtime
        
        mock_guest = Mock()
        mock_guest.guestState = "notRunning"
        mock_vm.guest = mock_guest
        
        properties = vm_collector.get_vm_properties(mock_vm)
        assert properties is None
    
    def test_set_dns_name_with_fqdn(self, vm_collector):
        """Test DNS name setting with FQDN from ipStack"""
        mock_vm = Mock()
        properties = {}
        
        # Mock ipStack with domain name
        mock_ip_stack = Mock()
        mock_dns_config = Mock()
        mock_dns_config.domainName = "example.com"
        mock_ip_stack.dnsConfig = mock_dns_config
        
        mock_guest = Mock()
        mock_guest.hostName = "test-vm"
        mock_guest.ipStack = [mock_ip_stack]
        mock_vm.guest = mock_guest
        
        vm_collector._set_dns_name(mock_vm, properties)
        assert properties["DNS Name"] == "test-vm.example.com"
    
    def test_set_dns_name_fallback(self, vm_collector):
        """Test DNS name setting with fallback logic"""
        mock_vm = Mock()
        mock_vm.name = "test-vm"
        properties = {}
        
        mock_guest = Mock()
        mock_guest.hostName = "test-vm"
        mock_guest.domainName = "local.domain"
        mock_guest.ipStack = []
        mock_vm.guest = mock_guest
        
        vm_collector._set_dns_name(mock_vm, properties)
        assert properties["DNS Name"] == "test-vm.local.domain"
    
    def test_set_disk_info(self, vm_collector):
        """Test disk information extraction"""
        mock_vm = Mock()
        properties = {}
        
        # Mock virtual disks
        mock_disk1 = Mock()
        mock_disk1.capacityInKB = 20971520  # 20GB in KB
        
        mock_disk2 = Mock()
        mock_disk2.capacityInKB = 10485760  # 10GB in KB
        
        mock_hardware = Mock()
        mock_hardware.device = [mock_disk1, mock_disk2]
        
        mock_config = Mock()
        mock_config.hardware = mock_hardware
        mock_vm.config = mock_config
        
        vm_collector._set_disk_info(mock_vm, properties)
        
        assert properties["Disks"] == "2"
        assert properties["Total disk capacity MiB"] == "30720"  # 30GB in MiB
    
    def test_get_vm_network_properties(self, vm_collector):
        """Test network properties extraction"""
        mock_vm = Mock()
        mock_vm.name = "test-vm"
        
        # Mock network interface
        mock_nic = Mock()
        mock_nic.network = "VM Network"
        mock_nic.ipAddress = ["192.168.1.100", "fe80::1"]
        mock_nic.macAddress = "00:50:56:12:34:56"
        mock_nic.deviceConfigId = 4000
        
        mock_guest = Mock()
        mock_guest.net = [mock_nic]
        mock_vm.guest = mock_guest
        
        # Mock hardware device for switch info
        mock_device = Mock()
        mock_device.key = 4000
        mock_backing = Mock(spec=vim.vm.device.VirtualEthernetCard.NetworkBackingInfo)
        mock_backing.deviceName = "vSwitch0"
        mock_device.backing = mock_backing
        
        mock_hardware = Mock()
        mock_hardware.device = [mock_device]
        mock_config = Mock()
        mock_config.hardware = mock_hardware
        mock_vm.config = mock_config
        
        network_props = vm_collector.get_vm_network_properties(mock_vm)
        
        assert len(network_props) == 1
        assert network_props[0]["VM"] == "test-vm"
        assert network_props[0]["Network"] == "VM Network"
        assert network_props[0]["IPv4 Address"] == "192.168.1.100"
        assert network_props[0]["IPv6 Address"] == "fe80::1"
        assert network_props[0]["Mac Address"] == "00:50:56:12:34:56"
        assert network_props[0]["Switch"] == "vSwitch0"
    
    def test_get_vm_network_properties_dvs(self, vm_collector):
        """Test network properties extraction with DVS"""
        mock_vm = Mock()
        mock_vm.name = "test-vm"
        
        # Set up DVS mapping
        vm_collector.dvs_uuid_to_name["dvs-uuid-123"] = "Production-DVS"
        
        # Mock network interface
        mock_nic = Mock()
        mock_nic.network = "Production-Network"
        mock_nic.ipAddress = ["10.0.1.100"]
        mock_nic.macAddress = "00:50:56:78:90:12"
        mock_nic.deviceConfigId = 4000
        
        mock_guest = Mock()
        mock_guest.net = [mock_nic]
        mock_vm.guest = mock_guest
        
        # Mock DVS backing
        mock_device = Mock()
        mock_device.key = 4000
        mock_port = Mock()
        mock_port.switchUuid = "dvs-uuid-123"
        mock_backing = Mock(spec=vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo)
        mock_backing.port = mock_port
        mock_device.backing = mock_backing
        
        mock_hardware = Mock()
        mock_hardware.device = [mock_device]
        mock_config = Mock()
        mock_config.hardware = mock_hardware
        mock_vm.config = mock_config
        
        network_props = vm_collector.get_vm_network_properties(mock_vm)
        
        assert len(network_props) == 1
        assert network_props[0]["Switch"] == "Production-DVS"
    
    def test_get_vm_cpu_properties(self, vm_collector, mock_vm_powered_on):
        """Test CPU properties extraction"""
        cpu_props = vm_collector.get_vm_cpu_properties(mock_vm_powered_on)
        
        assert cpu_props["VM"] == "test-vm-01"
        assert cpu_props["CPUs"] == "4"
        assert cpu_props["Sockets"] == "2"  # 4 CPUs / 2 cores per socket
        assert cpu_props["Reservation"] == "1000"
    
    def test_get_vm_memory_properties(self, vm_collector, mock_vm_powered_on):
        """Test memory properties extraction"""
        memory_props = vm_collector.get_vm_memory_properties(mock_vm_powered_on)
        
        assert memory_props["VM"] == "test-vm-01"
        assert memory_props["Size MiB"] == "8192"
        assert memory_props["Reservation"] == "4096"
    
    def test_get_vm_disk_properties(self, vm_collector):
        """Test disk properties extraction"""
        mock_vm = Mock()
        mock_vm.name = "test-vm"
        
        # Mock virtual disks
        mock_disk1 = Mock(spec=vim.vm.device.VirtualDisk)
        mock_disk1.key = 2000
        mock_disk1.capacityInKB = 20971520  # 20GB
        mock_backing1 = Mock()
        mock_backing1.fileName = "[datastore1] test-vm/test-vm.vmdk"
        mock_disk1.backing = mock_backing1
        
        mock_disk2 = Mock(spec=vim.vm.device.VirtualDisk)
        mock_disk2.key = 2001
        mock_disk2.capacityInKB = 10485760  # 10GB
        mock_backing2 = Mock()
        mock_backing2.fileName = "[datastore1] test-vm/test-vm_1.vmdk"
        mock_disk2.backing = mock_backing2
        
        mock_hardware = Mock()
        mock_hardware.device = [mock_disk1, mock_disk2]
        mock_config = Mock()
        mock_config.hardware = mock_hardware
        mock_vm.config = mock_config
        
        disk_props = vm_collector.get_vm_disk_properties(mock_vm)
        
        assert len(disk_props) == 2
        assert disk_props[0]["VM"] == "test-vm"
        assert disk_props[0]["Disk"] == "1"
        assert disk_props[0]["Disk Key"] == "2000"
        assert disk_props[0]["Capacity MiB"] == "20480"
        assert disk_props[0]["Disk Path"] == "[datastore1] test-vm/test-vm.vmdk"
        
        assert disk_props[1]["Disk"] == "2"
        assert disk_props[1]["Disk Key"] == "2001"
        assert disk_props[1]["Capacity MiB"] == "10240"
    
    def test_get_vm_partition_properties(self, vm_collector):
        """Test partition properties extraction"""
        mock_vm = Mock()
        mock_vm.name = "test-vm"
        
        # Mock virtual disk
        mock_disk = Mock(spec=vim.vm.device.VirtualDisk)
        mock_disk.key = 2000
        mock_disk.unitNumber = 0
        mock_disk.capacityInKB = 20971520  # 20GB
        mock_backing = Mock()
        mock_backing.fileName = "[datastore1] test-vm/test-vm.vmdk"
        mock_disk.backing = mock_backing
        
        mock_hardware = Mock()
        mock_hardware.device = [mock_disk]
        mock_config = Mock()
        mock_config.hardware = mock_hardware
        mock_vm.config = mock_config
        
        # Mock guest disk info
        mock_guest_disk = Mock()
        mock_guest_disk.diskPath = "test-vm.vmdk"
        mock_guest_disk.freeSpace = 5368709120  # 5GB in bytes
        mock_guest = Mock()
        mock_guest.disk = [mock_guest_disk]
        mock_vm.guest = mock_guest
        
        partition_props = vm_collector.get_vm_partition_properties(mock_vm)
        
        assert len(partition_props) == 1
        assert partition_props[0]["VM"] == "test-vm"
        assert partition_props[0]["Disk Key"] == "2000"
        assert partition_props[0]["Disk"] == "0"
        assert partition_props[0]["Capacity MiB"] == "20480"
        assert partition_props[0]["Free MiB"] == "5120"
    
    def test_get_vm_tools_properties(self, vm_collector, mock_vm_powered_on):
        """Test VMware Tools properties extraction"""
        tools_props = vm_collector.get_vm_tools_properties(mock_vm_powered_on)
        
        assert tools_props["VM"] == "test-vm-01"
        assert tools_props["Tools"] == "toolsOk"
    
    def test_print_duplicate_uuids_summary(self, vm_collector, capsys):
        """Test duplicate UUIDs summary printing"""
        # Add some duplicate UUIDs
        vm_collector.duplicate_uuids = {
            "uuid-123": ["vm-duplicate-1", "vm-duplicate-2"],
            "uuid-456": ["vm-duplicate-3"]
        }
        
        vm_collector.print_duplicate_uuids_summary()
        
        captured = capsys.readouterr()
        assert "skipped as duplicates" in captured.out
        assert "uuid-123" in captured.out
        assert "vm-duplicate-1, vm-duplicate-2" in captured.out
        assert "uuid-456" in captured.out
        assert "vm-duplicate-3" in captured.out
    
    def test_print_duplicate_uuids_summary_empty(self, vm_collector, capsys):
        """Test duplicate UUIDs summary when no duplicates exist"""
        vm_collector.print_duplicate_uuids_summary()
        
        captured = capsys.readouterr()
        assert captured.out == ""
    
    def test_load_vm_skip_list_with_io_error(self, mock_service_instance):
        """Test skip list loading with IO error"""
        mock_si, mock_content, mock_container = mock_service_instance
        
        # Mock DVS view
        mock_dvs_view = Mock()
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        mock_dvs_view.view = []
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', side_effect=IOError("File read error")):
            collector = VMCollector(mock_si, mock_content, mock_container)
            assert collector.vm_skip_list == []
    
    def test_get_vm_network_properties_no_nics(self, vm_collector):
        """Test network properties when VM has no NICs"""
        mock_vm = Mock()
        mock_vm.name = "test-vm-no-nics"
        
        mock_guest = Mock()
        mock_guest.net = []
        mock_vm.guest = mock_guest
        
        network_props = vm_collector.get_vm_network_properties(mock_vm)
        
        assert network_props is None
    
    def test_get_vm_disk_properties_no_disks(self, vm_collector):
        """Test disk properties when VM has no disks"""
        mock_vm = Mock()
        mock_vm.name = "test-vm-no-disks"
        
        mock_hardware = Mock()
        mock_hardware.device = []
        mock_config = Mock()
        mock_config.hardware = mock_hardware
        mock_vm.config = mock_config
        
        disk_props = vm_collector.get_vm_disk_properties(mock_vm)
        
        assert len(disk_props) == 1
        assert disk_props[0]["VM"] == "test-vm-no-disks"
        assert disk_props[0]["Disk"] == ""
        assert disk_props[0]["Capacity MiB"] == ""
