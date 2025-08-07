#!/usr/bin/env python
"""
Unit tests for performance_collector.py module.
Tests the PerformanceCollector class and its methods.
"""

import pytest
import datetime
from unittest.mock import Mock, patch
from src.collectors.performance_collector import PerformanceCollector
from pyVmomi import vim


class TestPerformanceCollector:
    """Test class for PerformanceCollector"""
    
    @pytest.fixture
    def mock_service_instance(self):
        """Create a mock service instance for testing"""
        mock_si = Mock()
        mock_content = Mock()
        mock_perf_manager = Mock()
        
        # Setup the mock hierarchy
        mock_si.RetrieveContent.return_value = mock_content
        mock_content.perfManager = mock_perf_manager
        
        # Mock performance counters
        mock_counter1 = Mock()
        mock_counter1.key = 1
        mock_counter1.groupInfo.key = "cpu"
        mock_counter1.nameInfo.key = "usage"
        mock_counter1.rollupType = "average"
        
        mock_counter2 = Mock()
        mock_counter2.key = 2
        mock_counter2.groupInfo.key = "mem"
        mock_counter2.nameInfo.key = "usage"
        mock_counter2.rollupType = "average"
        
        mock_counter3 = Mock()
        mock_counter3.key = 3
        mock_counter3.groupInfo.key = "virtualDisk"
        mock_counter3.nameInfo.key = "readIOSize"
        mock_counter3.rollupType = "latest"
        
        mock_perf_manager.perfCounter = [mock_counter1, mock_counter2, mock_counter3]
        
        return mock_si
    
    @pytest.fixture
    def performance_collector(self, mock_service_instance):
        """Create a PerformanceCollector instance for testing"""
        return PerformanceCollector(mock_service_instance)
    
    @pytest.fixture
    def mock_vm(self):
        """Create a mock VM object"""
        mock_vm = Mock(spec=vim.VirtualMachine)
        mock_vm.name = "test-vm"
        mock_vm.config.uuid = "test-uuid-123"
        mock_vm.runtime.powerState = "poweredOn"
        return mock_vm
    
    def test_init(self, mock_service_instance):
        """Test PerformanceCollector initialization"""
        collector = PerformanceCollector(mock_service_instance)
        
        assert collector.si == mock_service_instance  # Service instance should be stored correctly
        assert collector.content == mock_service_instance.RetrieveContent.return_value  # Content should be retrieved from service instance
        assert collector.perf_manager == mock_service_instance.RetrieveContent.return_value.perfManager  # Performance manager should be extracted from content
        assert collector.metric_cache == {}  # Metric cache should be initialized as empty dictionary
        assert collector.counters_initialized is False  # Counters should not be initialized yet
        assert collector.perf_counters == {}  # Performance counters should be initialized as empty dictionary
    
    def test_initialize_counters(self, performance_collector):
        """Test _initialize_counters method"""
        # Initially counters should not be initialized
        assert performance_collector.counters_initialized is False  # Counters should start uninitialized
        assert performance_collector.perf_counters == {}  # Performance counters should start empty
        
        # Call _initialize_counters
        performance_collector._initialize_counters()
        
        # Check that counters are now initialized
        assert performance_collector.counters_initialized is True  # Counters should now be marked as initialized
        assert len(performance_collector.perf_counters) == 3  # Should have loaded all 3 mock counters
        assert 1 in performance_collector.perf_counters  # CPU counter should be present
        assert 2 in performance_collector.perf_counters  # Memory counter should be present
        assert 3 in performance_collector.perf_counters  # Virtual disk counter should be present
        
        # Calling again should not reinitialize
        old_counters = performance_collector.perf_counters
        performance_collector._initialize_counters()
        assert performance_collector.perf_counters is old_counters  # Should reuse existing counters, not reinitialize
    
    def test_get_available_metrics(self, performance_collector, mock_vm):
        """Test get_available_metrics method"""
        # Mock QueryAvailablePerfMetric response
        mock_counter_id1 = Mock()
        mock_counter_id1.counterId = 1
        mock_counter_id2 = Mock()
        mock_counter_id2.counterId = 2
        
        performance_collector.perf_manager.QueryAvailablePerfMetric.return_value = [
            mock_counter_id1, mock_counter_id2
        ]
        
        # Call get_available_metrics
        metrics = performance_collector.get_available_metrics(mock_vm)
        
        # Verify results
        expected_metrics = {
            "cpu.usage.average": 1,
            "mem.usage.average": 2
        }
        assert metrics == expected_metrics  # Should return correctly mapped metric names to counter IDs
        
        # Verify caching works
        assert "Mock" in performance_collector.metric_cache  # Cache should contain entry for the mock VM
        
        # Call again to test cache
        metrics2 = performance_collector.get_available_metrics(mock_vm)
        assert metrics2 == metrics  # Second call should return same results from cache
        
        # Verify QueryAvailablePerfMetric was only called once due to caching
        assert performance_collector.perf_manager.QueryAvailablePerfMetric.call_count == 1  # Should only query vCenter once, then use cache
    
    @patch('src.collectors.performance_collector.vim.PerformanceManager.QuerySpec')
    @patch('src.collectors.performance_collector.vim.PerformanceManager.MetricId')
    def test_get_metric_values(self, mock_metric_id, mock_query_spec, performance_collector, mock_vm):
        """Test get_metric_values method"""
        # Setup mock performance query result
        mock_metric_value1 = Mock()
        mock_metric_value1.id.counterId = 1
        mock_metric_value1.value = [50, 60, 70]
        
        mock_metric_value2 = Mock()
        mock_metric_value2.id.counterId = 2
        mock_metric_value2.value = [80, 85, 90]
        
        mock_entity_metrics = Mock()
        mock_entity_metrics.value = [mock_metric_value1, mock_metric_value2]
        
        performance_collector.perf_manager.QueryPerf.return_value = [mock_entity_metrics]
        
        # Call get_metric_values
        with patch('datetime.datetime') as mock_datetime:
            mock_now = datetime.datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            result = performance_collector.get_metric_values(mock_vm, [1, 2], 60, 180, 20)
        
        # Verify results
        expected_result = {
            "cpu.usage.average": [50, 60, 70],
            "mem.usage.average": [80, 85, 90]
        }
        assert result == expected_result  # Should return metric values mapped by metric name
        
        # Verify QueryPerf was called
        performance_collector.perf_manager.QueryPerf.assert_called_once()  # Should make exactly one performance query call
    
    @patch('src.collectors.performance_collector.vim.PerformanceManager.QuerySpec')
    @patch('src.collectors.performance_collector.vim.PerformanceManager.MetricId')
    def test_get_metric_values_empty_result(self, mock_metric_id, mock_query_spec, performance_collector, mock_vm):
        """Test get_metric_values with empty result"""
        performance_collector.perf_manager.QueryPerf.return_value = []
        
        result = performance_collector.get_metric_values(mock_vm, [1, 2], 60, 180, 20)
        
        assert result == {}  # Should return empty dictionary when no performance data is available
    
    def test_collect_detailed_vm_metrics(self, performance_collector, mock_vm):
        """Test collect_detailed_vm_metrics method"""
        # Mock get_available_metrics
        performance_collector.get_available_metrics = Mock(return_value={
            'cpu.usage.average': 1,
            'mem.usage.average': 2,
            'virtualDisk.readIOSize.latest': 3,
            'virtualDisk.writeIOSize.latest': 4
        })
        
        # Mock get_metric_values
        performance_collector.get_metric_values = Mock(return_value={
            'cpu.usage.average': [5000, 6000, 7000],  # Values in centipercent
            'mem.usage.average': [8000, 8500, 9000],  # Values in centipercent
            'virtualDisk.readIOSize.latest': [1024, 2048, 4096],
            'virtualDisk.writeIOSize.latest': [512, 1024, 2048]
        })
        
        # Call collect_detailed_vm_metrics
        result = performance_collector.collect_detailed_vm_metrics(mock_vm, 60, 180, 20)
        
        # Verify results
        expected_result = {
            'avgCpuUsagePctDec': 60.0,  # (50+60+70)/3 = 60
            'maxCpuUsagePctDec': 70.0,  # max(50,60,70) = 70
            'avgRamUtlPctDec': 85.0,    # (80+85+90)/3 = 85
            'maxRamUsagePctDec': 90.0,  # max(80,85,90) = 90
            'Storage-Max Read IOPS Size': 4096.0,  # max(1024,2048,4096) = 4096
            'Storage-Max Write IOPS Size': 2048.0  # max(512,1024,2048) = 2048
        }
        assert result == expected_result
    
    def test_collect_detailed_vm_metrics_missing_metrics(self, performance_collector, mock_vm):
        """Test collect_detailed_vm_metrics with missing metrics"""
        # Mock get_available_metrics with only CPU metrics
        performance_collector.get_available_metrics = Mock(return_value={
            'cpu.usage.average': 1
        })
        
        # Mock get_metric_values
        performance_collector.get_metric_values = Mock(return_value={
            'cpu.usage.average': [5000, 6000, 7000]  # Values in centipercent
        })
        
        # Call collect_detailed_vm_metrics
        result = performance_collector.collect_detailed_vm_metrics(mock_vm, 60, 180, 20)
        
        # Verify results - should only have CPU metrics
        expected_result = {
            'avgCpuUsagePctDec': 60.0,
            'maxCpuUsagePctDec': 70.0
        }
        assert result == expected_result  # Should gracefully handle missing metrics and only return available ones
    
    def test_determine_sampling_parameters(self, performance_collector):
        """Test _determine_sampling_parameters method"""
        # Test real-time (≤ 60 minutes)
        samples, desc, interval_id = performance_collector._determine_sampling_parameters(30)
        assert samples == 90  # (30 * 60) // 20  # Should calculate correct number of 20-second samples for 30 minutes
        assert desc == "20-second real-time"  # Should return correct description for real-time interval
        assert interval_id == 20  # Should return correct vCenter interval ID for real-time data
        
        # Test short-term (≤ 24 hours)
        samples, desc, interval_id = performance_collector._determine_sampling_parameters(240)
        assert samples == 48  # 240 // 5  # Should calculate correct number of 5-minute samples for 4 hours
        assert desc == "5-minute short-term"  # Should return correct description for short-term interval
        assert interval_id == 300  # Should return correct vCenter interval ID for short-term data
        
        # Test medium-term (≤ 7 days)
        samples, desc, interval_id = performance_collector._determine_sampling_parameters(2880)
        assert samples == 96  # 2880 // 30  # Should calculate correct number of 30-minute samples for 1 day
        assert desc == "30-minute medium-term"  # Should return correct description for medium-term interval
        assert interval_id == 1800  # Should return correct vCenter interval ID for medium-term data
        
        # Test long-term (≤ 30 days)
        samples, desc, interval_id = performance_collector._determine_sampling_parameters(14400)
        assert samples == 120  # 10080 // 120  # Should calculate correct number of 2-hour samples for 7 days
        assert desc == "2-hour long-term"  # Should return correct description for long-term interval
        assert interval_id == 7200  # Should return correct vCenter interval ID for long-term data
        
        # Test historical (> 30 days)
        samples, desc, interval_id = performance_collector._determine_sampling_parameters(50000)
        assert samples == 34  # 50000 // 1440  # Should calculate correct number of daily samples for extended period
        assert desc == "1-day historical"  # Should return correct description for historical interval
        assert interval_id == 86400  # Should return correct vCenter interval ID for historical data
    
    @patch('builtins.print')
    def test_get_performance_properties(self, mock_print, performance_collector):
        """Test get_performance_properties method"""
        # Mock content and container
        mock_content = Mock()
        mock_container = Mock()
        mock_container_view = Mock()
        
        # Setup mock VMs
        mock_vm1 = Mock()
        mock_vm1.name = "vm1"
        mock_vm1.config.uuid = "uuid1"
        mock_vm1.runtime.powerState = "poweredOn"
        
        mock_vm2 = Mock()
        mock_vm2.name = "vm2"
        mock_vm2.config.uuid = "uuid2"
        mock_vm2.runtime.powerState = "poweredOff"
        
        mock_vm3 = Mock()
        mock_vm3.name = "vm3"
        mock_vm3.config.uuid = "uuid3"
        mock_vm3.runtime.powerState = "poweredOn"
        
        mock_container_view.view = [mock_vm1, mock_vm2, mock_vm3]
        mock_content.viewManager.CreateContainerView.return_value = mock_container_view
        
        # Mock collect_detailed_vm_metrics
        performance_collector.collect_detailed_vm_metrics = Mock(return_value={
            'avgCpuUsagePctDec': 50.0,
            'maxCpuUsagePctDec': 70.0
        })
        
        # Call get_performance_properties
        with patch('datetime.datetime') as mock_datetime:
            mock_now = datetime.datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.now().strftime.return_value = "2023-01-01 12:00:00"
            
            result = performance_collector.get_performance_properties(mock_content, mock_container, 60)
        
        # Verify results
        assert len(result) == 2  # Should only process powered-on VMs, excluding the powered-off VM
        assert result[0]['VM Name'] == 'vm1'  # First result should contain correct VM name
        assert result[0]['VM UUID'] == 'uuid1'  # First result should contain correct VM UUID
        assert result[0]['avgCpuUsagePctDec'] == 50.0  # First result should contain correct average CPU usage
        assert result[0]['maxCpuUsagePctDec'] == 70.0  # First result should contain correct maximum CPU usage
        assert result[0]['Timestamp'] == "2023-01-01 12:00:00"  # First result should contain correct timestamp
        
        assert result[1]['VM Name'] == 'vm3'  # Second result should contain correct VM name for third VM
        assert result[1]['VM UUID'] == 'uuid3'  # Second result should contain correct VM UUID for third VM
        
        # Verify collect_detailed_vm_metrics was called for powered on VMs only
        assert performance_collector.collect_detailed_vm_metrics.call_count == 2  # Should only collect metrics for the 2 powered-on VMs
    
    def test_get_metric_headers(self, performance_collector):
        """Test get_metric_headers method"""
        headers = performance_collector.get_metric_headers()
        
        expected_headers = [
            'VM Name', 
            'VM UUID', 
            'maxCpuUsagePctDec', 
            'avgCpuUsagePctDec', 
            'maxRamUsagePctDec', 
            'avgRamUtlPctDec',
            'Storage-Max Read IOPS Size', 
            'Storage-Max Write IOPS Size',
            'Timestamp'
        ]
        
        assert headers == expected_headers  # Should return all expected column headers in correct order for CSV export
    
    def test_get_metric_values_with_disk_metrics(self, performance_collector, mock_vm):
        """Test get_metric_values with disk metrics that require wildcard instance"""
        # Setup mock performance query result for disk metrics
        mock_metric_value = Mock()
        mock_metric_value.id.counterId = 3  # virtualDisk metric
        mock_metric_value.value = [1024, 2048]
        
        mock_entity_metrics = Mock()
        mock_entity_metrics.value = [mock_metric_value]
        
        performance_collector.perf_manager.QueryPerf.return_value = [mock_entity_metrics]
        
        # Call get_metric_values
        result = performance_collector.get_metric_values(mock_vm, [3], 60, 180, 20)
        
        # Verify results
        expected_result = {
            "virtualDisk.readIOSize.latest": [1024, 2048]
        }
        assert result == expected_result  # Should return disk metric values correctly mapped by metric name
        
        # Verify the metric spec was created with wildcard instance for disk metrics
        performance_collector.perf_manager.QueryPerf.assert_called_once()  # Should make exactly one performance query call
        call_args = performance_collector.perf_manager.QueryPerf.call_args[1]['querySpec'][0]
        metric_spec = call_args.metricId[0]
        assert metric_spec.instance == "*"  # Should use wildcard for virtualDisk metrics to aggregate across all disk instances
    
    def test_get_metric_values_aggregates_multiple_instances(self, performance_collector, mock_vm):
        """Test that get_metric_values properly aggregates values from multiple instances"""
        # Setup mock performance query result with multiple metric instances
        mock_metric_value1 = Mock()
        mock_metric_value1.id.counterId = 1
        mock_metric_value1.value = [50, 60]
        
        mock_metric_value2 = Mock()
        mock_metric_value2.id.counterId = 1  # Same counter ID, different instance
        mock_metric_value2.value = [70, 80]
        
        mock_entity_metrics = Mock()
        mock_entity_metrics.value = [mock_metric_value1, mock_metric_value2]
        
        performance_collector.perf_manager.QueryPerf.return_value = [mock_entity_metrics]
        
        # Call get_metric_values
        result = performance_collector.get_metric_values(mock_vm, [1], 60, 180, 20)
        
        # Verify results are aggregated
        expected_result = {
            "cpu.usage.average": [50, 60, 70, 80]  # Values from both instances combined
        }
        assert result == expected_result  # Should properly aggregate values from multiple metric instances into single list
