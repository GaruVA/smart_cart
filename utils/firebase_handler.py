import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import os
import sys
import time
from datetime import datetime

class FirebaseHandler:
    def __init__(self, credentials_path=None):
        """Initialize Firebase connection
        
        Args:
            credentials_path: Path to Firebase credentials JSON file
        """
        self.db = None
        self.online = False
        self.offline_mode = False
        self.credentials_path = credentials_path or self._find_credentials()
        self.mock_database = None
        
        if self.credentials_path:
            self.initialize_firebase()
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
                # Query Firestore for products
                products_ref = self.db.collection('products').limit(limit).stream()
                barcodes = [doc.id for doc in products_ref]
                
                if barcodes:
                    return barcodes
                else:
                    # Fallback to offline if no online products
                    print("No products found in Firestore, using offline data")
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
        
        Args:
            session_data: Dictionary containing session information
            
        Returns:
            str: Session ID if successful, None otherwise
        """
        if not self.db or self.offline_mode:
            print("Running in offline mode, session not saved to cloud")
            # Generate a unique offline session ID with timestamp
            offline_id = f"offline-session-{int(time.time())}"
            self._save_offline_session(offline_id, session_data)
            return offline_id
            
        try:
            # Add server timestamp
            session_data['server_timestamp'] = firestore.SERVER_TIMESTAMP
            
            # Create a new document with auto-generated ID
            session_ref = self.db.collection('sessions').document()
            session_ref.set(session_data)
            print(f"Session saved with ID: {session_ref.id}")
            return session_ref.id
        except Exception as e:
            print(f"Error saving session, using offline mode: {str(e).splitlines()[0]}")
            # Fall back to offline mode if saving to Firestore fails
            offline_id = f"offline-session-{int(time.time())}"
            self._save_offline_session(offline_id, session_data)
            return offline_id
    
    def _save_offline_session(self, session_id, session_data):
        """Save session data locally in case online saving fails
        
        Args:
            session_id: Generated offline session ID
            session_data: Session data dictionary
        """
        try:
            # Create sessions directory if it doesn't exist
            sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "offline_sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            
            # Save session to file
            session_file = os.path.join(sessions_dir, f"{session_id}.json")
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            print(f"Saved offline session to {session_file}")
        except Exception as e:
            print(f"Error saving offline session: {str(e)}")

    def switch_to_offline_mode(self):
        """Manually switch to offline mode"""
        self.offline_mode = True
        if not self.mock_database:
            self.mock_database = self._get_basic_mock_database()
        print("Switched to offline mode")
        
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
            self.online = True
            self.offline_mode = False
            return True
        except Exception:
            self.offline_mode = True
            return False