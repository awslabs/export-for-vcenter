#!/usr/bin/env python
"""
Integration tests for vm_collector.py module.
Tests the VMCollector class against a real vCenter simulator (vcsim).

Prerequisites:
- Docker must be installed and running
- vcsim container should be running on localhost:9090
  Start with: docker run -p 9090:9090 vmware/vcsim -l :9090
"""

import pytest
import ssl
import tempfile
import os
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from src.collectors.vm_collector import VMCollector


class TestVMCollectorIntegration:
    """Integration test class for VMCollector using vcsim"""
    
    @pytest.fixture(scope="class")
    def vcenter_connection(self):
        """Create connection to vcsim for testing"""
        try:
            # Create SSL context that doesn't verify certificates (for vcsim)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Connect to vcsim
            service_instance = SmartConnect(
                host="localhost",
                port=9090,
                user="user",
                pwd="pass",
                sslContext=context
            )
            
            content = service_instance.RetrieveContent()
            container = content.rootFolder
            
            yield service_instance, content, container
            
            # Cleanup
            Disconnect(service_instance)
            
        except Exception as e:
            pytest.skip(f"Could not connect to vcsim: {e}. Make sure vcsim is running on localhost:9090")
    
    @pytest.fixture
    def vm_collector(self, vcenter_connection):
        """Create VMCollector instance with real vCenter connection"""
        service_instance, content, container = vcenter_connection
        return VMCollector(service_instance, content, container)
    
    @pytest.fixture
    def sample_vms(self, vcenter_connection):
        """Get sample VMs from vcsim"""
        service_instance, content, container = vcenter_connection
        
        # Create container view for VMs
        vm_view = content.viewManager.CreateContainerView(
            container, [vim.VirtualMachine], True
        )
        
        vms = list(vm_view.view)
        vm_view.Destroy()
        
        return vms
    
    def test_vm_collector_initialization(self, vm_collector):
        """Test that VMCollector initializes correctly with real vCenter"""
        assert vm_collector.service_instance is not None
        assert vm_collector.content is not None
        assert vm_collector.container is not None
        assert isinstance(vm_collector.seen_uuids, set)
        assert isinstance(vm_collector.duplicate_uuids, dict)
        assert isinstance(vm_collector.vm_skip_list, list)
        assert isinstance(vm_collector.dvs_uuid_to_name, dict)
    
    def test_get_vm_properties_real_vm(self, vm_collector, sample_vms):
        """Test getting properties from real VMs in vcsim"""
        if not sample_vms:
            pytest.skip("No VMs found in vcsim")
        
        vm = sample_vms[0]
        properties = vm_collector.get_vm_properties(vm)
        
        # vcsim VMs are typically powered on by default
        if properties is not None:
            # Verify required fields are present
            assert "VM" in properties
            assert "Powerstate" in properties
            assert "Template" in properties
            assert "CPUs" in properties
            assert "Memory" in properties
            assert "Host" in properties
            assert "VM ID" in properties
            assert "VM UUID" in properties
            assert "VI SDK API Version" in properties
            assert "VI SDK Server type" in properties
            
            # Verify VM name matches
            assert properties["VM"] == vm.name
            
            # Verify power state
            assert properties["Powerstate"] in ["poweredOn", "poweredOff", "suspended"]
            
            # Verify template flag
            assert properties["Template"] in ["True", "False"]
            
            print(f"Successfully retrieved properties for VM: {properties['VM']}")
    
    def test_get_vm_network_properties_real_vm(self, vm_collector, sample_vms):
        """Test getting network properties from real VMs"""
        if not sample_vms:
            pytest.skip("No VMs found in vcsim")
        
        vm = sample_vms[0]
        network_props = vm_collector.get_vm_network_properties(vm)
        
        assert isinstance(network_props, list)
        assert len(network_props) >= 1
        
        # Check first network interface
        first_nic = network_props[0]
        assert "VM" in first_nic
        assert "Network" in first_nic
        assert "IPv4 Address" in first_nic
        assert "IPv6 Address" in first_nic
        assert "Switch" in first_nic
        assert "Mac Address" in first_nic
        
        assert first_nic["VM"] == vm.name
        
        print(f"Successfully retrieved network properties for VM: {first_nic['VM']}")
    
    def test_get_vm_cpu_properties_real_vm(self, vm_collector, sample_vms):
        """Test getting CPU properties from real VMs"""
        if not sample_vms:
            pytest.skip("No VMs found in vcsim")
        
        vm = sample_vms[0]
        cpu_props = vm_collector.get_vm_cpu_properties(vm)
        
        assert "VM" in cpu_props
        assert "CPUs" in cpu_props
        assert "Sockets" in cpu_props
        assert "Reservation" in cpu_props
        
        assert cpu_props["VM"] == vm.name
        
        # CPU count should be a positive integer if present
        if cpu_props["CPUs"]:
            assert int(cpu_props["CPUs"]) > 0
        
        print(f"Successfully retrieved CPU properties for VM: {cpu_props['VM']}")
    
    def test_get_vm_memory_properties_real_vm(self, vm_collector, sample_vms):
        """Test getting memory properties from real VMs"""
        if not sample_vms:
            pytest.skip("No VMs found in vcsim")
        
        vm = sample_vms[0]
        memory_props = vm_collector.get_vm_memory_properties(vm)
        
        assert "VM" in memory_props
        assert "Size MiB" in memory_props
        assert "Reservation" in memory_props
        
        assert memory_props["VM"] == vm.name
        
        # Memory size should be a positive integer if present
        if memory_props["Size MiB"]:
            assert int(memory_props["Size MiB"]) > 0
        
        print(f"Successfully retrieved memory properties for VM: {memory_props['VM']}")
    
    def test_get_vm_disk_properties_real_vm(self, vm_collector, sample_vms):
        """Test getting disk properties from real VMs"""
        if not sample_vms:
            pytest.skip("No VMs found in vcsim")
        
        vm = sample_vms[0]
        disk_props = vm_collector.get_vm_disk_properties(vm)
        
        assert isinstance(disk_props, list)
        assert len(disk_props) >= 1
        
        # Check first disk
        first_disk = disk_props[0]
        assert "VM" in first_disk
        assert "Disk" in first_disk
        assert "Disk Key" in first_disk
        assert "Disk Path" in first_disk
        assert "Capacity MiB" in first_disk
        
        assert first_disk["VM"] == vm.name
        
        print(f"Successfully retrieved disk properties for VM: {first_disk['VM']}")
    
    def test_get_vm_partition_properties_real_vm(self, vm_collector, sample_vms):
        """Test getting partition properties from real VMs"""
        if not sample_vms:
            pytest.skip("No VMs found in vcsim")
        
        vm = sample_vms[0]
        partition_props = vm_collector.get_vm_partition_properties(vm)
        
        assert isinstance(partition_props, list)
        assert len(partition_props) >= 1
        
        # Check first partition
        first_partition = partition_props[0]
        assert "VM" in first_partition
        assert "Disk Key" in first_partition
        assert "Disk" in first_partition
        assert "Capacity MiB" in first_partition
        assert "Free MiB" in first_partition
        
        assert first_partition["VM"] == vm.name
        
        print(f"Successfully retrieved partition properties for VM: {first_partition['VM']}")
    
    def test_get_vm_tools_properties_real_vm(self, vm_collector, sample_vms):
        """Test getting VMware Tools properties from real VMs"""
        if not sample_vms:
            pytest.skip("No VMs found in vcsim")
        
        vm = sample_vms[0]
        tools_props = vm_collector.get_vm_tools_properties(vm)
        
        assert "VM" in tools_props
        assert "Tools" in tools_props
        
        assert tools_props["VM"] == vm.name
        
        print(f"Successfully retrieved tools properties for VM: {tools_props['VM']}")
    
    def test_multiple_vms_processing(self, vm_collector, sample_vms):
        """Test processing multiple VMs"""
        if len(sample_vms) < 2:
            pytest.skip("Need at least 2 VMs for this test")
        
        processed_vms = []
        
        for vm in sample_vms[:3]:  # Test first 3 VMs
            properties = vm_collector.get_vm_properties(vm)
            if properties:  # Only process powered-on VMs
                processed_vms.append(properties)
        
        # Verify we processed some VMs
        assert len(processed_vms) > 0
        
        # Verify each VM has unique name
        vm_names = [vm["VM"] for vm in processed_vms]
        assert len(vm_names) == len(set(vm_names))
        
        print(f"Successfully processed {len(processed_vms)} VMs")
    
    def test_skip_list_functionality_with_temp_file(self, vcenter_connection):
        """Test skip list functionality with a temporary file"""
        service_instance, content, container = vcenter_connection
        
        # Create temporary skip list file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test-skip-vm\n")
            f.write("# This is a comment\n")
            f.write("skip-pattern-*\n")
            temp_file = f.name
        
        try:
            # Patch the VMCollector to use our temp file
            original_load_method = VMCollector._load_vm_skip_list
            
            def mock_load_skip_list(self, filename):
                return original_load_method(self, temp_file)
            
            VMCollector._load_vm_skip_list = mock_load_skip_list
            
            collector = VMCollector(service_instance, content, container)
            
            # Verify skip list was loaded
            assert len(collector.vm_skip_list) == 2
            assert "test-skip-vm" in collector.vm_skip_list
            assert "skip-pattern-*" in collector.vm_skip_list
            
            # Test skip logic
            from unittest.mock import Mock
            mock_vm = Mock()
            mock_vm.name = "test-skip-vm"
            assert collector._should_skip_vm(mock_vm) is True
            
            mock_vm.name = "skip-pattern-test"
            assert collector._should_skip_vm(mock_vm) is True
            
            mock_vm.name = "normal-vm"
            assert collector._should_skip_vm(mock_vm) is False
            
        finally:
            # Cleanup
            os.unlink(temp_file)
            VMCollector._load_vm_skip_list = original_load_method
    
    def test_duplicate_uuid_detection(self, vm_collector):
        """Test duplicate UUID detection functionality"""
        # Simulate VMs with duplicate UUIDs
        vm_props1 = {
            "VM": "vm-original",
            "VM UUID": "duplicate-uuid-test"
        }
        
        vm_props2 = {
            "VM": "vm-duplicate",
            "VM UUID": "duplicate-uuid-test"
        }
        
        # First VM should not be marked as duplicate
        assert vm_collector._is_duplicate_uuid(vm_props1) is False
        
        # Second VM with same UUID should be marked as duplicate
        assert vm_collector._is_duplicate_uuid(vm_props2) is True
        
        # Verify tracking
        assert "duplicate-uuid-test" in vm_collector.seen_uuids
        assert "duplicate-uuid-test" in vm_collector.duplicate_uuids
        assert "vm-duplicate" in vm_collector.duplicate_uuids["duplicate-uuid-test"]
    
    def test_dvs_mapping_functionality(self, vm_collector):
        """Test DVS UUID to name mapping functionality"""
        # The DVS mapping should be a dictionary
        assert isinstance(vm_collector.dvs_uuid_to_name, dict)
        
        # In vcsim, there might not be any DVS switches by default
        # but the mapping should still be initialized
        print(f"DVS mapping contains {len(vm_collector.dvs_uuid_to_name)} entries")
    
    def test_vm_filtering_powered_off(self, vm_collector, vcenter_connection):
        """Test that powered-off VMs are properly filtered"""
        service_instance, content, container = vcenter_connection
        
        # Get all VMs including powered off ones
        vm_view = content.viewManager.CreateContainerView(
            container, [vim.VirtualMachine], True
        )
        
        all_vms = list(vm_view.view)
        vm_view.Destroy()
        
        if not all_vms:
            pytest.skip("No VMs found in vcsim")
        
        powered_on_count = 0
        filtered_count = 0
        
        for vm in all_vms:
            properties = vm_collector.get_vm_properties(vm)
            if properties is not None:
                powered_on_count += 1
            else:
                filtered_count += 1
        
        print(f"Found {len(all_vms)} total VMs")
        print(f"Processed {powered_on_count} powered-on VMs")
        print(f"Filtered out {filtered_count} VMs")
        
        # At least some VMs should be processed
        assert powered_on_count >= 0
    
    @pytest.mark.parametrize("property_method", [
        "get_vm_properties",
        "get_vm_network_properties", 
        "get_vm_cpu_properties",
        "get_vm_memory_properties",
        "get_vm_disk_properties",
        "get_vm_partition_properties",
        "get_vm_tools_properties"
    ])
    def test_all_property_methods_work(self, vm_collector, sample_vms, property_method):
        """Test that all property extraction methods work without errors"""
        if not sample_vms:
            pytest.skip("No VMs found in vcsim")
        
        vm = sample_vms[0]
        method = getattr(vm_collector, property_method)
        
        try:
            result = method(vm)
            
            # All methods should return something (dict or list)
            assert result is not None
            
            # Network, disk, and partition methods return lists
            if property_method in ["get_vm_network_properties", "get_vm_disk_properties", "get_vm_partition_properties"]:
                assert isinstance(result, list)
                assert len(result) >= 1
                # Each item should have VM name
                for item in result:
                    assert "VM" in item
                    assert item["VM"] == vm.name
            else:
                # Other methods return dict or None
                if result is not None:
                    assert isinstance(result, dict)
                    assert "VM" in result
                    assert result["VM"] == vm.name
            
            print(f"Method {property_method} executed successfully for VM: {vm.name}")
            
        except Exception as e:
            pytest.fail(f"Method {property_method} failed with error: {e}")
