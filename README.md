# Export for vCenter

Export for vCenter is a Python script designed to collect inventory data from VMware vCenter. It retrieves only data that is required as inputs for [AWS Transform for VMware](https://aws.amazon.com/transform/vmware/) and [AWS Transform Assessments](https://aws.amazon.com/transform/assessment/). Data is written out with filenames and column headers that match the [RVTools](https://www.robware.net/download) CSV format. This is not a replacement for RVTools as it retrieves only the data required by AWS Transform. 

The tool now also includes functionality to collect performance metrics using vCenter performance statistics.

## Getting started

Why might you want to use Export for vCenter instead of RVTools?

- You do not want to install a Windows executable to retrieve vCenter inventory.

- Your Application Security group has already approved Python, and you do not want to wait for RVTools aproval.

- You want to see exactly which API calls are being made against your vCenter Server.

- You are a Mac or Linux user and do not want to use Windows to retrieve vCenter inventory.

- You want control over which VMs get exported.

- You need to ensure only the minimum required information is exported from vCenter

### Install Python

This tool is dependent on Python3, you can find installation instructions for your operating system in the Python [documentation](https://wiki.python.org/moin/BeginnersGuide/Download). Python 3.10 or greater is required.

> Note: If you upgrade your Python version, you may need to restart your terminal session to get the script to execute.

### Download code

If you know git, clone the repo with:

```bash
git clone https://github.com/awslabs/export-for-vcenter.git
```

If you do not know git, you can download a zipfile from [Releases](https://github.com/awslabs/export-for-vcenter/releases)

### Install Python modules and packages

You do not have to do a virtual environment configuration, but it a good practice to follow. Using Python's virtual environment functionality will prevent any libraries used in this program from overwriting versions already on your workstation.

First, change into the code directory that you downloaded/cloned above.

On Mac/Linux, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows, run:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

When you navigate to the `export-for-vcenter` folder, you will find a requirements.txt file that list all your Python packages. They can all be installed by running the following command on Linux/Mac:

```bash
pip3 install -r requirements.txt
```

On Windows, run:

```powershell
python -m pip install -r requirements.txt
```

### Configuring the skip list

This script automatically skips the following objects:

 - VMs that are in `PoweredOff` state
 - VM guests that are in `notRunning` state
 - VMs with no IP address assigned
 - Hosts that are model `VMware Mobility Platform`
 - VMs with duplicate UUIDs. Only the first VM will be exported, any duplicates will be noted with a message
 - VMs in `vm-skip-list.txt`

The text file `vm-skip-list.txt` contains a list of VMs - if entries here match a VM name, that VM will be skipped and will not appear in the export. The list accepts regular expressions.  You can add your own custom expressions to skip additional VMs if you choose. 

## Running the script

### Configure environment variables

| Variable                         | Purpose                                            | Type | Required
| -------------------------------- | -------------------------------------------------- | ---- | ---
| EXP_VCENTER_HOST                 | vCenter FQDN, do not include https://              | str  | Yes
| EXP_VCENTER_USER                 | vCenter username                                   | str  | Yes
| EXP_VCENTER_PASSWORD             | vCenter password                                   | str  | Yes
| EXP_DISABLE_SSL_VERIFICATION     | If true, disables SSL check for vCenter connection | bool | No

> Note: An account with the Administrator role is shown in the examples below. A Read-Only role is supported if you add the user at the top level of the vCenter.

Windows:

```powershell
# Optional, prevents commands from being saved in command history for the current session
# This is a way to avoid accidentally leaking credentials
Set-PSReadLineOption -HistorySaveStyle SaveNothing

# Just the FQDN, do not include https://
$env:EXP_VCENTER_HOST = "vcenter.fqdn.url"
$env:EXP_VCENTER_USER= "administrator@vsphere.local"
$env:EXP_VCENTER_PASSWORD = "xxxxx"
```

Linux/Mac:

BASH and ZSH have different variables to prevent commands from being saved in command history.

BASH on Linux
```bash
HIST_IGNORE="(export)"
```

zsh on Mac
```bash
HISTORY_IGNORE="(export)"
```

The export commands are the same for both Linux and Mac
```bash
# Just the FQDN, do not include https://
export EXP_VCENTER_HOST="vcenter.fqdn.url"
export EXP_VCENTER_USER="xxxxx"
export EXP_VCENTER_PASSWORD="xxxxx"
```

### Run the script

#### Basic Usage

The main script is located in the `src/` directory, but you can run it from the project root using the provided runner script:

Windows

```powershell

# Run from src directory
python .\src\vcexport.py
```

Linux/Mac:

```bash

# Run from src directory
python3 src/vcexport.py
```

#### Command Line Options

The script supports several command line options to customize the export:

```bash
# Default behavior - exports inventory and performance statistics (60 minutes)
python3 src/vcexport.py

# Skip performance statistics collection
python3 src/vcexport.py --no-statistics

# Custom performance collection time windows
python3 src/vcexport.py --perf-interval 240     # 4 hours of performance data
python3 src/vcexport.py --perf-interval 1440    # 24 hours of performance data
python3 src/vcexport.py --perf-interval 10080   # 7 days of performance data
python3 src/vcexport.py --perf-interval 43200   # 30 days of performance data

# Show help
python3 src/vcexport.py --help
```

**Performance Collection Options:**
- `--perf-interval MINUTES`: Time interval in minutes for performance collection (default: 60)
- `--no-statistics`: Skip performance statistics collection entirely

The script automatically determines the appropriate vCenter sampling period based on the time interval:
- **≤ 60 minutes**: 20-second real-time intervals
- **≤ 24 hours**: 5-minute short-term intervals
- **≤ 7 days**: 30-minute medium-term intervals
- **≤ 30 days**: 2-hour long-term intervals
- **> 30 days**: 1-day historical intervals

### Script output

The script will output a file named `vcexport.zip` in the same folder as `vcexport.py`. This zip file contains:
- Standard inventory data in RVTools CSV format
- Performance metrics data collected from vCenter performance statistics

### Cleanup

- Close your terminal session
- Optional - Delete the export file vcexport.zip
- Optional - If you will not be doing any new exports, delete the entire project folder

## Performance Metrics Collection

Export for vCenter now includes functionality to collect performance metrics from vCenter using performance statistics API. The performance metrics collection automatically gathers the following metrics for all powered-on VMs:
- `maxCpuUsagePctDec` (maximum CPU usage percentage as decimal)
- `avgCpuUsagePctDec` (average CPU usage percentage as decimal)
- `maxRamUsagePctDec` (maximum RAM usage percentage as decimal)
- `avgRamUtlPctDec` (average RAM utilization percentage as decimal)
- `Storage-Max Read IOPS Size` (maximum virtual disk read request size in bytes)
- `Storage-Max Write IOPS Size` (maximum virtual disk write request size in bytes)

Performance metrics are collected over a 60-minute interval with 180 samples.

**Default Collection Settings:**
- **Time Window**: 60 minutes (uses the 20-second real-time interval)
- **Sample Count**: 180 samples (one sample every 20 seconds for 60 minutes)
- **Data Source**: Real-time performance statistics from vCenter

**Why These Defaults Were Chosen:**
- **60 minutes**: Provides a meaningful performance window while staying within the real-time data retention period
- **180 samples**: Gives granular 20-second intervals across the full hour (60 minutes ÷ 20 seconds = 180 samples)
- **20-second interval**: Most granular data available, best for capturing performance spikes and variations

**Note**: This tool uses whatever performance statistics are already being collected by your vCenter. Most vCenter environments have basic performance collection enabled by default, so no additional configuration is needed.

**Automatic Sampling Period Selection:**
The tool automatically selects the appropriate vCenter historical interval based on your requested time window:
- Use `--perf-interval 60` for detailed recent performance (20-second sampling)
- Use `--perf-interval 240` for 4-hour trends (5-minute sampling)
- Use `--perf-interval 1440` for daily patterns (30-minute sampling)
- Use `--perf-interval 10080` for weekly analysis (2-hour sampling)
- Use `--perf-interval 43200` for monthly capacity planning (daily sampling)

##### Performance Data Sampling Periods

vCenter Server's PerformanceManager uses predefined historical intervals for collecting and storing performance data. According to [VMware documentation](https://vdc-download.vmware.com/vmwb-repository/dcr-public/8e6af87a-b054-416d-8b61-aa9fba096944/617db479-aee6-4717-a94c-8bddd19785b9/vim.HistoricalInterval.html#samplingPeriod), these intervals are:

| Interval ID | Sampling Period | Description | Data Retention |
|-------------|----------------|-------------|----------------|
| 20          | 20 seconds     | Real-time   | Stored for 1 hour |
| 300         | 5 minutes      | Short-term  | Stored for 1 day |
| 1800        | 30 minutes     | Medium-term | Stored for 1 week |
| 7200        | 2 hours        | Long-term   | Stored for 1 month |
| 86400       | 1 day          | Historical  | Stored for 1 year |

When using the Export for vCenter performance collection functions, the `interval_mins` parameter determines which historical interval is used, and the `samples` parameter determines how many data points to collect within that interval. Choose appropriate values based on your assessment needs and the retention period required.

**Note**: The default 60-minute collection window uses the 20-second real-time interval (Interval ID 20) from the table above. This provides the most granular performance data available, but is limited to the past hour. For longer historical periods, you would need to adjust the collection parameters to use different sampling intervals.

## Testing

Export for vCenter includes comprehensive unit and integration tests to ensure reliability and functionality.

### Prerequisites for Testing

1. **Python Dependencies**: Install test dependencies from requirements.txt
2. **Docker**: Required for integration tests (to run vCenter simulator)

### Running Unit Tests

Unit tests use mocks and don't require external dependencies:

```bash
# Run unit tests with coverage
pytest -k unit -v --cov=src
```

### Running Integration Tests

Integration tests require a running vCenter simulator (vcsim) to test against real vCenter API behavior.

**Step 1: Start vCenter Simulator**
```bash
# Start vcsim Docker container
docker run -p 9090:9090 vmware/vcsim -l :9090
```

**Step 2: Run Integration Tests** (in a separate terminal)
```bash
# Run integration tests with coverage
pytest -k integration -v --cov=src
```

### Running All Tests

```bash
# Make sure vcsim is running first, then:
pytest -v --cov=src
```

### About vcsim

- **vcsim** is a vCenter and ESXi API based simulator from VMware
- Provides a lightweight way to test vCenter API interactions without a real vCenter environment
- Integration tests connect to `localhost:9090` where vcsim runs
- More information: https://hub.docker.com/r/vmware/vcsim