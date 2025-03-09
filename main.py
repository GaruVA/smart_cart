import os

# Disable Kivy's argument parser
os.environ['KIVY_NO_ARGS'] = '1'

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
from kivy.properties import NumericProperty, StringProperty

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

class ItemWidget(BoxLayout):
    """Widget for displaying individual items in the cart"""
    item_id = NumericProperty(0)
    item_name = StringProperty('')
    item_price = NumericProperty(0.0)

# Register with Factory so it can be used in the kv file
Factory.register('ItemWidget', cls=ItemWidget)

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
        
        # Start connection status check timer (every 10 seconds)
        Clock.schedule_interval(self.update_connection_status, 10.0)
        
        # Initialize the display
        self.update_cart_display()
        
        # Set initial connection status
        self.update_connection_status(0)
    
    def update_connection_status(self, dt):
        """Update connection status display"""
        if not hasattr(self.firebase, 'offline_mode'):
            # If Firebase handler doesn't have the attribute, assume offline
            self.ids.connection_status.text = 'Offline'
            return
        
        # Only do a connection test every few updates to avoid excessive checks
        if dt > 0 and int(time.time()) % 30 != 0:
            # Just show current status without testing
            self.ids.connection_status.text = 'Offline' if self.firebase.offline_mode else 'Online'
            return
        
        # Test connection and update status
        if self.firebase.test_connection():
            self.ids.connection_status.text = 'Online'
        else:
            self.ids.connection_status.text = 'Offline'
    
    def scan_item(self, instance=None):
        """Handle item scanning"""
        # In development mode, use a popup to enter barcode
        # In production, this would interface with the actual scanner
        self.show_barcode_input()
    
    def show_barcode_input(self):
        """Show popup for entering barcode manually (for development)"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=5)
        
        input_label = Label(text='Enter barcode:', size_hint_y=None, height=30)
        input_field = TextInput(multiline=False, size_hint_y=None, height=40)
        
        # Get sample barcodes from the firebase handler
        sample_barcodes = self.firebase.get_available_barcodes(limit=5)
        
        # Create sample barcode buttons
        samples_box = BoxLayout(orientation='vertical', spacing=2, size_hint_y=None, height=120)
        samples_title = Label(text='Sample barcodes:', size_hint_y=None, height=20, halign='left')
        samples_title.bind(size=samples_title.setter('text_size'))
        samples_box.add_widget(samples_title)
        
        # Create a grid for the sample buttons
        from kivy.uix.gridlayout import GridLayout
        barcode_grid = GridLayout(cols=2, spacing=4, size_hint_y=None)
        barcode_grid.bind(minimum_height=barcode_grid.setter('height'))
        
        for barcode in sample_barcodes:
            barcode_btn = Button(
                text=barcode, 
                size_hint_y=None, 
                height=30
            )
            barcode_grid.add_widget(barcode_btn)
            
            # Bind to set the text field when clicked
            def create_callback(barcode_text):
                return lambda instance: setattr(input_field, 'text', barcode_text)
            barcode_btn.bind(on_press=create_callback(barcode))
        
        # Add grid to samples box
        samples_box.add_widget(barcode_grid)
        
        buttons = BoxLayout(size_hint_y=None, height=50, spacing=10)
        random_btn = Button(text='Random')
        scan_btn = Button(text='Scan')
        cancel_btn = Button(text='Cancel')
        
        buttons.add_widget(random_btn)
        buttons.add_widget(scan_btn)
        buttons.add_widget(cancel_btn)
        
        content.add_widget(input_label)
        content.add_widget(input_field)
        content.add_widget(samples_box)
        content.add_widget(buttons)
        
        popup = Popup(title='Scan Item', content=content, size_hint=(0.8, 0.6))
        
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
            
            # Update connection status in case network state changed
            self.update_connection_status(0)
    
    def update_cart_display(self):
        """Update the UI with cart contents"""
        # Update total
        total = self.shopping_cart.get_total()
        item_count = len(self.shopping_cart.items)
        
        if item_count == 0:
            self.ids.total_label.text = "Cart Empty - Ready to Scan"
        elif item_count == 1:
            self.ids.total_label.text = f"Total: ${total:.2f} (1 item)"
        else:
            self.ids.total_label.text = f"Total: ${total:.2f} ({item_count} items)"
        
        # Clear and rebuild items list
        self.ids.item_list.clear_widgets()
        
        # Add items
        for item_id, item in self.shopping_cart.items.items():
            item_widget = ItemWidget(
                item_id=item_id,
                item_name=item['name'],
                item_price=item['price']
            )
            self.ids.item_list.add_widget(item_widget)
    
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
    
    def end_session(self, instance=None):
        """End shopping session and generate checkout info"""
        if self.shopping_cart.is_empty():
            self.show_message_popup("Cart is empty", "Please scan items before checkout")
            return
            
        session_data = self.shopping_cart.get_session_data()
        session_id = self.firebase.save_session(session_data)
        
        # Update connection status after trying to save session
        self.update_connection_status(0)
        
        # Display checkout information
        self.show_checkout_popup(session_id)
    
    def show_checkout_popup(self, session_id):
        """Display checkout information"""
        content = BoxLayout(orientation='vertical', padding=10)
        
        # Session info
        total = self.shopping_cart.get_total()
        items_count = len(self.shopping_cart.items)
        
        # Format session ID to make it more readable
        if session_id.startswith("offline-session"):
            session_display = "OFFLINE-" + session_id[-6:]
            full_session_id = session_id  # Offline ID is already the full ID
        else:
            # For Firebase IDs, we're just showing the last part for display purposes
            # The full ID is still stored in Firestore
            session_display = session_id[-8:] if len(session_id) > 8 else session_id
            full_session_id = session_id  # Store the full Firebase ID
        
        header_label = Label(
            text="Checkout Complete",
            font_size=24,
            size_hint_y=0.2
        )
        content.add_widget(header_label)
        
        # Generate QR code for session ID
        from kivy.core.image import Image as CoreImage
        from io import BytesIO
        import qrcode
        
        # Create QR code
        try:
            # Generate QR code with session ID
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(full_session_id)
            qr.make(fit=True)
            
            # Create an image from the QR code
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR to bytes buffer
            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")
            buffer.seek(0)
            
            # Create Kivy image from buffer
            qr_texture = CoreImage(BytesIO(buffer.read()), ext="png").texture
            
            # Use an Image widget instead of Label for QR display
            from kivy.uix.image import Image
            qr_image = Image(texture=qr_texture, size_hint=(1, None), height=200)
        except Exception as e:
            # Fallback to text if QR generation fails
            print(f"QR code generation failed: {e}")
            qr_image = Label(
                text="[Checkout Barcode]",
                font_size=24,
                size_hint_y=0.2
            )
        
        # Session summary
        summary_text = f"Total Amount: ${total:.2f}\n"
        summary_text += f"Items: {items_count}\n\n"
        summary_text += f"Session ID: {session_display}"
        
        if full_session_id != session_display:
            summary_text += f"\n(Shortened from {full_session_id})"
        
        if session_id.startswith("offline"):
            summary_text += "\n\n(Running in offline mode)"
        
        info_label = Label(
            text=summary_text,
            halign='center',
            valign='middle',
            size_hint_y=0.5
        )
        content.add_widget(info_label)
        
        # Add QR code to the popup
        content.add_widget(qr_image)
        
        # Close button
        close_btn = Button(
            text="Done",
            size_hint=(0.8, 0.2),
            pos_hint={'center_x': 0.5}
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
        self.firebase_handler = FirebaseHandler()
        self.ultrasonic_sensor = MockUltrasonicSensor()
        self.load_sensor = MockLoadSensor()
        self.barcode_scanner = MockBarcodeScanner()
        self.title = 'Smart Shopping Cart'
        return CartScreen()
    
    def scan_item(self, *args):
        """Proxy to CartScreen's scan_item method"""
        if self.root:
            self.root.scan_item()
    
    def checkout(self, *args):
        """Proxy to CartScreen's end_session method"""
        if self.root:
            self.root.end_session()
    
    def on_stop(self):
        """App is closing, clean up"""
        self.root.on_stop()


if __name__ == '__main__':
    SmartCartApp().run()