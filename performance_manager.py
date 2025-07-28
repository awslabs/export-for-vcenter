#!/usr/bin/env python
"""
Module for collecting performance metrics from vCenter using performance statistics.
This can be used to collect CPU, memory, disk, and network metrics for VMs and hosts.
"""

import datetime
import statistics
from pyVmomi import vim


class PerformanceCollector:
    """
    Class to collect performance metrics from vCenter using performance statistics.
    """
    
    def __init__(self, service_instance):
        """
        Initialize the PerformanceCollector with a vCenter service instance.
        
        Args:
            service_instance: A connected vCenter service instance
        """
        self.si = service_instance
        self.content = self.si.RetrieveContent()
        self.perf_manager = self.content.perfManager
        
        # Cache for metric names to counter IDs by entity type
        self.metric_cache = {}
        # Flag to indicate if counters have been initialized
        self.counters_initialized = False
        # Dictionary to store all performance counters
        self.perf_counters = {}
        
    def _initialize_counters(self):
        """
        Initialize the performance counters dictionary once.
        """
        if not self.counters_initialized:
            # Get all performance counters
            self.perf_counters = {c.key: c for c in self.perf_manager.perfCounter}
            self.counters_initialized = True
    
    def get_available_metrics(self, entity):
        """
        Get available performance metrics for a given entity.
        
        Args:
            entity: A vCenter managed entity (VM, Host, etc.)
            
        Returns:
            dict: Dictionary of available metrics with their IDs
        """
        # Initialize counters if not already done
        self._initialize_counters()
        
        # Check if we've already cached metrics for this entity type
        entity_type = type(entity).__name__
        if entity_type in self.metric_cache:
            return self.metric_cache[entity_type]
        
        available_metrics = {}
        
        # Get all available counters for the entity
        counter_ids = self.perf_manager.QueryAvailablePerfMetric(
            entity=entity, 
            intervalId=20  # Real-time metrics (20 second interval)
        )
        
        # Map the available counter IDs to their names
        for counter_id in counter_ids:
            counter = self.perf_counters.get(counter_id.counterId)
            if counter:
                metric_name = f"{counter.groupInfo.key}.{counter.nameInfo.key}.{counter.rollupType}"
                available_metrics[metric_name] = counter_id.counterId
        
        # Cache the metrics for this entity type
        self.metric_cache[entity_type] = available_metrics
        
        return available_metrics
    
    def get_metric_values(self, entity, metric_ids, interval_mins=60, samples=180, interval_id=20):
        """
        Get performance metric values for a given entity.
        
        Args:
            entity: A vCenter managed entity (VM, Host, etc.)
            metric_ids (list): List of metric IDs to collect
            interval_mins (int): Time interval in minutes for metrics collection
            samples (int): Number of samples to collect
            
        Returns:
            dict: Dictionary of metric values
        """
        # Initialize counters if not already done
        self._initialize_counters()
        
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(minutes=interval_mins)
        
        # Create metric query specs
        metrics = []

        for metric_id in metric_ids:
            # Get the counter to determine the appropriate instance value
            counter = self.perf_counters.get(metric_id)
            if counter:
                # Determine the appropriate instance value based on the metric group
                instance = ""  # Default for system-wide metrics
                if counter.groupInfo.key in ["disk", "virtualDisk", "net", "datastore"]:
                    instance = "*"  # Use wildcard for metrics with multiple instances
                
                metric_spec = vim.PerformanceManager.MetricId(counterId=metric_id, instance=instance)
                metrics.append(metric_spec)

        # Create query spec
        query_spec = vim.PerformanceManager.QuerySpec(
            entity=entity,
            metricId=metrics,
            intervalId=interval_id,  # Use the appropriate interval ID based on time window
            startTime=start_time,
            endTime=end_time,
            maxSample=samples
        )
        
        # Query performance metrics
        result = self.perf_manager.QueryPerf(querySpec=[query_spec])
        # Process results
        metric_values = {}
        
        if result:
            for entity_metrics in result:
                for metric in entity_metrics.value:
                    counter_id = metric.id.counterId
                    # Find the counter name using cached counters
                    counter = self.perf_counters.get(counter_id)
                    
                    if counter:
                        metric_name = f"{counter.groupInfo.key}.{counter.nameInfo.key}.{counter.rollupType}"
                        if metric_name in metric_values:
                           metric_values[metric_name].extend(metric.value) 
                        else:
                           metric_values[metric_name] = metric.value
        return metric_values

    def collect_detailed_vm_metrics(self, vm, interval_mins=60, samples=180, interval_id=20):
        """
        Collect detailed performance metrics for a VM including:
        - maxCpuUsagePctDec (maximum CPU usage percentage)
        - avgCpuUsagePctDec (average CPU usage percentage)
        - maxRamUsagePctDec (maximum RAM usage percentage)
        - avgRamUtlPctDec (average RAM utilization percentage)
        - Storage-Max Read IOPS Size
        - Storage-Max Write IOPS Size
        
        Args:
            vm: A vCenter VM object
            interval_mins (int): Time interval in minutes for metrics collection
            samples (int): Number of samples to collect
            
        Returns:
            dict: Dictionary of VM metrics
        """
        # Get available metrics for this VM
        available_metrics = self.get_available_metrics(vm)
        # Define the metrics we want to collect
        desired_metrics = {
            'cpu.usage.average': None,  # For avgCpuUsagePctDec & maxCpuUsagePctDec
            'mem.usage.average': None,  # For avgRamUtlPctDec & maxRamUsagePctDec
            'virtualDisk.readIOSize.latest': None,   # Size of read operations
            'virtualDisk.writeIOSize.latest': None  # Size of write operations
        }
        
        # Filter for metrics we want that are available
        metric_ids = []
        for metric_name in desired_metrics:
            if metric_name in available_metrics:
                metric_ids.append(available_metrics[metric_name])

        # Get metric values with multiple samples
        raw_metrics = {}
        if metric_ids:
            raw_metrics = self.get_metric_values(vm, metric_ids, interval_mins, samples, interval_id)

        # Process the raw metrics into the format we want
        processed_metrics = {}

        # Calculate CPU metrics
        if 'cpu.usage.average' in raw_metrics:
            values = [v/100.0 for v in raw_metrics['cpu.usage.average']]  # Convert to decimal percentage
            processed_metrics['avgCpuUsagePctDec'] = round(statistics.mean(values), 2)
            processed_metrics['maxCpuUsagePctDec'] = round(max(values), 2)
        
        # Calculate RAM metrics
        if 'mem.usage.average' in raw_metrics:
            values = [v/100.0 for v in raw_metrics['mem.usage.average']]  # Convert to decimal percentage
            processed_metrics['avgRamUtlPctDec'] = round(statistics.mean(values), 2)
            processed_metrics['maxRamUsagePctDec'] = round(max(values), 2)
        
        # Calculate Storage metrics
        if 'virtualDisk.readIOSize.latest' in raw_metrics:
            values = raw_metrics['virtualDisk.readIOSize.latest']
            processed_metrics['Storage-Max Read IOPS Size'] = round(max(values), 2)
        
        if 'virtualDisk.writeIOSize.latest' in raw_metrics:
            values = raw_metrics['virtualDisk.writeIOSize.latest']
            processed_metrics['Storage-Max Write IOPS Size'] = round(max(values), 2)
        
        return processed_metrics
    
    def _determine_sampling_parameters(self, interval_mins):
        """
        Determine appropriate sampling period and sample count based on time interval.
        
        Args:
            interval_mins (int): Time interval in minutes for metrics collection
            
        Returns:
            tuple: (samples, interval_description, interval_id)
        """
        if interval_mins <= 60:
            # Real-time: 20-second intervals
            samples = (interval_mins * 60) // 20  # Convert minutes to seconds, then divide by 20-second intervals
            interval_description = "20-second real-time"
            interval_id = 20
        elif interval_mins <= 1440:  # 24 hours
            # Short-term: 5-minute intervals  
            samples = interval_mins // 5  # Divide minutes by 5-minute intervals
            interval_description = "5-minute short-term"
            interval_id = 300
        elif interval_mins <= 10080:  # 7 days
            # Medium-term: 30-minute intervals
            samples = interval_mins // 30  # Divide minutes by 30-minute intervals
            interval_description = "30-minute medium-term"
            interval_id = 1800
        elif interval_mins <= 43200:  # 30 days
            # Long-term: 2-hour intervals
            samples = interval_mins // 120  # Divide minutes by 120-minute intervals
            interval_description = "2-hour long-term"
            interval_id = 7200
        else:
            # Historical: 1-day intervals
            samples = interval_mins // 1440  # Divide minutes by 1440-minute intervals (24 hours)
            interval_description = "1-day historical"
            interval_id = 86400
        
        return samples, interval_description, interval_id

    def get_performance_properties(self, content, container, interval_mins=60):
        """
        Export detailed performance metrics for multiple VMs.
        Automatically determines appropriate sampling period and sample count based on interval.
        
        Args:
            content: vCenter content object
            container: vCenter container object
            interval_mins (int): Time interval in minutes for metrics collection
            
        Returns:
            list: List of performance metric dictionaries
        """
        # Determine appropriate sampling parameters
        samples, interval_description, interval_id = self._determine_sampling_parameters(interval_mins)
        
        performance_metric_properties_list = []
        
        # Collect performance metrics
        print("Collecting performance metrics...")
        print(f"Time interval: {interval_mins} minutes using {interval_description} sampling ({samples} samples)")
        
        # Get content and container view
        container_view = content.viewManager.CreateContainerView(container, [vim.VirtualMachine], True)
        
        # Get all VMs
        all_vms = list(container_view.view)
        
        # Filter for powered on VMs
        powered_on_vms = [vm for vm in all_vms if vm.runtime.powerState == 'poweredOn']
        
        # Process VMs in batches to avoid overwhelming vCenter
        batch_size = 10
        for i in range(0, len(powered_on_vms), batch_size):
            batch = powered_on_vms[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(powered_on_vms) + batch_size - 1)//batch_size} ({len(batch)} VMs)")
            
            for vm in batch:
                print(f"Processing VM {i+1} of {len(powered_on_vms)}: {vm.name}")
                metrics = self.collect_detailed_vm_metrics(vm, interval_mins, samples, interval_id)
                performance_metric = {
                    'VM Name': vm.name,
                    'VM UUID': vm.config.uuid if hasattr(vm, 'config') and vm.config else '',
                    'Timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Add metrics to the row
                for metric_name, value in metrics.items():
                    performance_metric[metric_name] = value
                
                performance_metric_properties_list.append(performance_metric)  

        return performance_metric_properties_list

    def get_metric_headers(self):
        return [
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
