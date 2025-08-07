#!/usr/bin/env python
"""
Unit tests for csv_exporter.py module.
Tests the CSVExporter class and its methods using mocks.
"""

import pytest
import os
import csv
import zipfile
import tempfile
from unittest.mock import Mock, patch, mock_open, MagicMock
from src.exporters.csv_exporter import CSVExporter


class TestCSVExporter:
    """Test class for CSVExporter"""
    
    @pytest.fixture
    def csv_exporter(self):
        """Create CSVExporter instance for testing"""
        return CSVExporter(output_dir="/tmp/test")
    
    @pytest.fixture
    def sample_data(self):
        """Sample data for testing CSV operations"""
        return {
            "vm_info": [
                {
                    "VM": "test-vm-1",
                    "Powerstate": "poweredOn",
                    "Template": "False",
                    "DNS Name": "test-vm-1.example.com",
                    "CPUs": "2",
                    "Memory": "4096",
                    "Total disk capacity MiB": "20480",
                    "NICs": "1",
                    "Disks": "1",
                    "Host": "test-host-1",
                    "OS according to the configuration file": "ubuntu64Guest",
                    "OS according to the VMware Tools": "Ubuntu Linux (64-bit)",
                    "VI SDK API Version": "7.0",
                    "Primary IP Address": "192.168.1.100",
                    "VM ID": "vm-123",
                    "VM UUID": "test-uuid-123",
                    "VI SDK Server type": "VirtualCenter",
                    "VI SDK Server": "vcenter.example.com",
                    "VI SDK UUID": "vcenter-uuid-123"
                }
            ],
            "vm_network": [
                {
                    "VM": "test-vm-1",
                    "Network": "VM Network",
                    "IPv4 Address": "192.168.1.100",
                    "IPv6 Address": "",
                    "Switch": "vSwitch0",
                    "Mac Address": "00:50:56:12:34:56"
                }
            ],
            "source": {
                "Name": "vcenter.example.com",
                "API version": "7.0",
                "Vendor": "VMware, Inc.",
                "VI SDK UUID": "vcenter-uuid-123"
            },
            "performance": [
                {
                    "VM Name": "test-vm-1",
                    "VM UUID": "test-uuid-123",
                    "Timestamp": "2024-01-01T12:00:00Z",
                    "maxCpuUsagePctDec": "0.75",
                    "avgCpuUsagePctDec": "0.45"
                }
            ]
        }
    
    @pytest.fixture
    def mock_perf_collector(self):
        """Mock performance collector for testing"""
        mock_collector = Mock()
        mock_collector.get_metric_headers.return_value = [
            "VM Name", "VM UUID", "Timestamp", 
            "maxCpuUsagePctDec", "avgCpuUsagePctDec",
            "maxRamUsagePctDec", "avgRamUtlPctDec"
        ]
        return mock_collector

    def test_init_default_output_dir(self):
        """Test CSVExporter initialization with default output directory"""
        exporter = CSVExporter()
        assert exporter.output_dir == "."
        assert exporter.csv_files == []
    
    def test_init_custom_output_dir(self):
        """Test CSVExporter initialization with custom output directory"""
        exporter = CSVExporter("/custom/path")
        assert exporter.output_dir == "/custom/path"
        assert exporter.csv_files == []
    
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('csv.DictWriter')
    def test_write_csv_file_success(self, mock_dict_writer, mock_file, mock_makedirs, csv_exporter):
        """Test successful CSV file writing"""
        # Setup mock writer
        mock_writer = Mock()
        mock_dict_writer.return_value = mock_writer
        
        headers = ["VM", "Powerstate", "CPUs"]
        data = [{"VM": "test-vm", "Powerstate": "poweredOn", "CPUs": "2"}]
        
        result = csv_exporter.write_csv_file("/tmp/test.csv", headers, data)
        
        assert result is True
        mock_makedirs.assert_called_once()
        mock_file.assert_called_once_with("/tmp/test.csv", 'w', newline='')
        mock_dict_writer.assert_called_once_with(mock_file.return_value, fieldnames=headers)
        mock_writer.writeheader.assert_called_once()
        mock_writer.writerow.assert_called_once_with(data[0])
        assert "/tmp/test.csv" in csv_exporter.csv_files
    
    @patch('os.makedirs')
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_write_csv_file_failure(self, mock_file, mock_makedirs, csv_exporter, capsys):
        """Test CSV file writing failure"""
        headers = ["VM", "Powerstate"]
        data = [{"VM": "test-vm", "Powerstate": "poweredOn"}]
        
        result = csv_exporter.write_csv_file("/tmp/test.csv", headers, data)
        
        assert result is False
        captured = capsys.readouterr()
        assert "Error writing CSV file /tmp/test.csv: Permission denied" in captured.out
    
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('csv.DictWriter')
    def test_write_source_csv_success(self, mock_dict_writer, mock_file, mock_makedirs, csv_exporter):
        """Test successful source CSV file writing"""
        mock_writer = Mock()
        mock_dict_writer.return_value = mock_writer
        
        headers = ["Name", "API version", "Vendor"]
        source_data = {"Name": "vcenter.example.com", "API version": "7.0", "Vendor": "VMware, Inc."}
        
        result = csv_exporter.write_source_csv("/tmp/source.csv", headers, source_data)
        
        assert result is True
        mock_makedirs.assert_called_once()
        mock_file.assert_called_once_with("/tmp/source.csv", 'w', newline='')
        mock_dict_writer.assert_called_once_with(mock_file.return_value, fieldnames=headers)
        mock_writer.writeheader.assert_called_once()
        mock_writer.writerow.assert_called_once_with(source_data)
        assert "/tmp/source.csv" in csv_exporter.csv_files
    
    @patch('os.makedirs')
    @patch('builtins.open', side_effect=Exception("Disk full"))
    def test_write_source_csv_failure(self, mock_file, mock_makedirs, csv_exporter, capsys):
        """Test source CSV file writing failure"""
        headers = ["Name", "API version"]
        source_data = {"Name": "vcenter.example.com", "API version": "7.0"}
        
        result = csv_exporter.write_source_csv("/tmp/source.csv", headers, source_data)
        
        assert result is False
        captured = capsys.readouterr()
        assert "Error writing source CSV file /tmp/source.csv: Disk full" in captured.out
    
    @patch('zipfile.ZipFile')
    @patch('os.path.exists', return_value=True)
    @patch('os.remove')
    def test_create_zip_archive_success_with_purge(self, mock_remove, mock_exists, mock_zipfile, csv_exporter, capsys):
        """Test successful zip archive creation with CSV purge"""
        # Setup mock zip file
        mock_zip = Mock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        
        # Add some files to track
        csv_exporter.csv_files = ["/tmp/file1.csv", "/tmp/file2.csv"]
        
        result = csv_exporter.create_zip_archive("test.zip", purge_csv=True)
        
        assert result == "test.zip"
        mock_zipfile.assert_called_once_with("test.zip", 'w')
        assert mock_zip.write.call_count == 2
        mock_zip.write.assert_any_call("/tmp/file1.csv", "file1.csv")
        mock_zip.write.assert_any_call("/tmp/file2.csv", "file2.csv")
        
        # Check purge functionality
        assert mock_remove.call_count == 2
        mock_remove.assert_any_call("/tmp/file1.csv")
        mock_remove.assert_any_call("/tmp/file2.csv")
        
        captured = capsys.readouterr()
        assert "All CSV files have been zipped to test.zip" in captured.out
        assert "Purging CSV files, leaving only the ZIP." in captured.out
    
    @patch('zipfile.ZipFile')
    @patch('os.path.exists', return_value=True)
    def test_create_zip_archive_success_no_purge(self, mock_exists, mock_zipfile, csv_exporter, capsys):
        """Test successful zip archive creation without CSV purge"""
        mock_zip = Mock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        
        csv_exporter.csv_files = ["/tmp/file1.csv"]
        
        result = csv_exporter.create_zip_archive("test.zip", purge_csv=False)
        
        assert result == "test.zip"
        captured = capsys.readouterr()
        assert "All CSV files have been zipped to test.zip" in captured.out
        assert "Purging CSV files" not in captured.out
    
    @patch('zipfile.ZipFile', side_effect=Exception("Zip error"))
    def test_create_zip_archive_failure(self, mock_zipfile, csv_exporter, capsys):
        """Test zip archive creation failure"""
        csv_exporter.csv_files = ["/tmp/file1.csv"]
        
        result = csv_exporter.create_zip_archive("test.zip")
        
        assert result is None
        captured = capsys.readouterr()
        assert "Error creating zip archive: Zip error" in captured.out
    
    def test_get_default_filenames(self, csv_exporter):
        """Test getting default filenames"""
        filenames = csv_exporter.get_default_filenames()
        
        expected_keys = [
            "info", "network", "vcpu", "memory", "disk", "partition",
            "vsource", "vtools", "vhost", "vnic", "sc_vmk", "vswitch",
            "dvswitch", "vport", "dvport", "performance"
        ]
        
        assert isinstance(filenames, dict)
        for key in expected_keys:
            assert key in filenames
        
        # Check specific filenames
        assert filenames["info"] == "RVTools_tabvInfo.csv"
        assert filenames["performance"] == "vcexport_tabvPerformance.csv"
        assert filenames["vsource"] == "RVTools_tabvSource.csv"
    
    def test_get_csv_headers(self, csv_exporter):
        """Test getting CSV headers"""
        headers = csv_exporter.get_csv_headers()
        
        expected_keys = [
            "info", "network", "vcpu", "memory", "disk", "partition",
            "vsource", "vtools", "vhost", "vnic", "sc_vmk", "vswitch",
            "dvswitch", "vport", "dvport", "performance"
        ]
        
        assert isinstance(headers, dict)
        for key in expected_keys:
            assert key in headers
            assert isinstance(headers[key], list)
            assert len(headers[key]) > 0
        
        # Check specific headers
        assert "VM" in headers["info"]
        assert "Powerstate" in headers["info"]
        assert "VM Name" in headers["performance"]
        assert "Timestamp" in headers["performance"]
    
    @patch.object(CSVExporter, 'write_csv_file', return_value=True)
    @patch.object(CSVExporter, 'write_source_csv', return_value=True)
    def test_export_all_data_success(self, mock_write_source, mock_write_csv, csv_exporter, sample_data, mock_perf_collector, capsys):
        """Test successful export of all data types"""
        created_files = csv_exporter.export_all_data(
            sample_data, 
            export_statistics=True, 
            perf_collector=mock_perf_collector
        )
        
        # Should have called write_csv_file for each data type except source
        expected_csv_calls = 15  # All data types except source
        assert mock_write_csv.call_count == expected_csv_calls
        
        # Should have called write_source_csv once
        mock_write_source.assert_called_once()
        
        # Check that performance collector headers were used
        mock_perf_collector.get_metric_headers.assert_called_once()
        
        # Check console output
        captured = capsys.readouterr()
        assert "Exported 1 VMs to RVTools_tabvInfo.csv" in captured.out
        assert "Exported network data for 1 VM NICs to RVTools_tabvNetwork.csv" in captured.out
        assert "Exported source data to RVTools_tabvSource.csv" in captured.out
        assert "Exported performance metrics data for 1 VMs to vcexport_tabvPerformance.csv" in captured.out
    
    @patch.object(CSVExporter, 'write_csv_file', return_value=True)
    @patch.object(CSVExporter, 'write_source_csv', return_value=True)
    def test_export_all_data_no_statistics(self, mock_write_source, mock_write_csv, csv_exporter, sample_data, capsys):
        """Test export with statistics disabled"""
        created_files = csv_exporter.export_all_data(
            sample_data, 
            export_statistics=False, 
            perf_collector=None
        )
        
        # Check console output for disabled statistics
        captured = capsys.readouterr()
        assert "Created empty performance file (statistics collection disabled)" in captured.out
    
    @patch.object(CSVExporter, 'write_csv_file', return_value=False)
    @patch.object(CSVExporter, 'write_source_csv', return_value=True)
    def test_export_all_data_partial_failure(self, mock_write_source, mock_write_csv, csv_exporter, sample_data):
        """Test export with some failures"""
        created_files = csv_exporter.export_all_data(sample_data)
        
        # Should still attempt all exports even if some fail
        assert mock_write_csv.call_count == 15
        mock_write_source.assert_called_once()
    
    def test_export_all_data_empty_data(self, csv_exporter):
        """Test export with empty data dictionary"""
        empty_data = {}
        
        with patch.object(csv_exporter, 'write_csv_file', return_value=True) as mock_write_csv, \
             patch.object(csv_exporter, 'write_source_csv', return_value=True) as mock_write_source:
            
            created_files = csv_exporter.export_all_data(empty_data)
            
            # Should still attempt all exports with empty lists/dicts
            assert mock_write_csv.call_count == 15
            mock_write_source.assert_called_once()
    
    @patch.object(CSVExporter, 'write_csv_file')
    def test_export_all_data_uses_correct_headers_with_perf_collector(self, mock_write_csv, csv_exporter, sample_data, mock_perf_collector):
        """Test that export uses performance collector headers when available"""
        mock_write_csv.return_value = True
        
        with patch.object(csv_exporter, 'write_source_csv', return_value=True):
            csv_exporter.export_all_data(
                sample_data, 
                export_statistics=True, 
                perf_collector=mock_perf_collector
            )
        
        # Find the performance file write call
        performance_call = None
        for call in mock_write_csv.call_args_list:
            if call[0][0] == "vcexport_tabvPerformance.csv":
                performance_call = call
                break
        
        assert performance_call is not None
        # Check that custom headers from perf_collector were used
        expected_headers = mock_perf_collector.get_metric_headers.return_value
        assert performance_call[0][1] == expected_headers
    
    @patch.object(CSVExporter, 'write_csv_file')
    def test_export_all_data_uses_default_headers_without_perf_collector(self, mock_write_csv, csv_exporter, sample_data):
        """Test that export uses default headers when no performance collector"""
        mock_write_csv.return_value = True
        
        with patch.object(csv_exporter, 'write_source_csv', return_value=True):
            csv_exporter.export_all_data(
                sample_data, 
                export_statistics=False, 
                perf_collector=None
            )
        
        # Find the performance file write call
        performance_call = None
        for call in mock_write_csv.call_args_list:
            if call[0][0] == "vcexport_tabvPerformance.csv":
                performance_call = call
                break
        
        assert performance_call is not None
        # Check that default headers were used
        default_headers = csv_exporter.get_csv_headers()["performance"]
        assert performance_call[0][1] == default_headers
