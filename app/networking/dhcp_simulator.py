import datetime
import ipaddress
import re

class DHCPSimulator:
    """
    Academic DHCP Simulation Engine.
    Simulates the standard 4-step DORA (Discover, Offer, Request, Acknowledge) process.
    Operates over a defined address pool without binding real UDP ports 67/68 or altering host network adapters.
    """
    def __init__(self, pool_start='192.168.10.100', pool_end='192.168.10.115', 
                 subnet_mask='255.255.255.0', gateway='192.168.10.1', 
                 dns_server='192.168.10.10', lease_duration_seconds=3600):
        self.pool_start = ipaddress.IPv4Address(pool_start)
        self.pool_end = ipaddress.IPv4Address(pool_end)
        self.subnet_mask = subnet_mask
        self.gateway = gateway
        self.dns_server = dns_server
        self.lease_duration_seconds = lease_duration_seconds
        
        # Build list of all pool IPs
        start_int = int(self.pool_start)
        end_int = int(self.pool_end)
        if start_int > end_int:
            raise ValueError("DHCP pool start must be less than or equal to pool end.")
        self.all_pool_ips = [str(ipaddress.IPv4Address(i)) for i in range(start_int, end_int + 1)]

    @staticmethod
    def validate_mac(mac):
        """Validates standard MAC address formats (e.g., 00:1A:2B:3C:4D:5E or 00-1A-2B-3C-4D-5E)."""
        mac = (mac or '').strip().upper()
        if re.match(r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", mac):
            return mac.replace("-", ":")
        return None

    def get_pool_status(self, db):
        """
        Calculates current pool status by checking active leases in database.
        Returns total, leased, available counts, and lease dictionaries.
        """
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Expire old active leases if past lease_end
        db.execute(
            "UPDATE dhcp_leases SET status = 'expired' WHERE status = 'active' AND lease_end < ?",
            (now,)
        )
        db.commit()

        # Query all leases
        rows = db.execute("SELECT * FROM dhcp_leases ORDER BY lease_start DESC").fetchall()
        leases = [dict(r) for r in rows]

        active_leased_ips = {r['ip_address'] for r in leases if r['status'] == 'active'}
        available_ips = [ip for ip in self.all_pool_ips if ip not in active_leased_ips]

        return {
            "total_pool_capacity": len(self.all_pool_ips),
            "pool_range": f"{self.pool_start} - {self.pool_end}",
            "leased_count": len(active_leased_ips),
            "available_count": len(available_ips),
            "available_ips": available_ips,
            "leases": leases
        }

    def simulate_dora_lease(self, db, mac_address, hostname):
        """
        Simulates the full 4-step DHCP DORA handshake:
        1. DHCP DISCOVER (Client Broadcast, UDP src:68 dst:67)
        2. DHCP OFFER    (Server Unicast/Broadcast, UDP src:67 dst:68)
        3. DHCP REQUEST  (Client Broadcast confirming chosen IP)
        4. DHCP ACK      (Server confirms lease and network parameters)
        """
        cleaned_mac = self.validate_mac(mac_address)
        if not cleaned_mac:
            raise ValueError(f"Invalid MAC address format '{mac_address}'. Use XX:XX:XX:XX:XX:XX format.")

        hostname = (hostname or 'student-workstation').strip()
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        lease_end_dt = now + datetime.timedelta(seconds=self.lease_duration_seconds)
        lease_end_str = lease_end_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Check if client already holds an active lease
        existing = db.execute(
            "SELECT * FROM dhcp_leases WHERE mac_address = ? AND status = 'active'",
            (cleaned_mac,)
        ) .fetchone()

        if existing:
            assigned_ip = existing['ip_address']
            is_renewal = True
            # Update renewal time
            db.execute(
                "UPDATE dhcp_leases SET lease_start = ?, lease_end = ?, hostname = ? WHERE id = ?",
                (now_str, lease_end_str, hostname, existing['id'])
            )
            db.commit()
        else:
            is_renewal = False
            # Find first free IP from pool
            pool_status = self.get_pool_status(db)
            available = pool_status['available_ips']
            if not available:
                raise ValueError("DHCP Pool Exhausted: No simulated IP addresses available in pool range.")

            assigned_ip = available[0]
            # Reuse an inactive row because the database requires each IP to be unique.
            inactive = db.execute(
                "SELECT id FROM dhcp_leases WHERE ip_address = ? AND status != 'active' LIMIT 1",
                (assigned_ip,)
            ).fetchone()

            if inactive:
                db.execute(
                    """UPDATE dhcp_leases
                       SET mac_address = ?, hostname = ?, subnet_mask = ?, gateway = ?,
                           dns_server = ?, lease_start = ?, lease_end = ?, status = 'active'
                       WHERE id = ?""",
                    (cleaned_mac, hostname, self.subnet_mask, self.gateway,
                     self.dns_server, now_str, lease_end_str, inactive["id"])
                )
            else:
                db.execute(
                    """INSERT INTO dhcp_leases
                       (mac_address, hostname, ip_address, subnet_mask, gateway, dns_server, lease_start, lease_end, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (cleaned_mac, hostname, assigned_ip, self.subnet_mask,
                     self.gateway, self.dns_server, now_str, lease_end_str)
                )
            db.commit()

        # Generate DORA packet simulation details for academic inspection
        dora_trace = [
            {
                "step": "1. DHCP DISCOVER",
                "sender": f"Client ({cleaned_mac})",
                "receiver": "Broadcast (255.255.255.255)",
                "layer4": "UDP Src: 68 -> Dst: 67",
                "message": f"Client '{hostname}' broadcasts a discovery message requesting an IPv4 configuration."
            },
            {
                "step": "2. DHCP OFFER",
                "sender": f"DHCP Server ({self.gateway})",
                "receiver": f"Client ({cleaned_mac})",
                "layer4": "UDP Src: 67 -> Dst: 68",
                "message": f"Server offers IP {assigned_ip}, Subnet {self.subnet_mask}, Gateway {self.gateway}, DNS {self.dns_server} with lease duration {self.lease_duration_seconds}s."
            },
            {
                "step": "3. DHCP REQUEST",
                "sender": f"Client ({cleaned_mac})",
                "receiver": "Broadcast (255.255.255.255)",
                "layer4": "UDP Src: 68 -> Dst: 67",
                "message": f"Client accepts offer and formally requests IP {assigned_ip}."
            },
            {
                "step": "4. DHCP ACKNOWLEDGMENT (ACK)",
                "sender": f"DHCP Server ({self.gateway})",
                "receiver": f"Client ({cleaned_mac})",
                "layer4": "UDP Src: 67 -> Dst: 68",
                "message": f"Server commits lease for {assigned_ip} to {cleaned_mac} until {lease_end_str}."
            }
        ]

        return {
            "success": True,
            "mac_address": cleaned_mac,
            "hostname": hostname,
            "assigned_ip": assigned_ip,
            "subnet_mask": self.subnet_mask,
            "gateway": self.gateway,
            "dns_server": self.dns_server,
            "lease_start": now_str,
            "lease_end": lease_end_str,
            "is_renewal": is_renewal,
            "dora_trace": dora_trace
        }

    def release_lease(self, db, mac_address):
        """
        Simulates DHCP RELEASE message (Client sends unicast to Server UDP 67 releasing IP).
        """
        cleaned_mac = self.validate_mac(mac_address)
        if not cleaned_mac:
            raise ValueError("Invalid MAC address.")

        existing = db.execute(
            "SELECT * FROM dhcp_leases WHERE mac_address = ? AND status = 'active'",
            (cleaned_mac,)
        ).fetchone()

        if not existing:
            raise ValueError(f"No active lease found for MAC {cleaned_mac}.")

        db.execute(
            "UPDATE dhcp_leases SET status = 'released' WHERE id = ?",
            (existing['id'],)
        )
        db.commit()

        return {
            "success": True,
            "mac_address": cleaned_mac,
            "released_ip": existing['ip_address'],
            "message": f"Lease for IP {existing['ip_address']} successfully released back to DHCP pool."
        }
