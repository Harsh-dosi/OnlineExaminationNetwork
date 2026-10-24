import ipaddress

def parse_subnet_input(ip_str, prefix_or_mask_str):
    """
    Parse and validate user IPv4 address and CIDR prefix / subnet mask.
    Returns a dictionary of comprehensive subnet details or raises ValueError.
    """
    ip_str = (ip_str or '').strip()
    prefix_or_mask_str = (prefix_or_mask_str or '').strip()

    if not ip_str:
        raise ValueError("IPv4 address cannot be empty.")
        
    try:
        ip_obj = ipaddress.IPv4Address(ip_str)
    except ipaddress.AddressValueError:
        raise ValueError(f"'{ip_str}' is not a valid IPv4 address (must be 4 octets between 0 and 255).")

    # Determine prefix length
    if not prefix_or_mask_str:
        prefix_len = 24  # Default fallback
    elif prefix_or_mask_str.startswith('/'):
        try:
            prefix_len = int(prefix_or_mask_str[1:])
        except ValueError:
            raise ValueError(f"Invalid CIDR prefix: '{prefix_or_mask_str}'")
    elif prefix_or_mask_str.isdigit():
        prefix_len = int(prefix_or_mask_str)
    else:
        # Check if it's a dotted decimal subnet mask like 255.255.255.0
        try:
            mask_obj = ipaddress.IPv4Address(prefix_or_mask_str)
            mask_int = int(mask_obj)
            # Verify contiguous 1s followed by 0s
            binary_str = f"{mask_int:032b}"
            if '01' in binary_str:
                raise ValueError(f"Subnet mask '{prefix_or_mask_str}' is non-contiguous.")
            prefix_len = binary_str.count('1')
        except ipaddress.AddressValueError:
            raise ValueError(f"Invalid subnet mask or prefix: '{prefix_or_mask_str}'")

    if not (0 <= prefix_len <= 32):
        raise ValueError("Prefix length must be between 0 and 32.")

    # Build IPv4Network object (strict=False allows calculating network from a host IP)
    network_obj = ipaddress.IPv4Network(f"{ip_str}/{prefix_len}", strict=False)
    
    total_addresses = network_obj.num_addresses
    
    # Calculate usable host count and range
    if prefix_len == 32:
        # Single host route
        usable_hosts = 1
        first_usable = str(network_obj.network_address)
        last_usable = str(network_obj.network_address)
        broadcast_address = "N/A (Host Route /32)"
        note = "/32 represents a single host route. Network and host are identical."
    elif prefix_len == 31:
        # RFC 3021 Point-to-Point links
        usable_hosts = 2
        first_usable = str(network_obj.network_address)
        last_usable = str(network_obj.broadcast_address)
        broadcast_address = "None (RFC 3021 Point-to-Point)"
        note = "/31 is used for point-to-point links (RFC 3021). Both addresses are usable."
    else:
        usable_hosts = max(0, total_addresses - 2)
        first_usable = str(network_obj.network_address + 1)
        last_usable = str(network_obj.broadcast_address - 1)
        broadcast_address = str(network_obj.broadcast_address)
        note = "Standard subnetting: First address is Network ID; last address is Broadcast."

    # Binary representations for academic analysis
    ip_bin = ".".join(f"{int(octet):08b}" for octet in ip_str.split("."))
    mask_bin = ".".join(f"{int(octet):08b}" for octet in str(network_obj.netmask).split("."))
    net_bin = ".".join(f"{int(octet):08b}" for octet in str(network_obj.network_address).split("."))

    # Address Class Classification
    first_octet = int(ip_str.split(".")[0])
    if 1 <= first_octet <= 126:
        ip_class = "Class A"
        default_mask = "255.0.0.0 (/8)"
    elif first_octet == 127:
        ip_class = "Loopback (127.0.0.0/8)"
        default_mask = "255.0.0.0 (/8)"
    elif 128 <= first_octet <= 191:
        ip_class = "Class B"
        default_mask = "255.255.0.0 (/16)"
    elif 192 <= first_octet <= 223:
        ip_class = "Class C"
        default_mask = "255.255.255.0 (/24)"
    elif 224 <= first_octet <= 239:
        ip_class = "Class D (Multicast)"
        default_mask = "N/A"
    else:
        ip_class = "Class E (Experimental)"
        default_mask = "N/A"

    is_private = ip_obj.is_private
    address_scope = "Private (RFC 1918 / Local)" if is_private else "Public (Internet Routable)"
    if ip_obj.is_loopback:
        address_scope = "Loopback (Host Internal)"

    wildcard_mask = str(ipaddress.IPv4Address(int(network_obj.hostmask)))

    return {
        "input_ip": ip_str,
        "input_prefix": prefix_len,
        "network_address": str(network_obj.network_address),
        "subnet_mask": str(network_obj.netmask),
        "wildcard_mask": wildcard_mask,
        "broadcast_address": broadcast_address,
        "first_usable": first_usable,
        "last_usable": last_usable,
        "total_addresses": total_addresses,
        "usable_hosts": usable_hosts,
        "prefix_length": f"/{prefix_len}",
        "ip_class": ip_class,
        "default_mask": default_mask,
        "address_scope": address_scope,
        "ip_binary": ip_bin,
        "mask_binary": mask_bin,
        "net_binary": net_bin,
        "note": note,
        "is_valid": True
    }

def get_sample_exam_network_plan():
    """
    Returns the documented reference network plan for the Examination Network.
    Subnet: 192.168.10.0/24 (Class C, Private RFC 1918)
    """
    return {
        "network_cidr": "192.168.10.0/24",
        "subnet_mask": "255.255.255.0",
        "gateway": "192.168.10.1 (Router / Default Gateway)",
        "dns_server": "192.168.10.10 (Simulated DNS Resolver / exam.local)",
        "exam_server_static": "192.168.10.50 (Online Examination Server Web Host)",
        "dhcp_pool_range": "192.168.10.100 - 192.168.10.150 (Dynamic Client IP Pool)",
        "broadcast_address": "192.168.10.255",
        "total_hosts": 254,
        "purpose": "Classroom isolated local exam subnet without requiring cloud or internet routes."
    }
