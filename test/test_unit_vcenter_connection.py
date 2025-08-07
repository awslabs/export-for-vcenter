#!/usr/bin/env python
"""
Unit tests for vcenter_connection.py module.
Tests the VCenterConnection class using mocks to avoid external dependencies.
"""

import pytest
import ssl
from unittest.mock import Mock, patch, MagicMock
from pyVmomi import vim
from src.connection.vcenter_connection import VCenterConnection


class TestVCenterConnectionUnit:
    """Unit test class for VCenterConnection"""
    
    def test_init_default_parameters(self):
        """Test VCenterConnection initialization with default parameters"""
        conn = VCenterConnection("test-host", "test-user", "test-password")
        
        assert conn.host == "test-host"
        assert conn.user == "test-user"
        assert conn.password == "test-password"
        assert conn.port == 443
        assert conn.disable_ssl_verification is False
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
    
    def test_init_custom_parameters(self):
        """Test VCenterConnection initialization with custom parameters"""
        conn = VCenterConnection(
            host="custom-host",
            user="custom-user", 
            password="custom-password",
            port=8443,
            disable_ssl_verification=True
        )
        
        assert conn.host == "custom-host"
        assert conn.user == "custom-user"
        assert conn.password == "custom-password"
        assert conn.port == 8443
        assert conn.disable_ssl_verification is True
    
    @patch('src.connection.vcenter_connection.connect.SmartConnect')
    @patch('src.connection.vcenter_connection.atexit.register')
    def test_connect_success_with_ssl_verification(self, mock_atexit, mock_smart_connect):
        """Test successful connection with SSL verification enabled"""
        # Setup mocks
        mock_service_instance = Mock()
        mock_content = Mock()
        mock_container = Mock()
        
        mock_smart_connect.return_value = mock_service_instance
        mock_service_instance.RetrieveContent.return_value = mock_content
        mock_content.rootFolder = mock_container
        
        # Create connection and connect
        conn = VCenterConnection("test-host", "test-user", "test-password")
        
        with patch('builtins.print') as mock_print:
            result = conn.connect()
        
        # Verify connection was successful
        assert result == mock_service_instance
        assert conn.service_instance == mock_service_instance
        assert conn.content == mock_content
        assert conn.container == mock_container
        
        # Verify SmartConnect was called with correct parameters
        mock_smart_connect.assert_called_once_with(
            host="test-host",
            user="test-user",
            pwd="test-password",
            port=443,
            disableSslCertValidation=False,
            sslContext=None
        )
        
        # Verify atexit was registered
        mock_atexit.assert_called_once()
        
        # Verify success message was printed
        mock_print.assert_called_with("Successfully connected to vCenter Server: test-host")
    
    @patch('src.connection.vcenter_connection.ssl.create_default_context')
    @patch('src.connection.vcenter_connection.connect.SmartConnect')
    @patch('src.connection.vcenter_connection.atexit.register')
    def test_connect_success_with_ssl_disabled(self, mock_atexit, mock_smart_connect, mock_ssl_context):
        """Test successful connection with SSL verification disabled"""
        # Setup mocks
        mock_service_instance = Mock()
        mock_content = Mock()
        mock_container = Mock()
        mock_context = Mock()
        
        mock_smart_connect.return_value = mock_service_instance
        mock_service_instance.RetrieveContent.return_value = mock_content
        mock_content.rootFolder = mock_container
        mock_ssl_context.return_value = mock_context
        
        # Create connection with SSL disabled and connect
        conn = VCenterConnection("test-host", "test-user", "test-password", disable_ssl_verification=True)
        
        with patch('builtins.print') as mock_print:
            result = conn.connect()
        
        # Verify connection was successful
        assert result == mock_service_instance
        assert conn.service_instance == mock_service_instance
        assert conn.content == mock_content
        assert conn.container == mock_container
        
        # Verify SSL context was created and configured
        mock_ssl_context.assert_called_once()
        assert mock_context.check_hostname is False
        assert mock_context.verify_mode == ssl.CERT_NONE
        
        # Verify SmartConnect was called with SSL disabled
        mock_smart_connect.assert_called_once_with(
            host="test-host",
            user="test-user",
            pwd="test-password",
            port=443,
            disableSslCertValidation=True,
            sslContext=mock_context
        )
        
        # Verify success message was printed
        mock_print.assert_called_with("Successfully connected to vCenter Server: test-host")
    
    @patch('src.connection.vcenter_connection.connect.SmartConnect')
    def test_connect_invalid_login(self, mock_smart_connect):
        """Test connection failure due to invalid login credentials"""
        # Setup mock to raise InvalidLogin exception
        mock_smart_connect.side_effect = vim.fault.InvalidLogin()
        
        conn = VCenterConnection("test-host", "bad-user", "bad-password")
        
        with patch('builtins.print') as mock_print:
            result = conn.connect()
        
        # Verify connection failed
        assert result is None
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
        
        # Verify error message was printed
        mock_print.assert_called_with("Invalid login credentials")
    
    @patch('src.connection.vcenter_connection.connect.SmartConnect')
    def test_connect_general_exception(self, mock_smart_connect):
        """Test connection failure due to general exception"""
        # Setup mock to raise general exception
        error_message = "Connection timeout"
        mock_smart_connect.side_effect = Exception(error_message)
        
        conn = VCenterConnection("unreachable-host", "test-user", "test-password")
        
        with patch('builtins.print') as mock_print:
            result = conn.connect()
        
        # Verify connection failed
        assert result is None
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
        
        # Verify error message was printed
        mock_print.assert_called_with(f"Failed to connect to vCenter Server: {error_message}")
    
    def test_get_content_when_connected(self):
        """Test get_content method when connection is established"""
        conn = VCenterConnection("test-host", "test-user", "test-password")
        mock_content = Mock()
        conn.content = mock_content
        
        result = conn.get_content()
        assert result == mock_content
    
    def test_get_content_when_not_connected(self):
        """Test get_content method when not connected"""
        conn = VCenterConnection("test-host", "test-user", "test-password")
        
        result = conn.get_content()
        assert result is None
    
    def test_get_container_when_connected(self):
        """Test get_container method when connection is established"""
        conn = VCenterConnection("test-host", "test-user", "test-password")
        mock_container = Mock()
        conn.container = mock_container
        
        result = conn.get_container()
        assert result == mock_container
    
    def test_get_container_when_not_connected(self):
        """Test get_container method when not connected"""
        conn = VCenterConnection("test-host", "test-user", "test-password")
        
        result = conn.get_container()
        assert result is None
    
    @patch('src.connection.vcenter_connection.connect.Disconnect')
    def test_disconnect_when_connected(self, mock_disconnect):
        """Test disconnect method when connection exists"""
        conn = VCenterConnection("test-host", "test-user", "test-password")
        mock_service_instance = Mock()
        mock_content = Mock()
        mock_container = Mock()
        
        # Set up connection state
        conn.service_instance = mock_service_instance
        conn.content = mock_content
        conn.container = mock_container
        
        conn.disconnect()
        
        # Verify disconnect was called
        mock_disconnect.assert_called_once_with(mock_service_instance)
        
        # Verify state was reset
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
    
    @patch('src.connection.vcenter_connection.connect.Disconnect')
    def test_disconnect_when_not_connected(self, mock_disconnect):
        """Test disconnect method when no connection exists"""
        conn = VCenterConnection("test-host", "test-user", "test-password")
        
        conn.disconnect()
        
        # Verify disconnect was not called
        mock_disconnect.assert_not_called()
        
        # Verify state remains None
        assert conn.service_instance is None
        assert conn.content is None
        assert conn.container is None
    
    @patch('src.connection.vcenter_connection.connect.SmartConnect')
    @patch('src.connection.vcenter_connection.atexit.register')
    def test_connect_custom_port(self, mock_atexit, mock_smart_connect):
        """Test connection with custom port"""
        mock_service_instance = Mock()
        mock_content = Mock()
        mock_container = Mock()
        
        mock_smart_connect.return_value = mock_service_instance
        mock_service_instance.RetrieveContent.return_value = mock_content
        mock_content.rootFolder = mock_container
        
        conn = VCenterConnection("test-host", "test-user", "test-password", port=8443)
        
        with patch('builtins.print'):
            conn.connect()
        
        # Verify SmartConnect was called with custom port
        mock_smart_connect.assert_called_once_with(
            host="test-host",
            user="test-user",
            pwd="test-password",
            port=8443,
            disableSslCertValidation=False,
            sslContext=None
        )
    
    @patch('src.connection.vcenter_connection.connect.SmartConnect')
    def test_connect_preserves_existing_connection_on_failure(self, mock_smart_connect):
        """Test that connection failure doesn't affect existing connection state"""
        conn = VCenterConnection("test-host", "test-user", "test-password")
        
        # Set up existing connection state
        existing_service_instance = Mock()
        existing_content = Mock()
        existing_container = Mock()
        
        conn.service_instance = existing_service_instance
        conn.content = existing_content
        conn.container = existing_container
        
        # Make connection fail
        mock_smart_connect.side_effect = Exception("Connection failed")
        
        with patch('builtins.print'):
            result = conn.connect()
        
        # Verify connection failed but existing state is preserved
        assert result is None
        assert conn.service_instance == existing_service_instance
        assert conn.content == existing_content
        assert conn.container == existing_container
