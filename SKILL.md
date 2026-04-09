---
name: gcp-ssh-troubleshoot

description: Troubleshoot SSH connection issues for a Compute Engine instance on GCP.
Use when the user use the word "ssh" or ask to "test", "check" a ssh connection.
Example "I can't connect to my VM using ssh", "Can you check my ssh connection to the VM?", "Test ssh connection to my VM"

dependencies: |
    >=gcloud 551.0.0
    >=python3.8
    google-api-core==2.30.2
    google-cloud-compute==1.47.0
    google-cloud-resource-manager==1.17.0

metadata:
    author: Emmanuel DRECQ
    version: 0.1.0


# Skill: Troubleshoot Compute Engine VM SSH Connection

**Goal** To diagnose and resolve SSH connection issues with a Google Cloud Platform Virtual Machine.

**Required IAM Roles and Permissions:**
- roles/compute.viewer: To view the status of VM instances and firewall rules.
- roles/iap.tunnelResourceAccessor: To test IAP-based SSH connections.
- roles/compute.osLogin: If OS Login is enabled, this role is needed to access the VM via SSH.

**Required APIs:**
- Compute Engine API: To check VM status and firewall rules.
- Cloud Resource Manager API: To check IAM permissions.

**Authentication:**
- Application Default Credentials (ADC) for API calls.
- gcloud CLI authentication for SSH connection testing.

**Instructions:**

1.  **Gather Information:** Ask for the Project ID, instance, and Zone.

2.  **Execute Troubleshooting Script:** Run the `script/gcp_ssh_troubleshoot.py` script with the collected information. The script performs the following automated checks

    *   **Check VM Status:** Verifies that the VM instance is in the `RUNNING` state.

    *   **Check Firewall Rules:** Checks the project's firewall rules to ensure that an ingress rule allows SSH traffic (TCP port 22) to the VM's network.

    *   **Check IAP Permissions:** Tests if the currently authenticated user has the necessary IAM permissions for IAP (Identity-Aware Proxy) tunneling (`iap.tunnelDestGroups.accessViaIAP` and `iap.tunnelInstances.accessViaIAP`).

    *   **Check IAP Configuration:** Checks if the VM is configured to allow IAP tunneling by verifying the `enable-oslogin` metadata key is set to `true`.

    *   **Attempt SSH Connection:** Tries to connect to the VM using `gcloud compute ssh`.

3.  **Analyze Results:**

    *   **If Successful:** Inform the user the connection from the tool was successful and the issue is likely with their local machine or a third-party client. Suggest checking local firewall settings.

    *   **If Failed:** The script will output detailed error information. Analyze the output to determine the cause
        *   **"Permission denied":** This suggests an issue with SSH keys or OS-level permissions on the VM.
        *   **"Connection timed out":** This points to a network connectivity problem, such as missing firewall rules or an OS-level firewall on the VM.
        *   **Other errors:** Review the script's output for specific details and suggestions.

4.  **Provide Guidance:** Based on the analysis, provide the user with the specific findings and recommended commands or actions to resolve the issue, as suggested by the script's output.

---