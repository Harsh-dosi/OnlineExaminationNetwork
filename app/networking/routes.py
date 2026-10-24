from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from app.models.db import get_db, log_network_event
from app.auth.routes import login_required, admin_required, verify_csrf_token, generate_csrf_token
from app.networking.subnet import parse_subnet_input, get_sample_exam_network_plan
from app.networking.dhcp_simulator import DHCPSimulator
from app.networking.dns_simulator import DNSSimulator
from app.networking.monitoring import get_server_network_interfaces, get_application_health, get_recent_event_logs, get_event_statistics
from app.networking.performance import run_http_benchmark, record_benchmark_result, get_performance_history

bp = Blueprint('networking', __name__, url_prefix='/network')

# Initialize simulators with app config defaults
def get_dhcp_sim():
    cfg = current_app.config
    return DHCPSimulator(
        pool_start=cfg.get('DHCP_POOL_START', '192.168.10.100'),
        pool_end=cfg.get('DHCP_POOL_END', '192.168.10.120'),
        subnet_mask='255.255.255.0',
        gateway=cfg.get('DHCP_GATEWAY', '192.168.10.1'),
        dns_server=cfg.get('DHCP_DNS_SERVER', '192.168.10.10'),
        lease_duration_seconds=cfg.get('DHCP_DEFAULT_LEASE_TIME', 3600)
    )

def get_dns_sim():
    return DNSSimulator(default_ttl=current_app.config.get('DNS_DEFAULT_TTL', 300))

# ----------------- MONITORING DASHBOARD -----------------
@bp.route('/')
@bp.route('/dashboard')
def dashboard():
    """Network Monitoring and Server Status Dashboard."""
    db = get_db()
    health = get_application_health(db, port=current_app.config['PORT'])
    stats = get_event_statistics(db)
    recent_logs = get_recent_event_logs(db, limit=30)
    sample_plan = get_sample_exam_network_plan()
    
    return render_template(
        'network_dashboard.html',
        health=health,
        stats=stats,
        recent_logs=recent_logs,
        sample_plan=sample_plan
    )

# ----------------- SUBNET CALCULATOR -----------------
@bp.route('/subnet', methods=['GET', 'POST'])
def subnet_calculator():
    """Interactive IPv4 Subnet Calculator."""
    result = None
    error = None
    sample_plan = get_sample_exam_network_plan()

    ip_input = request.form.get('ip_address', '192.168.10.50') if request.method == 'POST' else '192.168.10.50'
    prefix_input = request.form.get('prefix_or_mask', '24') if request.method == 'POST' else '24'

    if request.method == 'POST':
        try:
            result = parse_subnet_input(ip_input, prefix_input)
            log_network_event(
                "SUBNET_CALC",
                request.remote_addr,
                f"Calculated subnet for IP {ip_input} Prefix {prefix_input}",
                200
            )
        except ValueError as ex:
            error = str(ex)

    return render_template(
        'subnet_calculator.html',
        result=result,
        error=error,
        ip_input=ip_input,
        prefix_input=prefix_input,
        sample_plan=sample_plan,
        csrf_token=generate_csrf_token()
    )

@bp.route('/api/subnet/calculate', methods=['POST'])
def api_subnet_calculate():
    """JSON API endpoint for programmatic subnet calculation."""
    data = request.get_json(silent=True) or request.form
    ip = data.get('ip_address', '')
    prefix = data.get('prefix_or_mask', '')
    try:
        res = parse_subnet_input(ip, prefix)
        return jsonify({"success": True, "data": res}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ----------------- DHCP SIMULATION -----------------
@bp.route('/dhcp', methods=['GET', 'POST'])
def dhcp_demo():
    """DHCP DORA Simulation Management and Demonstration Interface."""
    db = get_db()
    dhcp = get_dhcp_sim()
    status = dhcp.get_pool_status(db)
    dora_result = None
    error = None

    if request.method == 'POST':
        action = request.form.get('action')
        mac = request.form.get('mac_address', '').strip()
        hostname = request.form.get('hostname', '').strip()

        if action == 'request':
            try:
                dora_result = dhcp.simulate_dora_lease(db, mac, hostname)
                log_network_event(
                    "DHCP_SIM",
                    request.remote_addr,
                    f"DHCP DORA completed: Allocated {dora_result['assigned_ip']} to MAC {dora_result['mac_address']} ({hostname})",
                    200
                )
                flash(f"DHCP Lease successfully allocated: {dora_result['assigned_ip']}", "success")
            except ValueError as ex:
                error = str(ex)
                log_network_event("DHCP_SIM_FAIL", request.remote_addr, f"DHCP allocation failed: {ex}", 400)
                flash(error, "danger")

        elif action == 'release':
            try:
                rel = dhcp.release_lease(db, mac)
                log_network_event(
                    "DHCP_SIM",
                    request.remote_addr,
                    f"DHCP Release: {rel['released_ip']} released by MAC {rel['mac_address']}",
                    200
                )
                flash(rel['message'], "info")
            except ValueError as ex:
                error = str(ex)
                flash(error, "danger")

        # Refresh pool status after action
        status = dhcp.get_pool_status(db)

    return render_template(
        'dhcp_demo.html',
        status=status,
        dora_result=dora_result,
        error=error,
        csrf_token=generate_csrf_token()
    )

@bp.route('/api/dhcp/lease', methods=['POST'])
def api_dhcp_lease():
    """JSON API to request a simulated DHCP lease."""
    data = request.get_json(silent=True) or request.form
    mac = data.get('mac_address', '')
    hostname = data.get('hostname', 'client-device')
    db = get_db()
    dhcp = get_dhcp_sim()
    try:
        res = dhcp.simulate_dora_lease(db, mac, hostname)
        return jsonify({"success": True, "lease": res}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ----------------- DNS SIMULATION -----------------
@bp.route('/dns', methods=['GET', 'POST'])
def dns_demo():
    """DNS Simulation Interface with Zone Management and Cache Inspection."""
    db = get_db()
    dns = get_dns_sim()
    query_result = None
    error = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'query':
            hostname = request.form.get('query_hostname', '').strip()
            try:
                query_result = dns.resolve(db, hostname)
                log_network_event(
                    "DNS_SIM",
                    request.remote_addr,
                    f"DNS query '{hostname}' -> Status: {query_result['status']} ({query_result['source']})",
                    200
                )
            except ValueError as ex:
                error = str(ex)

        elif action == 'add_record':
            if not verify_csrf_token():
                flash("CSRF validation failed.", "danger")
                return redirect(url_for('networking.dns_demo'))

            hostname = request.form.get('hostname', '').strip()
            target_ip = request.form.get('target_ip', '').strip()
            ttl = request.form.get('ttl', type=int, default=300)
            try:
                dns.add_or_update_record(db, hostname, target_ip, ttl_seconds=ttl)
                flash(f"DNS Zone record for '{hostname}' saved successfully.", "success")
                log_network_event("DNS_SIM", request.remote_addr, f"Added/Updated DNS record: {hostname} -> {target_ip}", 200)
            except ValueError as ex:
                flash(str(ex), "danger")

        elif action == 'clear_cache':
            dns.clear_cache(db)
            flash("Simulated DNS Cache cleared successfully.", "info")
            log_network_event("DNS_SIM", request.remote_addr, "DNS cache flushed", 200)

    data = dns.get_all_records(db)
    server_info = get_server_network_interfaces()

    return render_template(
        'dns_demo.html',
        records=data['records'],
        cache=data['cache'],
        query_result=query_result,
        server_info=server_info,
        error=error,
        csrf_token=generate_csrf_token()
    )

@bp.route('/api/dns/resolve', methods=['GET', 'POST'])
def api_dns_resolve():
    """JSON API to resolve hostname against simulated DNS."""
    hostname = request.args.get('hostname') or (request.get_json(silent=True) or {}).get('hostname')
    db = get_db()
    dns = get_dns_sim()
    try:
        res = dns.resolve(db, hostname)
        return jsonify({"success": True, "result": res}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ----------------- TOPOLOGY & PROTOCOLS -----------------
@bp.route('/topology')
def topology():
    """Academic Network Topology and Protocol Explanations."""
    server_info = get_server_network_interfaces()
    sample_plan = get_sample_exam_network_plan()
    return render_template('topology.html', server_info=server_info, sample_plan=sample_plan)

# ----------------- PERFORMANCE TESTING -----------------
@bp.route('/performance', methods=['GET', 'POST'])
def performance():
    """Interactive HTTP Network Performance Benchmark."""
    db = get_db()
    result = None
    server_port = current_app.config['PORT']
    default_url = f"http://127.0.0.1:{server_port}/api/health"

    target_url = request.form.get('target_url', default_url) if request.method == 'POST' else default_url
    req_count = request.form.get('request_count', type=int, default=20) if request.method == 'POST' else 20

    if request.method == 'POST':
        test_name = request.form.get('test_name', 'Manual HTTP Web Benchmark')
        # Protect server from excessive benchmark loads
        req_count = max(1, min(req_count, 100))
        
        result = run_http_benchmark(target_url, request_count=req_count)
        record_benchmark_result(db, test_name, result)
        
        log_network_event(
            "PERF_TEST",
            request.remote_addr,
            f"Performance benchmark '{test_name}': {result['successful_requests']}/{result['request_count']} ok, Avg: {result['avg_response_ms']}ms, RPS: {result['throughput_rps']}",
            200
        )
        flash(f"Benchmark completed: {result['request_count']} requests sent in {result['total_duration_sec']}s.", "success")

    history = get_performance_history(db, limit=15)
    return render_template(
        'performance.html',
        result=result,
        history=history,
        target_url=target_url,
        req_count=req_count,
        csrf_token=generate_csrf_token()
    )

# ----------------- HEALTH & SYSTEM API -----------------
@bp.route('/api/health')
def api_health():
    """Application and DB health check endpoint for monitoring and benchmarking."""
    db = get_db()
    health = get_application_health(db, port=current_app.config['PORT'])
    return jsonify({
        "status": health['status'],
        "uptime": health['uptime'],
        "database": health['database_status'],
        "db_latency_ms": health['database_latency_ms'],
        "server_ip": health['network_info']['primary_lan_ip'],
        "port": health['server_port']
    }), 200
