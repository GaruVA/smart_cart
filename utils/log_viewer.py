"""
Log viewer utility for Smart Cart
This utility can be used to view and analyze cart activity logs
"""

import os
import json
import datetime
import sys
from collections import defaultdict

# Add parent directory to path to import FirebaseHandler
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.firebase_handler import FirebaseHandler

class LogViewer:
    def __init__(self):
        self.firebase = FirebaseHandler()
        
    def get_logs_from_firestore(self, limit=50, cart_id=None, activity_type=None):
        """Retrieve logs from Firestore
        
        Args:
            limit: Maximum number of logs to retrieve
            cart_id: Filter logs by cart ID
            activity_type: Filter logs by activity type
            
        Returns:
            list: List of log entries sorted by timestamp (newest first)
        """
        if not self.firebase.db or self.firebase.offline_mode:
            print("Cannot retrieve logs: Firebase is offline")
            return []
            
        try:
            # Start with base query
            query = self.firebase.db.collection('cartLogs')
            
            # Apply filters
            if cart_id:
                query = query.where('cart_id', '==', cart_id)
            if activity_type:
                query = query.where('activity_type', '==', activity_type)
                
            # Order by timestamp descending (newest first)
            query = query.order_by('timestamp', direction='DESCENDING').limit(limit)
            
            # Execute query
            logs = list(query.stream())
            
            # Convert to dictionaries and add document ID
            result = []
            for log in logs:
                log_data = log.to_dict()
                log_data['id'] = log.id
                result.append(log_data)
                
            return result
        
        except Exception as e:
            print(f"Error retrieving logs: {str(e)}")
            return []
    
    def get_offline_logs(self):
        """Retrieve logs from offline storage
        
        Returns:
            list: List of offline log entries sorted by timestamp (newest first)
        """
        offline_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_logs")
        if not os.path.exists(offline_dir):
            print("No offline logs directory found")
            return []
            
        logs = []
        
        # Get all log files
        try:
            log_files = [f for f in os.listdir(offline_dir) if f.endswith('.json')]
            
            for log_file in log_files:
                file_path = os.path.join(offline_dir, log_file)
                
                try:
                    with open(file_path, 'r') as f:
                        log_data = json.load(f)
                        log_data['id'] = log_file.replace('.json', '')
                        logs.append(log_data)
                except Exception as e:
                    print(f"Error reading log file {log_file}: {str(e)}")
                    
            # Sort by timestamp (newest first)
            logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return logs
            
        except Exception as e:
            print(f"Error reading offline logs: {str(e)}")
            return []
    
    def get_all_logs(self, limit=50, cart_id=None, activity_type=None):
        """Get both online and offline logs
        
        Returns:
            list: Combined list of logs sorted by timestamp (newest first)
        """
        # Try to get logs from Firestore
        try:
            print("Attempting to retrieve logs from Firestore...")
            online_logs = self.get_logs_from_firestore(limit=limit, cart_id=cart_id, activity_type=activity_type)
            print(f"Retrieved {len(online_logs)} logs from Firestore")
        except Exception as e:
            print(f"Error retrieving logs from Firestore: {e}")
            online_logs = []
            
        # Get offline logs
        try:
            offline_logs = self.get_offline_logs()
            print(f"Retrieved {len(offline_logs)} logs from offline storage")
        except Exception as e:
            print(f"Error retrieving offline logs: {e}")
            offline_logs = []
            
        # Combine logs
        all_logs = online_logs + offline_logs
        print(f"Combined {len(all_logs)} logs total")
        
        # Sort by timestamp (newest first)
        all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Limit results
        return all_logs[:limit]
    
    def print_logs(self, logs):
        """Print logs to console in a readable format"""
        if not logs:
            print("No logs found")
            return
            
        print(f"\n===== Found {len(logs)} logs =====\n")
        
        for log in logs:
            # Format timestamp
            timestamp_str = log.get('timestamp', 'Unknown time')
            try:
                # Parse timestamp and format it
                timestamp = datetime.datetime.fromisoformat(timestamp_str)
                formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_time = timestamp_str
                
            # Print log header
            print(f"[{formatted_time}] {log.get('activity_type', 'unknown').upper()} - Cart: {log.get('cart_id', 'unknown')}")
            
            # Print details
            details = log.get('details', {})
            if details:
                print("  Details:")
                for key, value in details.items():
                    print(f"    - {key}: {value}")
            print()
    
    def generate_activity_summary(self, logs):
        """Generate a summary of cart activities"""
        if not logs:
            print("No logs found for summary")
            return
            
        # Count by activity type
        activity_counts = defaultdict(int)
        
        # Count by cart ID
        cart_counts = defaultdict(int)
        
        # Calculate average price of scanned items
        scanned_prices = []
        
        # Calculate average checkout totals
        checkout_totals = []
        
        for log in logs:
            activity_type = log.get('activity_type', 'unknown')
            activity_counts[activity_type] += 1
            
            cart_id = log.get('cart_id', 'unknown')
            cart_counts[cart_id] += 1
            
            details = log.get('details', {})
            
            # Add price to scanned prices if available
            if activity_type == 'scan' and 'price' in details:
                try:
                    scanned_prices.append(float(details['price']))
                except:
                    pass
                    
            # Add total amount to checkout totals if available
            if activity_type == 'checkout' and 'total_amount' in details:
                try:
                    checkout_totals.append(float(details['total_amount']))
                except:
                    pass
        
        # Print summary
        print("\n===== Activity Summary =====\n")
        
        print("Activity Counts:")
        for activity, count in activity_counts.items():
            print(f"  - {activity}: {count}")
            
        print("\nCart Usage:")
        for cart, count in cart_counts.items():
            print(f"  - Cart {cart}: {count} activities")
            
        if scanned_prices:
            avg_price = sum(scanned_prices) / len(scanned_prices)
            print(f"\nAverage Scanned Item Price: ${avg_price:.2f}")
            
        if checkout_totals:
            avg_total = sum(checkout_totals) / len(checkout_totals)
            print(f"Average Checkout Total: ${avg_total:.2f}")
            
        print()

if __name__ == "__main__":
    print("Smart Cart Log Viewer")
    print("---------------------")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='View Smart Cart logs')
    parser.add_argument('--limit', type=int, default=20, help='Maximum number of logs to retrieve')
    parser.add_argument('--cart', type=str, help='Filter by cart ID')
    parser.add_argument('--type', type=str, help='Filter by activity type (scan, weight_change, remove, checkout)')
    parser.add_argument('--summary', action='store_true', help='Generate activity summary')
    parser.add_argument('--offline', action='store_true', help='View only offline logs')
    parser.add_argument('--verbose', action='store_true', help='Show detailed debug information')
    parser.add_argument('--sync', action='store_true', help='Force sync of offline logs before viewing')
    
    args = parser.parse_args()
    
    # Initialize the log viewer
    viewer = LogViewer()
    
    # Check Firebase connection
    if args.verbose:
        print("Checking Firebase connection...")
        connection_status = viewer.firebase.test_connection()
        print(f"Firebase connection: {'Online' if connection_status else 'Offline'}")
        
        # Check for offline logs
        offline_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_logs")
        if os.path.exists(offline_dir):
            log_files = [f for f in os.listdir(offline_dir) if f.endswith('.json')]
            print(f"Found {len(log_files)} offline log files")
    
    # Sync offline logs if requested
    if args.sync and not viewer.firebase.offline_mode:
        print("Syncing offline logs to Firestore...")
        synced, failed = viewer.firebase.sync_offline_logs()
        print(f"Synced {synced} logs, failed to sync {failed} logs")
    
    # Get logs based on command line arguments
    if args.offline:
        print("Retrieving offline logs only...")
        logs = viewer.get_offline_logs()
    else:
        print(f"Retrieving logs (limit={args.limit})...")
        logs = viewer.get_all_logs(limit=args.limit, cart_id=args.cart, activity_type=args.type)
    
    # Display the logs
    viewer.print_logs(logs)
    
    # Generate summary if requested
    if args.summary:
        viewer.generate_activity_summary(logs)
