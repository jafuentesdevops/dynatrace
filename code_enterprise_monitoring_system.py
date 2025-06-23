#!/usr/bin/env python3
"""
Enterprise Automated Monitoring System
======================================

What enterprises MOST seek in 2024:
- Intelligent automation of critical processes
- Proactive system and service monitoring
- Automatic alerts and rapid incident response
- MTTR (Mean Time To Recovery) reduction

Author: MiniMax Agent
Date: 2025-06-23
"""

import psutil
import requests
import smtplib
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import os

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enterprise_monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class MetricAlert:
    """Structure to define metrics and alert thresholds"""
    name: str
    type: str  # 'system', 'api', 'custom'
    critical_threshold: float
    warning_threshold: float
    unit: str
    description: str
    automatic_action: Optional[str] = None

@dataclass
class Incident:
    """Structure to record incidents"""
    timestamp: datetime
    metric: str
    current_value: float
    threshold: float
    severity: str  # 'critical', 'warning', 'info'
    message: str
    resolved: bool = False
    resolution_time: Optional[datetime] = None

class MonitoringDatabase:
    """Handles storage of metrics and incidents"""
    
    def __init__(self, db_path: str = "enterprise_monitoring.db"):
        self.db_path = db_path
        self.initialize_db()
    
    def initialize_db(self):
        """Creates necessary tables for monitoring"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Historical metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historical_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                metric TEXT,
                value REAL,
                status TEXT
            )
        ''')
        
        # Incidents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                metric TEXT,
                current_value REAL,
                threshold REAL,
                severity TEXT,
                message TEXT,
                resolved BOOLEAN,
                resolution_time DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_metric(self, metric: str, value: float, status: str):
        """Saves a metric to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO historical_metrics (timestamp, metric, value, status) VALUES (?, ?, ?, ?)",
            (datetime.now(), metric, value, status)
        )
        conn.commit()
        conn.close()
    
    def save_incident(self, incident: Incident):
        """Saves an incident to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO incidents 
               (timestamp, metric, current_value, threshold, severity, message, resolved, resolution_time) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (incident.timestamp, incident.metric, incident.current_value, 
             incident.threshold, incident.severity, incident.message, 
             incident.resolved, incident.resolution_time)
        )
        conn.commit()
        conn.close()

class AlertNotifier:
    """Handles sending alerts through different channels"""
    
    def __init__(self, email_config: Dict[str, str] = None, webhook_url: str = None):
        self.email_config = email_config
        self.webhook_url = webhook_url
    
    def send_email(self, recipient: str, subject: str, message: str):
        """Sends alert via email"""
        if not self.email_config:
            logger.warning("Email configuration not available")
            return False
        
        try:
            msg = MimeMultipart()
            msg['From'] = self.email_config['user']
            msg['To'] = recipient
            msg['Subject'] = subject
            
            msg.attach(MimeText(message, 'html'))
            
            server = smtplib.SMTP(self.email_config['server'], self.email_config['port'])
            server.starttls()
            server.login(self.email_config['user'], self.email_config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent to {recipient}")
            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    def send_webhook(self, data: Dict[str, Any]):
        """Sends alert via webhook (Slack, Teams, etc.)"""
        if not self.webhook_url:
            logger.warning("Webhook URL not configured")
            return False
        
        try:
            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Webhook sent successfully")
            return True
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            return False

class SystemMonitor:
    """Monitors operating system metrics"""
    
    def get_system_metrics(self) -> Dict[str, float]:
        """Gets current system metrics"""
        try:
            metrics = {
                'cpu_percentage': psutil.cpu_percent(interval=1),
                'memory_percentage': psutil.virtual_memory().percent,
                'disk_percentage': psutil.disk_usage('/').percent,
                'system_load_1min': os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0,
                'active_processes': len(psutil.pids()),
                'network_connections': len(psutil.net_connections()),
            }
            
            # Network metrics
            net_stats = psutil.net_io_counters()
            metrics.update({
                'bytes_sent_mb': net_stats.bytes_sent / (1024 * 1024),
                'bytes_received_mb': net_stats.bytes_recv / (1024 * 1024),
            })
            
            return metrics
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}

class APIMonitor:
    """Monitors availability and performance of critical APIs"""
    
    def __init__(self, critical_apis: List[Dict[str, str]]):
        self.critical_apis = critical_apis
    
    def check_api(self, api_config: Dict[str, str]) -> Dict[str, Any]:
        """Checks the status of a specific API"""
        try:
            start_time = time.time()
            response = requests.get(
                api_config['url'],
                headers=api_config.get('headers', {}),
                timeout=api_config.get('timeout', 10)
            )
            response_time = time.time() - start_time
            
            return {
                'name': api_config['name'],
                'available': response.status_code == 200,
                'status_code': response.status_code,
                'response_time_ms': response_time * 1000,
                'response_size_kb': len(response.content) / 1024
            }
        except Exception as e:
            return {
                'name': api_config['name'],
                'available': False,
                'status_code': 0,
                'response_time_ms': 0,
                'error': str(e)
            }
    
    def check_all_apis(self) -> List[Dict[str, Any]]:
        """Checks all APIs in parallel"""
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.check_api, self.critical_apis))
        return results

class EnterpriseMonitoringSystem:
    """Main automated monitoring system"""
    
    def __init__(self, config_path: str = "monitoring_config.json"):
        self.config = self.load_configuration(config_path)
        self.db = MonitoringDatabase()
        self.notifier = AlertNotifier(
            self.config.get('email'),
            self.config.get('webhook_url')
        )
        self.system_monitor = SystemMonitor()
        self.api_monitor = APIMonitor(self.config.get('critical_apis', []))
        self.active_alerts = {}
        self.running = False
        
        # Define enterprise-typical metrics and thresholds
        self.configured_metrics = [
            MetricAlert("cpu_percentage", "system", 85.0, 70.0, "%", 
                       "Server CPU usage", "restart_non_critical_services"),
            MetricAlert("memory_percentage", "system", 90.0, 75.0, "%", 
                       "RAM memory usage", "clear_cache"),
            MetricAlert("disk_percentage", "system", 85.0, 70.0, "%", 
                       "Disk space utilization", "clean_old_logs"),
            MetricAlert("api_response_time", "api", 5000.0, 2000.0, "ms", 
                       "Critical API response time", "scale_instances"),
        ]
    
    def load_configuration(self, config_path: str) -> Dict[str, Any]:
        """Loads configuration from JSON file"""
        default_config = {
            "monitoring_interval": 60,  # seconds
            "email_recipients": ["admin@company.com"],
            "critical_apis": [
                {
                    "name": "Main API",
                    "url": "https://api.company.com/health",
                    "timeout": 10
                }
            ],
            "automatic_actions": True,
            "log_level": "INFO"
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                default_config.update(file_config)
            else:
                # Create default configuration file
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"Configuration file created: {config_path}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
        
        return default_config
    
    def evaluate_system_metrics(self, system_metrics: Dict[str, float]):
        """Evaluates system metrics against configured thresholds"""
        for metric_config in self.configured_metrics:
            if metric_config.type != "system":
                continue
                
            current_value = system_metrics.get(metric_config.name, 0)
            
            # Determine severity
            if current_value >= metric_config.critical_threshold:
                severity = "critical"
            elif current_value >= metric_config.warning_threshold:
                severity = "warning"
            else:
                severity = "normal"
                # Resolve alert if it existed
                if metric_config.name in self.active_alerts:
                    self.resolve_alert(metric_config.name)
                continue
            
            # Generate alert if it doesn't exist or has worsened
            self.generate_alert(metric_config, current_value, severity)
    
    def evaluate_api_metrics(self, api_results: List[Dict[str, Any]]):
        """Evaluates API metrics against configured thresholds"""
        for result in api_results:
            api_name = result['name']
            
            if not result['available']:
                self.generate_api_alert(api_name, "API not available", "critical", 
                                      result.get('error', 'No response'))
            elif 'response_time_ms' in result:
                response_time = result['response_time_ms']
                time_metric = next(
                    (m for m in self.configured_metrics if m.name == "api_response_time"),
                    None
                )
                
                if time_metric:
                    if response_time >= time_metric.critical_threshold:
                        severity = "critical"
                    elif response_time >= time_metric.warning_threshold:
                        severity = "warning"
                    else:
                        severity = "normal"
                        if f"api_{api_name}" in self.active_alerts:
                            self.resolve_alert(f"api_{api_name}")
                        continue
                    
                    self.generate_api_alert(api_name, 
                                          f"High response time: {response_time:.2f}ms",
                                          severity, "")
    
    def generate_alert(self, metric_config: MetricAlert, current_value: float, severity: str):
        """Generates a new alert or updates an existing one"""
        alert_key = metric_config.name
        
        # Check if an active alert of the same or lower level already exists
        if alert_key in self.active_alerts:
            existing_alert = self.active_alerts[alert_key]
            if self.severity_level(existing_alert.severity) >= self.severity_level(severity):
                return  # Don't generate duplicate or lower severity alert
        
        # Create new incident
        threshold_used = (metric_config.critical_threshold if severity == "critical" 
                         else metric_config.warning_threshold)
        
        incident = Incident(
            timestamp=datetime.now(),
            metric=metric_config.name,
            current_value=current_value,
            threshold=threshold_used,
            severity=severity,
            message=f"{metric_config.description}: {current_value:.2f}{metric_config.unit} "
                   f"(threshold: {threshold_used}{metric_config.unit})"
        )
        
        # Save to database
        self.db.save_incident(incident)
        self.active_alerts[alert_key] = incident
        
        # Send notifications
        self.send_notifications(incident)
        
        # Execute automatic action if configured
        if (self.config.get('automatic_actions', False) and 
            metric_config.automatic_action):
            self.execute_automatic_action(metric_config.automatic_action, incident)
        
        logger.warning(f"ALERT {severity.upper()}: {incident.message}")
    
    def generate_api_alert(self, api_name: str, message: str, severity: str, detail: str):
        """Generates API-specific alert"""
        alert_key = f"api_{api_name}"
        
        incident = Incident(
            timestamp=datetime.now(),
            metric=f"API {api_name}",
            current_value=0,
            threshold=0,
            severity=severity,
            message=f"{message} - {detail}" if detail else message
        )
        
        self.db.save_incident(incident)
        self.active_alerts[alert_key] = incident
        self.send_notifications(incident)
        
        logger.warning(f"API ALERT {severity.upper()}: {api_name} - {message}")
    
    def severity_level(self, severity: str) -> int:
        """Converts severity to number for comparison"""
        levels = {"normal": 0, "warning": 1, "critical": 2}
        return levels.get(severity, 0)
    
    def resolve_alert(self, alert_key: str):
        """Resolves an active alert"""
        if alert_key in self.active_alerts:
            incident = self.active_alerts[alert_key]
            incident.resolved = True
            incident.resolution_time = datetime.now()
            
            # Update in database
            self.db.save_incident(incident)
            
            # Send resolution notification
            self.send_resolution_notification(incident)
            
            del self.active_alerts[alert_key]
            logger.info(f"Alert resolved: {incident.metric}")
    
    def send_notifications(self, incident: Incident):
        """Sends notifications through all configured channels"""
        # Email
        for recipient in self.config.get('email_recipients', []):
            subject = f"🚨 ALERT {incident.severity.upper()}: {incident.metric}"
            html_message = self.generate_html_alert_message(incident)
            self.notifier.send_email(recipient, subject, html_message)
        
        # Webhook (Slack, Teams, etc.)
        webhook_data = {
            "text": f"🚨 ALERT {incident.severity.upper()}",
            "attachments": [{
                "color": "danger" if incident.severity == "critical" else "warning",
                "fields": [
                    {"title": "Metric", "value": incident.metric, "short": True},
                    {"title": "Current Value", "value": f"{incident.current_value:.2f}", "short": True},
                    {"title": "Threshold", "value": f"{incident.threshold:.2f}", "short": True},
                    {"title": "Timestamp", "value": incident.timestamp.strftime("%Y-%m-%d %H:%M:%S"), "short": True},
                    {"title": "Message", "value": incident.message, "short": False}
                ]
            }]
        }
        self.notifier.send_webhook(webhook_data)
    
    def send_resolution_notification(self, incident: Incident):
        """Sends notification when an alert is resolved"""
        duration = incident.resolution_time - incident.timestamp
        
        for recipient in self.config.get('email_recipients', []):
            subject = f"✅ RESOLVED: {incident.metric}"
            message = f"""
            <h3>✅ Alert Resolved</h3>
            <p><strong>Metric:</strong> {incident.metric}</p>
            <p><strong>Duration:</strong> {duration}</p>
            <p><strong>Resolved at:</strong> {incident.resolution_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
            self.notifier.send_email(recipient, subject, message)
    
    def generate_html_alert_message(self, incident: Incident) -> str:
        """Generates HTML message for email alerts"""
        color = "#FF0000" if incident.severity == "critical" else "#FFA500"
        
        return f"""
        <html>
        <body>
            <div style="border-left: 4px solid {color}; padding: 20px; background-color: #f9f9f9;">
                <h2 style="color: {color};">🚨 ALERT {incident.severity.upper()}</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td><strong>Metric:</strong></td><td>{incident.metric}</td></tr>
                    <tr><td><strong>Current Value:</strong></td><td>{incident.current_value:.2f}</td></tr>
                    <tr><td><strong>Threshold:</strong></td><td>{incident.threshold:.2f}</td></tr>
                    <tr><td><strong>Timestamp:</strong></td><td>{incident.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                    <tr><td><strong>Message:</strong></td><td>{incident.message}</td></tr>
                </table>
                <p style="margin-top: 20px; font-size: 12px; color: #666;">
                    Enterprise Monitoring System - MiniMax Agent
                </p>
            </div>
        </body>
        </html>
        """
    
    def execute_automatic_action(self, action: str, incident: Incident):
        """Executes automatic remediation actions"""
        logger.info(f"Executing automatic action: {action} for {incident.metric}")
        
        try:
            if action == "restart_non_critical_services":
                # Example: restart services that consume high CPU
                logger.info("Simulating restart of non-critical services...")
                # In production, real commands would go here:
                # subprocess.run(["systemctl", "restart", "non_critical_service"])
                
            elif action == "clear_cache":
                # Example: clear system cache
                logger.info("Simulating cache cleanup...")
                # In production:
                # subprocess.run(["sync"])
                # subprocess.run(["echo", "3", ">", "/proc/sys/vm/drop_caches"])
                
            elif action == "clean_old_logs":
                # Example: clean old logs
                logger.info("Simulating old log cleanup...")
                # In production:
                # subprocess.run(["find", "/var/log", "-name", "*.log", "-mtime", "+30", "-delete"])
                
            elif action == "scale_instances":
                # Example: scale cloud instances
                logger.info("Simulating automatic instance scaling...")
                # In production would make calls to AWS, Azure, etc.
                
        except Exception as e:
            logger.error(f"Error executing automatic action {action}: {e}")
    
    def monitoring_cycle(self):
        """Main monitoring cycle"""
        logger.info("Starting monitoring cycle...")
        
        # Get system metrics
        system_metrics = self.system_monitor.get_system_metrics()
        if system_metrics:
            # Save historical metrics
            for metric, value in system_metrics.items():
                status = "normal"
                # Determine status based on thresholds
                metric_config = next(
                    (m for m in self.configured_metrics if m.name == metric),
                    None
                )
                if metric_config:
                    if value >= metric_config.critical_threshold:
                        status = "critical"
                    elif value >= metric_config.warning_threshold:
                        status = "warning"
                
                self.db.save_metric(metric, value, status)
            
            # Evaluate alerts
            self.evaluate_system_metrics(system_metrics)
        
        # Check APIs
        if self.config.get('critical_apis'):
            api_results = self.api_monitor.check_all_apis()
            self.evaluate_api_metrics(api_results)
        
        # Log general status
        critical_alerts = sum(1 for a in self.active_alerts.values() if a.severity == "critical")
        warning_alerts = sum(1 for a in self.active_alerts.values() if a.severity == "warning")
        
        logger.info(f"Monitoring completed - Active alerts: {critical_alerts} critical, {warning_alerts} warnings")
    
    def start_monitoring(self):
        """Starts the monitoring system in the background"""
        self.running = True
        logger.info("🚀 Enterprise Monitoring System started")
        
        def monitoring_loop():
            while self.running:
                try:
                    self.monitoring_cycle()
                    time.sleep(self.config['monitoring_interval'])
                except KeyboardInterrupt:
                    logger.info("Monitoring interrupted by user")
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring cycle: {e}")
                    time.sleep(30)  # Wait 30 seconds before retrying
        
        # Run in separate thread to avoid blocking
        monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitoring_thread.start()
        
        return monitoring_thread
    
    def stop_monitoring(self):
        """Stops the monitoring system"""
        self.running = False
        logger.info("🛑 Enterprise Monitoring System stopped")
    
    def generate_status_report(self) -> Dict[str, Any]:
        """Generates a current system status report"""
        current_metrics = self.system_monitor.get_system_metrics()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system_metrics": current_metrics,
            "active_alerts": {
                key: {
                    "metric": alert.metric,
                    "severity": alert.severity,
                    "current_value": alert.current_value,
                    "message": alert.message,
                    "active_time": (datetime.now() - alert.timestamp).total_seconds()
                }
                for key, alert in self.active_alerts.items()
            },
            "total_critical_alerts": sum(1 for a in self.active_alerts.values() if a.severity == "critical"),
            "total_warning_alerts": sum(1 for a in self.active_alerts.values() if a.severity == "warning"),
            "system_healthy": len([a for a in self.active_alerts.values() if a.severity == "critical"]) == 0
        }

def main():
    """Main function to run the monitoring system"""
    print("🏢 Enterprise Automated Monitoring System")
    print("=" * 50)
    print("✅ What enterprises MOST seek in 2024:")
    print("   • Intelligent automation of critical processes")
    print("   • Proactive 24/7 system and service monitoring")
    print("   • Automatic alerts and rapid incident response")
    print("   • MTTR (Mean Time To Recovery) reduction")
    print("   • Observability and predictive analytics")
    print()
    
    # Initialize monitoring system
    system = EnterpriseMonitoringSystem()
    
    try:
        # Show initial configuration
        print("📋 Current Configuration:")
        print(f"   • Monitoring interval: {system.config['monitoring_interval']} seconds")
        print(f"   • Monitored APIs: {len(system.config.get('critical_apis', []))}")
        print(f"   • Email recipients: {len(system.config.get('email_recipients', []))}")
        print(f"   • Automatic actions: {'✅ Enabled' if system.config.get('automatic_actions') else '❌ Disabled'}")
        print()
        
        # Execute immediate monitoring iteration
        print("🔍 Running initial monitoring check...")
        system.monitoring_cycle()
        
        # Generate status report
        report = system.generate_status_report()
        print(f"📊 System Status:")
        print(f"   • System healthy: {'✅ YES' if report['system_healthy'] else '❌ NO'}")
        print(f"   • Critical alerts: {report['total_critical_alerts']}")
        print(f"   • Warning alerts: {report['total_warning_alerts']}")
        print()
        
        # Show current metrics
        print("📈 System Metrics:")
        for metric, value in report['system_metrics'].items():
            print(f"   • {metric}: {value:.2f}")
        print()
        
        # Start continuous monitoring
        print("🚀 Starting continuous monitoring...")
        print("   (Press Ctrl+C to stop)")
        
        monitoring_thread = system.start_monitoring()
        
        # Keep program running
        while system.running:
            time.sleep(60)
            # Show report every minute
            current_report = system.generate_status_report()
            if current_report['total_critical_alerts'] > 0 or current_report['total_warning_alerts'] > 0:
                print(f"⚠️  Status: {current_report['total_critical_alerts']} critical, "
                      f"{current_report['total_warning_alerts']} warnings")
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitoring system...")
        system.stop_monitoring()
        print("✅ System stopped successfully")
    except Exception as e:
        logger.error(f"Fatal system error: {e}")
        system.stop_monitoring()

if __name__ == "__main__":
    main()