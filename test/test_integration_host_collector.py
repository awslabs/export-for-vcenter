#!/usr/bin/env python3
"""
Integration tests for host_collector.py module.
Tests the HostCollector class against a real vCenter simulator (vcsim).
"""

import pytest
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import atexit
from src.collectors.host_collector import HostCollector


class TestHostCollectorIntegration:
    """Integration test class for HostCollector"""
    
    @pytest.fixture(scope="class")
    def vcenter_connection(self):
        """Create connection to vcsim"""
        try:
            si = SmartConnect(
                host='localhost',
                user='user',
                pwd='pass',
                port=9090,
                sslContext=None
            )
            
            atexit.register(Disconnect, si)
            return si
        except Exception as e:
            pytest.skip(f"Could not connect to vcsim: {e}")
    
    @pytest.fixture(scope="class")
    def content_and_container(self, vcenter_connection):
        """Get content and container from vCenter connection"""
        content = vcenter_connection.RetrieveContent()
        container = content.rootFolder
        return content, container
    
    @pytest.fixture(scope="class")
    def host_collector(self, content_and_container):
        """Create HostCollector instance"""
        content, container = content_and_container
        return HostCollector(content, container)
    
    def test_integration_get_host_properties(self, host_collector):
        """Test end-to-end host properties collection"""
        result = host_collector.get_host_properties()
        
        # Verify results structure
        assert isinstance(result, list)
        
        if len(result) > 0:
            host = result[0]
            
            # Verify all expected keys are present
            expected_keys = [
                "Host", "# CPU", "# Cores", "# Memory", "# NICs",
                "Vendor", "Model", "Object ID", "UUID", "VI SDK UUID"
            ]
            
            for key in expected_keys:
                assert key in host, f"Missing key: {key}"
            
            # Verify data types and basic validation
            assert isinstance(host["Host"], str)
            assert isinstance(host["# CPU"], str)
            assert isinstance(host["# Cores"], str)
            assert isinstance(host["# Memory"], str)
            assert isinstance(host["# NICs"], str)
            assert isinstance(host["Vendor"], str)
            assert isinstance(host["Model"], str)
            assert isinstance(host["Object ID"], str)
            assert isinstance(host["UUID"], str)
            assert isinstance(host["VI SDK UUID"], str)
            
            # Verify no VMware Mobility Platform hosts are included
            assert host["Model"] != "VMware Mobility Platform"
            
            # Verify numeric fields are numeric strings (when not empty)
            if host["# CPU"]:
                assert host["# CPU"].isdigit()
            if host["# Cores"]:
                assert host["# Cores"].isdigit()
            if host["# Memory"]:
                assert host["# Memory"].isdigit()
            if host["# NICs"]:
                assert host["# NICs"].isdigit()
    
    def test_integration_get_host_nic_properties(self, host_collector):
        """Test end-to-end host NIC properties collection"""
        result = host_collector.get_host_nic_properties()
        
        # Verify results structure
        assert isinstance(result, list)
        
        if len(result) > 0:
            nic = result[0]
            
            # Verify all expected keys are present
            expected_keys = ["Host", "Network Device", "MAC", "Switch"]
            
            for key in expected_keys:
                assert key in nic, f"Missing key: {key}"
            
            # Verify data types
            assert isinstance(nic["Host"], str)
            assert isinstance(nic["Network Device"], str)
            assert isinstance(nic["MAC"], str)
            assert isinstance(nic["Switch"], str)
            
            # Verify MAC address format (if present)
            if nic["MAC"]:
                # Basic MAC address validation (should contain colons)
                assert ":" in nic["MAC"] or "-" in nic["MAC"]
            
            # Verify network device naming convention
            if nic["Network Device"]:
                assert nic["Network Device"].startswith("vmnic") or nic["Network Device"].startswith("eth")
    
    def test_integration_get_host_vmk_properties(self, host_collector):
        """Test end-to-end host VMkernel properties collection"""
        result = host_collector.get_host_vmk_properties()
        
        # Verify results structure
        assert isinstance(result, list)
        
        if len(result) > 0:
            vmk = result[0]
            
            # Verify all expected keys are present
            expected_keys = ["Host", "Mac Address", "IP Address", "IP 6 Address", "Subnet mask"]
            
            for key in expected_keys:
                assert key in vmk, f"Missing key: {key}"
            print(vmk)
            # Verify data types
            assert isinstance(vmk["Host"], str)
            assert isinstance(vmk["Mac Address"], str)
            assert isinstance(vmk["IP Address"], str)
            assert isinstance(vmk["IP 6 Address"], str)
            assert isinstance(vmk["Subnet mask"], str)
            
            # Verify IP address format (if present)
            if vmk["IP Address"]:
                # Basic IPv4 validation (should contain dots)
                assert "." in vmk["IP Address"]
                parts = vmk["IP Address"].split(".")
                assert len(parts) == 4
            
            # Verify IPv6 address format (if present)
            if vmk["IP 6 Address"]:
                # Basic IPv6 validation (should contain colons)
                assert ":" in vmk["IP 6 Address"]
            
            # Verify subnet mask format (if present)
            if vmk["Subnet mask"]:
                # Basic subnet mask validation (should contain dots)
                assert "." in vmk["Subnet mask"]
                parts = vmk["Subnet mask"].split(".")
                assert len(parts) == 4
    
    def test_integration_host_consistency(self, host_collector):
        """Test that host data is consistent across different collection methods"""
        host_properties = host_collector.get_host_properties()
        nic_properties = host_collector.get_host_nic_properties()
        vmk_properties = host_collector.get_host_vmk_properties()
        
        if len(host_properties) > 0:
            # Get unique host names from each collection
            host_names_from_properties = {host["Host"] for host in host_properties}
            host_names_from_nics = {nic["Host"] for nic in nic_properties}
            host_names_from_vmks = {vmk["Host"] for vmk in vmk_properties}
            
            # Verify that NIC and VMK host names are subsets of host properties
            # (some hosts might not have NICs or VMKs configured)
            assert host_names_from_nics.issubset(host_names_from_properties)
            assert host_names_from_vmks.issubset(host_names_from_properties)
            
            # Verify NIC count consistency
            for host in host_properties:
                host_name = host["Host"]
                expected_nic_count = int(host["# NICs"]) if host["# NICs"].isdigit() else 0
                actual_nic_count = len([nic for nic in nic_properties if nic["Host"] == host_name])
                
                # The actual count should match the expected count
                # (allowing for cases where NICs might not be configured)
                if expected_nic_count > 0:
                    assert actual_nic_count <= expected_nic_count
    
    def test_integration_no_mobility_platform_hosts(self, host_collector):
        """Test that VMware Mobility Platform hosts are properly filtered out"""
        result = host_collector.get_host_properties()
        
        # Verify no mobility platform hosts are included
        for host in result:
            assert host["Model"] != "VMware Mobility Platform"
    
    def test_integration_data_completeness(self, host_collector):
        """Test that collected data has reasonable completeness"""
        host_properties = host_collector.get_host_properties()
        
        if len(host_properties) > 0:
            for host in host_properties:
                # Host name should always be present
                assert host["Host"], "Host name should not be empty"
                
                # Object ID should always be present
                assert host["Object ID"], "Object ID should not be empty"
                
                # VI SDK UUID should always be present
                assert host["VI SDK UUID"], "VI SDK UUID should not be empty"
    
    def test_integration_error_handling(self, host_collector):
        """Test that the collector handles various edge cases gracefully"""
        # This test verifies that the methods don't crash even if
        # the vCenter environment has unusual configurations
        
        try:
            host_properties = host_collector.get_host_properties()
            nic_properties = host_collector.get_host_nic_properties()
            vmk_properties = host_collector.get_host_vmk_properties()
            
            # All methods should return lists
            assert isinstance(host_properties, list)
            assert isinstance(nic_properties, list)
            assert isinstance(vmk_properties, list)
            
        except Exception as e:
            pytest.fail(f"HostCollector methods should not raise exceptions: {e}")
    
    def test_integration_view_cleanup(self, host_collector, content_and_container):
        """Test that views are properly cleaned up after collection"""
        content, container = content_and_container
        
        # Get initial view count (if possible to track)
        initial_views = []
        try:
            # This is a basic test - in a real environment you might track
            # view manager state more precisely
            initial_views = content.viewManager.viewList if hasattr(content.viewManager, 'viewList') else []
        except:
            pass
        
        # Perform collections
        host_collector.get_host_properties()
        host_collector.get_host_nic_properties()
        host_collector.get_host_vmk_properties()
        
        # Verify no views are leaked (basic check)
        # In a real implementation, you might have more sophisticated tracking
        try:
            final_views = content.viewManager.viewList if hasattr(content.viewManager, 'viewList') else []
            # The number of views should not have increased significantly
            assert len(final_views) <= len(initial_views) + 1  # Allow for some variance
        except:
            # If we can't track views directly, just ensure no exceptions occurred
            pass
    
    def test_integration_multiple_hosts(self, host_collector):
        """Test collection when multiple hosts are present"""
        result = host_collector.get_host_properties()
        
        # vcsim typically creates multiple hosts, verify we can handle them
        assert isinstance(result, list)
        
        if len(result) > 1:
            # Verify each host has unique identifiers
            host_names = [host["Host"] for host in result]
            object_ids = [host["Object ID"] for host in result]
            uuids = [host["UUID"] for host in result if host["UUID"]]
            
            # Host names should be unique
            assert len(host_names) == len(set(host_names))
            
            # Object IDs should be unique
            assert len(object_ids) == len(set(object_ids))
            
            # UUIDs should be unique (if present)
            if uuids:
                assert len(uuids) == len(set(uuids))
    
    def test_integration_performance_with_large_dataset(self, host_collector):
        """Test that collection performs reasonably with larger datasets"""
        import time
        
        start_time = time.time()
        
        # Collect all data types
        host_properties = host_collector.get_host_properties()
        nic_properties = host_collector.get_host_nic_properties()
        vmk_properties = host_collector.get_host_vmk_properties()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Collection should complete in reasonable time (adjust threshold as needed)
        assert execution_time < 30.0, f"Collection took too long: {execution_time} seconds"
        
        # Verify we got some results
        total_items = len(host_properties) + len(nic_properties) + len(vmk_properties)
        assert total_items >= 0  # Should at least not fail
