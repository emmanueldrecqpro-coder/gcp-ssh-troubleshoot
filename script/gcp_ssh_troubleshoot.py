#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A Python script to automate troubleshooting SSH connection issues with a
Google Cloud Platform Virtual Machine.

This script follows the diagnostic steps outlined in the ssh-troubleshoot skill.
"""

import argparse
import subprocess
import sys
from typing import List

from google.api_core import exceptions
from google.cloud import compute_v1
from google.cloud import resourcemanager_v3


# --- Color Codes for better terminal output ---
class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def get_instance_details(
    project_id: str, zone: str, instance_name: str
) -> compute_v1.Instance | None:
    """
    Retrieves the full details of a VM instance.

    Args:
        project_id: The Google Cloud project ID.
        zone: The zone where the VM is located.
        instance_name: The name of the virtual machine.

    Returns:
        A compute_v1.Instance object or None if not found or an error occurs.
    """
    try:
        client = compute_v1.InstancesClient()
        instance = client.get(project=project_id, zone=zone, instance=instance_name)
        return instance
    except exceptions.NotFound:
        print(f"{Colors.FAIL}NOT FOUND{Colors.ENDC}")
        return None
    except Exception as e:
        print(f"{Colors.FAIL}ERROR{Colors.ENDC}")
        print(f"   An unexpected error occurred: {e}")
        return None


def check_vm_status(instance: compute_v1.Instance) -> bool:
    """Checks if the VM instance status is RUNNING."""
    print("1. Checking VM status... ", end="")
    if instance.status == "RUNNING":
        print(f"{Colors.OKGREEN}VM instance status is {instance.status}{Colors.ENDC}")
        return True
    else:
        print(f"{Colors.FAIL}VM instance status is {instance.status}{Colors.ENDC}")
        return False


def check_firewall_rules(project_id: str, network: str) -> bool:
    """
    Checks if an ingress firewall rule allows TCP port 22.

    Args:
        project_id: The Google Cloud project ID.
        network: The network URL of the VM.

    Returns:
        True if a valid SSH rule is found, False otherwise.
    """
    print("2. Checking for firewall rule allowing SSH (tcp:22)... ", end="")
    try:
        client = compute_v1.FirewallsClient()
        firewalls = client.list(project=project_id)

        for rule in firewalls:
            # Rule must be for the correct network, enabled, and ingress
            if rule.network != network or rule.disabled or rule.direction != "INGRESS":
                continue

            # Check if the rule allows tcp:22
            for allowed in rule.allowed:
                if allowed.I_p_protocol == "tcp":
                    # not allowed.ports == True means allowed.ports is empty => it means all ports are allowed.
                    # Otherwise, check for port 22.
                    if not allowed.ports or "22" in allowed.ports:
                        print(
                            f"{Colors.OKGREEN}Found firewall rule ('{rule.name}'){Colors.ENDC}"
                        )
                        return True

        print(f"{Colors.FAIL}Firewall rule not found{Colors.ENDC}")
        return False
    except Exception as e:
        print(f"{Colors.FAIL}ERROR{Colors.ENDC}")
        print(f"   Could not check firewall rules: {e}")
        return False


# How to test permissions : https://docs.cloud.google.com/iam/docs/testing-permissions#how_to_test_permissions
def test_iap_permissions(project_id: str) -> bool:
    """
    Tests IAP permissions of currently authenticated user to a project.

    Args:
        project_id: The Google Cloud project ID.
    Returns:
        True if the user has the required permissions, False otherwise.
    """

    print("3. Checking current user IAP permissions... ", end="")

    projects_client = resourcemanager_v3.ProjectsClient()
    if not project_id.startswith("projects/"):
        project_id = "projects/" + project_id

    owned_permissions = projects_client.test_iam_permissions(
        resource=project_id,
        permissions=[
            "iap.tunnelDestGroups.accessViaIAP",
            "iap.tunnelInstances.accessViaIAP",
        ],
    ).permissions

    if (
        "iap.tunnelDestGroups.accessViaIAP" in owned_permissions
        and "iap.tunnelInstances.accessViaIAP" in owned_permissions
    ):
        print(f"{Colors.OKGREEN}Has required permissions{Colors.ENDC}")
        return True
    else:
        print(f"{Colors.FAIL}Missing required permissions{Colors.ENDC}")
        return False


def check_iap_tunnel(instance: compute_v1.Instance) -> bool:
    """
    Checks if the VM is configured to allow IAP tunneling.

    Args:
        instance: The compute_v1.Instance object.
    Returns:
        True if IAP tunneling is allowed, False otherwise.
    """
    print("4. Checking if IAP tunneling is allowed... ", end="")
    try:
        for item in instance.metadata.items:
            if item.key == "enable-oslogin" and item.value.lower() == "true":
                print(f"{Colors.OKGREEN}IAP tunneling is enabled{Colors.ENDC}")
                return True
        print(f"{Colors.FAIL}IAP tunneling is not enabled{Colors.ENDC}")
        return False
    except Exception as e:
        print(f"{Colors.FAIL}ERROR{Colors.ENDC}")
        print(f"   Could not check IAP tunneling: {e}")
        return False


def attempt_ssh_connection(project_id: str, zone: str, instance: str) -> None:
    """
    Attempts to connect to the VM using 'gcloud compute ssh' and analyzes the output.
    """
    print("5. Attempting to connect via 'gcloud compute ssh'... ", end="")

    command = [
        "gcloud",
        "compute",
        "ssh",
        f"--project={project_id}",
        f"--zone={zone}",
        instance,
        "--command=echo 'SSH_SUCCESS'",
        "--ssh-flag=-o ConnectTimeout=10",  # Set a 10-second timeout
    ]

    # Using subprocess to capture stdout and stderr
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,  # Do not raise exception on non-zero exit code
    )

    if process.returncode == 0 and "SSH_SUCCESS" in process.stdout:
        print(f"{Colors.OKGREEN}SSH connection was successful.{Colors.ENDC}")
        print(
            "If you are still having issues with a different client, the problem is likely on your local machine."
        )
        print("Suggestions:")
        print("  - Check your local firewall settings.")
        print("  - Ensure your third-party SSH client is configured correctly.")
        return

    # If connection failed, print details and analyze
    print(f"{Colors.FAIL}FAILURE: 'gcloud compute ssh' command failed.{Colors.ENDC}")
    print(
        f"{Colors.HEADER}------------------- Error Details -------------------{Colors.ENDC}"
    )
    # Combine stdout and stderr for full context
    full_output = process.stdout + process.stderr
    print(full_output)
    print(
        f"{Colors.HEADER}-----------------------------------------------------{Colors.ENDC}"
    )

    print("Analyzing error message...")
    if "Permission denied" in full_output:
        print(
            f"{Colors.WARNING}Analysis: 'Permission denied' error detected.{Colors.ENDC}"
        )
        print("  This often indicates an issue with SSH keys or OS-level permissions.")
        print(
            "  - Your public key may not be in the VM's metadata or in ~/.ssh/authorized_keys on the VM."
        )
        print(
            "  - File permissions on the VM's ~/.ssh/ directory or authorized_keys file might be incorrect."
        )
    elif "Connection timed out" in full_output:
        print(
            f"{Colors.WARNING}Analysis: 'Connection timed out' error detected.{Colors.ENDC}"
        )
        print("  This suggests a network connectivity issue.")
        print("  - Re-verify the firewall rules for your project and VPC.")
        print(
            "  - Check for OS-level firewalls on the VM (e.g., 'ufw' on Ubuntu, 'firewalld' on CentOS/RHEL)."
        )
        print("  - Ensure the SSH daemon (sshd) is running on the VM.")
    else:
        print(
            f"{Colors.WARNING}Analysis: Could not determine a specific common cause.{Colors.ENDC}"
        )
        print(
            "  Please review the detailed error output above to diagnose the problem."
        )


def main():
    """Main function to orchestrate the troubleshooting process."""
    parser = argparse.ArgumentParser(
        description="Troubleshoot SSH connection issues with a Google Cloud VM."
    )
    parser.add_argument("--project", required=True, help="The Google Cloud project ID.")
    parser.add_argument(
        "--instance", required=True, help="The name of the virtual machine."
    )
    parser.add_argument(
        "--zone", required=True, help="The zone where the VM is located."
    )
    args = parser.parse_args()

    print(
        f"Starting SSH troubleshooting for VM '{args.instance}' in project '{args.project}'..."
    )
    print("-----------------------------------------------------")

    # 1. Get VM instance details
    instance = get_instance_details(args.project, args.zone, args.instance)
    if not instance:
        print(f"{Colors.FAIL}Could not retrieve VM details. Aborting.{Colors.ENDC}")
        sys.exit(1)

    # 2. Check VM Status
    if not check_vm_status(instance):
        print(f"{Colors.FAIL}Aborting: VM is not in a RUNNING state.{Colors.ENDC}")
        sys.exit(1)

    # 3. Check Firewall Rules
    network_url = instance.network_interfaces[0].network
    if not check_firewall_rules(args.project, network_url):
        print("   Consider creating a rule, for example:")
        print(
            f"   gcloud compute firewall-rules create allow-ssh-{args.instance} --allow tcp:22 --network {network_url.split('/')[-1]} --source-ranges 0.0.0.0/0"
        )

    # 3. Check IAP Tunneling Permissions
    if not test_iap_permissions(args.project):
        print(
            "To use IAP tunneling, your account needs the following permissions: 'iap.tunnelDestGroups.accessViaIAP' and 'iap.tunnelInstances.accessViaIAP'."
        )
        print("Configure the iam role iap.tunnelResourceAccessor.")

    # 4. Check IAP Tunneling
    if not check_iap_tunnel(instance):
        print(
            "If you want to use IAP tunneling, enable it by adding the metadata key 'enable-oslogin' with value 'true' to your VM."
        )

    # 5. Attempt SSH Connection and Analyze
    attempt_ssh_connection(args.project, args.zone, args.instance)

    print("-----------------------------------------------------")
    print("Troubleshooting finished.")


if __name__ == "__main__":
    main()
