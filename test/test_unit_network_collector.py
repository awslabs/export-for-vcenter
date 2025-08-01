#!/usr/bin/env python
"""
Unit tests for network_collector.py module.
Tests the NetworkCollector class and its methods.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.collectors.network_collector import NetworkCollector
from pyVmomi import vim


class TestNetworkCollector:
    """Test class for NetworkCollector"""
    
    @pytest.fixture
    def mock_content(self):
        """Create a mock content object for testing"""
        mock_content = Mock()
        mock_content.about.fullName = "VMware vCenter Server 7.0"
        mock_content.about.instanceUuid = "test-uuid-123"
        
        # Mock viewManager
        mock_view_manager = Mock()
        mock_content.viewManager = mock_view_manager
        
        return mock_content
    
    @pytest.fixture
    def mock_container(self):
        """Create a mock container for testing"""
        return Mock()
    
    @pytest.fixture
    def network_collector(self, mock_content, mock_container):
        """Create NetworkCollector instance for testing"""
        return NetworkCollector(mock_content, mock_container)
    
    def test_init(self, mock_content, mock_container):
        """Test NetworkCollector initialization"""
        collector = NetworkCollector(mock_content, mock_container)
        assert collector.content == mock_content
        assert collector.container == mock_container
    
    def test_get_vm_dvport_properties_empty(self, network_collector, mock_content):
        """Test get_vm_dvport_properties with no DVS"""
        # Mock empty DVS view
        mock_dvs_view = Mock()
        mock_dvs_view.view = []
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        
        result = network_collector.get_vm_dvport_properties()
        
        assert result == []
        mock_dvs_view.Destroy.assert_called_once()
    
    def test_get_vm_dvport_properties_with_dvs(self, network_collector, mock_content):
        """Test get_vm_dvport_properties with DVS and port groups"""
        # Mock DVS with port groups
        mock_pg = Mock()
        mock_pg.key = "dvportgroup-123"
        mock_pg.config.defaultPortConfig.vlan.vlanId = 100
        
        mock_dvs = Mock()
        mock_dvs.name = "test-dvs"
        mock_dvs.portgroup = [mock_pg]
        
        mock_dvs_view = Mock()
        mock_dvs_view.view = [mock_dvs]
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        
        result = network_collector.get_vm_dvport_properties()
        
        assert len(result) == 1
        assert result[0]["Port"] == "dvportgroup-123"
        assert result[0]["Switch"] == "test-dvs"
        assert result[0]["VLAN"] == "100"
        mock_dvs_view.Destroy.assert_called_once()
    
    def test_get_vlan_info_numeric(self, network_collector):
        """Test _get_vlan_info with numeric VLAN ID"""
        mock_pg = Mock()
        mock_pg.config.defaultPortConfig.vlan.vlanId = 100
        
        result = network_collector._get_vlan_info(mock_pg)
        assert result == "100"
    
    def test_get_vlan_info_range(self, network_collector):
        """Test _get_vlan_info with VLAN range"""
        mock_range = Mock()
        mock_range.start = 100
        mock_range.end = 200
        
        mock_pg = Mock()
        mock_pg.config.defaultPortConfig.vlan.vlanId = [mock_range]
        
        result = network_collector._get_vlan_info(mock_pg)
        assert result == "100-200"
    
    def test_get_vlan_info_no_vlan(self, network_collector):
        """Test _get_vlan_info with no VLAN configuration"""
        mock_pg = Mock()
        del mock_pg.config  # Remove config attribute
        
        result = network_collector._get_vlan_info(mock_pg)
        assert result == ""
    
    def test_get_vm_port_properties_empty(self, network_collector, mock_content):
        """Test get_vm_port_properties with no hosts"""
        mock_host_view = Mock()
        mock_host_view.view = []
        mock_content.viewManager.CreateContainerView.return_value = mock_host_view
        
        result = network_collector.get_vm_port_properties()
        
        assert result == []
        mock_host_view.Destroy.assert_called_once()
    
    def test_get_vm_port_properties_with_hosts(self, network_collector, mock_content):
        """Test get_vm_port_properties with hosts and port groups"""
        # Create a more controlled mock that doesn't have distributedVirtualSwitch
        mock_pg = MagicMock()
        mock_pg.spec.name = "VM Network"
        mock_pg.spec.vswitchName = "vSwitch0"
        mock_pg.spec.vlanId = 0
        
        # Use side_effect to control hasattr behavior
        def mock_hasattr(obj, attr):
            if attr == "distributedVirtualSwitch":
                return False
            return True
        
        # Mock host
        mock_host = Mock()
        mock_host.config.network.portgroup = [mock_pg]
        
        mock_host_view = Mock()
        mock_host_view.view = [mock_host]
        mock_content.viewManager.CreateContainerView.return_value = mock_host_view
        
        # Patch hasattr to control the distributedVirtualSwitch check
        with patch('builtins.hasattr', side_effect=mock_hasattr):
            result = network_collector.get_vm_port_properties()
        
        assert len(result) == 1
        assert result[0]["Port Group"] == "VM Network"
        assert result[0]["Switch"] == "vSwitch0"
        assert result[0]["VLAN"] == "0"
        mock_host_view.Destroy.assert_called_once()
    
    def test_get_vm_port_properties_skip_distributed(self, network_collector, mock_content):
        """Test get_vm_port_properties skips distributed port groups"""
        # Mock distributed port group (should be skipped)
        mock_dvpg = MagicMock()
        mock_dvpg.spec.name = "DV Port Group"
        mock_dvpg.spec.distributedVirtualSwitch = Mock()
        
        # Mock standard port group (should be included)
        mock_pg = MagicMock()
        mock_pg.spec.name = "VM Network"
        mock_pg.spec.vswitchName = "vSwitch0"
        mock_pg.spec.vlanId = 0
        
        # Mock host with both types
        mock_host = Mock()
        mock_host.config.network.portgroup = [mock_dvpg, mock_pg]
        
        mock_host_view = Mock()
        mock_host_view.view = [mock_host]
        mock_content.viewManager.CreateContainerView.return_value = mock_host_view
        
        # Control hasattr behavior for both port groups
        def mock_hasattr(obj, attr):
            if attr == "distributedVirtualSwitch":
                # Return True for dvpg (has the attribute), False for pg (doesn't have it)
                return obj == mock_dvpg.spec
            return True
        
        with patch('builtins.hasattr', side_effect=mock_hasattr):
            result = network_collector.get_vm_port_properties()
        
        # Should only have the standard port group, not the distributed one
        assert len(result) == 1
        assert result[0]["Port Group"] == "VM Network"
        assert result[0]["Switch"] == "vSwitch0"
        mock_host_view.Destroy.assert_called_once()
    
    def test_get_vm_dvswitch_properties_empty(self, network_collector, mock_content):
        """Test get_vm_dvswitch_properties with no DVS"""
        mock_dvs_view = Mock()
        mock_dvs_view.view = []
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        
        result = network_collector.get_vm_dvswitch_properties()
        
        assert result == []
        mock_dvs_view.Destroy.assert_called_once()
    
    def test_get_vm_dvswitch_properties_with_dvs(self, network_collector, mock_content):
        """Test get_vm_dvswitch_properties with DVS"""
        # Mock datacenter
        mock_datacenter = Mock(spec=vim.Datacenter)
        mock_datacenter.name = "test-dc"
        
        # Mock host member
        mock_host = Mock()
        mock_host.name = "test-host"
        
        # Mock DVS
        mock_dvs = Mock()
        mock_dvs.name = "test-dvs"
        mock_dvs.parent = mock_datacenter
        mock_dvs.config.vendor = "VMware"
        mock_dvs.config.version = "7.0.0"
        mock_dvs.config.description = "Test DVS"
        mock_dvs.config.createTime = "2023-01-01T00:00:00Z"
        mock_dvs.config.maxPorts = 8192
        mock_dvs.summary.numPorts = 1024
        mock_dvs.summary.hostMember = [mock_host]
        mock_dvs.vm = []
        mock_dvs.customValue = []
        mock_dvs._moId = "dvs-123"
        
        # Mock traffic shaping and other policies
        mock_dvs.config.defaultPortConfig.inShapingPolicy.enabled.value = True
        mock_dvs.config.defaultPortConfig.inShapingPolicy.averageBandwidth.value = 1000000
        mock_dvs.config.defaultPortConfig.inShapingPolicy.peakBandwidth.value = 2000000
        mock_dvs.config.defaultPortConfig.inShapingPolicy.burstSize.value = 1048576
        
        mock_dvs.config.defaultPortConfig.outShapingPolicy.enabled.value = False
        mock_dvs.config.defaultPortConfig.outShapingPolicy.averageBandwidth.value = 500000
        mock_dvs.config.defaultPortConfig.outShapingPolicy.peakBandwidth.value = 1000000
        mock_dvs.config.defaultPortConfig.outShapingPolicy.burstSize.value = 524288
        
        mock_dvs.config.linkDiscoveryProtocolConfig.protocol = "cdp"
        mock_dvs.config.linkDiscoveryProtocolConfig.operation = "listen"
        mock_dvs.config.lacpApiVersion = "multipleLag"
        mock_dvs.config.defaultPortConfig.lacpPolicy.enable.value = True
        mock_dvs.config.defaultPortConfig.lacpPolicy.mode.value = "active"
        mock_dvs.config.maxMtu = 9000
        mock_dvs.config.contact.name = "Admin"
        mock_dvs.config.contact.contact = "admin@company.com"
        
        mock_dvs_view = Mock()
        mock_dvs_view.view = [mock_dvs]
        mock_content.viewManager.CreateContainerView.return_value = mock_dvs_view
        
        result = network_collector.get_vm_dvswitch_properties()
        
        assert len(result) == 1
        dvs_props = result[0]
        assert dvs_props["Switch"] == "test-dvs"
        assert dvs_props["Datacenter"] == "test-dc"
        assert dvs_props["Vendor"] == "VMware"
        assert dvs_props["Version"] == "7.0.0"
        assert dvs_props["Host members"] == "test-host"
        assert dvs_props["# VMs"] == "0"
        assert dvs_props["In Traffic Shaping"] == "True"
        assert dvs_props["In Avg"] == "1000"  # 1000000 / 1000
        assert dvs_props["Out Traffic Shaping"] == "False"
        mock_dvs_view.Destroy.assert_called_once()
    
    def test_get_datacenter_name(self, network_collector):
        """Test _get_datacenter_name method"""
        # Mock datacenter hierarchy
        mock_datacenter = Mock(spec=vim.Datacenter)
        mock_datacenter.name = "test-datacenter"
        
        mock_dvs = Mock()
        mock_dvs.parent = mock_datacenter
        
        result = network_collector._get_datacenter_name(mock_dvs)
        assert result == "test-datacenter"
    
    def test_get_datacenter_name_no_datacenter(self, network_collector):
        """Test _get_datacenter_name with no datacenter parent"""
        mock_dvs = Mock()
        mock_dvs.parent = None
        
        result = network_collector._get_datacenter_name(mock_dvs)
        assert result == ""
    
    def test_get_host_members(self, network_collector):
        """Test _get_host_members method"""
        mock_host1 = Mock()
        mock_host1.name = "host1"
        mock_host2 = Mock()
        mock_host2.name = "host2"
        
        mock_dvs = Mock()
        mock_dvs.summary.hostMember = [mock_host1, mock_host2]
        
        result = network_collector._get_host_members(mock_dvs)
        assert result == "host1, host2"
    
    def test_get_host_members_empty(self, network_collector):
        """Test _get_host_members with no host members"""
        mock_dvs = Mock()
        mock_dvs.summary.hostMember = []
        
        result = network_collector._get_host_members(mock_dvs)
        assert result == ""
    
    def test_get_custom_attributes(self, network_collector):
        """Test _get_custom_attributes method"""
        mock_value1 = Mock()
        mock_value1.key = "com.vrlcm.snapshot"
        mock_value1.value = "snapshot-123"
        
        mock_value2 = Mock()
        mock_value2.key = "Datastore"
        mock_value2.value = "datastore1"
        
        mock_value3 = Mock()
        mock_value3.key = "Tier"
        mock_value3.value = "Gold"
        
        mock_dvs = Mock()
        mock_dvs.customValue = [mock_value1, mock_value2, mock_value3]
        
        snapshot, datastore, tier = network_collector._get_custom_attributes(mock_dvs)
        assert snapshot == "snapshot-123"
        assert datastore == "datastore1"
        assert tier == "Gold"
    
    def test_get_custom_attributes_empty(self, network_collector):
        """Test _get_custom_attributes with no custom values"""
        mock_dvs = Mock()
        mock_dvs.customValue = []
        
        snapshot, datastore, tier = network_collector._get_custom_attributes(mock_dvs)
        assert snapshot == ""
        assert datastore == ""
        assert tier == ""
    
    def test_get_traffic_shaping_value(self, network_collector):
        """Test _get_traffic_shaping_value method"""
        mock_dvs = Mock()
        mock_dvs.config.defaultPortConfig.inShapingPolicy.enabled.value = True
        mock_dvs.config.defaultPortConfig.inShapingPolicy.averageBandwidth.value = 1000000
        
        # Test enabled value
        result = network_collector._get_traffic_shaping_value(mock_dvs, "inShapingPolicy", "enabled")
        assert result == "True"
        
        # Test bandwidth value with division
        result = network_collector._get_traffic_shaping_value(mock_dvs, "inShapingPolicy", "averageBandwidth", divide_by=1000)
        assert result == "1000"
    
    def test_get_traffic_shaping_value_missing_attribute(self, network_collector):
        """Test _get_traffic_shaping_value with missing attribute"""
        mock_dvs = Mock()
        del mock_dvs.config  # Remove config attribute
        
        result = network_collector._get_traffic_shaping_value(mock_dvs, "inShapingPolicy", "enabled")
        assert result == ""
    
    def test_get_lacp_value(self, network_collector):
        """Test _get_lacp_value method"""
        mock_dvs = Mock()
        mock_dvs.config.defaultPortConfig.lacpPolicy.enable.value = True
        mock_dvs.config.defaultPortConfig.lacpPolicy.mode.value = "active"
        
        # Test enable value
        result = network_collector._get_lacp_value(mock_dvs, "enable")
        assert result == "True"
        
        # Test mode value
        result = network_collector._get_lacp_value(mock_dvs, "mode")
        assert result == "active"
    
    def test_get_lacp_value_missing_attribute(self, network_collector):
        """Test _get_lacp_value with missing attribute"""
        mock_dvs = Mock()
        del mock_dvs.config  # Remove config attribute
        
        result = network_collector._get_lacp_value(mock_dvs, "enable")
        assert result == ""
    
    def test_get_vm_vswitch_properties_empty(self, network_collector, mock_content):
        """Test get_vm_vswitch_properties with no hosts"""
        mock_host_view = Mock()
        mock_host_view.view = []
        mock_content.viewManager.CreateContainerView.return_value = mock_host_view
        
        result = network_collector.get_vm_vswitch_properties()
        
        assert result == []
        mock_host_view.Destroy.assert_called_once()
    
    def test_get_vm_vswitch_properties_with_hosts(self, network_collector, mock_content):
        """Test get_vm_vswitch_properties with hosts and vswitches"""
        # Mock datacenter and cluster
        mock_datacenter = Mock(spec=vim.Datacenter)
        mock_datacenter.name = "test-dc"
        mock_datacenter.parent = None
        
        mock_cluster = Mock(spec=vim.ClusterComputeResource)
        mock_cluster.name = "test-cluster"
        mock_cluster.parent = mock_datacenter
        
        # Mock vswitch
        mock_vswitch = Mock()
        mock_vswitch.name = "vSwitch0"
        mock_vswitch.numPorts = 128
        mock_vswitch.numPortsAvailable = 120
        mock_vswitch.mtu = 1500
        mock_vswitch.spec.policy.security.allowPromiscuous = False
        mock_vswitch.spec.policy.security.macChanges = True
        mock_vswitch.spec.policy.security.forgedTransmits = True
        mock_vswitch.spec.policy.shapingPolicy.enabled = False
        mock_vswitch.spec.policy.shapingPolicy.averageBandwidth = 0
        mock_vswitch.spec.policy.shapingPolicy.peakBandwidth = 0
        mock_vswitch.spec.policy.shapingPolicy.burstSize = 0
        mock_vswitch.spec.policy.nicTeaming.policy = "loadbalance_srcid"
        mock_vswitch.spec.policy.nicTeaming.reversePolicy = True
        mock_vswitch.spec.policy.nicTeaming.notifySwitches = True
        mock_vswitch.spec.policy.nicTeaming.rollingOrder = False
        
        # Mock host
        mock_host = Mock()
        mock_host.name = "test-host"
        mock_host.parent = mock_cluster
        mock_host.config.network.vswitch = [mock_vswitch]
        mock_host.config.netOffloadCapabilities.csOffload = True
        mock_host.config.netOffloadCapabilities.tcpSegmentation = True
        
        mock_host_view = Mock()
        mock_host_view.view = [mock_host]
        mock_content.viewManager.CreateContainerView.return_value = mock_host_view
        
        result = network_collector.get_vm_vswitch_properties()
        
        assert len(result) == 1
        vswitch_props = result[0]
        assert vswitch_props["Host"] == "test-host"
        assert vswitch_props["Datacenter"] == "test-dc"
        assert vswitch_props["Cluster"] == "test-cluster"
        assert vswitch_props["Switch"] == "vSwitch0"
        assert vswitch_props["# Ports"] == "128"
        assert vswitch_props["Free Ports"] == "120"
        assert vswitch_props["MTU"] == "1500"
        mock_host_view.Destroy.assert_called_once()
    
    def test_get_host_location_info(self, network_collector):
        """Test _get_host_location_info method"""
        # Mock hierarchy: host -> cluster -> datacenter
        mock_datacenter = Mock(spec=vim.Datacenter)
        mock_datacenter.name = "test-datacenter"
        mock_datacenter.parent = None
        
        mock_cluster = Mock(spec=vim.ClusterComputeResource)
        mock_cluster.name = "test-cluster"
        mock_cluster.parent = mock_datacenter
        
        mock_host = Mock()
        mock_host.parent = mock_cluster
        
        datacenter, cluster = network_collector._get_host_location_info(mock_host)
        assert datacenter == "test-datacenter"
        assert cluster == "test-cluster"
    
    def test_get_host_location_info_no_cluster(self, network_collector):
        """Test _get_host_location_info with host directly under datacenter"""
        mock_datacenter = Mock(spec=vim.Datacenter)
        mock_datacenter.name = "test-datacenter"
        mock_datacenter.parent = None
        
        mock_host = Mock()
        mock_host.parent = mock_datacenter
        
        datacenter, cluster = network_collector._get_host_location_info(mock_host)
        assert datacenter == "test-datacenter"
        assert cluster == ""
    
    def test_build_vswitch_properties(self, network_collector):
        """Test _build_vswitch_properties method"""
        mock_host = Mock()
        mock_host.name = "test-host"
        mock_host.config.netOffloadCapabilities.csOffload = True
        mock_host.config.netOffloadCapabilities.tcpSegmentation = False
        
        mock_vswitch = Mock()
        mock_vswitch.name = "vSwitch0"
        mock_vswitch.numPorts = 128
        mock_vswitch.numPortsAvailable = 120
        mock_vswitch.mtu = 1500
        mock_vswitch.spec.policy.security.allowPromiscuous = False
        mock_vswitch.spec.policy.security.macChanges = True
        mock_vswitch.spec.policy.security.forgedTransmits = True
        mock_vswitch.spec.policy.shapingPolicy.enabled = True
        mock_vswitch.spec.policy.shapingPolicy.averageBandwidth = 1000000
        mock_vswitch.spec.policy.shapingPolicy.peakBandwidth = 2000000
        mock_vswitch.spec.policy.shapingPolicy.burstSize = 1048576
        mock_vswitch.spec.policy.nicTeaming.policy = "loadbalance_srcid"
        mock_vswitch.spec.policy.nicTeaming.reversePolicy = True
        mock_vswitch.spec.policy.nicTeaming.notifySwitches = True
        mock_vswitch.spec.policy.nicTeaming.rollingOrder = False
        
        result = network_collector._build_vswitch_properties(
            mock_host, mock_vswitch, "test-dc", "test-cluster"
        )
        
        assert result["Host"] == "test-host"
        assert result["Datacenter"] == "test-dc"
        assert result["Cluster"] == "test-cluster"
        assert result["Switch"] == "vSwitch0"
        assert result["# Ports"] == "128"
        assert result["Free Ports"] == "120"
        assert result["MTU"] == "1500"
        assert result["Promiscuous Mode"] == "False"
        assert result["Mac Changes"] == "True"
        assert result["Forged Transmits"] == "True"
        assert result["Traffic Shaping"] == "True"
        assert result["Width"] == "1000000"
        assert result["Peak"] == "2000000"
        assert result["Burst"] == "1048576"
        assert result["Policy"] == "loadbalance_srcid"
        assert result["TSO"] == "True"
        assert result["Zero Copy Xmit"] == "False"
        assert result["VI SDK Server"] == "VMware vCenter Server 7.0"
        assert result["VI SDK UUID"] == "test-uuid-123"
    
    def test_build_dvswitch_properties(self, network_collector):
        """Test _build_dvswitch_properties method"""
        mock_dvs = Mock()
        mock_dvs.name = "test-dvs"
        mock_dvs.config.vendor = "VMware"
        mock_dvs.config.version = "7.0.0"
        mock_dvs.config.description = "Test DVS"
        mock_dvs.config.maxPorts = 8192
        mock_dvs.summary.numPorts = 1024
        mock_dvs.config.linkDiscoveryProtocolConfig.protocol = "cdp"
        mock_dvs.config.linkDiscoveryProtocolConfig.operation = "listen"
        mock_dvs.config.lacpApiVersion = "multipleLag"
        mock_dvs.config.maxMtu = 9000
        mock_dvs.config.contact.name = "Admin"
        mock_dvs.config.contact.contact = "admin@company.com"
        mock_dvs._moId = "dvs-123"
        
        # Mock the traffic shaping and LACP methods to return expected values
        with patch.object(network_collector, '_get_traffic_shaping_value') as mock_traffic, \
             patch.object(network_collector, '_get_lacp_value') as mock_lacp:
            
            # Configure mock return values
            mock_traffic.side_effect = lambda dvs, policy, attr, divide_by=None: {
                ('inShapingPolicy', 'enabled'): 'True',
                ('inShapingPolicy', 'averageBandwidth'): '1000',
                ('inShapingPolicy', 'peakBandwidth'): '2000',
                ('inShapingPolicy', 'burstSize'): '1024',
                ('outShapingPolicy', 'enabled'): 'False',
                ('outShapingPolicy', 'averageBandwidth'): '500',
                ('outShapingPolicy', 'peakBandwidth'): '1000',
                ('outShapingPolicy', 'burstSize'): '512'
            }.get((policy, attr), '')
            
            mock_lacp.side_effect = lambda dvs, attr: {
                'enable': 'True',
                'mode': 'active'
            }.get(attr, '')
            
            result = network_collector._build_dvswitch_properties(
                mock_dvs, "test-dc", "host1, host2", "5", "2023-01-01", 
                "snapshot-123", "datastore1", "Gold"
            )
        
        assert result["Switch"] == "test-dvs"
        assert result["Datacenter"] == "test-dc"
        assert result["Name"] == "test-dvs"
        assert result["Vendor"] == "VMware"
        assert result["Version"] == "7.0.0"
        assert result["Description"] == "Test DVS"
        assert result["Created"] == "2023-01-01"
        assert result["Host members"] == "host1, host2"
        assert result["Max Ports"] == "8192"
        assert result["# Ports"] == "1024"
        assert result["# VMs"] == "5"
        assert result["CDP Type"] == "cdp"
        assert result["CDP Operation"] == "listen"
        assert result["LACP Name"] == "multipleLag"
        assert result["Max MTU"] == "9000"
        assert result["Contact"] == "Admin"
        assert result["Admin Name"] == "admin@company.com"
        assert result["Object ID"] == "dvs-123"
        assert result["com.vrlcm.snapshot"] == "snapshot-123"
        assert result["Datastore"] == "datastore1"
        assert result["Tier"] == "Gold"
        assert result["VI SDK Server"] == "VMware vCenter Server 7.0"
        assert result["VI SDK UUID"] == "test-uuid-123"
