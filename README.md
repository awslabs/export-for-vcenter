# Export for vCenter

Export for vCenter is a Python script designed to collect inventory data from VMware vCenter. It retrieves only data that is required as inputs for [AWS Transform for VMware](https://aws.amazon.com/transform/vmware/) and [AWS Transform Assessments](https://aws.amazon.com/transform/assessment/). Data is written out with filenames and column headers that match the [RVTools](https://www.robware.net/download) CSV format. This is not a replacement for RVTools as it retrieves only the data required by AWS Transform. 

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

Windows

```
python .\vcexport.py
```

Linux/Mac:

```bash
python3 vcexport.py
```

### Script output

The script will output a file named `vcexport.zip` in the same folder as `vcexport.py`.

### Cleanup

- Close your terminal session
- Optional - Delete the export file vcexport.zip
- Optional - If you will not be doing any new exports, delete the entire project folder