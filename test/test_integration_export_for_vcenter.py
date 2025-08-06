#!/usr/bin/env python
"""
Consolidated integration tests for Export for vCenter using vcsim.
Tests the complete end-to-end workflow from command-line to file output.
"""
import pytest
import sys
import os
import subprocess
import zipfile
import csv
from pathlib import Path
from pyVim.connect import SmartConnect
import ssl

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestExportForVCenterIntegration:
    """End-to-end integration tests for Export for vCenter using vcsim."""
    
    @classmethod
    def setup_class(cls):
        """Set up class-level fixtures."""
        cls.vcsim_host = "localhost"
        cls.vcsim_port = 9090
        cls.vcsim_user = "user"
        cls.vcsim_password = "pass"
        cls.script_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'vcexport_modular.py')
        
        # Check if vcsim is running
        cls.vcsim_available = cls._check_vcsim_availability()
        if not cls.vcsim_available:
            pytest.skip("vcsim is not available at localhost:9090. Run: docker run -p 9090:9090 vmware/vcsim -l :9090")
    
    @classmethod
    def _check_vcsim_availability(cls):
        """Check if vcsim is running and accessible using actual vCenter API connection."""
        try:
            # Create SSL context that ignores certificate verification (like vcsim)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Try to connect to vcsim using the same method as the application
            service_instance = SmartConnect(
                host=cls.vcsim_host,
                port=cls.vcsim_port,
                user=cls.vcsim_user,
                pwd=cls.vcsim_password,
                sslContext=ssl_context
            )
            
            if service_instance:
                # Successfully connected, disconnect and return True
                from pyVim.connect import Disconnect
                Disconnect(service_instance)
                return True
            return False
            
        except Exception:
            return False
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        if not self.vcsim_available:
            pytest.skip("vcsim is not available")
        
        # Store original environment variables
        self.original_env = {}
        env_vars = ['EXP_VCENTER_HOST', 'EXP_VCENTER_USER', 'EXP_VCENTER_PASSWORD', 'EXP_DISABLE_SSL_VERIFICATION']
        for var in env_vars:
            self.original_env[var] = os.environ.get(var)
        
        # Set up environment variables for vcsim
        os.environ['EXP_VCENTER_HOST'] = f"{self.vcsim_host}:{self.vcsim_port}"
        os.environ['EXP_VCENTER_USER'] = self.vcsim_user
        os.environ['EXP_VCENTER_PASSWORD'] = self.vcsim_password
        os.environ['EXP_DISABLE_SSL_VERIFICATION'] = 'true'
    
    def teardown_method(self):
        """Clean up after each test method."""
        # Restore original environment variables
        for var, value in self.original_env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        
        # Clean up any created files
        self._cleanup_files()
    
    def _cleanup_files(self):
        """Clean up any files created during tests."""
        # Remove zip files
        for zip_file in Path('.').glob('*vcexport*.zip'):
            try:
                zip_file.unlink()
            except OSError:
                pass
        
        # Remove CSV files
        for csv_file in Path('.').glob('*.csv'):
            try:
                csv_file.unlink()
            except OSError:
                pass
    
    def _run_script(self, args=None, timeout=60):
        """
        Run the vcexport_modular.py script with given arguments.
        
        Args:
            args (list): Command line arguments
            timeout (int): Timeout in seconds
            
        Returns:
            subprocess.CompletedProcess: Result of the script execution
        """
        if args is None:
            args = []
        
        cmd = [sys.executable, self.script_path] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd='.'  # Run in current directory (test directory) not src directory
            )
            return result
        except subprocess.TimeoutExpired:
            pytest.fail(f"Script execution timed out after {timeout} seconds")
    
    def _verify_zip_contents(self, zip_path, expected_files=None):
        """
        Verify the contents of the created zip file.
        
        Args:
            zip_path (str): Path to the zip file
            expected_files (list): List of expected file patterns
            
        Returns:
            list: List of files found in the zip
        """
        if expected_files is None:
            expected_files = ['tabvInfo', 'tabvHost']  # Basic expected files
        
        assert os.path.exists(zip_path), f"Zip file {zip_path} does not exist"
        
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            file_list = zip_file.namelist()
            
            # Check for expected file patterns
            for pattern in expected_files:
                found = any(pattern in filename for filename in file_list)
                assert found, f"Expected file pattern '{pattern}' not found in zip contents: {file_list}"
            
            return file_list
    
    def _verify_csv_structure(self, csv_path):
        """
        Verify that a CSV file has proper structure.
        
        Args:
            csv_path (str): Path to the CSV file
        """
        assert os.path.exists(csv_path), f"CSV file {csv_path} does not exist"
        
        with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)
            
            # Should have at least a header row
            assert len(rows) >= 1, f"CSV file {csv_path} is empty"
            
            # Header row should not be empty
            header = rows[0]
            assert len(header) > 0, f"CSV file {csv_path} has empty header"
            assert all(col.strip() for col in header), f"CSV file {csv_path} has empty column names"
    
    # Core End-to-End Tests
    
    def test_complete_export_workflow_default(self):
        """Test the complete export workflow with default settings."""
        result = self._run_script(['--max-count', '2'])  # Limit for speed
        
        # Should complete successfully
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        # Verify expected output messages
        expected_messages = [
            "Starting export process",
            "Starting data collection",
            "Getting source properties",
            "Getting host properties",
            "Getting performance metric properties",
            "Exporting data to CSV files",
            "Export completed successfully"
        ]
        
        for message in expected_messages:
            assert message in result.stdout, f"Expected message '{message}' not found in output"
        
        # Verify zip file creation
        assert "vcexport.zip" in result.stdout
        zip_path = "vcexport.zip"
        
        # Verify zip contents
        file_list = self._verify_zip_contents(zip_path)
        assert len(file_list) > 0, "Zip file is empty"
    
    def test_export_without_performance_statistics(self):
        """Test export workflow without performance statistics collection."""
        result = self._run_script(['--no-statistics', '--max-count', '2'])
        
        # Should complete successfully
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        # Should mention skipping statistics
        assert "Skipping performance statistics collection" in result.stdout
        
        # Should not mention performance collection
        assert "Getting performance metric properties" not in result.stdout
        
        # Verify zip file creation
        zip_path = "vcexport.zip"
        self._verify_zip_contents(zip_path)
    
    def test_export_with_custom_performance_interval(self):
        """Test export workflow with custom performance interval."""
        result = self._run_script(['--perf-interval', '240', '--max-count', '1'])
        
        # Should complete successfully
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        # Should mention performance collection
        assert "Getting performance metric properties" in result.stdout
        
        # Verify zip file creation
        zip_path = "vcexport.zip"
        self._verify_zip_contents(zip_path)
    
    def test_export_keep_csv_files(self):
        """Test export workflow keeping individual CSV files."""
        result = self._run_script(['--keep-csv', '--no-statistics', '--max-count', '1'])
        
        # Should complete successfully
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        # Verify zip file creation
        zip_path = "vcexport.zip"
        zip_contents = self._verify_zip_contents(zip_path)
        
        # Should also have individual CSV files
        csv_files = list(Path('.').glob('*.csv'))
        assert len(csv_files) > 0, "No CSV files found when --keep-csv was specified"
        
        # Verify CSV file structure
        for csv_file in csv_files[:3]:  # Check first 3 files
            self._verify_csv_structure(str(csv_file))
    
    def test_export_with_vm_limit(self):
        """Test export workflow with VM count limit."""
        result = self._run_script(['--max-count', '1', '--no-statistics'])
        
        # Should complete successfully
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        # Should mention processing limited VMs
        assert "processing" in result.stdout.lower()
        
        # Verify zip file creation
        zip_path = "vcexport.zip"
        self._verify_zip_contents(zip_path)
    
    # Error Handling Tests
    
    def test_missing_environment_variables(self):
        """Test script behavior with missing environment variables."""
        # Remove required environment variables
        for var in ['EXP_VCENTER_HOST', 'EXP_VCENTER_USER', 'EXP_VCENTER_PASSWORD']:
            os.environ.pop(var, None)
        
        result = self._run_script(['--max-count', '1'])
        
        # Should fail with error code 1
        assert result.returncode == 1
        
        # Should print error message
        assert "Please set EXP_VCENTER_HOST, EXP_VCENTER_USER, and EXP_VCENTER_PASSWORD" in result.stdout
    
    def test_invalid_vcenter_host(self):
        """Test script behavior with invalid vCenter host."""
        # Set invalid host
        os.environ['EXP_VCENTER_HOST'] = 'invalid-host.example.com'
        
        result = self._run_script(['--max-count', '1'], timeout=30)
        
        # Should fail with error code 1
        assert result.returncode == 1
        
        # Should print connection failure message
        assert "Failed to connect to vCenter" in result.stdout
    
    def test_invalid_command_line_arguments(self):
        """Test script behavior with invalid command line arguments."""
        # Test invalid argument
        result = self._run_script(['--invalid-argument'])
        assert result.returncode == 2
        assert "unrecognized arguments" in result.stderr
        
        # Test invalid perf interval
        result = self._run_script(['--perf-interval', 'invalid'])
        assert result.returncode == 2
        assert "invalid int value" in result.stderr
        
        # Test invalid max count
        result = self._run_script(['--max-count', 'invalid'])
        assert result.returncode == 2
        assert "invalid int value" in result.stderr
    
    # Configuration and Help Tests
    
    def test_help_output(self):
        """Test script help output."""
        result = self._run_script(['--help'])
        
        # Should complete successfully
        assert result.returncode == 0
        
        # Should contain help information
        help_content = result.stdout
        assert "Export VM data from vCenter to CSV files" in help_content
        assert "--no-statistics" in help_content
        assert "--perf-interval" in help_content
        assert "--max-count" in help_content
        assert "--keep-csv" in help_content
        
        # Should contain environment variable information
        assert "EXP_VCENTER_HOST" in help_content
        assert "EXP_VCENTER_USER" in help_content
        assert "EXP_VCENTER_PASSWORD" in help_content
    
    def test_ssl_verification_configuration(self):
        """Test SSL verification configuration."""
        # Test with SSL verification disabled (default for vcsim)
        result = self._run_script(['--no-statistics', '--max-count', '1'])
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        # Test with SSL verification explicitly enabled
        os.environ['EXP_DISABLE_SSL_VERIFICATION'] = 'false'
        result = self._run_script(['--no-statistics', '--max-count', '1'], timeout=30)
        
        # May succeed or fail depending on vcsim SSL configuration
        # The important thing is that it handles the setting without crashing
        assert result.returncode in [0, 1]
    
    # Data Quality Tests
    
    def test_exported_data_structure(self):
        """Test that exported data has expected structure and content."""
        result = self._run_script(['--keep-csv', '--no-statistics', '--max-count', '1'])
        
        # Should complete successfully
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        # Check specific CSV files exist and have proper structure
        expected_csv_patterns = {
            'tabvInfo': ['VM', 'Host', 'OS', 'State'],  # VM info columns
            'tabvHost': ['Host', 'Cluster', 'Model'],   # Host info columns
        }
        
        csv_files = list(Path('.').glob('*.csv'))
        
        for pattern, expected_columns in expected_csv_patterns.items():
            # Find CSV file matching pattern
            matching_files = [f for f in csv_files if pattern in f.name]
            
            if matching_files:  # Only check if file exists (vcsim may not have all data)
                csv_file = matching_files[0]
                
                # Verify CSV structure
                with open(csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    headers = reader.fieldnames
                    
                    # Check that some expected columns exist
                    found_columns = [col for col in expected_columns if col in headers]
                    assert len(found_columns) > 0, f"No expected columns found in {csv_file}. Headers: {headers}"
    
    def test_zip_file_integrity(self):
        """Test that the created zip file is valid and contains expected files."""
        result = self._run_script(['--no-statistics', '--max-count', '1'])
        
        # Should complete successfully
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        zip_path = "vcexport.zip"
        assert os.path.exists(zip_path), "Zip file was not created"
        
        # Test zip file integrity
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # Test zip file integrity
                bad_file = zip_file.testzip()
                assert bad_file is None, f"Zip file is corrupted: {bad_file}"
                
                # Get file list
                file_list = zip_file.namelist()
                assert len(file_list) > 0, "Zip file is empty"
                
                # All files should be CSV files
                for filename in file_list:
                    assert filename.endswith('.csv'), f"Non-CSV file found in zip: {filename}"
                
        except zipfile.BadZipFile:
            pytest.fail("Created zip file is not a valid zip archive")
    
    def test_performance_collection_intervals(self):
        """Test different performance collection intervals."""
        intervals_to_test = [60, 240, 1440]  # 1 hour, 4 hours, 24 hours
        
        for interval in intervals_to_test:
            result = self._run_script(['--perf-interval', str(interval), '--max-count', '1'])
            
            # Should complete successfully
            assert result.returncode == 0, f"Script failed for interval {interval} with stderr: {result.stderr}"
            
            # Should mention performance collection
            assert "Getting performance metric properties" in result.stdout
            
            # Clean up for next iteration
            self._cleanup_files()


if __name__ == "__main__":
    pytest.main([__file__])
