#!/usr/bin/env python
"""
Modular script to export virtual machine and related config info from vCenter to CSV files.
This is a refactored version of vcexport.py using a modular architecture.
"""
import argparse
import os
import sys
from vcenter_orchestrator import VCenterOrchestrator


def main():
    """Main function to run the vCenter export process."""
    
    # Minimum Python version check
    if sys.version_info < (3, 10):
        print("Python 3.10 or higher is required to run this script.")
        print(f"Current Python version: {sys.version}")
        sys.exit(1)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Export VM data from vCenter to CSV files in RVTools format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables Required:
EXP_VCENTER_HOST      vCenter FQDN (do not include https://)
EXP_VCENTER_USER      vCenter username
EXP_VCENTER_PASSWORD  vCenter password

Performance Collection Examples:
python vcexport_modular.py                          # Default: 60 minutes
python vcexport_modular.py --perf-interval 240     # 4 hours of data
python vcexport_modular.py --perf-interval 1440    # 24 hours of data
python vcexport_modular.py --no-statistics         # Skip performance collection
        """
    )
    
    parser.add_argument(
        "--no-statistics",
        action="store_false",
        dest="export_statistics",
        default=True,
        help="Skip performance statistics collection"
    )
    
    parser.add_argument(
        "--perf-interval",
        type=int,
        default=60,
        help="Performance collection time interval in minutes (default: 60). Sampling period is automatically determined."
    )
    
    parser.add_argument(
        "--max-count",
        type=int,
        default=None,
        help="Maximum number of VMs to process (for testing purposes)"
    )
    
    parser.add_argument(
        "--keep-csv",
        action="store_false",
        dest="purge_csv",
        default=True,
        help="Keep individual CSV files after creating zip archive"
    )
    
    args = parser.parse_args()
    
    # Get vCenter details from environment variables
    vcenter_host = os.environ.get("EXP_VCENTER_HOST")
    vcenter_user = os.environ.get("EXP_VCENTER_USER")
    vcenter_password = os.environ.get("EXP_VCENTER_PASSWORD")
    disable_ssl_verification = os.environ.get("EXP_DISABLE_SSL_VERIFICATION", "false").lower() == "true"

    # Validate environment variables
    if not all([vcenter_host, vcenter_user, vcenter_password]):
        print("Error: Please set EXP_VCENTER_HOST, EXP_VCENTER_USER, and EXP_VCENTER_PASSWORD environment variables")
        sys.exit(1)

    # Create orchestrator instance
    orchestrator = VCenterOrchestrator(
        host=vcenter_host,
        user=vcenter_user,
        password=vcenter_password,
        disable_ssl_verification=disable_ssl_verification
    )
    
    try:
        # Connect to vCenter
        if not orchestrator.connect():
            print("Failed to connect to vCenter")
            sys.exit(1)
        
        # Export data
        print("Starting export process, this will take some time...")
        zip_file = orchestrator.export_data(
            max_count=args.max_count,
            purge_csv=args.purge_csv,
            export_statistics=args.export_statistics,
            perf_interval=args.perf_interval
        )
        
        if zip_file:
            print(f"Export completed successfully: {zip_file}")
        else:
            print("Export failed")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nExport interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Export failed with error: {str(e)}")
        sys.exit(1)
    finally:
        # Always disconnect
        orchestrator.disconnect()


if __name__ == "__main__":
    main()
