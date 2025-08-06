#!/usr/bin/env python
"""
Unit tests for VCenterOrchestrator class.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.vcenter_orchestrator import VCenterOrchestrator
from pyVmomi import vim


class TestVCenterOrchestrator:
    """Test cases for VCenterOrchestrator class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.host = "test-vcenter.example.com"
        self.user = "test-user"
        self.password = "test-password"
        self.port = 443
        self.disable_ssl = False
        
        # Create orchestrator instance
        self.orchestrator = VCenterOrchestrator(
            self.host, self.user, self.password, self.port, self.disable_ssl
        )
    
    def test_init(self):
        """Test VCenterOrchestrator initialization."""
        assert self.orchestrator.connection is not None
        assert self.orchestrator.service_instance is None
        assert self.orchestrator.content is None
        assert self.orchestrator.container is None
        assert self.orchestrator.vm_collector is None
        assert self.orchestrator.host_collector is None
        assert self.orchestrator.network_collector is None
        assert self.orchestrator.performance_collector is None
        assert self.orchestrator.csv_exporter is not None
    
    def test_connect_success(self):
        """Test successful connection to vCenter."""
        # Mock connection components
        mock_service_instance = Mock()
        mock_content = Mock()
        mock_container = Mock()
        
        # Mock the view manager and container view for collector initialization
        mock_dvs_view = Mock()
        mock_dvs_view.view = []  # Empty list for DVS view iteration
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        
        self.orchestrator.connection.connect = Mock(return_value=mock_service_instance)
        self.orchestrator.connection.get_content = Mock(return_value=mock_content)
        self.orchestrator.connection.get_container = Mock(return_value=mock_container)
        
        # Test connection
        result = self.orchestrator.connect()
        
        # Assertions
        assert result is True
        assert self.orchestrator.service_instance == mock_service_instance
        assert self.orchestrator.content == mock_content
        assert self.orchestrator.container == mock_container
        
        # Verify collectors were initialized (they should not be None)
        assert self.orchestrator.vm_collector is not None
        assert self.orchestrator.host_collector is not None
        assert self.orchestrator.network_collector is not None
        assert self.orchestrator.performance_collector is not None
    
    def test_connect_failure(self):
        """Test failed connection to vCenter."""
        self.orchestrator.connection.connect = Mock(return_value=None)
        
        result = self.orchestrator.connect()
        
        assert result is False
        assert self.orchestrator.service_instance is None
    
    def test_get_source_properties(self):
        """Test extraction of source properties from vCenter."""
        # Mock about info
        mock_about = Mock()
        mock_about.name = "VMware vCenter Server"
        mock_about.apiVersion = "7.0.3.0"
        mock_about.vendor = "VMware, Inc."
        mock_about.instanceUuid = "12345678-1234-1234-1234-123456789012"
        
        mock_content = Mock()
        mock_content.about = mock_about
        self.orchestrator.content = mock_content
        
        result = self.orchestrator.get_source_properties()
        
        expected = {
            "Name": "VMware vCenter Server",
            "API version": "7.0.3.0",
            "Vendor": "VMware, Inc.",
            "VI SDK UUID": "12345678-1234-1234-1234-123456789012"
        }
        
        assert result == expected
    
    def test_get_source_properties_missing_attributes(self):
        """Test source properties extraction with missing attributes."""
        mock_about = Mock()
        # Only set some attributes
        mock_about.name = "VMware vCenter Server"
        # Remove the missing attributes completely so hasattr returns False
        del mock_about.apiVersion
        del mock_about.vendor
        del mock_about.instanceUuid
        
        mock_content = Mock()
        mock_content.about = mock_about
        self.orchestrator.content = mock_content
        
        result = self.orchestrator.get_source_properties()
        
        expected = {
            "Name": "VMware vCenter Server",
            "API version": "",
            "Vendor": "",
            "VI SDK UUID": ""
        }
        
        assert result == expected
    
    @patch('vcenter_orchestrator.vim')
    def test_collect_vm_data_success(self, mock_vim):
        """Test successful VM data collection."""
        # Mock VMs
        mock_vm1 = Mock()
        mock_vm1.name = "test-vm-1"
        mock_vm2 = Mock()
        mock_vm2.name = "test-vm-2"
        
        # Mock container view
        mock_container_view = Mock()
        mock_container_view.view = [mock_vm1, mock_vm2]
        
        # Mock content and view manager
        mock_content = Mock()
        mock_content.viewManager.CreateContainerView.return_value = mock_container_view
        self.orchestrator.content = mock_content
        self.orchestrator.container = Mock()
        
        # Mock VM collector
        mock_vm_collector = Mock()
        mock_vm_collector._should_skip_vm.return_value = False
        mock_vm_collector._is_duplicate_uuid.return_value = False
        
        # Mock VM properties
        vm_properties = {"Primary IP Address": "192.168.1.100", "VM": "test-vm-1"}
        mock_vm_collector.get_vm_properties.return_value = vm_properties
        mock_vm_collector.get_vm_network_properties.return_value = [{"Network": "VM Network"}]
        mock_vm_collector.get_vm_cpu_properties.return_value = {"CPUs": 2}
        mock_vm_collector.get_vm_memory_properties.return_value = {"Memory": 4096}
        mock_vm_collector.get_vm_disk_properties.return_value = [{"Disk": "Hard disk 1"}]
        mock_vm_collector.get_vm_partition_properties.return_value = [{"Partition": "C:"}]
        mock_vm_collector.get_vm_tools_properties.return_value = {"Tools Status": "toolsOk"}
        
        self.orchestrator.vm_collector = mock_vm_collector
        
        result = self.orchestrator.collect_vm_data()
        
        # Verify structure
        assert "vm_info" in result
        assert "vm_network" in result
        assert "vm_cpu" in result
        assert "vm_memory" in result
        assert "vm_disk" in result
        assert "vm_partition" in result
        assert "vm_tools" in result
        
        # Verify data was collected for both VMs
        assert len(result["vm_info"]) == 2
        assert len(result["vm_cpu"]) == 2
        assert len(result["vm_memory"]) == 2
        assert len(result["vm_tools"]) == 2
        
        # Verify container view was destroyed
        mock_container_view.Destroy.assert_called_once()
    
    @patch('vcenter_orchestrator.vim')
    def test_collect_vm_data_with_max_count(self, mock_vim):
        """Test VM data collection with max_count limit."""
        # Mock 5 VMs
        mock_vms = []
        for i in range(5):
            vm = Mock()
            vm.name = f"test-vm-{i+1}"
            mock_vms.append(vm)
        
        # Mock container view
        mock_container_view = Mock()
        mock_container_view.view = mock_vms
        
        # Mock content and view manager
        mock_content = Mock()
        mock_content.viewManager.CreateContainerView.return_value = mock_container_view
        self.orchestrator.content = mock_content
        self.orchestrator.container = Mock()
        
        # Mock VM collector
        mock_vm_collector = Mock()
        mock_vm_collector._should_skip_vm.return_value = False
        mock_vm_collector._is_duplicate_uuid.return_value = False
        
        # Mock VM properties
        vm_properties = {"Primary IP Address": "192.168.1.100", "VM": "test-vm"}
        mock_vm_collector.get_vm_properties.return_value = vm_properties
        mock_vm_collector.get_vm_network_properties.return_value = []
        mock_vm_collector.get_vm_cpu_properties.return_value = {}
        mock_vm_collector.get_vm_memory_properties.return_value = {}
        mock_vm_collector.get_vm_disk_properties.return_value = []
        mock_vm_collector.get_vm_partition_properties.return_value = []
        mock_vm_collector.get_vm_tools_properties.return_value = {}
        
        self.orchestrator.vm_collector = mock_vm_collector
        
        # Test with max_count = 3
        result = self.orchestrator.collect_vm_data(max_count=3)
        
        # Should only process 3 VMs
        assert len(result["vm_info"]) == 3
        assert mock_vm_collector.get_vm_properties.call_count == 3
    
    @patch('vcenter_orchestrator.vim')
    def test_collect_vm_data_skip_vm(self, mock_vim):
        """Test VM data collection with skipped VMs."""
        # Mock VM
        mock_vm = Mock()
        mock_vm.name = "test-vm-skip"
        
        # Mock container view
        mock_container_view = Mock()
        mock_container_view.view = [mock_vm]
        
        # Mock content and view manager
        mock_content = Mock()
        mock_content.viewManager.CreateContainerView.return_value = mock_container_view
        self.orchestrator.content = mock_content
        self.orchestrator.container = Mock()
        
        # Mock VM collector to skip VM
        mock_vm_collector = Mock()
        mock_vm_collector._should_skip_vm.return_value = True
        
        self.orchestrator.vm_collector = mock_vm_collector
        
        result = self.orchestrator.collect_vm_data()
        
        # Should have empty results since VM was skipped
        assert len(result["vm_info"]) == 0
        mock_vm_collector.get_vm_properties.assert_not_called()
    
    @patch('vcenter_orchestrator.vim')
    def test_collect_vm_data_no_ip_address(self, mock_vim):
        """Test VM data collection with VM having no IP address."""
        # Mock VM
        mock_vm = Mock()
        mock_vm.name = "test-vm-no-ip"
        
        # Mock container view
        mock_container_view = Mock()
        mock_container_view.view = [mock_vm]
        
        # Mock content and view manager
        mock_content = Mock()
        mock_content.viewManager.CreateContainerView.return_value = mock_container_view
        self.orchestrator.content = mock_content
        self.orchestrator.container = Mock()
        
        # Mock VM collector
        mock_vm_collector = Mock()
        mock_vm_collector._should_skip_vm.return_value = False
        mock_vm_collector._is_duplicate_uuid.return_value = False
        
        # Mock VM properties without IP address
        vm_properties = {"Primary IP Address": "", "VM": "test-vm-no-ip"}
        mock_vm_collector.get_vm_properties.return_value = vm_properties
        
        self.orchestrator.vm_collector = mock_vm_collector
        
        result = self.orchestrator.collect_vm_data()
        
        # Should have empty results since VM has no IP
        assert len(result["vm_info"]) == 0
        mock_vm_collector.get_vm_network_properties.assert_not_called()
    
    @patch('vcenter_orchestrator.vim')
    def test_collect_vm_data_powered_off(self, mock_vim):
        """Test VM data collection with powered off VM."""
        # Mock VM
        mock_vm = Mock()
        mock_vm.name = "test-vm-powered-off"
        
        # Mock container view
        mock_container_view = Mock()
        mock_container_view.view = [mock_vm]
        
        # Mock content and view manager
        mock_content = Mock()
        mock_content.viewManager.CreateContainerView.return_value = mock_container_view
        self.orchestrator.content = mock_content
        self.orchestrator.container = Mock()
        
        # Mock VM collector
        mock_vm_collector = Mock()
        mock_vm_collector._should_skip_vm.return_value = False
        mock_vm_collector.get_vm_properties.return_value = None  # Powered off VM
        
        self.orchestrator.vm_collector = mock_vm_collector
        
        result = self.orchestrator.collect_vm_data()
        
        # Should have empty results since VM is powered off
        assert len(result["vm_info"]) == 0
        mock_vm_collector.get_vm_network_properties.assert_not_called()
    
    def test_collect_all_data_success(self):
        """Test successful collection of all data."""
        # Mock all collectors
        self.orchestrator.host_collector = Mock()
        self.orchestrator.network_collector = Mock()
        self.orchestrator.performance_collector = Mock()
        
        # Mock return values
        self.orchestrator.get_source_properties = Mock(return_value={"Name": "vCenter"})
        self.orchestrator.host_collector.get_host_properties.return_value = [{"Host": "host1"}]
        self.orchestrator.host_collector.get_host_nic_properties.return_value = [{"NIC": "vmnic0"}]
        self.orchestrator.host_collector.get_host_vmk_properties.return_value = [{"VMK": "vmk0"}]
        self.orchestrator.network_collector.get_vm_vswitch_properties.return_value = [{"vSwitch": "vSwitch0"}]
        self.orchestrator.network_collector.get_vm_dvswitch_properties.return_value = [{"dvSwitch": "dvSwitch0"}]
        self.orchestrator.network_collector.get_vm_port_properties.return_value = [{"Port": "VM Network"}]
        self.orchestrator.network_collector.get_vm_dvport_properties.return_value = [{"dvPort": "dvPortGroup"}]
        self.orchestrator.performance_collector.get_performance_properties.return_value = [{"Performance": "data"}]
        self.orchestrator.collect_vm_data = Mock(return_value={
            "vm_info": [{"VM": "test-vm"}],
            "vm_network": [],
            "vm_cpu": [],
            "vm_memory": [],
            "vm_disk": [],
            "vm_partition": [],
            "vm_tools": []
        })
        
        result = self.orchestrator.collect_all_data()
        
        # Verify all data types are present
        expected_keys = [
            "source", "host", "host_nic", "host_vmk", "vswitch", "dvswitch",
            "vport", "dvport", "performance", "vm_info", "vm_network", "vm_cpu",
            "vm_memory", "vm_disk", "vm_partition", "vm_tools"
        ]
        
        for key in expected_keys:
            assert key in result
        
        # Verify performance collector was called with correct parameters
        self.orchestrator.performance_collector.get_performance_properties.assert_called_once_with(
            self.orchestrator.content,
            self.orchestrator.container,
            interval_mins=60
        )
    
    def test_collect_all_data_no_statistics(self):
        """Test collection of all data without performance statistics."""
        # Mock all collectors
        self.orchestrator.host_collector = Mock()
        self.orchestrator.network_collector = Mock()
        self.orchestrator.performance_collector = Mock()
        
        # Mock return values
        self.orchestrator.get_source_properties = Mock(return_value={"Name": "vCenter"})
        self.orchestrator.host_collector.get_host_properties.return_value = []
        self.orchestrator.host_collector.get_host_nic_properties.return_value = []
        self.orchestrator.host_collector.get_host_vmk_properties.return_value = []
        self.orchestrator.network_collector.get_vm_vswitch_properties.return_value = []
        self.orchestrator.network_collector.get_vm_dvswitch_properties.return_value = []
        self.orchestrator.network_collector.get_vm_port_properties.return_value = []
        self.orchestrator.network_collector.get_vm_dvport_properties.return_value = []
        self.orchestrator.collect_vm_data = Mock(return_value={
            "vm_info": [],
            "vm_network": [],
            "vm_cpu": [],
            "vm_memory": [],
            "vm_disk": [],
            "vm_partition": [],
            "vm_tools": []
        })
        
        result = self.orchestrator.collect_all_data(export_statistics=False)
        
        # Verify performance data is empty
        assert result["performance"] == []
        
        # Verify performance collector was not called
        self.orchestrator.performance_collector.get_performance_properties.assert_not_called()
    
    def test_collect_all_data_custom_perf_interval(self):
        """Test collection of all data with custom performance interval."""
        # Mock all collectors
        self.orchestrator.host_collector = Mock()
        self.orchestrator.network_collector = Mock()
        self.orchestrator.performance_collector = Mock()
        
        # Mock return values
        self.orchestrator.get_source_properties = Mock(return_value={"Name": "vCenter"})
        self.orchestrator.host_collector.get_host_properties.return_value = []
        self.orchestrator.host_collector.get_host_nic_properties.return_value = []
        self.orchestrator.host_collector.get_host_vmk_properties.return_value = []
        self.orchestrator.network_collector.get_vm_vswitch_properties.return_value = []
        self.orchestrator.network_collector.get_vm_dvswitch_properties.return_value = []
        self.orchestrator.network_collector.get_vm_port_properties.return_value = []
        self.orchestrator.network_collector.get_vm_dvport_properties.return_value = []
        self.orchestrator.performance_collector.get_performance_properties.return_value = []
        self.orchestrator.collect_vm_data = Mock(return_value={
            "vm_info": [],
            "vm_network": [],
            "vm_cpu": [],
            "vm_memory": [],
            "vm_disk": [],
            "vm_partition": [],
            "vm_tools": []
        })
        
        result = self.orchestrator.collect_all_data(perf_interval=240)
        
        # Verify performance collector was called with custom interval
        self.orchestrator.performance_collector.get_performance_properties.assert_called_once_with(
            self.orchestrator.content,
            self.orchestrator.container,
            interval_mins=240
        )
    
    def test_export_data_success(self):
        """Test successful data export."""
        # Mock service instance
        self.orchestrator.service_instance = Mock()
        
        # Mock collect_all_data
        mock_data = {"vm_info": [{"VM": "test-vm"}]}
        self.orchestrator.collect_all_data = Mock(return_value=mock_data)
        
        # Mock CSV exporter
        self.orchestrator.csv_exporter.export_all_data = Mock(return_value=["file1.csv", "file2.csv"])
        self.orchestrator.csv_exporter.create_zip_archive = Mock(return_value="vcexport.zip")
        
        result = self.orchestrator.export_data()
        
        assert result == "vcexport.zip"
        
        # Verify methods were called
        self.orchestrator.collect_all_data.assert_called_once_with(None, True, 60)
        self.orchestrator.csv_exporter.export_all_data.assert_called_once_with(
            mock_data, True, self.orchestrator.performance_collector
        )
        self.orchestrator.csv_exporter.create_zip_archive.assert_called_once_with(purge_csv=True)
    
    def test_export_data_no_connection(self):
        """Test data export without valid connection."""
        # No service instance
        self.orchestrator.service_instance = None
        
        result = self.orchestrator.export_data()
        
        assert result is None
    
    def test_export_data_custom_parameters(self):
        """Test data export with custom parameters."""
        # Mock service instance
        self.orchestrator.service_instance = Mock()
        
        # Mock collect_all_data
        mock_data = {"vm_info": []}
        self.orchestrator.collect_all_data = Mock(return_value=mock_data)
        
        # Mock CSV exporter
        self.orchestrator.csv_exporter.export_all_data = Mock(return_value=[])
        self.orchestrator.csv_exporter.create_zip_archive = Mock(return_value="vcexport.zip")
        
        result = self.orchestrator.export_data(
            max_count=10,
            purge_csv=False,
            export_statistics=False,
            perf_interval=240
        )
        
        assert result == "vcexport.zip"
        
        # Verify methods were called with custom parameters
        self.orchestrator.collect_all_data.assert_called_once_with(10, False, 240)
        self.orchestrator.csv_exporter.export_all_data.assert_called_once_with(
            mock_data, False, None
        )
        self.orchestrator.csv_exporter.create_zip_archive.assert_called_once_with(purge_csv=False)
    
    def test_disconnect(self):
        """Test disconnection from vCenter."""
        # Mock connection
        self.orchestrator.connection = Mock()
        
        self.orchestrator.disconnect()
        
        self.orchestrator.connection.disconnect.assert_called_once()
    
    def test_disconnect_no_connection(self):
        """Test disconnection when no connection exists."""
        self.orchestrator.connection = None
        
        # Should not raise an exception
        self.orchestrator.disconnect()


if __name__ == "__main__":
    pytest.main([__file__])
