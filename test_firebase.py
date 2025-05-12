#!/usr/bin/env python3
"""
Firebase Handler Test Script
Tests the FirebaseHandler implementation with the fixed cart ID
"""

import os
import sys
from utils.firebase_handler import FirebaseHandler

def main():
    print("Testing FirebaseHandler with fixed cart ID...")
    
    # Create FirebaseHandler instance
    firebase = FirebaseHandler()
    
    # Print cart ID
    print(f"Current cart ID: {firebase.get_cart_id()}")
    print(f"Is cart ID '34tzyyBVfilqXhs2gjw9'? {firebase.get_cart_id() == '34tzyyBVfilqXhs2gjw9'}")
    
    # Test connection
    print(f"Testing Firestore connection...")
    connection_ok = firebase.test_connection()
    print(f"Connection status: {'Connected' if connection_ok else 'Offline'}")
    
    # Test starting a session
    print(f"\nStarting a test shopping session...")
    session_id = firebase.start_shopping_session()
    print(f"Session started with ID: {session_id}")
    
    # Get active session
    active_session = firebase.get_active_session()
    print(f"Active session: {active_session}")
    
    # Print cart ID from active session
    if active_session and 'cartId' in active_session:
        print(f"Cart ID in session: {active_session['cartId']}")
        print(f"Is session using correct cart ID? {active_session['cartId'] == '34tzyyBVfilqXhs2gjw9'}")
    
    # Complete the test session
    print("\nCompleting test session...")
    firebase.complete_shopping_session()
    print("Test session completed")

if __name__ == "__main__":
    main()
