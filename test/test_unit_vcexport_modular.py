#!/usr/bin/env python
"""
Unit tests for vcexport_modular.py main script.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os
import argparse

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import vcexport_modular


class TestVCExportModular:
    """Test cases for vcexport_modular.py main script."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Store original sys.argv
        self.original_argv = sys.argv.copy()
        
        # Store original environment variables
        self.original_env = {}
        env_vars = ['EXP_VCENTER_HOST', 'EXP_VCENTER_USER', 'EXP_VCENTER_PASSWORD', 'EXP_DISABLE_SSL_VERIFICATION']
        for var in env_vars:
            self.original_env[var] = os.environ.get(var)
    
    def teardown_method(self):
        """Clean up after each test method."""
        # Restore original sys.argv
        sys.argv = self.original_argv
        
        # Restore original environment variables
        for var, value in self.original_env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
    
    def test_python_version_check_success(self):
        """Test that Python version check passes for supported versions."""
        with patch('sys.version_info', (3, 10, 0)):
            # Should not raise SystemExit
            try:
                # Import would trigger version check
                import importlib
                importlib.reload(vcexport_modular)
            except SystemExit:
                pytest.fail("Python version check should pass for 3.10+")
    
    @patch('vcexport_modular.VCenterOrchestrator')
    def test_main_success_default_args(self, mock_orchestrator_class):
        """Test successful main execution with default arguments."""
        # Set up environment variables
        os.environ['EXP_VCENTER_HOST'] = 'test-vcenter.example.com'
        os.environ['EXP_VCENTER_USER'] = 'test-user'
        os.environ['EXP_VCENTER_PASSWORD'] = 'test-password'
        
        # Mock orchestrator instance
        mock_orchestrator = Mock()
        mock_orchestrator.connect.return_value = True
        mock_orchestrator.export_data.return_value = 'vcexport.zip'
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Mock sys.argv for default arguments
        sys.argv = ['vcexport_modular.py']
        
        with patch('sys.exit') as mock_exit:
            vcexport_modular.main()
            
            # Verify orchestrator was created with correct parameters
            mock_orchestrator_class.assert_called_once_with(
                host='test-vcenter.example.com',
                user='test-user',
                password='test-password',
                disable_ssl_verification=False
            )
            
            # Verify orchestrator methods were called
            mock_orchestrator.connect.assert_called_once()
            mock_orchestrator.export_data.assert_called_once_with(
                max_count=None,
                purge_csv=True,
                export_statistics=True,
                perf_interval=60
            )
            mock_orchestrator.disconnect.assert_called_once()
            
            # Should not exit with error
            mock_exit.assert_not_called()
    
    @patch('vcexport_modular.VCenterOrchestrator')
    def test_main_success_custom_args(self, mock_orchestrator_class):
        """Test successful main execution with custom arguments."""
        # Set up environment variables
        os.environ['EXP_VCENTER_HOST'] = 'test-vcenter.example.com'
        os.environ['EXP_VCENTER_USER'] = 'test-user'
        os.environ['EXP_VCENTER_PASSWORD'] = 'test-password'
        os.environ['EXP_DISABLE_SSL_VERIFICATION'] = 'true'
        
        # Mock orchestrator instance
        mock_orchestrator = Mock()
        mock_orchestrator.connect.return_value = True
        mock_orchestrator.export_data.return_value = 'vcexport.zip'
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Mock sys.argv with custom arguments
        sys.argv = [
            'vcexport_modular.py',
            '--no-statistics',
            '--perf-interval', '240',
            '--max-count', '50',
            '--keep-csv'
        ]
        
        with patch('sys.exit') as mock_exit:
            vcexport_modular.main()
            
            # Verify orchestrator was created with SSL verification disabled
            mock_orchestrator_class.assert_called_once_with(
                host='test-vcenter.example.com',
                user='test-user',
                password='test-password',
                disable_ssl_verification=True
            )
            
            # Verify orchestrator methods were called with custom parameters
            mock_orchestrator.export_data.assert_called_once_with(
                max_count=50,
                purge_csv=False,
                export_statistics=False,
                perf_interval=240
            )
    
    def test_main_missing_environment_variables(self):
        """Test main execution with missing environment variables."""
        # Clear environment variables
        for var in ['EXP_VCENTER_HOST', 'EXP_VCENTER_USER', 'EXP_VCENTER_PASSWORD']:
            os.environ.pop(var, None)
        
        sys.argv = ['vcexport_modular.py']
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                vcexport_modular.main()
                
                # Should print error message and exit
                mock_print.assert_any_call(
                    "Error: Please set EXP_VCENTER_HOST, EXP_VCENTER_USER, and EXP_VCENTER_PASSWORD environment variables"
                )
                mock_exit.assert_called_with(1)
    
    def test_main_partial_environment_variables(self):
        """Test main execution with only some environment variables set."""
        # Set only some environment variables
        os.environ['EXP_VCENTER_HOST'] = 'test-vcenter.example.com'
        os.environ.pop('EXP_VCENTER_USER', None)
        os.environ.pop('EXP_VCENTER_PASSWORD', None)
        
        sys.argv = ['vcexport_modular.py']
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                vcexport_modular.main()
                
                # Should print error message and exit
                mock_print.assert_any_call(
                    "Error: Please set EXP_VCENTER_HOST, EXP_VCENTER_USER, and EXP_VCENTER_PASSWORD environment variables"
                )
                mock_exit.assert_called_with(1)
    
    @patch('vcexport_modular.VCenterOrchestrator')
    def test_main_connection_failure(self, mock_orchestrator_class):
        """Test main execution with connection failure."""
        # Set up environment variables
        os.environ['EXP_VCENTER_HOST'] = 'test-vcenter.example.com'
        os.environ['EXP_VCENTER_USER'] = 'test-user'
        os.environ['EXP_VCENTER_PASSWORD'] = 'test-password'
        
        # Mock orchestrator instance with connection failure
        mock_orchestrator = Mock()
        mock_orchestrator.connect.return_value = False
        mock_orchestrator_class.return_value = mock_orchestrator
        
        sys.argv = ['vcexport_modular.py']
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                vcexport_modular.main()
                
                # Should print error message and exit
                mock_print.assert_any_call("Failed to connect to vCenter")
                mock_exit.assert_called_with(1)
                
                # Should still call disconnect
                mock_orchestrator.disconnect.assert_called_once()
    
    @patch('vcexport_modular.VCenterOrchestrator')
    def test_main_export_failure(self, mock_orchestrator_class):
        """Test main execution with export failure."""
        # Set up environment variables
        os.environ['EXP_VCENTER_HOST'] = 'test-vcenter.example.com'
        os.environ['EXP_VCENTER_USER'] = 'test-user'
        os.environ['EXP_VCENTER_PASSWORD'] = 'test-password'
        
        # Mock orchestrator instance with export failure
        mock_orchestrator = Mock()
        mock_orchestrator.connect.return_value = True
        mock_orchestrator.export_data.return_value = None  # Export failure
        mock_orchestrator_class.return_value = mock_orchestrator
        
        sys.argv = ['vcexport_modular.py']
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                vcexport_modular.main()
                
                # Should print error message and exit
                mock_print.assert_called_with("Export failed")
                mock_exit.assert_called_with(1)
                
                # Should still call disconnect
                mock_orchestrator.disconnect.assert_called_once()
    
    @patch('vcexport_modular.VCenterOrchestrator')
    def test_main_keyboard_interrupt(self, mock_orchestrator_class):
        """Test main execution with keyboard interrupt."""
        # Set up environment variables
        os.environ['EXP_VCENTER_HOST'] = 'test-vcenter.example.com'
        os.environ['EXP_VCENTER_USER'] = 'test-user'
        os.environ['EXP_VCENTER_PASSWORD'] = 'test-password'
        
        # Mock orchestrator instance
        mock_orchestrator = Mock()
        mock_orchestrator.connect.return_value = True
        mock_orchestrator.export_data.side_effect = KeyboardInterrupt()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        sys.argv = ['vcexport_modular.py']
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                vcexport_modular.main()
                
                # Should print interrupt message and exit
                mock_print.assert_called_with("\nExport interrupted by user")
                mock_exit.assert_called_with(1)
                
                # Should still call disconnect
                mock_orchestrator.disconnect.assert_called_once()
    
    @patch('vcexport_modular.VCenterOrchestrator')
    def test_main_generic_exception(self, mock_orchestrator_class):
        """Test main execution with generic exception."""
        # Set up environment variables
        os.environ['EXP_VCENTER_HOST'] = 'test-vcenter.example.com'
        os.environ['EXP_VCENTER_USER'] = 'test-user'
        os.environ['EXP_VCENTER_PASSWORD'] = 'test-password'
        
        # Mock orchestrator instance
        mock_orchestrator = Mock()
        mock_orchestrator.connect.return_value = True
        mock_orchestrator.export_data.side_effect = Exception("Test error")
        mock_orchestrator_class.return_value = mock_orchestrator
        
        sys.argv = ['vcexport_modular.py']
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                vcexport_modular.main()
                
                # Should print error message and exit
                mock_print.assert_called_with("Export failed with error: Test error")
                mock_exit.assert_called_with(1)
                
                # Should still call disconnect
                mock_orchestrator.disconnect.assert_called_once()
    
    def test_argument_parser_default_values(self):
        """Test argument parser with default values."""
        parser = argparse.ArgumentParser()
        
        # Add the same arguments as in the main script
        parser.add_argument("--no-statistics", action="store_false", dest="export_statistics", default=True)
        parser.add_argument("--perf-interval", type=int, default=60)
        parser.add_argument("--max-count", type=int, default=None)
        parser.add_argument("--keep-csv", action="store_false", dest="purge_csv", default=True)
        
        # Parse empty arguments (defaults)
        args = parser.parse_args([])
        
        assert args.export_statistics is True
        assert args.perf_interval == 60
        assert args.max_count is None
        assert args.purge_csv is True
    
    def test_argument_parser_custom_values(self):
        """Test argument parser with custom values."""
        parser = argparse.ArgumentParser()
        
        # Add the same arguments as in the main script
        parser.add_argument("--no-statistics", action="store_false", dest="export_statistics", default=True)
        parser.add_argument("--perf-interval", type=int, default=60)
        parser.add_argument("--max-count", type=int, default=None)
        parser.add_argument("--keep-csv", action="store_false", dest="purge_csv", default=True)
        
        # Parse custom arguments
        args = parser.parse_args([
            '--no-statistics',
            '--perf-interval', '240',
            '--max-count', '100',
            '--keep-csv'
        ])
        
        assert args.export_statistics is False
        assert args.perf_interval == 240
        assert args.max_count == 100
        assert args.purge_csv is False
    
    def test_ssl_verification_environment_variable(self):
        """Test SSL verification environment variable parsing."""
        # Test 'true' value
        os.environ['EXP_DISABLE_SSL_VERIFICATION'] = 'true'
        result = os.environ.get("EXP_DISABLE_SSL_VERIFICATION", "false").lower() == "true"
        assert result is True
        
        # Test 'false' value
        os.environ['EXP_DISABLE_SSL_VERIFICATION'] = 'false'
        result = os.environ.get("EXP_DISABLE_SSL_VERIFICATION", "false").lower() == "true"
        assert result is False
        
        # Test 'TRUE' value (case insensitive)
        os.environ['EXP_DISABLE_SSL_VERIFICATION'] = 'TRUE'
        result = os.environ.get("EXP_DISABLE_SSL_VERIFICATION", "false").lower() == "true"
        assert result is True
        
        # Test missing value (default)
        os.environ.pop('EXP_DISABLE_SSL_VERIFICATION', None)
        result = os.environ.get("EXP_DISABLE_SSL_VERIFICATION", "false").lower() == "true"
        assert result is False
        
        # Test other value
        os.environ['EXP_DISABLE_SSL_VERIFICATION'] = 'yes'
        result = os.environ.get("EXP_DISABLE_SSL_VERIFICATION", "false").lower() == "true"
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__])
