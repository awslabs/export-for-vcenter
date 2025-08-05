#!/usr/bin/env python
"""
Module for handling vCenter connections and authentication.
"""
import ssl
import atexit
from pyVim import connect
from pyVmomi import vim


class VCenterConnection:
    """
    Class to handle vCenter server connections.
    """
    
    def __init__(self, host, user, password, port=443, disable_ssl_verification=False):
        """
        Initialize connection parameters.
        
        Args:
            host (str): The vCenter server hostname or IP address
            user (str): The username to authenticate with
            password (str): The password to authenticate with
            port (int): The port to connect on (default: 443)
            disable_ssl_verification (bool): Whether to disable SSL certificate verification
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.disable_ssl_verification = disable_ssl_verification
        self.service_instance = None
        self.content = None
        self.container = None
    
    def connect(self):
        """
        Connect to vCenter server and return the service instance object.
        
        Returns:
            ServiceInstance: The vCenter service instance or None if connection failed
        """
        context = None
        
        # Create SSL context if SSL verification is disabled
        if self.disable_ssl_verification:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        
        try:
            # Connect to vCenter server
            self.service_instance = connect.SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                port=self.port,
                disableSslCertValidation=self.disable_ssl_verification,
                sslContext=context
            )
            
            # Register disconnect function to be called when script exits
            atexit.register(connect.Disconnect, self.service_instance)
            
            # Initialize content and container
            self.content = self.service_instance.RetrieveContent()
            self.container = self.content.rootFolder
            
            print(f"Successfully connected to vCenter Server: {self.host}")
            return self.service_instance
        
        except vim.fault.InvalidLogin:
            print("Invalid login credentials")
            return None
        except Exception as e:
            print(f"Failed to connect to vCenter Server: {str(e)}")
            return None
    
    def get_content(self):
        """Get the service instance content."""
        return self.content
    
    def get_container(self):
        """Get the root folder container."""
        return self.container
    
    def disconnect(self):
        """Disconnect from vCenter server."""
        if self.service_instance:
            connect.Disconnect(self.service_instance)
            self.service_instance = None
            self.content = None
            self.container = None