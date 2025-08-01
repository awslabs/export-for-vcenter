#!/usr/bin/env python3
import pytest
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import atexit
from src.collectors.performance_collector import PerformanceCollector

class TestPerformanceCollectorIntegration:
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
    def collector(self, vcenter_connection):
        """Create PerformanceCollector instance"""
        return PerformanceCollector(vcenter_connection)

    def test_integration_metrics_collection(self, collector, vcenter_connection):
        """Test end-to-end metrics collection"""
        content = vcenter_connection.RetrieveContent()
        container = content.rootFolder
        
        # Get performance metrics
        metrics = collector.get_performance_properties(
            content,
            container,
            interval_mins=20
        )
        
        # Verify results
        assert isinstance(metrics, list)
        if len(metrics) > 0:
            first_vm = metrics[0]
            assert 'VM Name' in first_vm
            assert 'avgCpuUsagePctDec' in first_vm
            assert 'avgRamUtlPctDec' in first_vm

    def test_integration_available_metrics(self, collector, vcenter_connection):
        """Test getting available metrics from vcsim"""
        content = vcenter_connection.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )
        
        if container.view:
            vm = container.view[0]
            metrics = collector.get_available_metrics(vm)
            
            assert len(metrics) > 0
            assert any('cpu' in metric for metric in metrics)
            assert any('mem' in metric for metric in metrics)