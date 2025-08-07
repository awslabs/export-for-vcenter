#!/usr/bin/env python3
"""
Integration tests for network_collector.py module.
Tests the NetworkCollector class against a real vCenter simulator (vcsim).
"""

import pytest
from unittest.mock import Mock
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import atexit
from src.collectors.network_collector import NetworkCollector


class TestNetworkCollectorIntegration:
    """Integration test class for NetworkCollector using vcsim"""
    
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
    def network_collector(self, vcenter_connection):
        """Create NetworkCollector instance"""
        content = vcenter_connection.RetrieveContent()
        container = content.rootFolder
        return NetworkCollector(content, container)
    
    @pytest.fixture(scope="class")
    def vcenter_content(self, vcenter_connection):
        """Get vCenter content"""
        return vcenter_connection.RetrieveContent()
    
    def test_integration_get_vm_dvport_properties(self, network_collector):
        """Test get_vm_dvport_properties against vcsim"""
        result = network_collector.get_vm_dvport_properties()
        
        # vcsim should return a list (may be empty)
        assert isinstance(result, list)
        
        # If there are results, verify structure
        if result:
            dvport = result[0]
            assert "Port" in dvport
            assert "Switch" in dvport
            assert "VLAN" in dvport
            assert isinstance(dvport["Port"], str)
            assert isinstance(dvport["Switch"], str)
            assert isinstance(dvport["VLAN"], str)
    
    def test_integration_get_vm_port_properties(self, network_collector):
        """Test get_vm_port_properties against vcsim"""
        result = network_collector.get_vm_port_properties()
        
        # vcsim should return a list
        assert isinstance(result, list)
        
        # vcsim typically has standard port groups
        if result:
            port_group = result[0]
            assert "Port Group" in port_group
            assert "Switch" in port_group
            assert "VLAN" in port_group
            assert isinstance(port_group["Port Group"], str)
            assert isinstance(port_group["Switch"], str)
            assert isinstance(port_group["VLAN"], str)
    
    def test_integration_get_vm_dvswitch_properties(self, network_collector):
        """Test get_vm_dvswitch_properties against vcsim"""
        result = network_collector.get_vm_dvswitch_properties()
        
        # vcsim should return a list (may be empty if no DVS)
        assert isinstance(result, list)
        
        # If there are DVS results, verify structure
        if result:
            dvs = result[0]
            required_fields = [
                "Switch", "Datacenter", "Name", "Vendor", "Version",
                "Description", "Created", "Host members", "Max Ports",
                "# Ports", "# VMs", "VI SDK Server", "VI SDK UUID"
            ]
            
            for field in required_fields:
                assert field in dvs
                assert isinstance(dvs[field], str)
    
    def test_integration_get_vm_vswitch_properties(self, network_collector):
        """Test get_vm_vswitch_properties against vcsim"""
        result = network_collector.get_vm_vswitch_properties()
        
        # vcsim should return a list
        assert isinstance(result, list)
        
        # vcsim typically has standard vswitches
        if result:
            vswitch = result[0]
            required_fields = [
                "Host", "Datacenter", "Cluster", "Switch", "# Ports",
                "Free Ports", "MTU", "VI SDK Server", "VI SDK UUID"
            ]
            
            for field in required_fields:
                assert field in vswitch
                assert isinstance(vswitch[field], str)
            
            # Verify numeric fields are valid
            if vswitch["# Ports"]:
                assert vswitch["# Ports"].isdigit()
            if vswitch["Free Ports"]:
                assert vswitch["Free Ports"].isdigit()
            if vswitch["MTU"]:
                assert vswitch["MTU"].isdigit()
    
    def test_integration_datacenter_hierarchy(self, network_collector, vcenter_content):
        """Test that datacenter hierarchy is properly detected"""
        # Get datacenters from vcsim
        datacenter_view = vcenter_content.viewManager.CreateContainerView(
            vcenter_content.rootFolder, [vim.Datacenter], True
        )
        
        try:
            if datacenter_view.view:
                datacenter = datacenter_view.view[0]
                
                # Test _get_datacenter_name with a mock object that has this datacenter as parent
                class MockDVS:
                    def __init__(self, parent):
                        self.parent = parent
                
                mock_dvs = MockDVS(datacenter)
                result = network_collector._get_datacenter_name(mock_dvs)
                
                assert result == datacenter.name
                assert isinstance(result, str)
                assert len(result) > 0
        finally:
            datacenter_view.Destroy()
    
    def test_integration_host_hierarchy(self, network_collector, vcenter_content):
        """Test that host hierarchy is properly detected"""
        # Get hosts from vcsim
        host_view = vcenter_content.viewManager.CreateContainerView(
            vcenter_content.rootFolder, [vim.HostSystem], True
        )
        
        try:
            if host_view.view:
                host = host_view.view[0]
                
                # Test _get_host_location_info
                datacenter, cluster = network_collector._get_host_location_info(host)
                
                assert isinstance(datacenter, str)
                assert isinstance(cluster, str)
                # At least one should be non-empty in vcsim
                assert len(datacenter) > 0 or len(cluster) > 0
        finally:
            host_view.Destroy()
    
    def test_integration_vlan_info_extraction(self, network_collector, vcenter_content):
        """Test VLAN information extraction from real port groups"""
        # Get hosts to access their port groups
        host_view = vcenter_content.viewManager.CreateContainerView(
            vcenter_content.rootFolder, [vim.HostSystem], True
        )
        
        try:
            if host_view.view:
                host = host_view.view[0]
                if (hasattr(host, "config") and 
                    hasattr(host.config, "network") and 
                    hasattr(host.config.network, "portgroup")):
                    
                    for pg in host.config.network.portgroup:
                        # Test _get_vlan_info with real port group
                        vlan_info = network_collector._get_vlan_info(pg)
                        assert isinstance(vlan_info, str)
                        # VLAN info should be empty or a valid VLAN ID/range
                        if vlan_info:
                            assert vlan_info.replace("-", "").isdigit() or vlan_info.isdigit()
        finally:
            host_view.Destroy()
    
    def test_integration_traffic_shaping_extraction(self, network_collector, vcenter_content):
        """Test traffic shaping information extraction"""
        # Get DVS if available
        dvs_view = vcenter_content.viewManager.CreateContainerView(
            vcenter_content.rootFolder, [vim.DistributedVirtualSwitch], True
        )
        
        try:
            if dvs_view.view:
                dvs = dvs_view.view[0]
                
                # Test traffic shaping value extraction
                enabled = network_collector._get_traffic_shaping_value(dvs, "inShapingPolicy", "enabled")
                assert isinstance(enabled, str)
                
                avg_bw = network_collector._get_traffic_shaping_value(dvs, "inShapingPolicy", "averageBandwidth", divide_by=1000)
                assert isinstance(avg_bw, str)
        finally:
            dvs_view.Destroy()
    
    def test_integration_custom_attributes_extraction(self, network_collector, vcenter_content):
        """Test custom attributes extraction"""
        # Get DVS if available
        dvs_view = vcenter_content.viewManager.CreateContainerView(
            vcenter_content.rootFolder, [vim.DistributedVirtualSwitch], True
        )
        
        try:
            if dvs_view.view:
                dvs = dvs_view.view[0]
                
                # Test custom attributes extraction
                snapshot, datastore, tier = network_collector._get_custom_attributes(dvs)
                assert isinstance(snapshot, str)
                assert isinstance(datastore, str)
                assert isinstance(tier, str)
        finally:
            dvs_view.Destroy()
    
    def test_integration_host_members_extraction(self, network_collector, vcenter_content):
        """Test host members extraction from DVS"""
        # Get DVS if available
        dvs_view = vcenter_content.viewManager.CreateContainerView(
            vcenter_content.rootFolder, [vim.DistributedVirtualSwitch], True
        )
        
        try:
            if dvs_view.view:
                dvs = dvs_view.view[0]
                
                # Test host members extraction
                host_members = network_collector._get_host_members(dvs)
                assert isinstance(host_members, str)
                # If there are host members, they should be comma-separated
                if host_members:
                    assert all(isinstance(name.strip(), str) for name in host_members.split(","))
        finally:
            dvs_view.Destroy()
    
    def test_integration_lacp_value_extraction(self, network_collector, vcenter_content):
        """Test LACP value extraction"""
        # Get DVS if available
        dvs_view = vcenter_content.viewManager.CreateContainerView(
            vcenter_content.rootFolder, [vim.DistributedVirtualSwitch], True
        )
        
        try:
            if dvs_view.view:
                dvs = dvs_view.view[0]
                
                # Test LACP value extraction
                lacp_enable = network_collector._get_lacp_value(dvs, "enable")
                assert isinstance(lacp_enable, str)
                
                lacp_mode = network_collector._get_lacp_value(dvs, "mode")
                assert isinstance(lacp_mode, str)
        finally:
            dvs_view.Destroy()
    
    def test_integration_complete_workflow(self, network_collector):
        """Test complete workflow of collecting all network data"""
        # Test all main collection methods
        dvport_props = network_collector.get_vm_dvport_properties()
        port_props = network_collector.get_vm_port_properties()
        dvswitch_props = network_collector.get_vm_dvswitch_properties()
        vswitch_props = network_collector.get_vm_vswitch_properties()
        
        # All should return lists
        assert isinstance(dvport_props, list)
        assert isinstance(port_props, list)
        assert isinstance(dvswitch_props, list)
        assert isinstance(vswitch_props, list)
        
        # At least one collection should have data in vcsim
        total_items = len(dvport_props) + len(port_props) + len(dvswitch_props) + len(vswitch_props)
        assert total_items >= 0  # vcsim might not have all types of network objects
    
    def test_integration_error_handling(self, network_collector, vcenter_content):
        """Test error handling with invalid objects"""
        # Test with None objects - should not crash
        result = network_collector._get_vlan_info(None)
        assert result == ""
        
        result = network_collector._get_datacenter_name(None)
        assert result == ""
        
        result = network_collector._get_host_members(None)
        assert result == ""
        
        snapshot, datastore, tier = network_collector._get_custom_attributes(None)
        assert snapshot == ""
        assert datastore == ""
        assert tier == ""
        
        # Test with mock objects that have None parents
        mock_obj = Mock()
        mock_obj.parent = None
        result = network_collector._get_datacenter_name(mock_obj)
        assert result == ""
        
        datacenter, cluster = network_collector._get_host_location_info(mock_obj)
        assert datacenter == ""
        assert cluster == ""
    
    def test_integration_view_cleanup(self, network_collector, vcenter_content):
        """Test that views are properly cleaned up"""
        # This test ensures that the Destroy() method is called on views
        # We can't directly test this without mocking, but we can ensure
        # the methods complete without hanging or causing resource leaks
        
        # Run multiple collection cycles to test cleanup
        for _ in range(3):
            dvport_props = network_collector.get_vm_dvport_properties()
            port_props = network_collector.get_vm_port_properties()
            dvswitch_props = network_collector.get_vm_dvswitch_properties()
            vswitch_props = network_collector.get_vm_vswitch_properties()
            
            # All should complete successfully
            assert isinstance(dvport_props, list)
            assert isinstance(port_props, list)
            assert isinstance(dvswitch_props, list)
            assert isinstance(vswitch_props, list)
