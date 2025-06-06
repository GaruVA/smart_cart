import os

# Disable Kivy's argument parser
os.environ['KIVY_NO_ARGS'] = '1'
# Disable Xinput warnings
os.environ['KIVY_NO_XINPUT'] = '1'

import time
import threading
from datetime import datetime
from functools import partial

# Kivy imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.properties import NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle, RoundedRectangle

# Local imports
from utils.firebase_handler import FirebaseHandler
from models.mock_sensors import MockLoadSensor, MockBarcodeScanner
from models.ultrasonic_sensor import UltrasonicSensor
from models.load_sensor import LoadSensor


# Maximize the window on start
Window.maximize()

# Set window size to match typical Raspberry Pi touchscreen (800x480)
Window.size = (800, 480)

# Configure window and keyboard behavior
Window.softinput_mode = "below_target"  # Ensures keyboard doesn't cover the input field
Window.keyboard_anim_args = {'d': .2, 't': 'in_out_expo'}  # Smoother keyboard animation

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
    
    def start_remove_animation(self, *args):
        """Start animation for item removal"""
        anim = Animation(opacity=0, height=0, duration=0.3)
        # Store parent reference before animation starts
        parent = self.parent
        def remove_widget_safely(anim, widget):
            if parent and widget in parent.children:
                parent.remove_widget(widget)
        anim.bind(on_complete=remove_widget_safely)
        anim.start(self)

# Register with Factory so it can be used in the kv file
Factory.register('ItemWidget', cls=ItemWidget)

class CartScreen(BoxLayout):
    """Main screen for the smart cart UI"""
    
    def __init__(self, **kwargs):
        super(CartScreen, self).__init__(**kwargs)
        self.shopping_cart = ShoppingCart()
        
        # Initialize sensors
        self.distance_sensor = UltrasonicSensor()  # Using real ultrasonic sensor
        
        # Use real load sensor instead of mock
        try:
            print("Initializing real load sensor...")
            self.weight_sensor = LoadSensor()
            # Start continuous weight reading for smoother measurements
            self.weight_sensor.start_reading()
        except Exception as e:
            print(f"Error initializing load sensor, falling back to mock: {e}")
            self.weight_sensor = MockLoadSensor()
            # Start weight sensor simulation as fallback
            self.weight_sensor.start_simulation()
            
        self.barcode_scanner = MockBarcodeScanner()
        
        # Firebase handler for product data with fixed cart ID
        self.firebase = FirebaseHandler(cart_id="34tzyyBVfilqXhs2gjw9")
        
        # Start sensor update timer
        Clock.schedule_interval(self.update_sensor_display, 1.0)
        
        # Start connection status check timer (every 10 seconds)
        Clock.schedule_interval(self.update_connection_status, 10.0)
        
        # Initialize the display
        self.update_cart_display()
        
        # Set initial connection status
        self.update_connection_status(0)
        
        # Schedule setting focus to the barcode input
        Clock.schedule_once(self.set_barcode_input_focus, 0.5)
    
    def set_barcode_input_focus(self, dt):
        """Set focus to barcode input field"""
        if hasattr(self.ids, 'barcode_input'):
            self.ids.barcode_input.focus = True
    
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
        content = BoxLayout(orientation='vertical', padding=15, spacing=15)
        
        # Title with divider
        title_box = BoxLayout(orientation='vertical', size_hint_y=None, height='60dp')
        title_label = Label(
            text='Scan Product',
            font_size='24sp',
            size_hint_y=None,
            height='40dp',
            color=get_color_from_hex('#212121'),
            bold=True
        )
        
        # Add divider
        with title_box.canvas.after:
            Color(rgba=get_color_from_hex('#E0E0E0'))
            Rectangle(pos=(title_box.x, title_box.y), size=(title_box.width, 1))
            
        title_box.add_widget(title_label)
        content.add_widget(title_box)
        
        # Input section with background
        input_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height='100dp',
            padding=10
        )
        
        with input_container.canvas.before:
            Color(rgba=get_color_from_hex('#F5F5F5'))
            RoundedRectangle(pos=input_container.pos, size=input_container.size, radius=[5,])
        
        input_label = Label(
            text='Enter barcode:',
            size_hint_y=None,
            height='30dp',
            color=get_color_from_hex('#212121'),
            halign='left'
        )
        input_label.bind(size=input_label.setter('text_size'))
        
        input_field = Factory.CustomInput()
        
        input_container.add_widget(input_label)
        input_container.add_widget(input_field)
        content.add_widget(input_container)
        
        # Sample barcodes section with background
        samples_container = BoxLayout(
            orientation='vertical',
            padding=10,
            spacing=5
        )
        
        with samples_container.canvas.before:
            Color(rgba=get_color_from_hex('#F5F5F5'))
            RoundedRectangle(pos=samples_container.pos, size=samples_container.size, radius=[5,])
        
        samples_title = Label(
            text='Available Products:',
            size_hint_y=None,
            height='30dp',
            color=get_color_from_hex('#212121'),
            halign='left',
            bold=True
        )
        samples_title.bind(size=samples_title.setter('text_size'))
        samples_container.add_widget(samples_title)
        
        # Create a grid for the sample buttons
        from kivy.uix.gridlayout import GridLayout
        barcode_grid = GridLayout(
            cols=2,
            spacing=10,
            size_hint_y=None,
            padding=[0, 10, 0, 0]
        )
        barcode_grid.bind(minimum_height=barcode_grid.setter('height'))
        
        # Get sample barcodes
        sample_barcodes = self.firebase.get_available_barcodes(limit=6)
        
        for barcode in sample_barcodes:
            btn = Factory.SampleBarcodeButton(text=barcode)
            barcode_grid.add_widget(btn)
            
            def create_callback(barcode_text):
                return lambda instance: setattr(input_field, 'text', barcode_text)
            btn.bind(on_press=create_callback(barcode))
        
        samples_container.add_widget(barcode_grid)
        content.add_widget(samples_container)
        
        # Action buttons
        buttons = BoxLayout(size_hint_y=None, height='50dp', spacing=10)
        
        cancel_btn = Factory.CustomButton(
            text='Cancel',
            background_color=get_color_from_hex('#9E9E9E')
        )
        random_btn = Factory.CustomButton(
            text='Random',
            background_color=get_color_from_hex('#2196F3')
        )
        scan_btn = Factory.CustomButton(
            text='Add to Cart',
            background_color=get_color_from_hex('#4CAF50')
        )
        
        buttons.add_widget(cancel_btn)
        buttons.add_widget(random_btn)
        buttons.add_widget(scan_btn)
        
        content.add_widget(buttons)
        
        popup = Factory.CustomPopup(
            title='',
            content=content,
            size_hint=(None, None),
            size=('400dp', '450dp'),
            auto_dismiss=False
        )
        
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
        
        # Start with fade in animation
        content.opacity = 0
        popup.open()
        
        anim = Animation(opacity=1, duration=0.2)
        anim.start(content)
    
    def process_scanned_barcode(self, barcode):
        """Process a scanned barcode with animation"""
        product = self.firebase.get_product_by_barcode(barcode)
        
        if product:
            # Record weight before adding the item
            pre_add_weight = self.weight_sensor.read_weight()
            expected_weight_change = product.get('weight', 0)
            
            # Log the scan activity
            self.firebase.log_cart_activity('scan', {
                'barcode': barcode,
                'product_name': product['name'],
                'price': product['price'],
                'weight_before': pre_add_weight
            })
            
            # Add product to cart
            self.shopping_cart.add_item(product)
            
            # Start monitoring weight changes if this is the first item
            if len(self.shopping_cart.items) == 1:
                # Start weight monitoring only when first item is added
                if hasattr(self.weight_sensor, 'start_monitoring'):
                    self.weight_sensor.start_monitoring()
                    
            # Update weight simulation (for mock sensor)
            if 'weight' in product:
                self.weight_sensor.add_item(product['weight'])
            
            # Create and add new item widget with animation
            item_widget = ItemWidget(
                opacity=0,
                item_id=self.shopping_cart.next_id - 1,
                item_name=product['name'],
                item_price=product['price']
            )
            self.ids.item_list.add_widget(item_widget)
            
            # Animate the new item appearing
            anim = Animation(opacity=1, duration=0.3)
            anim.start(item_widget)
            
            # Update UI
            self.update_cart_display()
            
            # Log weight after adding
            weight_after = self.weight_sensor.read_weight()
            self.firebase.log_cart_activity('weight_change', {
                'product_name': product['name'],
                'weight_before': weight_after - (product.get('weight', 0)),
                'weight_after': weight_after,
                'weight_difference': product.get('weight', 0),
                'distance': self.distance_sensor.read_distance()
            })
            
            # Show success message
            self.show_toast(f"Added {product['name']}")
            
            # Check if weight actually changed
            if 'weight' in product and product['weight'] > 0:
                # Wait for weight sensor to stabilize (10 seconds)
                Clock.schedule_once(lambda dt: self.verify_weight_change(
                    pre_add_weight, 
                    expected_weight_change, 
                    f"Item '{product['name']}' has been added but no corresponding weight change was detected.",
                    1.0  # Threshold in kg (adjust as needed)
                ), 10.0)  # Check after 10 seconds 
            # Update connection status in case network state changed
            self.update_connection_status(0)
    
    def show_toast(self, message, duration=1):
        """Show a temporary message toast"""
        toast = Label(
            text=message,
            size_hint=(None, None),
            pos_hint={'center_x': 0.5, 'y': 0.1},
            font_size='16sp',
            color=(1, 1, 1, 1),
            padding=(20, 10)
        )
        toast.bind(texture_size=toast.setter('size'))
        
        # Add background
        with toast.canvas.before:
            Color(0.2, 0.2, 0.2, 0.8)
            Rectangle(pos=toast.pos, size=toast.size)
        
        # Add to window
        Window.add_widget(toast)
        
        # Animate in
        toast.opacity = 0
        anim = Animation(opacity=1, duration=0.2) + \
               Animation(opacity=1, duration=duration) + \
               Animation(opacity=0, duration=0.2)
        
        def remove_toast(*args):
            Window.remove_widget(toast)
            
        anim.bind(on_complete=remove_toast)
        anim.start(toast)
    
    def update_cart_display(self):
        """Update the UI with cart contents"""
        # Update total
        total = self.shopping_cart.get_total()
        item_count = len(self.shopping_cart.items)
        
        if item_count == 0:
            self.ids.total_label.text = "Cart Empty - Ready to Scan"
            self.ids.total_label.color = get_color_from_hex('#2196F3')  # Set blue color
        elif item_count == 1:
            self.ids.total_label.text = f"Total: ${total:.2f} (1 item)"
            self.ids.total_label.color = (1, 1, 1, 1)  # Reset to white
        else:
            self.ids.total_label.text = f"Total: ${total:.2f} ({item_count} items)"
            self.ids.total_label.color = (1, 1, 1, 1)  # Reset to white
        
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
        """Remove item from cart with animation"""
        item_widgets = [w for w in self.ids.item_list.children if isinstance(w, ItemWidget) and w.item_id == item_id]
        if item_widgets:
            item_widget = item_widgets[0]
            item = self.shopping_cart.items.get(item_id)
            
            if item:
                # Show confirmation popup before removal
                self.show_confirm_removal_popup(item_id, item['name'])
    
    def show_confirm_removal_popup(self, item_id, item_name):
        """Display confirmation popup before removing an item"""
        content = BoxLayout(orientation='vertical', padding=12, spacing=8)
        
        # Title 
        title_label = Label(
            text="Remove Item?",
            font_size='18sp',
            color=get_color_from_hex('#F44336'),  # Red color
            size_hint_y=None,
            height='40dp',
            bold=True
        )
        
        # Message
        message_label = Label(
            text=f"Do you want to remove {item_name} from your cart?",
            font_size='14sp',
            color=get_color_from_hex('#757575'),
            size_hint_y=None,
            height='45dp'
        )
        
        # Action buttons
        buttons = BoxLayout(size_hint_y=None, height='50dp', spacing=10)
        
        cancel_btn = Factory.CustomButton(
            text='Cancel',
            size_hint_x=0.5,
            background_color=get_color_from_hex('#9E9E9E')
        )
        
        confirm_btn = Factory.CustomButton(
            text='Remove',
            size_hint_x=0.5,
            background_color=get_color_from_hex('#F44336')  # Red color
        )
        
        buttons.add_widget(cancel_btn)
        buttons.add_widget(confirm_btn)
        
        content.add_widget(title_label)
        content.add_widget(message_label)
        content.add_widget(buttons)
        
        popup = Factory.CustomPopup(
            title='',
            content=content,
            size_hint=(None, None),
            size=('350dp', '200dp'),
            auto_dismiss=True
        )
        
        # Define button actions
        cancel_btn.bind(on_press=popup.dismiss)
        
        def on_confirm(instance):
            popup.dismiss()
            # Continue with item removal process
            item_widgets = [w for w in self.ids.item_list.children if isinstance(w, ItemWidget) and w.item_id == item_id]
            if item_widgets:
                item_widget = item_widgets[0]
                item = self.shopping_cart.items.get(item_id)
                
                if item:
                    # Remember current weight to verify after removal
                    self.pre_removal_weight = self.weight_sensor.read_weight()
                    self.expected_weight_change = item.get('weight', 0)
                    
                    # Start remove animation
                    item_widget.start_remove_animation()
                    
                    # Remove from shopping cart after animation
                    Clock.schedule_once(
                        lambda dt: self._complete_item_removal(item_id, item),
                        0.3
                    )
        
        confirm_btn.bind(on_press=on_confirm)
        popup.open()
    
    def _complete_item_removal(self, item_id, item):
        """Complete the item removal after animation"""
        # Log item removal
        self.firebase.log_cart_activity('remove', {
            'product_name': item['name'],
            'price': item['price'],
            'weight_before': self.weight_sensor.read_weight()
        })
        
        # Remove from shopping cart
        self.shopping_cart.remove_item(item_id)
        
        # Update weight simulation
        if 'weight' in item:
            self.weight_sensor.remove_item(item['weight'])
        
        # Update UI
        self.update_cart_display()
        
        # Check if weight actually changed
        if hasattr(self, 'pre_removal_weight') and hasattr(self, 'expected_weight_change'):
            # Wait for weight sensor to stabilize (10 seconds)
            Clock.schedule_once(lambda dt: self.verify_weight_change(
                self.pre_removal_weight, 
                -self.expected_weight_change, 
                f"Item '{item['name']}' has been removed but no corresponding weight change was detected.",
                1.0  # Threshold in kg (adjust as needed)
            ), 10.0)  # Check after 10 seconds
        
        # Show removed message
        self.show_toast(f"Removed {item['name']}")
    
    def update_sensor_display(self, dt):
        """Update display with sensor data (called by Clock)"""
        # Update display with readings from real sensors
        try:
            distance = self.distance_sensor.read_distance()
        except Exception as e:
            print(f"Error reading distance: {e}")
            distance = 0.0
            
        try:
            # The weight reading is already averaged in the LoadSensor class
            weight = self.weight_sensor.read_weight()
            
            # Check if we have stable weight that differs from the cart's expected weight
            # This could detect theft or incorrect scanning
            expected_weight = 0
            for item in self.shopping_cart.items.values():
                if 'weight' in item:
                    expected_weight += item['weight']
            
            # Display weight in kg with 2 decimal places for precision
            weight_str = f"Weight: {weight:.2f} kg"
            
            # Add indication if real weight differs significantly from expected weight
            # Only do this if we have items in the cart and expected weights
            significant_diff = 0.1  # kg threshold (100g)
            if expected_weight > 0 and abs(weight - expected_weight) > significant_diff:
                weight_str += f" (Expected: {expected_weight:.2f} kg)"
        except Exception as e:
            print(f"Error reading weight: {e}")
            weight = 0.0
            weight_str = f"Weight: {weight:.2f} kg"
        
        self.ids.sensor_label.text = f"Distance: {distance:.1f} cm | {weight_str}"
    
    def end_session(self, instance=None):
        """End shopping session and generate checkout info"""
        if self.shopping_cart.is_empty():
            self.show_message_popup("Cart is empty", "Please scan items before checkout")
            return
            
        session_data = self.shopping_cart.get_session_data()
        session_id = self.firebase.save_session(session_data)
        
        # Update connection status after trying to save session
        self.update_connection_status(0)
        
        # Log checkout activity
        self.firebase.log_cart_activity('checkout', {
            'total_amount': self.shopping_cart.get_total(),
            'item_count': len(self.shopping_cart.items),
            'session_id': session_id
        })
        
        # Display checkout information
        self.show_checkout_popup(session_id)
    
    def show_checkout_popup(self, session_id):
        """Display checkout information"""
        # Get session data for display
        total = self.shopping_cart.get_total()
        items_count = len(self.shopping_cart.items)
        session_display = session_id[-8:] if len(session_id) > 8 else session_id
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=8)
        
        # Header with payment instructions
        header_label = Label(
            text="Pay with PayPal",
            font_size='18sp',
            color=get_color_from_hex('#000000'),  # Changed to black to match theme
            size_hint_y=None,
            height='30dp',
            bold=True
        )
        
        instruction_label = Label(
            text="Scan this QR code to complete your payment",
            font_size='14sp',
            color=get_color_from_hex('#000000'),  # Changed to black to match theme
            size_hint_y=None,
            height='25dp'
        )
        
        content.add_widget(header_label)
        content.add_widget(instruction_label)
        
        # Generate QR code for session ID
        from kivy.core.image import Image as CoreImage
        from io import BytesIO
        import qrcode
        
        # QR code container with adjusted padding
        qr_container = BoxLayout(
            orientation='vertical',
            padding=8,
            size_hint_y=None,
            height=180,
            pos_hint={'center_x': 0.5}
        )
        
        try:
            # Generate PayPal payment QR code with correct amount
            # Format PayPal payment URL with the total amount
            paypal_base_url = "https://www.paypal.com/qrcodes/p2merchant/"
            
            # Create a clean amount string (remove $ and ensure proper format)
            amount_str = f"{total:.2f}"
            
            # PayPal URL parameters
            # We include:
            # - session_id as the invoice ID for tracking
            # - total amount for payment
            # - prefilled note with cart item count
            paypal_params = f"?invoiceId={session_id}&amount={amount_str}&note=SmartCart%20Payment%20({items_count}%20items)"
            
            # Complete PayPal payment URL
            paypal_payment_url = paypal_base_url + paypal_params
            
            # Generate QR code with PayPal payment URL
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium error correction for payment QR
                box_size=6,
                border=2,
            )
            qr.add_data(paypal_payment_url)
            qr.make(fit=True)
            
            # Create an image from the QR code
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")
            buffer.seek(0)
            
            qr_texture = CoreImage(BytesIO(buffer.read()), ext="png").texture
            
            from kivy.uix.image import Image
            qr_image = Image(
                texture=qr_texture,
                size_hint=(None, None),
                size=(150, 150),
                pos_hint={'center_x': 0.5}
            )
            qr_container.add_widget(qr_image)
        except Exception as e:
            print(f"QR code generation failed: {e}")
            qr_image = Label(
                text="[Checkout Barcode]",
                font_size='18sp',
                size_hint_y=None,
                height=150
            )
            qr_container.add_widget(qr_image)
        
        content.add_widget(qr_container)
        
        # Session summary - reduced spacing
        summary_box = BoxLayout(
            orientation='vertical',
            padding=8,  # Reduced padding
            spacing=4,  # Reduced spacing
            size_hint_y=None,
            height=100  # Reduced height
        )
        
        total_label = Label(
            text=f"Total Amount: ${total:.2f}",
            color=get_color_from_hex('#FFFFFF'),  # Changed to white for popup
            font_size='16sp',  # Reduced font
            bold=True,
            size_hint_y=None,
            height='30dp'  # Reduced height
        )
        
        items_label = Label(
            text=f"Items: {items_count}",
            color=get_color_from_hex('#FFFFFF'),  # Changed to white for popup
            font_size='14sp',  # Reduced font
            size_hint_y=None,
            height='25dp'  # Reduced height
        )
        
        session_label = Label(
            text=f"Session ID: {session_display}",
            color=get_color_from_hex('#FFFFFF'),  # Changed to white for popup
            font_size='14sp',  # Reduced font
            size_hint_y=None,
            height='25dp'  # Reduced height
        )
        
        if session_id.startswith("offline"):
            offline_label = Label(
                text="(Running in offline mode)",
                color=get_color_from_hex('#F44336'),
                font_size='12sp',  # Reduced font
                size_hint_y=None,
                height='20dp'  # Reduced height
            )
            summary_box.add_widget(offline_label)
        
        summary_box.add_widget(total_label)
        summary_box.add_widget(items_label)
        summary_box.add_widget(session_label)
        content.add_widget(summary_box)
        
        # Done button with minimal spacing
        done_btn = Factory.CustomButton(
            text="Done",
            size_hint=(0.6, None),  # Reduced width
            height='40dp',  # Reduced height
            pos_hint={'center_x': 0.5}
        )
        
        # Minimal spacing before button
        spacing_widget = Widget(size_hint_y=None, height='8dp')  # Reduced spacing
        content.add_widget(spacing_widget)
        content.add_widget(done_btn)
        
        # Create and show popup with adjusted size
        popup = Factory.CustomPopup(
            title='',
            content=content,
            size_hint=(None, None),
            size=(350, 400),  # Reduced size
            auto_dismiss=False
        )
        
        def on_close(instance):
            popup.dismiss()
            self.shopping_cart.clear()
            
            # Stop monitoring and reset weight sensor
            if hasattr(self.weight_sensor, 'stop_monitoring'):
                self.weight_sensor.stop_monitoring()
                
            # Tare the scale for next session
            self.weight_sensor.tare()
            
            # Update UI
            self.update_cart_display()
            
        done_btn.bind(on_press=on_close)
        popup.open()
    
    def show_message_popup(self, title, message):
        """Display a simple message popup with Material Design styling"""
        content = BoxLayout(orientation='vertical', padding=12, spacing=8)
        
        # Title with updated styling
        title_label = Label(
            text=title,
            font_size='18sp',
            color=get_color_from_hex('#2196F3'),
            size_hint_y=None,
            height='40dp',
            bold=True
        )
        
        # Message
        message_label = Label(
            text=message,
            font_size='14sp',
            color=get_color_from_hex('#757575'),
            size_hint_y=None,
            height='45dp'
        )
        
        # OK button
        ok_btn = Factory.CustomButton(
            text="OK",
            size_hint=(0.4, None),
            height='40dp',
            pos_hint={'center_x': 0.5}
        )
        
        content.add_widget(title_label)
        content.add_widget(message_label)
        content.add_widget(ok_btn)
        
        popup = Factory.CustomPopup(
            title='',
            content=content,
            size_hint=(None, None),
            size=(300, 160),
            auto_dismiss=True
        )
        
        def on_close(instance):
            anim = Animation(opacity=0, duration=0.2)
            anim.bind(on_complete=lambda *x: popup.dismiss())
            anim.start(content)
            
        ok_btn.bind(on_press=on_close)
        
        content.opacity = 0
        popup.open()
        
        anim = Animation(opacity=1, duration=0.2)
        anim.start(content)
        
    def on_stop(self):
        """Clean up when app is closing"""
        # Clean up sensors properly
        if hasattr(self.distance_sensor, 'cleanup'):
            self.distance_sensor.cleanup()
        elif hasattr(self.distance_sensor, 'stop_simulation'):
            self.distance_sensor.stop_simulation()
            
        # Proper cleanup for weight sensor (real or mock)
        if hasattr(self.weight_sensor, 'cleanup'):
            self.weight_sensor.cleanup()
        elif hasattr(self.weight_sensor, 'stop_simulation'):
            self.weight_sensor.stop_simulation()
            
        # Stop monitoring and continuous reading if available
        if hasattr(self.weight_sensor, 'stop_monitoring'):
            self.weight_sensor.stop_monitoring()
            
        if hasattr(self.weight_sensor, 'stop_reading'):
            self.weight_sensor.stop_reading()
    
    def verify_weight_change(self, previous_weight, expected_change, warning_message, threshold=0.1):
        """Verify that the weight has changed as expected
        
        Args:
            previous_weight (float): Weight before the change
            expected_change (float): Expected weight change (positive for addition, negative for removal)
            warning_message (str): Message to show if weight change is not detected
            threshold (float): Minimum weight change to consider valid (in kg)
        """
        current_weight = self.weight_sensor.read_weight()
        actual_change = current_weight - previous_weight
        
        # Check if the actual change is close to the expected change
        # For real-world use, we use a threshold to account for sensor variations
        if abs(actual_change - expected_change) > threshold:
            # Weight did not change as expected
            self.show_weight_warning_popup(warning_message, 
                                          f"Expected change: {expected_change:.2f} kg\nActual change: {actual_change:.2f} kg")
    
    def show_weight_warning_popup(self, title, message):
        """Display a warning popup for weight inconsistencies"""
        content = BoxLayout(orientation='vertical', padding=12, spacing=8)
        
        # Title with warning styling
        title_label = Label(
            text=title,
            font_size='18sp',
            color=get_color_from_hex('#FF9800'),  # Orange warning color
            size_hint_y=None,
            height='60dp',  # Increased for multi-line
            bold=True
        )
        title_label.bind(size=title_label.setter('text_size'))  # Enable text wrapping
        
        # Message
        message_label = Label(
            text=message,
            font_size='14sp',
            color=get_color_from_hex('#757575'),
            size_hint_y=None,
            height='80dp'  # Increased for multi-line
        )
        message_label.bind(size=message_label.setter('text_size'))  # Enable text wrapping
        
        # OK button
        ok_btn = Factory.CustomButton(
            text="OK",
            size_hint=(0.4, None),
            height='40dp',
            pos_hint={'center_x': 0.5},
            background_color=get_color_from_hex('#FF9800')  # Orange warning color
        )
        
        content.add_widget(title_label)
        content.add_widget(message_label)
        content.add_widget(ok_btn)
        
        popup = Factory.CustomPopup(
            title='',
            content=content,
            size_hint=(None, None),
            size=(350, 200),
            auto_dismiss=True
        )
        
        def on_close(instance):
            anim = Animation(opacity=0, duration=0.2)
            anim.bind(on_complete=lambda *x: popup.dismiss())
            anim.start(content)
            
        ok_btn.bind(on_press=on_close)
        
        content.opacity = 0
        popup.open()
        
        anim = Animation(opacity=1, duration=0.2)
        anim.start(content)
        

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
        self.firebase_handler = FirebaseHandler(cart_id="34tzyyBVfilqXhs2gjw9")
        self.ultrasonic_sensor = UltrasonicSensor()  # Using real ultrasonic sensor
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
    
    def process_barcode(self, barcode_text, *args):
        """Process barcode input from the textbox"""
        if self.root and barcode_text.strip():
            # Clear the input field
            self.root.ids.barcode_input.text = ""
            # Process the barcode
            self.root.process_scanned_barcode(barcode_text.strip())
    
    def on_stop(self):
        """App is closing, clean up"""
        self.root.on_stop()


if __name__ == '__main__':
    SmartCartApp().run()