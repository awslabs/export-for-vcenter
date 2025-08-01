#!/usr/bin/env python
"""
Integration tests for vcenter_connection.py module.
Tests the VCenterConnection class against a real vCenter simulator (vcsim).

Prerequisites:
- Docker must be installed and running
- vcsim container should be running on localhost:9090
  Start with: docker run -p 9090:9090 vmware/vcsim -l :9090

Note: These tests require a running vcsim instance and will be skipped if
the connection cannot be established.
"""

import pytest
import socket
from pyVmomi import vim
from src.connection.vcenter_connection import VCenterConnection


def is_vcsim_running():
    """Check if vcsim is running on localhost:9090"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 9090))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.mark.skipif(not is_vcsim_running(), reason="vcsim not running on localhost:9090")
class TestVCenterConnectionIntegration:
    """Integration test class for VCenterConnection using vcsim"""
    
    def test_successful_connection_to_vcsim(self):
        """Test successful connection to vcsim with default credentials"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        # Test connection
        service_instance = conn.connect()
        
        # Verify connection was successful
        assert service_instance is not None
        assert conn.service_instance is not None
        assert conn.content is not None
        assert conn.container is not None
        
        # Verify we can access vCenter content
        content = conn.get_content()
        assert content is not None
        assert hasattr(content, 'rootFolder')
        assert hasattr(content, 'viewManager')
        assert hasattr(content, 'propertyCollector')
        
        # Verify we can access container
        container = conn.get_container()
        assert container is not None
        assert container == content.rootFolder
        
        # Test disconnect
        conn.disconnect()
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
    
    def test_connection_with_ssl_verification_disabled(self):
        """Test connection with SSL verification explicitly disabled"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        service_instance = conn.connect()
        
        assert service_instance is not None
        assert conn.service_instance is not None
        
        # Cleanup
        conn.disconnect()
    
    def test_connection_with_invalid_host(self):
        """Test connection failure with invalid host"""
        conn = VCenterConnection(
            host="nonexistent-host",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        service_instance = conn.connect()
        
        # Connection should fail
        assert service_instance is None
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
    
    def test_connection_with_invalid_port(self):
        """Test connection failure with invalid port"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9999,  # Wrong port
            disable_ssl_verification=True
        )
        
        service_instance = conn.connect()
        
        # Connection should fail
        assert service_instance is None
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
    
    def test_multiple_connections_and_disconnections(self):
        """Test multiple connect/disconnect cycles"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        # First connection
        service_instance1 = conn.connect()
        assert service_instance1 is not None
        content1 = conn.get_content()
        container1 = conn.get_container()
        
        # Disconnect
        conn.disconnect()
        assert conn.service_instance is None
        
        # Second connection
        service_instance2 = conn.connect()
        assert service_instance2 is not None
        content2 = conn.get_content()
        container2 = conn.get_container()
        
        # Verify new connection objects
        assert content2 is not None
        assert container2 is not None
        
        # Final cleanup
        conn.disconnect()
    
    def test_vcenter_api_functionality(self):
        """Test that we can perform basic vCenter API operations after connection"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        service_instance = conn.connect()
        assert service_instance is not None
        
        content = conn.get_content()
        container = conn.get_container()
        
        try:
            # Test basic API operations
            # Get datacenter objects
            datacenter_view = content.viewManager.CreateContainerView(
                container, [vim.Datacenter], True
            )
            datacenters = datacenter_view.view
            datacenter_view.Destroy()
            
            # vcsim should have at least one datacenter
            assert len(datacenters) > 0
            assert isinstance(datacenters[0], vim.Datacenter)
            
            # Get VM objects
            vm_view = content.viewManager.CreateContainerView(
                container, [vim.VirtualMachine], True
            )
            vms = vm_view.view
            vm_view.Destroy()
            
            # vcsim should have VMs
            assert len(vms) >= 0  # May be 0 in minimal vcsim setup
            
            # Get host objects
            host_view = content.viewManager.CreateContainerView(
                container, [vim.HostSystem], True
            )
            hosts = host_view.view
            host_view.Destroy()
            
            # vcsim should have at least one host
            assert len(hosts) > 0
            assert isinstance(hosts[0], vim.HostSystem)
            
        finally:
            conn.disconnect()
    
    def test_connection_state_after_api_operations(self):
        """Test that connection state remains valid after API operations"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        service_instance = conn.connect()
        assert service_instance is not None
        
        content = conn.get_content()
        container = conn.get_container()
        
        # Perform some API operations
        try:
            # Create and destroy a view
            view = content.viewManager.CreateContainerView(
                container, [vim.Datacenter], True
            )
            datacenters = view.view
            view.Destroy()
            
            # Verify connection state is still valid
            assert conn.service_instance is not None
            assert conn.get_content() is not None
            assert conn.get_container() is not None
            
            # Verify we can still perform operations
            view2 = content.viewManager.CreateContainerView(
                container, [vim.HostSystem], True
            )
            hosts = view2.view
            view2.Destroy()
            
            assert len(hosts) > 0
            
        finally:
            conn.disconnect()
    
    def test_connection_with_default_port(self):
        """Test connection using default port (should fail for vcsim on 9090)"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            # Using default port 443, should fail since vcsim is on 9090
            disable_ssl_verification=True
        )
        
        service_instance = conn.connect()
        
        # Connection should fail because vcsim is not on port 443
        assert service_instance is None
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
    
    def test_get_methods_without_connection(self):
        """Test get_content and get_container methods without establishing connection"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        # Without connecting, these should return None
        assert conn.get_content() is None
        assert conn.get_container() is None
    
    def test_disconnect_without_connection(self):
        """Test disconnect method when no connection was established"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        # Should not raise an exception
        conn.disconnect()
        
        # State should remain None
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None


@pytest.mark.skipif(is_vcsim_running(), reason="vcsim is running, skipping offline tests")
class TestVCenterConnectionOffline:
    """Tests that run when vcsim is not available"""
    
    def test_connection_failure_when_vcsim_not_running(self):
        """Test connection failure when vcsim is not running"""
        conn = VCenterConnection(
            host="localhost",
            user="user",
            password="pass",
            port=9090,
            disable_ssl_verification=True
        )
        
        service_instance = conn.connect()
        
        # Connection should fail
        assert service_instance is None
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
