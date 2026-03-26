# Installation Guide - Data Center Operations Manager

## Prerequisites Checklist

### 1. Python Installation (Required)

**For Windows:**
```bash
# Download from https://www.python.org/downloads/windows/
# Run installer and CHECK "Add Python to PATH" during installation
python --version  # Verify: should show Python 3.8 or higher
pip --version     # Verify pip is installed
```

**For Linux/macOS:**
```bash
# Using package manager (recommended)
sudo apt update && sudo apt install python3-pip  # Ubuntu/Debian
brew install python@3.12                          # macOS with Homebrew

python3 --version   # Verify installation
pip3 --version      # Verify pip is installed
```

### 2. Install Project Dependencies

Navigate to the project directory and install dependencies:

```bash
cd Coding13
pip install -r requirements.txt
```

This installs all required packages:
- **Flask==3.0.0** - Web application framework
- **netmiko==4.2.0** - SSH automation for network devices
- **paramiko==3.4.0** - SSH protocol support
- **pandas==2.1.3** - Data analysis and CSV export
- **requests==2.31.0** - REST API communication (Dell iDRAC/Open-E)
- **pysnmp==5.0.4** - SNMP monitoring for APC PDUs and generic devices
- **gunicorn==21.2.0** - Production WSGI server (optional)

### 3. Network Configuration

Before starting the application, ensure your network infrastructure allows SSH/HTTPS access from the server running this application:

| Device Type | Protocol | Port | Notes |
|-------------|----------|------|-------|
| Cisco Devices | SSH | 22 | Ensure SSH service enabled |
| Dell iDRAC | HTTPS (REST API) | 443 | Self-signed certs common |
| Open-E JovianDSS | HTTPS (REST API) | 443 | Verify REST API enabled |
| APC PDUs | SNMP | 161 | Community string required |

## Initial Setup & Configuration

### Step 1: Configure Network Devices for Remote Access

**For Cisco Nexus/3750X/Routers:**
```bash
configure terminal
! Enable SSH
crypto key generate rsa modulus 2048
ip ssh version 2
ip domain-name yourdomain.com

! Create admin user with full privileges
username admin privilege 15 secret YourStrongPassword123

! Configure VTY lines for SSH access
line vty 0 4
 transport input ssh
 login local
exit

! Save configuration
write memory
```

**For Dell iDRAC:**
- Access iDRAC web interface or BIOS setup
- Enable **Redfish API** in system settings
- Create admin user with appropriate privileges (level 15 equivalent)
- Note: Self-signed certificates are standard; SSL verification will be disabled by default

**For TrueNAS Storage:**
```bash
# Ensure SSH service is enabled
service ssh start
sysrc sshd_enable="YES"
```

### Step 2: Start the Application

Once all dependencies are installed and network devices are configured:

```bash
python app.py
```

You should see output similar to:
```
 * Running on http://127.0.0.1:5003
 * Running on http://0.0.0.0:5003
Press CTRL+C to quit
```

### Step 3: Access the Web Interface

Open your browser and navigate to: **http://localhost:5003**

You'll see a login page. For this demo, enter any username and password (replace with proper authentication in production).

## Device Configuration Examples

### Adding Dell iDRAC Server

1. Open web interface: http://localhost:5003
2. Click "Add New Device" section
3. Fill in the form:
   - **Device Name**: Main Production Server
   - **IP Address**: 192.168.1.100 (iDRAC management IP)
   - **Device Type**: Dell iDRAC (Server Management)
   - **Username**: root
   - **Password**: YourPassword123
4. Click **"🔗 Connect to Device"**

**Expected Result:**
- Device appears in "Connected Devices" list with status "connected"
- Click **👁️ View** to see system info, hardware health, RAID/disk status

### Adding Cisco Nexus Switch (100Gbps)

```bash
# Fill in the form:
Device Name: Core Switch 1
IP Address: 192.168.1.50
Device Type: Cisco Nexus Switch (100Gbps)
Username: admin
Password: YourPassword123
```

**Expected Result:**
- Interface status shows link speeds (10/25/40/100 Gbps detected automatically)
- Real-time RX/TX byte counters and error rates available

### Adding TrueNAS Storage System

```bash
# Fill in the form:
Device Name: Primary Storage Array
IP Address: 192.168.1.200
Device Type: TrueNAS Storage
Username: root
Password: YourPassword123
```

**Expected Result:**
- ZFS pool status with capacity utilization
- Disk health monitoring (ONLINE/DEGRADED/FAILED states)

## Common Issues & Solutions

### Issue 1: Connection Timeouts

**Symptoms**: "Failed to connect to [IP]" error when adding device

**Solutions**:
1. **Verify network connectivity**:
   ```bash
   ping <device-ip>           # Test basic connectivity
   telnet <device-ip> 22      # Test SSH port access (Cisco/TrueNAS)
   telnet <device-ip> 443     # Test HTTPS port (iDRAC/Open-E)
   ```

2. **Check firewall rules**:
   - Windows Firewall: Allow Python executable through private/public networks
   - Linux iptables/firewalld: Ensure ports 22 and 443 are open outbound
   - Corporate firewalls: May need to whitelist the server IP for network device access

3. **Verify SSH service is running on target**:
   ```bash
   # On Cisco/Nexus/TrueNAS devices
   show version | include SSH    # Verify SSH enabled
   
   # On TrueNAS via console
   service ssh status           # Check if SSH daemon running
   ```

### Issue 2: Authentication Failures

**Symptoms**: "Authentication failed" or login errors despite correct credentials

**Solutions**:
1. **Verify username and password**:
   - Ensure case-sensitive passwords are entered correctly
   - For iDRAC: default admin user is typically `root` with password from system sticker
   - For Cisco: verify privilege level 15 access for full functionality

2. **Check account status**:
   ```bash
   # On Cisco devices
   show users                    # Check if user exists and active
   show run | include username   # Verify user configuration
   
   # On iDRAC web interface
   Users tab → verify user is not locked out
   ```

3. **Password complexity requirements**:
   - Some systems enforce minimum length or character types
   - Try simpler passwords for testing, then implement proper complexity later

### Issue 3: SSL Certificate Errors (Dell iDRAC/Open-E)

**Symptoms**: "SSL verification failed" errors when connecting to Dell iDRAC or Open-E storage

**Solutions**:
1. **This is expected behavior** - self-signed certificates are standard for these devices
2. **Application already disables SSL verification by default**:
   ```python
   # In app.py, line 89:
   requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
   ```

3. **For production environments**, consider importing valid CA-signed certificates:
   ```bash
   # Generate self-signed certificate (for testing only!)
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
   
   # Use with gunicorn in production:
   gunicorn --certfile cert.pem --keyfile key.pem app:app
   ```

### Issue 4: SNMP Errors (APC PDUs)

**Symptoms**: "SNMP error" or timeout when monitoring APC PDUs via SNMP

**Solutions**:
1. **Verify SNMP is enabled on target device**:
   ```bash
   # On APC PDU web interface
   Network → SNMP → ensure v2c or v3 is enabled
   
   # Check community string (default: "public" for read-only)
   ```

2. **Test SNMP manually**:
   ```bash
   snmpwalk -v 2c -c public <pdu-ip> 1.3.6.1.4.1.1974  # Test APC-specific OIDs
   ```

3. **Configure custom community string in app.py** (if needed):
   ```python
   # In device initialization, set:
   snmp_community = 'your-custom-community'
   ```

## Production Deployment Recommendations

### 1. Use Environment Variables for Sensitive Data

Create a `.env` file or use environment variables:

```bash
# Set before starting the application
export SECRET_KEY='your-secret-key-change-in-production'
export DB_PASSWORD='secure-database-password'
```

In `app.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env file if exists

app.secret_key = os.environ.get('SECRET_KEY', 'fallback-weak-key-not-for-production')
```

### 2. Enable HTTPS with Valid SSL Certificates

For production deployments, always use valid certificates:

```bash
# Using Let's Encrypt (recommended for free certificates)
sudo certbot --nginx -d yourdomain.com

# Or generate self-signed for internal use:
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

Then start with gunicorn:
```bash
gunicorn --certfile cert.pem --keyfile key.pem -w 4 -b 0.0.0.0:5003 app:app
```

### 3. Implement Proper User Authentication

Replace the demo authentication with a robust solution:

```python
from flask_login import LoginManager, login_user, logout_user, login_required

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)  # Load from database or LDAP
```

### 4. Set Up Audit Logging

Add comprehensive logging for all operations:

```python
import logging

# Configure file logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('operations.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Log all device operations
logger.info(f"Device {device_name} added to inventory")
```

## Testing the Installation

### Test 1: Verify Application is Running

```bash
curl http://localhost:5003
```

Should return HTML content (the login page). If you get a connection refused error, check that the application is running.

### Test 2: Add a Test Device

If you have a test device available:

1. Navigate to http://localhost:5003 in browser
2. Enter any username/password for demo authentication
3. Fill in the "Add New Device" form with your test device details
4. Click **"🔗 Connect to Device"**
5. Verify device appears in "Connected Devices" list

### Test 3: View Device Data

1. Click **👁️ View** button next to connected device
2. Browse through available tabs (System Info, Hardware, Interfaces, etc.)
3. Click **"⬇️ Download CSV"** buttons to export reports
4. Verify all data is being retrieved correctly

## Next Steps After Installation

1. **Explore all monitoring features**: System info, hardware health, interface statistics, storage status
2. **Configure scheduled backups**: Export configurations and reports regularly
3. **Set up alerting integration**: Connect with your existing monitoring/notification systems
4. **Implement proper security**: Replace demo authentication with robust user management
5. **Deploy to production server**: Use gunicorn or similar WSGI server for better performance

## Support & Troubleshooting

If you encounter issues not covered in this guide:

1. **Check application logs**: Look for error messages in terminal output
2. **Verify network connectivity**: Ensure firewall rules allow required ports
3. **Review device documentation**: Confirm SSH/REST API/SNMP configuration requirements
4. **Check Python dependencies**: `pip list` to verify all packages are installed correctly

---

**Installation complete!** Your Data Center Operations Manager is ready for monitoring your infrastructure. 🎉

For additional features and customization, refer to the main [README.md](README.md) file or contact support.
