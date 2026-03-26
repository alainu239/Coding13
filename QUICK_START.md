# Quick Start - Data Center Operations Manager (5-Minute Guide)

## Step 1: Install Python (If Not Already Installed)

**Windows:**
- Download from https://www.python.org/downloads/windows/
- **Important**: Check "Add Python to PATH" during installation!
- Verify: Open PowerShell and run `python --version`

**macOS/Linux:**
```bash
# Usually pre-installed, verify with:
python3 --version
```

## Step 2: Install Project Dependencies

Open terminal/command prompt and navigate to the project folder:

```bash
cd C:\Users\Mark.Cancino\.openclaw\workspace\Coding13
pip install -r requirements.txt
```

This installs all required packages. Wait for installation to complete (may take 2-5 minutes).

## Step 3: Start the Application

In the same terminal, run:

```bash
python app.py
```

You should see output like:
```
 * Running on http://127.0.0.1:5003
 * Running on http://0.0.0.0:5003
Press CTRL+C to quit
```

**✅ Application is now running!**

## Step 4: Access the Dashboard

Open your web browser and go to: **http://localhost:5003**

You'll see a login page. For this demo, enter any username/password (e.g., `admin` / `password`) to continue.

## Step 5: Add Your First Device

### Example: Adding a Dell iDRAC Server

1. Click "Add New Device" section
2. Fill in the form:
   - **Device Name**: Production Server 1
   - **IP Address**: 192.168.1.100 (your server's iDRAC management IP)
   - **Device Type**: Dell iDRAC (Server Management) *(select from dropdown)*
   - **Username**: root (or your admin username)
   - **Password**: YourPassword123
3. Click **"🔗 Connect to Device"**

**Expected Result:**
- Device appears in "Connected Devices" list with status indicator
- Green badge = connected, Red badge = disconnected

### Example: Adding Cisco Nexus Switch

```bash
Device Name: Core Switch 1
IP Address: 192.168.1.50 (switch management IP)
Device Type: Cisco Nexus Switch (100Gbps)
Username: admin
Password: YourSwitchPassword123
```

## Step 6: View Device Data! 🎉

Once your device shows as "connected":

1. Click the **👁️ View** button next to your device in the list
2. Browse through available tabs:
   - **🖥️ System Info**: Model, serial number, uptime
   - **⚙️ Hardware**: Temperature sensors, fan speeds, power supplies
   - **🔌 Interfaces**: Network interface stats (RX/TX bytes, errors)
   - **💾 Storage**: Pool/volume status (for TrueNAS/Open-E)
   - **💿 RAID/Disk**: RAID configuration and disk health
   - **🔄 Routing**: Routing table analysis (Cisco routers)

3. Click **"⬇️ Download CSV"** buttons to export reports!

## What You Can Monitor Right Now

✅ **Dell iDRAC Servers**
- System model, serial number, BIOS version
- Real-time temperature readings from all sensors
- Fan speeds for all cooling fans
- Power supply status and consumption (watts)
- RAID controller configuration
- Virtual disk capacity and physical disk health

✅ **Cisco Nexus/3750X Switches**
- Interface status with automatic speed detection (10G/25G/40G/100Gbps!)
- RX/TX byte counters for traffic analysis
- Error rate tracking (RX errors, TX errors)
- System uptime in human-readable format

✅ **Cisco Routers**
- Complete routing table with gateway information
- Route type identification (connected, static, OSPF, BGP)
- Network topology visualization support

✅ **TrueNAS/Open-E Storage Systems**
- ZFS pool status and capacity utilization
- Volume-based storage information
- Disk health monitoring (ONLINE/DEGRADED/FAILED states)
- Capacity breakdown in TB/GB with usage details

## Quick Actions Available

### Export Reports for Documentation
Click **"⬇️ Download CSV"** on any tab to save:
- System information reports
- Hardware health status (temp/fans/power)
- Interface statistics and traffic analysis
- Storage pool/volume capacity reports
- RAID configuration and disk health data
- Routing table documentation

### Monitor Multiple Devices
Add multiple devices of different types simultaneously. The dashboard shows all connected devices in one view with color-coded status indicators.

### Run Custom Commands (Advanced)
Use the custom command panel to execute any CLI command supported by your network device for advanced troubleshooting and verification.

## What's Next? 🚀

1. **Explore all features**: Try different tabs and see what data you can gather from each device type
2. **Add more devices**: Connect Dell servers, Cisco switches, storage systems, routers - mix and match!
3. **Export reports**: Download CSV files for documentation, auditing, or trend analysis
4. **Set up regular monitoring**: Use the dashboard to monitor your infrastructure in real-time

## Troubleshooting Quick Fixes

### Can't connect to device?
- Check firewall rules allow SSH (port 22) or HTTPS (port 443 for iDRAC/Open-E)
- Verify IP address and credentials are correct
- Ensure SSH service is running on target device

### SSL Certificate Errors with Dell iDRAC?
- This is expected! Self-signed certificates are standard for iDRAC devices
- Application already disables SSL verification by default
- No action needed - it works out of the box!

### Device shows as "disconnected"?
- Click **🔄 Refresh** to retry connection attempt
- Check username/password and network connectivity
- Verify device has SSH/REST API enabled

## Congratulations! 🎊

You now have a powerful data center operations management tool that provides real-time visibility into your critical infrastructure across multiple vendor platforms.

### Summary of What You Achieved in 5 Minutes:
✅ Installed all dependencies  
✅ Started the web application  
✅ Added your first monitored device  
✅ Viewed system information and hardware health  
✅ Exported reports for documentation  

**You're ready to monitor your entire data center!** 🏢🚀

For more detailed setup instructions, see [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md).
For project overview and features, see [README.md](README.md).

---

**Happy Monitoring!** 📊💡

*Quick Start Guide v1.0 - March 25, 2026*  
*Repository: https://github.com/alainu239/Coding13*
