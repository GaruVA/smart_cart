import os
import time
import threading
from datetime import datetime

# Kivy imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.factory import Factory

# Local imports
from utils.firebase_handler import FirebaseHandler
from models.mock_sensors import MockUltrasonicSensor, MockLoadSensor, MockBarcodeScanner

# Set window size to match typical Raspberry Pi touchscreen (800x480)
Window.size = (800, 480)

# Load KV file
kv_file = os.path.join(os.path.dirname(__file__), 'ui', 'smartcart.kv')
if os.path.exists(kv_file):
    Builder.load_file(kv_file)
else:
    print(f"Warning: KV file not found at {kv_file}")

class CartScreen(BoxLayout):
    """Main screen for the smart cart UI"""
    
    def __init__(self, **kwargs):
        super(CartScreen, self).__init__(**kwargs)
        self.shopping_cart = ShoppingCart()
        
        # Initialize mock sensors for development
        self.distance_sensor = MockUltrasonicSensor()
        self.weight_sensor = MockLoadSensor()
        self.barcode_scanner = MockBarcodeScanner()
        
        # Start sensor simulations
        self.distance_sensor.start_simulation()
        self.weight_sensor.start_simulation()
        
        # Firebase handler for product data
        self.firebase = FirebaseHandler()
        
        # Start sensor update timer
        Clock.schedule_interval(self.update_sensor_display, 1.0)
    
    def scan_item(self, instance):
        """Handle item scanning"""
        # In development mode, use a popup to enter barcode
        # In production, this would interface with the actual scanner
        self.show_barcode_input()
    
    def show_barcode_input(self):
        """Show popup for entering barcode manually (for development)"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        input_label = Label(text='Enter barcode:')
        input_field = TextInput(multiline=False)
        
        buttons = BoxLayout(size_hint_y=None, height=50, spacing=10)
        random_btn = Button(text='Random')
        scan_btn = Button(text='Scan')
        cancel_btn = Button(text='Cancel')
        
        buttons.add_widget(random_btn)
        buttons.add_widget(scan_btn)
        buttons.add_widget(cancel_btn)
        
        content.add_widget(input_label)
        content.add_widget(input_field)
        content.add_widget(buttons)
        
        popup = Popup(title='Scan Item', content=content, size_hint=(0.7, 0.4))
        
        # Bind actions
        def on_scan(btn):
            barcode = input_field.text.strip()
            if barcode:
                self.process_scanned_barcode(barcode)
                popup.dismiss()
            
        def on_random(btn):
            barcode = self.barcode_scanner.scan()
            input_field.text = barcode
            
        scan_btn.bind(on_press=on_scan)
        random_btn.bind(on_press=on_random)
        cancel_btn.bind(on_press=popup.dismiss)
        
        popup.open()
    
    def process_scanned_barcode(self, barcode):
        """Process a scanned barcode"""
        product = self.firebase.get_product_by_barcode(barcode)
        
        if product:
            # Add product to cart
            self.shopping_cart.add_item(product)
            
            # Update weight simulation
            if 'weight' in product:
                self.weight_sensor.add_item(product['weight'])
            
            # Update UI
            self.update_cart_display()
    
    def update_cart_display(self):
        """Update the UI with cart contents"""
        # Update total
        self.ids.total_label.text = f"Running Total: ${self.shopping_cart.get_total():.2f}"
        
        # Clear and rebuild items list
        self.ids.items_container.clear_widgets()
        
        # Add items
        for item_id, item in self.shopping_cart.items.items():
            item_widget = Factory.ItemWidget(
                item_id=item_id,
                item_name=item['name'],
                item_price=item['price']
            )
            self.ids.items_container.add_widget(item_widget)
    
    def remove_item(self, item_id):
        """Remove item from the cart"""
        item = self.shopping_cart.items.get(item_id)
        
        if item:
            # Remove from shopping cart
            self.shopping_cart.remove_item(item_id)
            
            # Update weight simulation
            if 'weight' in item:
                self.weight_sensor.remove_item(item['weight'])
            
            # Update UI
            self.update_cart_display()
    
    def update_sensor_display(self, dt):
        """Update display with sensor data (called by Clock)"""
        distance = self.distance_sensor.read_distance()
        weight = self.weight_sensor.read_weight()
        self.ids.sensor_label.text = f"Distance: {distance:.1f} cm | Weight: {weight:.2f} kg"
    
    def end_session(self, instance):
        """End shopping session and generate checkout info"""
        if self.shopping_cart.is_empty():
            self.show_message_popup("Cart is empty", "Please scan items before checkout")
            return
            
        session_data = self.shopping_cart.get_session_data()
        session_id = self.firebase.save_session(session_data)
        
        # Display checkout information
        self.show_checkout_popup(session_id)
    
    def show_checkout_popup(self, session_id):
        """Display checkout information"""
        content = BoxLayout(orientation='vertical', padding=10)
        
        # Session info
        total_text = f"Total: ${self.shopping_cart.get_total():.2f}"
        items_text = f"Items: {len(self.shopping_cart.items)}"
        
        info_label = Label(text=f"{total_text}\n{items_text}\n\nSession ID: {session_id}")
        content.add_widget(info_label)
        
        # Display a barcode image (in real app)
        barcode_label = Label(
            text="[Checkout Barcode Here]",
            font_size=24
        )
        content.add_widget(barcode_label)
        
        # Close button
        close_btn = Button(
            text="Done",
            size_hint=(1.0, 0.3)
        )
        content.add_widget(close_btn)
        
        popup = Popup(
            title="Ready for Checkout",
            content=content,
            size_hint=(0.8, 0.8),
            auto_dismiss=False
        )
        
        # When closed, reset cart
        def on_close(instance):
            popup.dismiss()
            self.shopping_cart.clear()
            self.weight_sensor.tare()
            self.update_cart_display()
            
        close_btn.bind(on_press=on_close)
        popup.open()
    
    def show_message_popup(self, title, message):
        """Display a simple message popup"""
        content = BoxLayout(orientation='vertical', padding=10)
        content.add_widget(Label(text=message))
        
        btn = Button(text="OK", size_hint=(1.0, 0.3))
        content.add_widget(btn)
        
        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.5, 0.3),
            auto_dismiss=True
        )
        
        btn.bind(on_press=popup.dismiss)
        popup.open()
        
    def on_stop(self):
        """Clean up when app is closing"""
        self.distance_sensor.stop_simulation()
        self.weight_sensor.stop_simulation()


class ShoppingCart:
    """Manages the shopping cart items and operations"""
    
    def __init__(self):
        self.items = {}  # Dictionary to store items by ID
        self.next_id = 1  # Simple ID generator
    
    def add_item(self, product):
        """Add an item to the cart
        
        Args:
            product: Product dictionary with price and other details
        """
        item_id = self.next_id
        self.items[item_id] = product
        self.next_id += 1
        
    def remove_item(self, item_id):
        """Remove an item from the cart
        
        Args:
            item_id: ID of the item to remove
        """
        if item_id in self.items:
            del self.items[item_id]
    
    def get_total(self):
        """Calculate total price of items in cart"""
        return sum(item['price'] for item in self.items.values())
    
    def is_empty(self):
        """Check if cart is empty"""
        return len(self.items) == 0
    
    def clear(self):
        """Clear all items from cart"""
        self.items = {}
        
    def get_session_data(self):
        """Get data to save for the session
        
        Returns:
            dict: Session data including items and timestamp
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'total': self.get_total(),
            'item_count': len(self.items),
            'items': list(self.items.values())
        }


class SmartCartApp(App):
    """Main application class"""
    
    def build(self):
        self.title = 'Smart Shopping Cart'
        return CartScreen()
    
    def on_stop(self):
        """App is closing, clean up"""
        self.root.on_stop()


if __name__ == '__main__':
    SmartCartApp().run()