#!/usr/bin/env python
"""
Unit tests for host_collector.py module.
Tests the HostCollector class and its methods.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.collectors.host_collector import HostCollector
from pyVmomi import vim


class TestHostCollector:
    """Test class for HostCollector"""
    
    @pytest.fixture
    def mock_content(self):
        """Create a mock content object for testing"""
        mock_content = Mock()
        mock_about = Mock()
        mock_about.instanceUuid = "test-instance-uuid"
        mock_content.about = mock_about
        return mock_content
    
    @pytest.fixture
    def mock_container(self):
        """Create a mock container object for testing"""
        return Mock()
    
    @pytest.fixture
    def host_collector(self, mock_content, mock_container):
        """Create a HostCollector instance for testing"""
        return HostCollector(mock_content, mock_container)
    
    @pytest.fixture
    def mock_host(self):
        """Create a mock host object with all required attributes"""
        mock_host = Mock()
        mock_host.name = "test-host.example.com"
        mock_host._moId = "host-123"
        
        # Mock hardware info
        mock_hardware = Mock()
        mock_cpu_info = Mock()
        mock_cpu_info.numCpuPackages = 2
        mock_cpu_info.numCpuCores = 16
        mock_hardware.cpuInfo = mock_cpu_info
        mock_hardware.memorySize = 68719476736  # 64GB in bytes
        
        mock_system_info = Mock()
        mock_system_info.vendor = "Dell Inc."
        mock_system_info.model = "PowerEdge R640"
        mock_system_info.uuid = "test-host-uuid"
        mock_hardware.systemInfo = mock_system_info
        
        mock_host.hardware = mock_hardware
        
        # Mock network config
        mock_config = Mock()
        mock_network = Mock()
        
        # Mock physical NICs
        mock_pnic1 = Mock()
        mock_pnic1.device = "vmnic0"
        mock_pnic1.mac = "00:50:56:12:34:56"
        mock_pnic1.key = "key-vim.host.PhysicalNic-vmnic0"
        
        mock_pnic2 = Mock()
        mock_pnic2.device = "vmnic1"
        mock_pnic2.mac = "00:50:56:12:34:57"
        mock_pnic2.key = "key-vim.host.PhysicalNic-vmnic1"
        
        mock_network.pnic = [mock_pnic1, mock_pnic2]
        
        # Mock virtual switches
        mock_vswitch = Mock()
        mock_vswitch.name = "vSwitch0"
        mock_vswitch.pnic = ["key-vim.host.PhysicalNic-vmnic0"]
        mock_network.vswitch = [mock_vswitch]
        
        # Mock VMkernel NICs
        mock_vnic = Mock()
        mock_vnic_spec = Mock()
        mock_vnic_spec.mac = "00:50:56:12:34:58"
        
        mock_ip = Mock()
        mock_ip.ipAddress = "192.168.1.100"
        mock_ip.subnetMask = "255.255.255.0"
        
        mock_ipv6_config = Mock()
        mock_ipv6_address = Mock()
        mock_ipv6_address.ipAddress = "fe80::250:56ff:fe12:3458"
        mock_ipv6_config.ipV6Address = [mock_ipv6_address]
        mock_ip.ipV6Config = mock_ipv6_config
        
        mock_vnic_spec.ip = mock_ip
        mock_vnic.spec = mock_vnic_spec
        
        mock_network.vnic = [mock_vnic]
        
        mock_config.network = mock_network
        mock_host.config = mock_config
        
        return mock_host
    
    @pytest.fixture
    def mock_mobility_host(self):
        """Create a mock host with VMware Mobility Platform model (should be skipped)"""
        mock_host = Mock()
        mock_host.name = "mobility-host.example.com"
        
        mock_hardware = Mock()
        mock_system_info = Mock()
        mock_system_info.model = "VMware Mobility Platform"
        mock_hardware.systemInfo = mock_system_info
        mock_host.hardware = mock_hardware
        
        return mock_host
    
    def test_init(self, mock_content, mock_container):
        """Test HostCollector initialization"""
        collector = HostCollector(mock_content, mock_container)
        assert collector.content == mock_content
        assert collector.container == mock_container
    
    def test_get_host_properties_success(self, host_collector, mock_host):
        """Test successful host properties collection"""
        # Mock the view manager and container view
        mock_view = Mock()
        mock_view.view = [mock_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        # Call the method
        result = host_collector.get_host_properties()
        
        # Verify the result
        assert len(result) == 1
        host_props = result[0]
        
        assert host_props["Host"] == "test-host.example.com"
        assert host_props["# CPU"] == "2"
        assert host_props["# Cores"] == "16"
        assert host_props["# Memory"] == "65536"  # 64GB in MB
        assert host_props["# NICs"] == "2"
        assert host_props["Vendor"] == "Dell Inc."
        assert host_props["Model"] == "PowerEdge R640"
        assert host_props["Object ID"] == "host-123"
        assert host_props["UUID"] == "test-host-uuid"
        assert host_props["VI SDK UUID"] == "test-instance-uuid"
        
        # Verify view was destroyed
        mock_view.Destroy.assert_called_once()
    
    def test_get_host_properties_skips_mobility_platform(self, host_collector, mock_mobility_host):
        """Test that VMware Mobility Platform hosts are skipped"""
        mock_view = Mock()
        mock_view.view = [mock_mobility_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        result = host_collector.get_host_properties()
        
        # Should return empty list since mobility platform hosts are skipped
        assert len(result) == 0
        mock_view.Destroy.assert_called_once()
    
    def test_get_host_properties_missing_attributes(self, host_collector):
        """Test host properties collection with missing attributes"""
        # Create a host with minimal attributes
        mock_host = Mock()
        mock_host.name = "minimal-host"
        # Remove other attributes to test hasattr checks
        del mock_host.hardware
        del mock_host._moId
        del mock_host.config
        
        mock_view = Mock()
        mock_view.view = [mock_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        result = host_collector.get_host_properties()
        
        # Should still return a result with empty strings for missing attributes
        assert len(result) == 1
        host_props = result[0]
        
        assert host_props["Host"] == "minimal-host"
        assert host_props["# CPU"] == ""
        assert host_props["# Cores"] == ""
        assert host_props["# Memory"] == ""
        assert host_props["# NICs"] == ""
        assert host_props["Vendor"] == ""
        assert host_props["Model"] == ""
        assert host_props["Object ID"] == ""
        assert host_props["UUID"] == ""
    
    def test_get_host_properties_view_cleanup_on_exception(self, host_collector):
        """Test that view is properly cleaned up even when exception occurs"""
        mock_view = Mock()
        mock_view.view = [Mock()]
        mock_view.view[0].name = "test-host"
        # Make hardware access raise an exception
        mock_view.view[0].hardware = Mock()
        mock_view.view[0].hardware.systemInfo = Mock()
        mock_view.view[0].hardware.systemInfo.model = Mock(side_effect=Exception("Test exception"))
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        # Should not raise exception and should clean up view
        with pytest.raises(Exception):
            host_collector.get_host_properties()
        
        mock_view.Destroy.assert_called_once()
    
    def test_get_host_nic_properties_success(self, host_collector, mock_host):
        """Test successful host NIC properties collection"""
        mock_view = Mock()
        mock_view.view = [mock_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        result = host_collector.get_host_nic_properties()
        
        assert len(result) == 2
        
        # Check first NIC
        nic1 = result[0]
        assert nic1["Host"] == "test-host.example.com"
        assert nic1["Network Device"] == "vmnic0"
        assert nic1["MAC"] == "00:50:56:12:34:56"
        assert nic1["Switch"] == "vSwitch0"
        
        # Check second NIC
        nic2 = result[1]
        assert nic2["Host"] == "test-host.example.com"
        assert nic2["Network Device"] == "vmnic1"
        assert nic2["MAC"] == "00:50:56:12:34:57"
        assert nic2["Switch"] == ""  # Not assigned to any switch
        
        mock_view.Destroy.assert_called_once()
    
    def test_get_host_nic_properties_no_network_config(self, host_collector):
        """Test NIC properties collection when host has no network config"""
        mock_host = Mock()
        mock_host.name = "test-host"
        # Remove config attribute
        del mock_host.config
        
        mock_view = Mock()
        mock_view.view = [mock_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        result = host_collector.get_host_nic_properties()
        
        # Should return empty list
        assert len(result) == 0
        mock_view.Destroy.assert_called_once()
    
    def test_get_host_vmk_properties_success(self, host_collector, mock_host):
        """Test successful VMkernel properties collection"""
        mock_view = Mock()
        mock_view.view = [mock_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        result = host_collector.get_host_vmk_properties()
        
        assert len(result) == 1
        
        vmk = result[0]
        assert vmk["Host"] == "test-host.example.com"
        assert vmk["Mac Address"] == "00:50:56:12:34:58"
        assert vmk["IP Address"] == "192.168.1.100"
        assert vmk["IP 6 Address"] == "fe80::250:56ff:fe12:3458"
        assert vmk["Subnet mask"] == "255.255.255.0"
        
        mock_view.Destroy.assert_called_once()
    
    def test_get_host_vmk_properties_no_ipv6(self, host_collector):
        """Test VMkernel properties collection without IPv6"""
        mock_host = Mock()
        mock_host.name = "test-host"
        
        mock_config = Mock()
        mock_network = Mock()
        
        mock_vnic = Mock()
        mock_vnic_spec = Mock()
        mock_vnic_spec.mac = "00:50:56:12:34:58"
        
        mock_ip = Mock()
        mock_ip.ipAddress = "192.168.1.100"
        mock_ip.subnetMask = "255.255.255.0"
        # No IPv6 config
        del mock_ip.ipV6Config
        
        mock_vnic_spec.ip = mock_ip
        mock_vnic.spec = mock_vnic_spec
        mock_network.vnic = [mock_vnic]
        
        mock_config.network = mock_network
        mock_host.config = mock_config
        
        mock_view = Mock()
        mock_view.view = [mock_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        result = host_collector.get_host_vmk_properties()
        
        assert len(result) == 1
        vmk = result[0]
        assert vmk["IP 6 Address"] == ""
    
    def test_get_host_vmk_properties_missing_attributes(self, host_collector):
        """Test VMkernel properties collection with missing attributes"""
        mock_host = Mock()
        mock_host.name = "test-host"
        
        mock_config = Mock()
        mock_network = Mock()
        
        # Create a mock vnic that has spec but spec has no attributes
        mock_vnic = Mock()
        mock_vnic.spec = Mock(spec=[])  # spec exists but has no attributes
        
        mock_network.vnic = [mock_vnic]
        mock_config.network = mock_network
        mock_host.config = mock_config
        
        mock_view = Mock()
        mock_view.view = [mock_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        result = host_collector.get_host_vmk_properties()
        
        assert len(result) == 1
        vmk = result[0]
        assert vmk["Host"] == "test-host"
        assert vmk["Mac Address"] == ""
        assert vmk["IP Address"] == ""
        assert vmk["IP 6 Address"] == ""
        assert vmk["Subnet mask"] == ""
    
    def test_get_host_vmk_properties_no_vnic(self, host_collector):
        """Test VMkernel properties collection when host has no vnics"""
        mock_host = Mock()
        mock_host.name = "test-host"
        
        mock_config = Mock()
        mock_network = Mock()
        # Remove vnic attribute
        del mock_network.vnic
        
        mock_config.network = mock_network
        mock_host.config = mock_config
        
        mock_view = Mock()
        mock_view.view = [mock_host]
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        result = host_collector.get_host_vmk_properties()
        
        # Should return empty list
        assert len(result) == 0
        mock_view.Destroy.assert_called_once()
    
    def test_all_methods_handle_view_cleanup(self, host_collector):
        """Test that all methods properly clean up views"""
        mock_view = Mock()
        mock_view.view = []
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        # Test all three methods
        host_collector.get_host_properties()
        host_collector.get_host_nic_properties()
        host_collector.get_host_vmk_properties()
        
        # Verify view was destroyed for each call
        assert mock_view.Destroy.call_count == 3
    
    @patch('src.collectors.host_collector.vim')
    def test_container_view_creation_parameters(self, mock_vim, host_collector):
        """Test that container views are created with correct parameters"""
        mock_view = Mock()
        mock_view.view = []
        
        mock_view_manager = Mock()
        mock_view_manager.CreateContainerView.return_value = mock_view
        host_collector.content.viewManager = mock_view_manager
        
        # Test host properties
        host_collector.get_host_properties()
        
        # Verify CreateContainerView was called with correct parameters
        mock_view_manager.CreateContainerView.assert_called_with(
            host_collector.container, [mock_vim.HostSystem], True
        )
        
        mock_view.Destroy.assert_called_once()
