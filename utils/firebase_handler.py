import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import os

class FirebaseHandler:
    def __init__(self, credentials_path=None):
        """Initialize Firebase connection
        
        Args:
            credentials_path: Path to Firebase credentials JSON file
        """
        self.db = None
        try:
            # If credentials path not provided, try to find it in common locations
            if credentials_path is None:
                credentials_path = self._find_credentials()
                
            if credentials_path and os.path.exists(credentials_path):
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                print("Firebase connection established successfully")
            else:
                print("Firebase credentials not found, running in offline mode")
        except Exception as e:
            print(f"Firebase initialization error: {e}")
            print("Running in offline mode")
            
    def _find_credentials(self):
        """Try to find Firebase credentials file in common locations"""
        common_paths = [
            "firebase_credentials.json",
            os.path.expanduser("~/firebase_credentials.json"),
            "/etc/smart_cart/firebase_credentials.json"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None
            
    def get_product_by_barcode(self, barcode):
        """Retrieve product information by barcode
        
        Args:
            barcode: Product barcode string
            
        Returns:
            dict: Product information or None if not found
        """
        if not self.db:
            return self._get_mock_product(barcode)
            
        try:
            product_ref = self.db.collection('products').document(barcode).get()
            if product_ref.exists:
                return product_ref.to_dict()
            else:
                print(f"Product with barcode {barcode} not found")
                return self._get_mock_product(barcode)
        except Exception as e:
            print(f"Error retrieving product: {e}")
            return self._get_mock_product(barcode)
            
    def _get_mock_product(self, barcode):
        """Returns mock product data when offline or product not found
        
        Args:
            barcode: Product barcode string
            
        Returns:
            dict: Mock product information
        """
        # Mock database of products for offline testing
        mock_products = {
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
            }
        }
        
        if barcode in mock_products:
            return mock_products[barcode]
        else:
            # Generate a mock product if barcode is not in our mock database
            return {
                "name": f"Unknown Item ({barcode})",
                "price": round(float(int(barcode) % 100) / 10, 2),
                "weight": round(float(int(barcode[-2:]) % 50) / 10, 2),
                "category": "unknown"
            }
            
    def save_session(self, session_data):
        """Save shopping session data to Firebase
        
        Args:
            session_data: Dictionary containing session information
            
        Returns:
            str: Session ID if successful, None otherwise
        """
        if not self.db:
            print("Running in offline mode, session not saved to cloud")
            return "offline-session"
            
        try:
            # Create a new document with auto-generated ID
            session_ref = self.db.collection('sessions').document()
            session_ref.set(session_data)
            print(f"Session saved with ID: {session_ref.id}")
            return session_ref.id
        except Exception as e:
            print(f"Error saving session: {e}")
            return None