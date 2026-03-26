from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from datetime import datetime, timedelta
import json
import io
import csv
import re
import logging
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'dcop-secret-key-change-in-production'  # Change in production!

# In-memory storage (use database in production)
datacenter_inventory = {}
monitoring_data = {}

class DataCenterDevice:
    """Base class for all data center devices"""
    
    def __init__(self, ip, name, device_type, credentials=None):
        self.ip = ip
        self.name = name
        self.device_type = device_type
        self.credentials = credentials or {}
        self.connection = None
        self.last_update = None
        
    def connect(self):
        """Establish connection to device"""
        raise NotImplementedError
    
    def disconnect(self):
        """Close connection"""
        if self.connection:
            try:
                self.connection.disconnect()
            except:
                pass
    
    def get_status(self):
        """Get basic status information"""
        return {
            'ip': self.ip,
            'name': self.name,
            'type': self.device_type,
            'status': 'unknown',
            'last_update': None
        }

# ==================== DEVICE HANDLERS ====================

class DellIDRAC(DataCenterDevice):
    """Handler for Dell iDRAC management"""
    
    def __init__(self, ip, username, password, name="Dell Server", **kwargs):
        super().__init__(ip, name, 'dell_idrac', {'username': username, 'password': password})
        self.idrac_url = f"https://{ip}"
        
    def connect(self):
        """Connect to iDRAC via REST API"""
        try:
            import requests
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            
            # Suppress SSL warnings for self-signed certs (common with iDRAC)
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            
            response = requests.get(
                f"{self.idrac_url}/redfish/v1/Managers/iDRAC.Embedded.1",
                auth=(self.credentials['username'], self.credentials['password']),
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                self.connection = True
                return True
            
            # Try SSH connection as fallback
            from netmiko import ConnectHandler
            self.connection = ConnectHandler(
                device_type='dell_idrac',
                hostname=self.ip,
                username=self.credentials['username'],
                password=self.credentials['password']
            )
            return True
            
        except Exception as e:
            logger.error(f"iDRAC connection failed for {self.ip}: {e}")
            return False
    
    def get_system_info(self):
        """Get system information from iDRAC"""
        try:
            import requests
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            
            # Get system info via REST API
            response = requests.get(
                f"{self.idrac_url}/redfish/v1/Systems/System.Embedded.1",
                auth=(self.credentials['username'], self.credentials['password']),
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse system information
                info = {
                    'model': data.get('Model', 'Unknown'),
                    'serial_number': data.get('SerialNumber', 'N/A'),
                    'manufacturer': data.get('Manufacturer', 'Unknown'),
                    'power_state': data.get('PowerState', 'Unknown'),
                    'bios_version': data.get('BiosReleaseDate', 'Unknown')
                }
                
                # Get processors
                if 'Processors' in data:
                    procs = data['Processors']['@odata.id']
                    proc_response = requests.get(
                        f"{self.idrac_url}{procs}",
                        auth=(self.credentials['username'], self.credentials['password']),
                        verify=False,
                        timeout=10
                    )
                    if proc_response.status_code == 200:
                        proc_data = proc_response.json()
                        info['processors'] = len(proc_data.get('Members', []))
                
                # Get memory
                if 'Memory' in data:
                    mem = data['Memory']['@odata.id']
                    mem_response = requests.get(
                        f"{self.idrac_url}{mem}",
                        auth=(self.credentials['username'], self.credentials['password']),
                        verify=False,
                        timeout=10
                    )
                    if mem_response.status_code == 200:
                        mem_data = mem_response.json()
                        info['memory'] = {
                            'total_mb': sum(m.get('SizeMB', 0) for m in mem_data.get('Members', [])),
                            'status': mem_data.get('@odata.id', '').split('/')[-1] if mem_data else 'unknown'
                        }
                
                return info
                
        except Exception as e:
            logger.error(f"Failed to get iDRAC system info: {e}")
            return {'error': str(e)}
    
    def get_hardware_status(self):
        """Get hardware status (temp, fans, power)"""
        try:
            import requests
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            
            # Get thermal status
            response = requests.get(
                f"{self.idrac_url}/redfish/v1/Systems/System.Embedded.1/Thermal",
                auth=(self.credentials['username'], self.credentials['password']),
                verify=False,
                timeout=10
            )
            
            temperatures = []
            if response.status_code == 200:
                data = response.json()
                for sensor in data.get('Temperatures', []):
                    temperatures.append({
                        'name': sensor.get('Name', 'Unknown'),
                        'reading_celsius': sensor.get('ReadingCelsius', 0),
                        'status': sensor.get('Status', {}).get('State', 'Unknown')
                    })
            
            # Get fan status
            response = requests.get(
                f"{self.idrac_url}/redfish/v1/Chassis/System.Embedded.1/Fans",
                auth=(self.credentials['username'], self.credentials['password']),
                verify=False,
                timeout=10
            )
            
            fans = []
            if response.status_code == 200:
                data = response.json()
                for fan in data.get('Members', []):
                    fan_response = requests.get(
                        f"{self.idrac_url}{fan['@odata.id']}",
                        auth=(self.credentials['username'], self.credentials['password']),
                        verify=False,
                        timeout=10
                    )
                    if fan_response.status_code == 200:
                        fans.append({
                            'name': fan.get('Name', 'Unknown'),
                            'reading_rpm': fan.get('Reading', 0),
                            'status': fan.get('Status', {}).get('State', 'Unknown')
                        })
            
            # Get power status
            response = requests.get(
                f"{self.idrac_url}/redfish/v1/Chassis/System.Embedded.1/Power",
                auth=(self.credentials['username'], self.credentials['password']),
                verify=False,
                timeout=10
            )
            
            power_supplies = []
            if response.status_code == 200:
                data = response.json()
                for psu in data.get('Members', []):
                    psu_response = requests.get(
                        f"{self.idrac_url}{psu['@odata.id']}",
                        auth=(self.credentials['username'], self.credentials['password']),
                        verify=False,
                        timeout=10
                    )
                    if psu_response.status_code == 200:
                        power_supplies.append({
                            'name': psu.get('Name', 'Unknown'),
                            'status': psu.get('Status', {}).get('State', 'Unknown'),
                            'power_consumed_watts': psu.get('PowerConsumedWatts', 0)
                        })
            
            return {
                'temperatures': temperatures,
                'fans': fans,
                'power_supplies': power_supplies
            }
            
        except Exception as e:
            logger.error(f"Failed to get hardware status: {e}")
            return {'error': str(e)}
    
    def get_disk_status(self):
        """Get RAID controller and disk status"""
        try:
            import requests
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            
            # Get RAID controllers
            response = requests.get(
                f"{self.idrac_url}/redfish/v1/Systems/System.Embedded.1/Storage",
                auth=(self.credentials['username'], self.credentials['password']),
                verify=False,
                timeout=10
            )
            
            disks = []
            if response.status_code == 200:
                data = response.json()
                for controller in data.get('Members', []):
                    ctrl_response = requests.get(
                        f"{self.idrac_url}{controller['@odata.id']}",
                        auth=(self.credentials['username'], self.credentials['password']),
                        verify=False,
                        timeout=10
                    )
                    if ctrl_response.status_code == 200:
                        ctrl_data = ctrl_response.json()
                        
                        # Get virtual disks
                        for vd in ctrl_data.get('VirtualDisks', []):
                            vd_response = requests.get(
                                f"{self.idrac_url}{vd['@odata.id']}",
                                auth=(self.credentials['username'], self.credentials['password']),
                                verify=False,
                                timeout=10
                            )
                            if vd_response.status_code == 200:
                                vdata = vd_response.json()
                                disks.append({
                                    'type': 'Virtual Disk',
                                    'name': vdata.get('Name', 'Unknown'),
                                    'status': vdata.get('Status', {}).get('State', 'Unknown'),
                                    'capacity_gb': vdata.get('SizeGB', 0),
                                    'raid_level': vdata.get('RAIDType', 'Unknown')
                                })
                        
                        # Get physical disks
                        for pd in ctrl_data.get('Disks', []):
                            pd_response = requests.get(
                                f"{self.idrac_url}{pd['@odata.id']}",
                                auth=(self.credentials['username'], self.credentials['password']),
                                verify=False,
                                timeout=10
                            )
                            if pd_response.status_code == 200:
                                pdata = pd_response.json()
                                disks.append({
                                    'type': 'Physical Disk',
                                    'name': pdata.get('Name', 'Unknown'),
                                    'status': pdata.get('Status', {}).get('State', 'Unknown'),
                                    'capacity_gb': pdata.get('SizeGB', 0),
                                    'media_type': pdata.get('MediaType', 'Unknown')
                                })
            
            return disks
            
        except Exception as e:
            logger.error(f"Failed to get disk status: {e}")
            return {'error': str(e)}

class CiscoNexus(DataCenterDevice):
    """Handler for Cisco Nexus switches with 100Gbps links"""
    
    def __init__(self, ip, username, password, name="Cisco Nexus", **kwargs):
        super().__init__(ip, name, 'cisco_nexus', {'username': username, 'password': password})
        
    def connect(self):
        """Connect via SSH using Netmiko"""
        try:
            from netmiko import ConnectHandler
            
            self.connection = ConnectHandler(
                device_type='cisco_nexus',
                hostname=self.ip,
                username=self.credentials['username'],
                password=self.credentials['password'],
                timeout=30
            )
            
            # Test connection
            self.connection.send_command('show version', expect_string=r'#')
            return True
            
        except Exception as e:
            logger.error(f"Nexus SSH connection failed for {self.ip}: {e}")
            return False
    
    def get_system_info(self):
        """Get system information"""
        try:
            version_output = self.connection.send_command('show version')
            
            info = {
                'model': 'Unknown',
                'serial_number': 'N/A',
                'uptime_seconds': 0,
                'uptime_formatted': 'Unknown',
                'software_version': 'Unknown'
            }
            
            for line in version_output.split('\n'):
                if 'System model' in line:
                    info['model'] = line.split('System model')[1].strip()
                elif 'Serial Number' in line:
                    info['serial_number'] = line.split('Serial Number')[1].strip()
                elif 'Version' in line and 'NXOS' in line:
                    info['software_version'] = line.split('Version')[1].strip()
            
            # Get uptime
            try:
                uptime_output = self.connection.send_command('show system uptime')
                for line in uptime_output.split('\n'):
                    if 'uptime' in line.lower():
                        info['uptime_formatted'] = line.strip().split(':')[-1].strip()
                        break
                
                # Parse seconds from uptime string
                uptime_str = info['uptime_formatted']
                info['uptime_seconds'] = self._parse_uptime(uptime_str)
            except:
                pass
            
            return info
            
        except Exception as e:
            return {'error': str(e)}
    
    def _parse_uptime(self, uptime_str):
        """Parse uptime string to seconds"""
        try:
            total_seconds = 0
            
            days_match = re.search(r'(\d+)\s+days?', uptime_str)
            if days_match:
                total_seconds += int(days_match.group(1)) * 86400
            
            hours_match = re.search(r'(\d+)\s+hours?', uptime_str)
            if hours_match:
                total_seconds += int(hours_match.group(1)) * 3600
            
            mins_match = re.search(r'(\d+)\s+minutes?', uptime_str)
            if mins_match:
                total_seconds += int(mins_match.group(1)) * 60
            
            return total_seconds
        except:
            return 0
    
    def get_interface_status(self):
        """Get interface status including 100Gbps links"""
        try:
            interfaces = self.connection.send_command('show ip interface brief')
            
            parsed_interfaces = []
            lines = interfaces.split('\n')[2:]
            
            for line in lines:
                if line.strip() and not line.startswith('Interface'):
                    parts = line.split()
                    if len(parts) >= 3:
                        interface_name = parts[0]
                        ip_address = parts[1] if parts[1] != 'unassigned' else ''
                        status = parts[2]
                        
                        # Get detailed stats for this interface
                        try:
                            detail_output = self.connection.send_command(f'show interfaces {interface_name}')
                            
                            rx_bytes = 0
                            tx_bytes = 0
                            rx_errors = 0
                            tx_errors = 0
                            
                            for detail_line in detail_output.split('\n'):
                                if 'input bytes' in detail_line.lower():
                                    match = re.search(r'(\d+)', detail_line)
                                    if match:
                                        rx_bytes = int(match.group(1))
                                elif 'output bytes' in detail_line.lower():
                                    match = re.search(r'(\d+)', detail_line)
                                    if match:
                                        tx_bytes = int(match.group(1))
                                elif 'input errors' in detail_line.lower():
                                    match = re.search(r'(\d+)', detail_line)
                                    if match:
                                        rx_errors = int(match.group(1))
                                elif 'output errors' in detail_line.lower():
                                    match = re.search(r'(\d+)', detail_line)
                                    if match:
                                        tx_errors = int(match.group(1))
                            
                            # Check for 100Gbps links
                            speed = 'Unknown'
                            if '100000 Mbps' in detail_output or '100 Gbps' in detail_output:
                                speed = '100 Gbps'
                            elif '40000 Mbps' in detail_output:
                                speed = '40 Gbps'
                            elif '25000 Mbps' in detail_output:
                                speed = '25 Gbps'
                            
                            parsed_interfaces.append({
                                'interface': interface_name,
                                'ip_address': ip_address,
                                'status': status,
                                'speed': speed,
                                'rx_bytes': rx_bytes,
                                'tx_bytes': tx_bytes,
                                'rx_errors': rx_errors,
                                'tx_errors': tx_errors
                            })
                        except:
                            parsed_interfaces.append({
                                'interface': interface_name,
                                'ip_address': ip_address,
                                'status': status,
                                'speed': 'Unknown',
                                'rx_bytes': 0,
                                'tx_bytes': 0,
                                'rx_errors': 0,
                                'tx_errors': 0
                            })
            
            return {
                'interfaces': parsed_interfaces,
                'count': len(parsed_interfaces)
            }
        except Exception as e:
            return {'error': str(e)}

class Cisco3750X(DataCenterDevice):
    """Handler for Cisco 3750X switches"""
    
    def __init__(self, ip, username, password, name="Cisco 3750X", **kwargs):
        super().__init__(ip, name, 'cisco_3750x', {'username': username, 'password': password})
        
    def connect(self):
        """Connect via SSH"""
        try:
            from netmiko import ConnectHandler
            
            self.connection = ConnectHandler(
                device_type='cisco_ios',
                hostname=self.ip,
                username=self.credentials['username'],
                password=self.credentials['password'],
                timeout=30
            )
            
            # Test connection
            self.connection.send_command('show version', expect_string=r'#')
            return True
            
        except Exception as e:
            logger.error(f"3750X SSH connection failed for {self.ip}: {e}")
            return False
    
    def get_system_info(self):
        """Get system information"""
        try:
            version_output = self.connection.send_command('show version')
            
            info = {
                'model': 'Unknown',
                'serial_number': 'N/A',
                'uptime_seconds': 0,
                'uptime_formatted': 'Unknown'
            }
            
            for line in version_output.split('\n'):
                if 'Processor board ID' in line:
                    info['serial_number'] = line.split('Processor board ID')[1].strip()
                elif 'Cisco IOS Software' in line:
                    pass  # Extract model from different field
            
            try:
                uptime_output = self.connection.send_command('show version | include Uptime')
                for line in uptime_output.split('\n'):
                    if 'Uptime' in line:
                        info['uptime_formatted'] = line.strip()
                        break
            except:
                pass
            
            return info
            
        except Exception as e:
            return {'error': str(e)}

class CiscoRouter(DataCenterDevice):
    """Handler for Cisco routers"""
    
    def __init__(self, ip, username, password, name="Cisco Router", **kwargs):
        super().__init__(ip, name, 'cisco_router', {'username': username, 'password': password})
        
    def connect(self):
        """Connect via SSH"""
        try:
            from netmiko import ConnectHandler
            
            self.connection = ConnectHandler(
                device_type='cisco_ios',
                hostname=self.ip,
                username=self.credentials['username'],
                password=self.credentials['password'],
                timeout=30
            )
            
            # Test connection
            self.connection.send_command('show version', expect_string=r'#')
            return True
            
        except Exception as e:
            logger.error(f"Router SSH connection failed for {self.ip}: {e}")
            return False
    
    def get_routing_info(self):
        """Get routing table information"""
        try:
            routes = self.connection.send_command('show ip route')
            
            # Parse routing table
            parsed_routes = []
            lines = routes.split('\n')[1:]  # Skip header
            
            for line in lines:
                if line.strip() and not line.startswith('Routing Table'):
                    parts = line.split()
                    if len(parts) >= 3:
                        network = parts[0]
                        gateway = parts[-2] if len(parts) > 1 else 'N/A'
                        
                        parsed_routes.append({
                            'network': network,
                            'gateway': gateway,
                            'type': parts[1] if len(parts) > 1 else 'Unknown'
                        })
            
            return {
                'routes': parsed_routes,
                'count': len(parsed_routes)
            }
        except Exception as e:
            return {'error': str(e)}

# ==================== MONITORING SYSTEMS ====================

class SNMPMonitor:
    """SNMP monitoring for various devices"""
    
    def __init__(self, ip, community='public', version=1):
        self.ip = ip
        self.community = community
        self.version = version
        try:
            from pysnmp.hlapi import *
            self.snmp_client = True
        except ImportError:
            logger.error("pysnmp not installed")
            self.snmp_client = False
    
    def get_oid(self, oid):
        """Get OID value via SNMP"""
        if not self.snmp_client:
            return None
        
        try:
            from pysnmp.hlapi import *
            
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(SnmpEngine(),
                       CommunityData(self.community),
                       UdpTransportTarget((self.ip, 161)),
                       ContextData(),
                       ObjectType(ObjectIdentity(oid)),
                       maxRepetitions=5)
            )
            
            if errorIndication:
                logger.error(f"SNMP Error for {self.ip}: {errorIndication}")
                return None
            
            result = {}
            for varBind in varBinds:
                obj_id = str(varBind[0])
                value = str(varBind[1])
                
                # Parse specific OIDs
                if 'temperature' in oid.lower() or '.1.3.6.1.4.1.2021.13.16.' in oid:
                    result['temperature_celsius'] = float(value)
                elif 'fan' in oid.lower():
                    result['fan_rpm'] = int(value)
                
            return result
            
        except Exception as e:
            logger.error(f"SNMP error for {self.ip}: {e}")
            return None

class TrueNASStorage(DataCenterDevice):
    """Handler for TrueNAS storage systems"""
    
    def __init__(self, ip, username, password, name="TrueNAS Storage", **kwargs):
        super().__init__(ip, name, 'truenas', {'username': username, 'password': password})
        
    def connect(self):
        """Connect via SSH/API"""
        try:
            from netmiko import ConnectHandler
            
            self.connection = ConnectHandler(
                device_type='cisco_ios',  # FreeBSD-based, use generic IOS
                hostname=self.ip,
                username=self.credentials['username'],
                password=self.credentials['password'],
                timeout=30
            )
            return True
            
        except Exception as e:
            logger.error(f"TrueNAS SSH connection failed for {self.ip}: {e}")
            return False
    
    def get_storage_status(self):
        """Get storage pool and disk status"""
        try:
            # Get pool information (ZFS)
            pools_output = self.connection.send_command('zpool list')
            
            pools = []
            for line in pools_output.split('\n')[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        pools.append({
                            'name': parts[0],
                            'status': parts[2],
                            'size_tb': float(parts[4].rstrip('T')) if len(parts) > 4 else 0,
                            'used_tb': float(parts[5].rstrip('T')) if len(parts) > 5 else 0
                        })
            
            # Get disk status
            disks_output = self.connection.send_command('zpool status')
            
            disks = []
            for line in disks_output.split('\n'):
                if 'ONLINE' in line:
                    match = re.search(r'(\S+)\s+ONLINE', line)
                    if match:
                        disks.append({
                            'disk': match.group(1),
                            'status': 'ONLINE'
                        })
            
            return {
                'pools': pools,
                'disks': disks
            }
        except Exception as e:
            return {'error': str(e)}

class OpenEDSSStorage(DataCenterDevice):
    """Handler for Open-E JovianDSS storage"""
    
    def __init__(self, ip, username, password, name="Open-E DSS", **kwargs):
        super().__init__(ip, name, 'open_e_dss', {'username': username, 'password': password})
        
    def connect(self):
        """Connect via REST API"""
        try:
            import requests
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            
            response = requests.get(
                f"https://{self.ip}/api/v1/system",
                auth=(self.credentials['username'], self.credentials['password']),
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            
        except Exception as e:
            logger.error(f"Open-E DSS connection failed for {self.ip}: {e}")
            return False
    
    def get_storage_status(self):
        """Get storage status"""
        try:
            import requests
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            
            response = requests.get(
                f"https://{self.ip}/api/v1/storage",
                auth=(self.credentials['username'], self.credentials['password']),
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                volumes = []
                for vol in data.get('volumes', []):
                    volumes.append({
                        'name': vol.get('name', 'Unknown'),
                        'size_gb': vol.get('size', 0),
                        'used_gb': vol.get('used', 0),
                        'status': vol.get('status', 'unknown')
                    })
                
                return {'volumes': volumes}
            
        except Exception as e:
            logger.error(f"Failed to get Open-E storage status: {e}")
            return {'error': str(e)}

# ==================== FLASK ROUTES ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    """Main dashboard"""
    return render_template('index.html')

@app.route('/api/add-device', methods=['POST'])
@login_required
def add_device():
    """Add a new device to inventory"""
    data = request.json
    
    if not all([data.get('ip'), data.get('name'), data.get('device_type')]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Create appropriate device handler based on type
    credentials = {
        'username': data.get('username', ''),
        'password': data.get('password', '')
    } if 'credentials' in data else {}
    
    try:
        if data['device_type'] == 'dell_idrac':
            device = DellIDRAC(
                ip=data['ip'],
                username=credentials['username'],
                password=credentials['password'],
                name=data.get('name', 'Dell Server')
            )
        elif data['device_type'] == 'cisco_nexus':
            device = CiscoNexus(
                ip=data['ip'],
                username=credentials['username'],
                password=credentials['password'],
                name=data.get('name', 'Cisco Nexus')
            )
        elif data['device_type'] == 'cisco_3750x':
            device = Cisco3750X(
                ip=data['ip'],
                username=credentials['username'],
                password=credentials['password'],
                name=data.get('name', 'Cisco 3750X')
            )
        elif data['device_type'] == 'cisco_router':
            device = CiscoRouter(
                ip=data['ip'],
                username=credentials['username'],
                password=credentials['password'],
                name=data.get('name', 'Cisco Router')
            )
        elif data['device_type'] == 'truenas':
            device = TrueNASStorage(
                ip=data['ip'],
                username=credentials['username'],
                password=credentials['password'],
                name=data.get('name', 'TrueNAS Storage')
            )
        elif data['device_type'] == 'open_e_dss':
            device = OpenEDSSStorage(
                ip=data['ip'],
                username=credentials['username'],
                password=credentials['password'],
                name=data.get('name', 'Open-E DSS')
            )
        else:
            return jsonify({'error': f'Unknown device type: {data["device_type"]}'}), 400
        
        if device.connect():
            datacenter_inventory[data['ip']] = {
                'device': device,
                'added_at': datetime.now().isoformat()
            }
            return jsonify({
                'success': True, 
                'message': f'Device {data["name"]} ({data["ip"]}) added successfully'
            })
        else:
            return jsonify({'error': f'Failed to connect to {data["ip"]}'}), 400
            
    except Exception as e:
        logger.error(f"Error adding device: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices')
@login_required
def list_devices():
    """List all devices"""
    return jsonify({
        'devices': [
            {
                'ip': ip,
                'name': data['device'].name,
                'type': data['device'].device_type,
                'added_at': data['added_at'],
                'status': 'connected' if data['device'].connection else 'disconnected'
            }
            for ip, data in datacenter_inventory.items()
        ]
    })

@app.route('/api/<ip>/system-info')
@login_required
def get_system_info(ip):
    """Get system information"""
    if ip not in datacenter_inventory:
        return jsonify({'error': 'Device not found'}), 404
    
    device = datacenter_inventory[ip]['device']
    
    if hasattr(device, 'get_system_info'):
        info = device.get_system_info()
        return jsonify(info)
    
    return jsonify(device.get_status())

@app.route('/api/<ip>/hardware-status')
@login_required
def get_hardware_status(ip):
    """Get hardware status"""
    if ip not in datacenter_inventory:
        return jsonify({'error': 'Device not found'}), 404
    
    device = datacenter_inventory[ip]['device']
    
    if hasattr(device, 'get_hardware_status'):
        status = device.get_hardware_status()
        
        # Export to CSV for download
        output_csv = []
        output_csv.append(['TYPE', 'NAME', 'STATUS', 'READING'])
        
        if isinstance(status, dict):
            if 'temperatures' in status:
                for temp in status['temperatures']:
                    output_csv.append(['TEMPERATURE', temp.get('name'), temp.get('status'), f"{temp.get('reading_celsius')}°C"])
            
            if 'fans' in status:
                for fan in status['fans']:
                    output_csv.append(['FAN', fan.get('name'), fan.get('status'), f"{fan.get('reading_rpm')} RPM"])
            
            if 'power_supplies' in status:
                for psu in status['power_supplies']:
                    output_csv.append(['POWER_SUPPLY', psu.get('name'), psu.get('status'), f"{psu.get('power_consumed_watts')}W"])
        
        # Write CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(output_csv)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'hardware_{ip}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    return jsonify({'error': 'Hardware status not available'})

@app.route('/api/<ip>/interface-status')
@login_required
def get_interface_status(ip):
    """Get interface status"""
    if ip not in datacenter_inventory:
        return jsonify({'error': 'Device not found'}), 404
    
    device = datacenter_inventory[ip]['device']
    
    if hasattr(device, 'get_interface_status'):
        interfaces = device.get_interface_status()
        
        # Export to CSV
        output_csv = []
        output_csv.append(['INTERFACE', 'IP_ADDRESS', 'STATUS', 'SPEED', 'RX_BYTES', 'TX_BYTES'])
        
        if 'interfaces' in interfaces:
            for iface in interfaces['interfaces']:
                output_csv.append([
                    iface.get('interface'),
                    iface.get('ip_address'),
                    iface.get('status'),
                    iface.get('speed'),
                    iface.get('rx_bytes'),
                    iface.get('tx_bytes')
                ])
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(output_csv)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'interfaces_{ip}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    return jsonify({'error': 'Interface status not available'})

@app.route('/api/<ip>/storage-status')
@login_required
def get_storage_status(ip):
    """Get storage system status"""
    if ip not in datacenter_inventory:
        return jsonify({'error': 'Device not found'}), 404
    
    device = datacenter_inventory[ip]['device']
    
    if hasattr(device, 'get_storage_status'):
        storage = device.get_storage_status()
        
        # Export to CSV
        output_csv = []
        output_csv.append(['TYPE', 'NAME', 'STATUS', 'SIZE_GB'])
        
        if isinstance(storage, dict):
            if 'pools' in storage:
                for pool in storage['pools']:
                    output_csv.append(['ZFS_POOL', pool.get('name'), pool.get('status'), f"{pool.get('size_tb')}TB"])
            
            if 'volumes' in storage:
                for vol in storage['volumes']:
                    output_csv.append(['VOLUME', vol.get('name'), vol.get('status'), vol.get('size_gb')])
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(output_csv)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'storage_{ip}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    return jsonify({'error': 'Storage status not available'})

@app.route('/api/<ip>/disks')
@login_required
def get_disk_status(ip):
    """Get disk/RAID status (Dell iDRAC)"""
    if ip not in datacenter_inventory:
        return jsonify({'error': 'Device not found'}), 404
    
    device = datacenter_inventory[ip]['device']
    
    if hasattr(device, 'get_disk_status'):
        disks = device.get_disk_status()
        
        # Export to CSV
        output_csv = []
        output_csv.append(['TYPE', 'NAME', 'STATUS', 'CAPACITY_GB'])
        
        if isinstance(disks, list):
            for disk in disks:
                output_csv.append([
                    disk.get('type'),
                    disk.get('name'),
                    disk.get('status'),
                    disk.get('capacity_gb')
                ])
        elif isinstance(disks, dict) and 'error' not in disks:
            for item in disks:
                output_csv.append([
                    item.get('type', 'Unknown'),
                    item.get('name', 'Unknown'),
                    item.get('status', 'Unknown'),
                    item.get('capacity_gb', 0)
                ])
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(output_csv)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'disks_{ip}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    return jsonify({'error': 'Disk status not available'})

@app.route('/api/<ip>/routing-info')
@login_required
def get_routing_info(ip):
    """Get routing table info (Cisco routers)"""
    if ip not in datacenter_inventory:
        return jsonify({'error': 'Device not found'}), 404
    
    device = datacenter_inventory[ip]['device']
    
    if hasattr(device, 'get_routing_info'):
        routes = device.get_routing_info()
        
        # Export to CSV
        output_csv = []
        output_csv.append(['NETWORK', 'GATEWAY', 'TYPE'])
        
        if 'routes' in routes:
            for route in routes['routes']:
                output_csv.append([
                    route.get('network'),
                    route.get('gateway'),
                    route.get('type')
                ])
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(output_csv)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'routing_{ip}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    return jsonify({'error': 'Routing info not available'})

@app.route('/api/<ip>/disconnect')
@login_required
def disconnect_device(ip):
    """Disconnect from device"""
    if ip not in datacenter_inventory:
        return jsonify({'error': 'Device not found'}), 404
    
    datacenter_inventory[ip]['device'].disconnect()
    del datacenter_inventory[ip]
    
    return jsonify({'success': True, 'message': f'Disconnected from {ip}'})

@app.route('/api/<ip>/refresh')
@login_required
def refresh_device_data(ip):
    """Refresh all data for a device"""
    if ip not in datacenter_inventory:
        return jsonify({'error': 'Device not found'}), 404
    
    device = datacenter_inventory[ip]['device']
    
    # Reconnect if needed
    if not device.connection or not device.connect():
        return jsonify({'error': f'Failed to connect to {ip}'}), 400
    
    result = {'status': 'connected', 'timestamp': datetime.now().isoformat()}
    
    if hasattr(device, 'get_system_info'):
        result['system_info'] = device.get_system_info()
    
    if hasattr(device, 'get_hardware_status'):
        result['hardware_status'] = device.get_hardware_status()
    
    return jsonify(result)

# Simple login system for demonstration
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # In production, use proper authentication!
        if username and password:  # Placeholder auth
            session['user'] = username
            return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5003)
