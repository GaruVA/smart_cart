import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import os
import sys
import time
from datetime import datetime

class FirebaseHandler:
    def __init__(self, credentials_path=None, cart_id=None):
        """Initialize Firebase connection
        
        Args:
            credentials_path: Path to Firebase credentials JSON file
            cart_id: ID of the cart (if None, will use the fixed cart ID "5DxLednzNqTVqfwbs2xf")
        """
        self.db = None
        self.online = False
        self.offline_mode = False
        self.credentials_path = credentials_path or self._find_credentials()
        self.mock_database = None
        self.cart_id = cart_id or "34tzyyBVfilqXhs2gjw9"
        self.active_session_id = None
        self.current_session = None
        
        # Initialize Firebase and register the cart
        if self.credentials_path:
            self.initialize_firebase()
            if self.online and not self.offline_mode:
                self._register_new_cart(self.cart_id)
        else:
            self.offline_mode = True
            self.mock_database = self._get_basic_mock_database()
            print("Firebase credentials not found, running in offline mode")
            
    def _find_credentials(self):
        """Try to find Firebase credentials file in common locations"""
        common_paths = [
            "firebase_credentials.json",
            os.path.expanduser("~/firebase_credentials.json"),
            "/etc/smart_cart/firebase_credentials.json",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "firebase_credentials.json")
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

    def initialize_firebase(self):
        """Initialize Firebase connection with credentials"""
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                cred = credentials.Certificate(self.credentials_path)
                firebase_admin.initialize_app(cred)
            
            # Test Firestore connection with a simple operation
            try:
                self.db = firestore.client()
                # Try a simple operation to check if Firestore is working
                collections = list(self.db.collections())
                self.online = True
                print("Firebase connection established successfully")
            except Exception as e:
                print(f"Firebase Firestore error: {str(e).splitlines()[0]}")
                print("Running in offline mode")
                self.offline_mode = True
                self.mock_database = self._get_basic_mock_database()
                
        except Exception as e:
            print(f"Firebase initialization error: {str(e).splitlines()[0]}")
            print("Running in offline mode")
            self.offline_mode = True
            self.mock_database = self._get_basic_mock_database()
            
    def _get_basic_mock_database(self):
        """Return a minimal mock database with common products
        
        This provides essential products for offline mode without requiring external files
        """
        return {
            "products": {
                "1234567890128": {
                    "name": "Milk 1L",
                    "price": 1.99,
                    "weight": 1.04,
                    "category": "dairy"
                },
                "5901234123457": {
                    "name": "Bread",
                    "price": 2.49, 
                    "weight": 0.5,
                    "category": "bakery"
                },
                "4005808262816": {
                    "name": "Toothpaste",
                    "price": 3.99,
                    "weight": 0.1,
                    "category": "personal care"
                },
                "8710398503968": {
                    "name": "Soap",
                    "price": 1.29,
                    "weight": 0.15,
                    "category": "personal care"
                },
                "3574660239881": {
                    "name": "Chocolate Bar",
                    "price": 0.99,
                    "weight": 0.1,
                    "category": "snacks"
                },
                "4011": {
                    "name": "Bananas",
                    "price": 2.93,
                    "weight": 2.48,
                    "category": "produce"
                },
                "4062": {
                    "name": "Cucumber",
                    "price": 1.29,
                    "weight": 0.35,
                    "category": "produce"
                },
                "5449000000996": {
                    "name": "Soda",
                    "price": 2.49,
                    "weight": 1.25,
                    "category": "beverages"
                },
                "7613035974685": {
                    "name": "Coffee",
                    "price": 8.99,
                    "weight": 0.75,
                    "category": "beverages"
                },
                "5029054534087": {
                    "name": "Chips",
                    "price": 3.49,
                    "weight": 0.15,
                    "category": "snacks"
                }
            }
        }
            
    def get_product_by_barcode(self, barcode):
        """Retrieve product information by barcode
        
        Args:
            barcode: Product barcode string
            
        Returns:
            dict: Product information or None if not found
        """
        if self.online and not self.offline_mode:
            try:
                # Try to get item from the 'items' collection (new structure)
                item_ref = self.db.collection('items').document(barcode).get()
                if item_ref.exists:
                    item_data = item_ref.to_dict()
                    # Convert to the format expected by the app
                    product_data = {
                        'name': item_data.get('name', f"Item {barcode}"),
                        'price': item_data.get('price', 0.0),
                        'category': item_data.get('category', 'unknown'),
                        # Add a default weight if not present
                        'weight': item_data.get('weight', 0.5)
                    }
                    # Add other fields from the Item structure
                    if 'description' in item_data:
                        product_data['description'] = item_data['description']
                    if 'stockQuantity' in item_data:
                        product_data['stock'] = item_data['stockQuantity']
                        
                    # Preserve the original ID
                    product_data['id'] = barcode
                    
                    return product_data
                else:
                    # Fallback to the old 'products' collection for backward compatibility
                    product_ref = self.db.collection('products').document(barcode).get()
                    if product_ref.exists:
                        product_data = product_ref.to_dict()
                        # Remove server timestamp from the returned data
                        if 'timestamp' in product_data:
                            del product_data['timestamp']
                        return product_data
                    else:
                        print(f"Product with barcode {barcode} not found in Firestore")
                        # Try offline data if online search fails
                        offline_product = self._get_offline_product(barcode)
                        if offline_product:
                            return offline_product
                        return self._generate_fallback_product(barcode)
            except Exception as e:
                print(f"Error fetching product from Firestore: {str(e).splitlines()[0]}")
                # Switch to offline mode after a failure
                self.offline_mode = True
                return self._get_offline_product(barcode) or self._generate_fallback_product(barcode)
        else:
            # Use offline data
            return self._get_offline_product(barcode) or self._generate_fallback_product(barcode)
    
    def _get_offline_product(self, barcode):
        """Get product from offline mock database
        
        Returns:
            dict: Product info or None if not found
        """
        if not hasattr(self, 'mock_database') or self.mock_database is None:
            self.mock_database = self._get_basic_mock_database()
            
        if 'products' in self.mock_database and barcode in self.mock_database['products']:
            return self.mock_database['products'][barcode]
        return None
            
    def _generate_fallback_product(self, barcode):
        """Generate a fallback product when not found in any database
        
        Args:
            barcode: Product barcode string
            
        Returns:
            dict: Generated product information
        """
        # Generate a mock product based on the barcode
        # This ensures we always have a product even with unknown barcodes
        try:
            price = round(float(int(barcode) % 100) / 10, 2)
            weight = round(float(int(barcode[-2:]) % 50) / 10, 2)
        except:
            # Fallback if barcode can't be parsed as expected
            price = 1.99
            weight = 0.5
            
        return {
            "name": f"Unknown Item ({barcode})",
            "price": price,
            "weight": weight,
            "category": "unknown"
        }
    
    def get_available_barcodes(self, limit=10):
        """Get a list of valid barcodes from Firestore or mock database
        
        Args:
            limit: Maximum number of barcodes to return
            
        Returns:
            list: List of available barcodes
        """
        if self.online and not self.offline_mode:
            try:
                # Query Firestore for items collection
                items_ref = self.db.collection('items').limit(limit).stream()
                barcodes = [doc.id for doc in items_ref]
                
                if barcodes:
                    return barcodes
                else:
                    # Fallback to 'products' collection for backward compatibility
                    products_ref = self.db.collection('products').limit(limit).stream()
                    barcodes = [doc.id for doc in products_ref]
                    
                    if barcodes:
                        print("Warning: Using legacy 'products' collection. Please migrate to 'items' collection.")
                        return barcodes
                    else:
                        # Fallback to offline if no online products
                        print("No items found in Firestore, using offline data")
                        return self._get_offline_barcodes(limit)
            except Exception as e:
                print(f"Error fetching barcodes from Firestore: {str(e).splitlines()[0]}")
                # Switch to offline mode after a failure
                self.offline_mode = True
                return self._get_offline_barcodes(limit)
        else:
            # Use offline data
            return self._get_offline_barcodes(limit)
    
    def _get_offline_barcodes(self, limit):
        """Get barcodes from offline mock database"""
        if hasattr(self, 'mock_database') and self.mock_database and 'products' in self.mock_database:
            barcodes = list(self.mock_database['products'].keys())
            return barcodes[:min(limit, len(barcodes))]
        return []
            
    def save_session(self, session_data):
        """Save shopping session data to Firebase
        
        This is a legacy method. For new code, use start_shopping_session(), add_item_to_session(),
        and complete_shopping_session() instead.
        
        Args:
            session_data: Dictionary containing session information
            
        Returns:
            str: Session ID if successful, None otherwise
        """
        if not self.db or self.offline_mode:
            print("Running in offline mode, session not saved to cloud")
            # Generate a unique offline session ID with timestamp
            offline_id = f"offline-session-{int(time.time())}"
            
            # Convert to the proper session format
            formatted_session = {
                'sessionId': offline_id,
                'cartId': self.cart_id,
                'status': session_data.get('status', 'completed'),
                'startedAt': datetime.now().isoformat(),
                'endedAt': datetime.now().isoformat(),
                'totalCost': session_data.get('total_cost', 0),
                'items': []
            }
            
            # Convert items if present
            if 'items' in session_data:
                for item in session_data['items']:
                    formatted_session['items'].append({
                        'itemId': item.get('id', ''),
                        'quantity': item.get('quantity', 1),
                        'unitPrice': item.get('price', 0)
                    })
                    
            self._save_offline_session(offline_id, formatted_session)
            return offline_id
            
        try:
            # Create a new document with auto-generated ID first to get the ID
            session_ref = self.db.collection('sessions').document()
            session_id = session_ref.id
            
            # Convert to the new session format
            formatted_session = {
                'sessionId': session_id,  # Include session ID in the initial document
                'cartId': self.cart_id,
                'status': session_data.get('status', 'completed'),
                'startedAt': firestore.SERVER_TIMESTAMP,
                'endedAt': firestore.SERVER_TIMESTAMP,
                'totalCost': session_data.get('total_cost', 0),
                'items': []
            }
            
            # Convert items if present
            total_cost = 0
            if 'items' in session_data:
                for item in session_data['items']:
                    unit_price = item.get('price', 0)
                    quantity = item.get('quantity', 1)
                    item_total = unit_price * quantity
                    total_cost += item_total
                    
                    formatted_session['items'].append({
                        'itemId': item.get('id', ''),
                        'quantity': quantity,
                        'unitPrice': unit_price
                    })
                
                # Update the total cost with the calculated value
                formatted_session['totalCost'] = total_cost
            
            # Set the document data in Firestore
            session_ref.set(formatted_session)
            
            # Also save offline as backup
            offline_formatted = dict(formatted_session)
            offline_formatted['startedAt'] = datetime.now().isoformat()
            offline_formatted['endedAt'] = datetime.now().isoformat()
            self._save_offline_session(session_id, offline_formatted)
            
            print(f"Session saved with ID: {session_id}")
            return session_id
        except Exception as e:
            print(f"Error saving session, using offline mode: {str(e).splitlines()[0]}")
            # Fall back to offline mode if saving to Firestore fails
            offline_id = f"offline-session-{int(time.time())}"
            
            # Convert to the proper session format
            formatted_session = {
                'sessionId': offline_id,
                'cartId': self.cart_id,
                'status': session_data.get('status', 'completed'),
                'startedAt': datetime.now().isoformat(),
                'endedAt': datetime.now().isoformat(),
                'totalCost': session_data.get('total_cost', 0),
                'items': []
            }
            
            # Convert items if present
            if 'items' in session_data:
                for item in session_data['items']:
                    formatted_session['items'].append({
                        'itemId': item.get('id', ''),
                        'quantity': item.get('quantity', 1),
                        'unitPrice': item.get('price', 0)
                    })
                
                # Update the total cost with the calculated value
                formatted_session['totalCost'] = total_cost
                    
            self._save_offline_session(offline_id, formatted_session)
            return offline_id
    
    def _save_offline_session(self, session_id, session_data):
        """Save session data locally in case online saving fails
        
        Args:
            session_id: Generated session ID
            session_data: Session data dictionary
        """
        try:
            # Create sessions directory if it doesn't exist
            sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            
            # Ensure session data has the correct structure
            # Convert datetime objects to string if needed
            normalized_data = dict(session_data)
            
            if 'startedAt' in normalized_data and isinstance(normalized_data['startedAt'], datetime):
                normalized_data['startedAt'] = normalized_data['startedAt'].isoformat()
                
            if 'endedAt' in normalized_data and isinstance(normalized_data['endedAt'], datetime):
                normalized_data['endedAt'] = normalized_data['endedAt'].isoformat()
                
            # Make sure session ID is included
            if 'sessionId' not in normalized_data:
                normalized_data['sessionId'] = session_id
                
            # Save session to file
            session_file = os.path.join(sessions_dir, f"{session_id}.json")
            with open(session_file, 'w') as f:
                json.dump(normalized_data, f, indent=2)
            print(f"Saved offline session to {session_file}")
        except Exception as e:
            print(f"Error saving offline session: {str(e)}")

    def switch_to_offline_mode(self):
        """Manually switch to offline mode"""
        self.offline_mode = True
        if not self.mock_database:
            self.mock_database = self._get_basic_mock_database()
        print("Switched to offline mode")
        
        # Update cart status if possible
        if self.cart_id:
            self._update_cart_status(self.cart_id, 'offline')
        
    def test_connection(self):
        """Test connection to Firestore
        
        Returns:
            bool: True if connected, False otherwise
        """
        if not self.db:
            return False
            
        try:
            # Try a simple operation to check if Firestore is working
            collections = list(self.db.collections())
            
            # If we were previously offline, sync any offline logs
            if self.offline_mode:
                self.sync_offline_logs()
                
            self.online = True
            self.offline_mode = False
            
            # Update cart status to online
            if self.cart_id:
                self._update_cart_status(self.cart_id, 'online')
                
            return True
        except Exception:
            self.offline_mode = True
            
            # Update cart status to offline if possible
            if self.cart_id and self.db:
                try:
                    self._update_cart_status(self.cart_id, 'offline')
                except:
                    pass
                    
            return False
            
    def log_cart_activity(self, activity_type, details=None):
        """Log basic cart activity to Firestore
        
        Args:
            activity_type (str): Type of activity (scan, add, remove, checkout, etc.)
            details (dict): Additional details about the activity
            
        Returns:
            bool: True if logged to Firestore, False if stored offline or on error
        """
        try:
            # Create a simple log entry
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'cart_id': self.cart_id,
                'activity_type': activity_type,
                'details': details or {}
            }
            
            # Add to Firestore
            if not self.offline_mode and self.db:
                try:
                    print(f"Attempting to log to Firestore collection 'cartLogs'...")
                    self.db.collection('cartLogs').add(log_entry)
                    print(f"Successfully logged {activity_type} activity to Firestore")
                    return True
                except Exception as firestore_error:
                    print(f"Firestore logging failed: {str(firestore_error)}")
                    print("Falling back to offline storage...")
                    # Fall back to offline storage
            
            # Store offline for later sync
            offline_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_logs")
            os.makedirs(offline_dir, exist_ok=True)
            
            filename = f"log_{int(time.time())}.json"
            file_path = os.path.join(offline_dir, filename)
            with open(file_path, 'w') as f:
                json.dump(log_entry, f)
            print(f"Saved log to offline storage: {file_path}")
            return False
        except Exception as e:
            print(f"Error logging activity: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    def sync_offline_logs(self):
        """Sync offline logs to Firebase when connection is restored
        
        Returns:
            tuple: (int, int) - (number of logs synced, number of logs that failed)
        """
        if self.offline_mode or not self.db:
            print("Cannot sync logs: system is offline")
            return (0, 0)
            
        # Path to offline logs
        offline_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_logs")
        print(f"Looking for offline logs in: {offline_dir}")
        
        if not os.path.exists(offline_dir):
            print("No offline logs directory found")
            return (0, 0)
            
        # Get all log files
        log_files = [f for f in os.listdir(offline_dir) if f.endswith('.json')]
        print(f"Found {len(log_files)} offline log files: {log_files}")
        
        if not log_files:
            print("No offline logs found")
            return (0, 0)
            
        synced = 0
        failed = 0
        
        for log_file in log_files:
            file_path = os.path.join(offline_dir, log_file)
            print(f"Processing log file: {file_path}")
            
            try:
                # Read log data
                with open(file_path, 'r') as f:
                    log_data = json.load(f)
                    print(f"Read log data: {log_data['activity_type']} at {log_data['timestamp']}")
                    
                # Add to Firestore
                print("Attempting to add to Firestore...")
                self.db.collection('cartLogs').add(log_data)
                print("Successfully added to Firestore")
                
                # Delete the file after successful sync
                os.remove(file_path)
                print(f"Deleted synced log file: {file_path}")
                
                synced += 1
                
            except Exception as e:
                print(f"Error syncing log {log_file}: {str(e)}")
                import traceback
                traceback.print_exc()
                failed += 1
                
        print(f"Sync complete: {synced} logs synced, {failed} logs failed")
        return (synced, failed)
            
    def _load_or_generate_cart_id(self):
        """Return the fixed cart ID and update the config file if needed
        
        Returns:
            str: Fixed cart ID "34tzyyBVfilqXhs2gjw9"
        """
        fixed_cart_id = "34tzyyBVfilqXhs2gjw9"
        cart_config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cart_config.json")
        
        # Update the config file with the fixed cart ID for consistency
        try:
            with open(cart_config_file, 'w') as f:
                json.dump({'cart_id': fixed_cart_id}, f)
            print(f"Using fixed cart ID: {fixed_cart_id}")
            
            # Update cart status in Firestore if possible
            if self.db and not self.offline_mode:
                self._update_cart_status(fixed_cart_id, 'online')
        except Exception as e:
            print(f"Error updating cart config: {str(e)}")
            
        return fixed_cart_id
    
    def _register_new_cart(self, cart_id):
        """Register a new cart in the Firestore database
        
        Args:
            cart_id: The ID of the cart to register
        """
        if not self.db or self.offline_mode:
            print(f"Running in offline mode, cart {cart_id} registered locally only")
            return
            
        try:
            # Create a new cart document in Firestore
            cart_data = {
                'cartId': cart_id,
                'status': 'online',
                'createdAt': firestore.SERVER_TIMESTAMP,
                'updatedAt': firestore.SERVER_TIMESTAMP
            }
            
            self.db.collection('carts').document(cart_id).set(cart_data)
            print(f"Cart {cart_id} registered in Firestore")
        except Exception as e:
            print(f"Error registering cart in Firestore: {str(e).splitlines()[0]}")
    
    def _update_cart_status(self, cart_id, status):
        """Update the status of a cart in Firestore
        
        Args:
            cart_id: The ID of the cart to update
            status: The new status ('online', 'offline', or 'maintenance')
        """
        if not self.db or self.offline_mode:
            print(f"Running in offline mode, cart status update skipped")
            return
            
        try:
            # Update the cart document in Firestore
            self.db.collection('carts').document(cart_id).update({
                'status': status,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            print(f"Cart {cart_id} status updated to {status}")
        except Exception as e:
            print(f"Error updating cart status: {str(e).splitlines()[0]}")
            # If the document doesn't exist, create it
            if "NOT_FOUND" in str(e):
                self._register_new_cart(cart_id)
        
    def get_cart_id(self):
        """Get the current cart ID
        
        Returns:
            str: Cart ID
        """
        return self.cart_id
    
    def start_shopping_session(self):
        """Start a new shopping session
        
        Returns:
            str: Session ID if successful, None otherwise
        """
        if not self.db or self.offline_mode:
            print("Running in offline mode, session created locally")
            # Generate a unique offline session ID with timestamp
            session_id = f"offline-session-{int(time.time())}"
            self.active_session_id = session_id
            self.current_session = {
                'sessionId': session_id,
                'cartId': self.cart_id,
                'status': 'active',
                'startedAt': datetime.now(),
                'endedAt': None,
                'totalCost': 0,
                'items': []
            }
            # Save offline session
            self._save_offline_session(session_id, self.current_session)
            print(f"Offline shopping session started with ID: {session_id}")
            return session_id
            
        try:
            # Create a new document with auto-generated ID first to get the ID
            session_ref = self.db.collection('sessions').document()
            self.active_session_id = session_ref.id
            
            # Create a new session document with the session ID included
            session_data = {
                'sessionId': self.active_session_id,  # Include session ID in the initial document
                'cartId': self.cart_id,
                'status': 'active',
                'startedAt': firestore.SERVER_TIMESTAMP,
                'endedAt': None,
                'totalCost': 0,
                'items': []
            }
            
            # Set the document data
            session_ref.set(session_data)
            
            self.current_session = session_data
            
            print(f"Shopping session started with ID: {session_ref.id} and stored in database")
            return session_ref.id
        except Exception as e:
            print(f"Error starting shopping session in database: {str(e).splitlines()[0]}")
            # Fall back to offline mode if Firestore fails
            session_id = f"offline-session-{int(time.time())}"
            self.active_session_id = session_id
            self.current_session = {
                'sessionId': session_id,
                'cartId': self.cart_id,
                'status': 'active',
                'startedAt': datetime.now(),
                'endedAt': None,
                'totalCost': 0,
                'items': []
            }
            # Save offline session
            self._save_offline_session(session_id, self.current_session)
            print(f"Created offline session due to database error: {session_id}")
            return session_id
    
    def add_item_to_session(self, item_id, quantity=1):
        """Add an item to the current shopping session
        
        Args:
            item_id: Item barcode
            quantity: Quantity to add (defaults to 1)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.active_session_id or not self.current_session:
            print("No active shopping session")
            return False
            
        # Get the product information
        product = self.get_product_by_barcode(item_id)
        if not product:
            print(f"Product with ID {item_id} not found")
            return False
            
        # Update the local session data
        item_exists = False
        for item in self.current_session.get('items', []):
            if item.get('itemId') == item_id:
                item['quantity'] += quantity
                item_exists = True
                break
                
        if not item_exists:
            self.current_session['items'].append({
                'itemId': item_id,
                'quantity': quantity,
                'unitPrice': product.get('price', 0)
            })
            
        # Recalculate total cost
        total_cost = 0
        for item in self.current_session.get('items', []):
            item_total = item.get('unitPrice', 0) * item.get('quantity', 0)
            total_cost += item_total
        self.current_session['totalCost'] = total_cost
        
        # Update the session in Firestore if online
        if self.online and not self.offline_mode and self.db:
            try:
                session_ref = self.db.collection('sessions').document(self.active_session_id)
                session_ref.update({
                    'sessionId': self.active_session_id,  # Include session ID in the update
                    'items': [dict(item) for item in self.current_session.get('items', [])],
                    'totalCost': total_cost,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                print(f"Session {self.active_session_id} updated in database with new item")
                return True
            except Exception as e:
                print(f"Error updating session in database: {str(e).splitlines()[0]}")
                # Save changes locally in case of database failure
                self._save_offline_session(self.active_session_id, self.current_session)
                return False
        else:
            # In offline mode, just update the local session
            self._save_offline_session(self.active_session_id, self.current_session)
            return True
    
    def remove_item_from_session(self, item_id, quantity=1):
        """Remove an item from the current shopping session
        
        Args:
            item_id: Item barcode
            quantity: Quantity to remove (defaults to 1)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.active_session_id or not self.current_session:
            print("No active shopping session")
            return False
            
        # Update the local session data
        updated = False
        items_to_keep = []
        for item in self.current_session.get('items', []):
            if item.get('itemId') == item_id:
                item['quantity'] -= quantity
                if item['quantity'] <= 0:
                    # Remove the item if quantity is zero or negative
                    updated = True
                    continue
                updated = True
            items_to_keep.append(item)
                
        if not updated:
            print(f"Item with ID {item_id} not found in session")
            return False
            
        self.current_session['items'] = items_to_keep
            
        # Recalculate total cost
        total_cost = 0
        for item in self.current_session.get('items', []):
            item_total = item.get('unitPrice', 0) * item.get('quantity', 0)
            total_cost += item_total
        self.current_session['totalCost'] = total_cost
        
        # Update the session in Firestore if online
        if self.online and not self.offline_mode and self.db:
            try:
                session_ref = self.db.collection('sessions').document(self.active_session_id)
                session_ref.update({
                    'sessionId': self.active_session_id,  # Include session ID in the update
                    'items': [dict(item) for item in self.current_session.get('items', [])],
                    'totalCost': total_cost,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                print(f"Session {self.active_session_id} updated in database with item removal")
                return True
            except Exception as e:
                print(f"Error updating session in database: {str(e).splitlines()[0]}")
                # Save changes locally in case of database failure
                self._save_offline_session(self.active_session_id, self.current_session)
                return False
        else:
            # In offline mode, just update the local session
            self._save_offline_session(self.active_session_id, self.current_session)
            return True
    
    def complete_shopping_session(self):
        """Complete the current shopping session
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.active_session_id or not self.current_session:
            print("No active shopping session to complete")
            return False
            
        # Update local session data
        self.current_session['status'] = 'completed'
        self.current_session['endedAt'] = datetime.now()
        
        if self.online and not self.offline_mode and self.db:
            try:
                session_ref = self.db.collection('sessions').document(self.active_session_id)
                session_ref.update({
                    'sessionId': self.active_session_id,  # Include session ID in the update
                    'status': 'completed',
                    'endedAt': firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                
                # Save a local copy as backup
                self._save_offline_session(self.active_session_id, self.current_session)
                
                # Clear the active session
                completed_session_id = self.active_session_id
                self.active_session_id = None
                self.current_session = None
                
                print(f"Shopping session {completed_session_id} completed and updated in database")
                return True
            except Exception as e:
                print(f"Error completing session in database: {str(e).splitlines()[0]}")
                
                # Save offline backup and clear active session
                self._save_offline_session(self.active_session_id, self.current_session)
                completed_session_id = self.active_session_id
                self.active_session_id = None
                self.current_session = None
                
                print(f"Session {completed_session_id} saved offline due to database error")
                return False
        else:
            # Save offline backup and clear active session
            self._save_offline_session(self.active_session_id, self.current_session)
            completed_session_id = self.active_session_id
            self.active_session_id = None
            self.current_session = None
            
            print(f"Offline shopping session {completed_session_id} completed and saved locally")
            return True
    
    def abandon_shopping_session(self):
        """Mark the current shopping session as abandoned
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.active_session_id or not self.current_session:
            print("No active shopping session to abandon")
            return False
            
        # Update local session data
        self.current_session['status'] = 'abandoned'
        self.current_session['endedAt'] = datetime.now()
        
        if self.online and not self.offline_mode and self.db:
            try:
                session_ref = self.db.collection('sessions').document(self.active_session_id)
                session_ref.update({
                    'sessionId': self.active_session_id,  # Include session ID in the update
                    'status': 'abandoned',
                    'endedAt': firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                
                # Save a local copy as backup
                self._save_offline_session(self.active_session_id, self.current_session)
                
                # Clear the active session
                abandoned_session_id = self.active_session_id
                self.active_session_id = None
                self.current_session = None
                
                print(f"Shopping session {abandoned_session_id} marked as abandoned in database")
                return True
            except Exception as e:
                print(f"Error abandoning session in database: {str(e).splitlines()[0]}")
                
                # Save offline backup and clear active session
                self._save_offline_session(self.active_session_id, self.current_session)
                abandoned_session_id = self.active_session_id
                self.active_session_id = None
                self.current_session = None
                
                print(f"Session {abandoned_session_id} saved offline as abandoned due to database error")
                return False
        else:
            # Save offline backup and clear active session
            self._save_offline_session(self.active_session_id, self.current_session)
            abandoned_session_id = self.active_session_id
            self.active_session_id = None
            self.current_session = None
            
            print(f"Offline shopping session {abandoned_session_id} marked as abandoned and saved locally")
            return True
    
    def get_active_session(self):
        """Get the current active shopping session
        
        Returns:
            dict: Current session data or None if no active session
        """
        return self.current_session
    
    def get_session(self, session_id):
        """Retrieve a shopping session by ID
        
        Args:
            session_id: ID of the session to retrieve
            
        Returns:
            dict: Session data or None if not found
        """
        # Check if it's the current active session
        if self.active_session_id == session_id and self.current_session:
            return self.current_session
            
        # Try to get from Firestore if online
        if self.online and not self.offline_mode and self.db:
            try:
                session_ref = self.db.collection('sessions').document(session_id).get()
                if session_ref.exists:
                    session_data = session_ref.to_dict()
                    session_data['sessionId'] = session_id  # Add the ID to the data
                    return session_data
                else:
                    print(f"Session {session_id} not found in database")
            except Exception as e:
                print(f"Error retrieving session from database: {str(e).splitlines()[0]}")
                
        # Try to find the offline session file
        try:
            sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_sessions")
            session_file = os.path.join(sessions_dir, f"{session_id}.json")
            
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    return json.load(f)
            else:
                print(f"Offline session file for {session_id} not found")
        except Exception as e:
            print(f"Error reading offline session: {str(e)}")
            
        return None
        
    def get_recent_sessions(self, limit=10):
        """Get recent shopping sessions for this cart
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            list: List of session data
        """
        sessions = []
        
        # Try to get from Firestore if online
        if self.online and not self.offline_mode and self.db:
            try:
                # Query for sessions with this cart ID, ordered by start time
                session_refs = (self.db.collection('sessions')
                                .where('cartId', '==', self.cart_id)
                                .order_by('startedAt', direction=firestore.Query.DESCENDING)
                                .limit(limit)
                                .stream())
                                
                for session_ref in session_refs:
                    session_data = session_ref.to_dict()
                    session_data['sessionId'] = session_ref.id  # Add the ID to the data
                    sessions.append(session_data)
                    
                if sessions:
                    return sessions
            except Exception as e:
                print(f"Error retrieving sessions from database: {str(e).splitlines()[0]}")
                
        # If online retrieval failed or returned no results, try offline
        try:
            sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_sessions")
            if os.path.exists(sessions_dir):
                session_files = [f for f in os.listdir(sessions_dir) if f.endswith('.json')]
                # Sort by modification time (newest first)
                session_files.sort(key=lambda f: os.path.getmtime(os.path.join(sessions_dir, f)), reverse=True)
                
                for file_name in session_files[:limit]:
                    try:
                        with open(os.path.join(sessions_dir, file_name), 'r') as f:
                            session_data = json.load(f)
                            sessions.append(session_data)
                    except Exception as e:
                        print(f"Error reading offline session {file_name}: {str(e)}")
        except Exception as e:
            print(f"Error listing offline sessions: {str(e)}")
            
        return sessions