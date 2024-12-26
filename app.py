from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_mongoengine import MongoEngine
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import qrcode
import base64
from io import BytesIO
import os
from bson import ObjectId

app = Flask(__name__,
           template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates')),
           static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), 'static')))
app.config['SECRET_KEY'] = 'your-secret-key'

# MongoDB settings
app.config['MONGODB_SETTINGS'] = {
    'db': 'parking_system',
    'host': 'localhost',
    'port': 27017
}

db = MongoEngine(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Document):
    username = db.StringField(unique=True, required=True, max_length=80)
    password_hash = db.StringField(required=True)
    is_admin = db.BooleanField(default=False)
    meta = {'collection': 'users'}

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)

class ParkingArea(db.Document):
    name = db.StringField(required=True, max_length=100)
    latitude = db.FloatField(required=True)
    longitude = db.FloatField(required=True)
    meta = {'collection': 'parking_areas'}

    @property
    def total_bus(self):
        return ParkingSpot.objects(area=self, vehicle_type='bus').count()
    
    @property
    def total_two_wheeler(self):
        return ParkingSpot.objects(area=self, vehicle_type='two_wheeler').count()
    
    @property
    def total_four_wheeler(self):
        return ParkingSpot.objects(area=self, vehicle_type='four_wheeler').count()

    @property
    def available_bus(self):
        return ParkingSpot.objects(area=self, vehicle_type='bus', is_occupied=False).count()
    
    @property
    def available_two_wheeler(self):
        return ParkingSpot.objects(area=self, vehicle_type='two_wheeler', is_occupied=False).count()
    
    @property
    def available_four_wheeler(self):
        return ParkingSpot.objects(area=self, vehicle_type='four_wheeler', is_occupied=False).count()

class ParkingSpot(db.Document):
    area = db.ReferenceField(ParkingArea, required=True)
    vehicle_type = db.StringField(required=True)  # 'two_wheeler', 'four_wheeler', 'bus'
    is_occupied = db.BooleanField(default=False)
    meta = {'collection': 'parking_spots'}

class Booking(db.Document):
    user = db.ReferenceField(User, required=True)
    spot = db.ReferenceField(ParkingSpot, required=True)
    vehicle_number = db.StringField(required=True, max_length=20)
    booking_time = db.DateTimeField(default=datetime.utcnow)
    start_date = db.DateTimeField(required=True)
    end_date = db.DateTimeField(required=True)
    duration = db.IntField(required=True)  # Duration in hours
    qr_code = db.StringField()
    is_verified = db.BooleanField(default=False)
    meta = {'collection': 'bookings'}

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.objects(id=ObjectId(user_id)).first()
    except:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([username, password, confirm_password]):
            flash('All fields are required')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('register.html')
        
        if User.objects(username=username).first():
            flash('Username already exists')
            return render_template('register.html')
        
        user = User(username=username)
        user.set_password(password)
        user.save()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.objects(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_admin:
                login_user(user)
                return redirect(url_for('user_dashboard'))
            else:
                flash('Please use admin login for admin accounts')
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.objects(username=username).first()
        
        if user and user.check_password(password):
            if user.is_admin:
                login_user(user)
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Access denied. Admin privileges required.')
        else:
            flash('Invalid username or password')
    return render_template('admin_login.html')

@app.route('/dashboard')
@login_required
def user_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    areas = list(ParkingArea.objects.all())
    user_bookings = Booking.objects(user=current_user)
    return render_template('user_dashboard.html', areas=areas, bookings=user_bookings)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('user_dashboard'))
    
    areas = ParkingArea.objects.all()
    area_stats = []
    
    for area in areas:
        # Get spots in this area
        spots = ParkingSpot.objects(area=area)
        spot_ids = [spot.id for spot in spots]
        
        # Get bookings for spots in this area
        area_bookings = Booking.objects(spot__in=spot_ids)
        
        total_spots = sum([
            area.total_bus if hasattr(area, 'total_bus') else 0,
            area.total_two_wheeler if hasattr(area, 'total_two_wheeler') else 0,
            area.total_four_wheeler if hasattr(area, 'total_four_wheeler') else 0
        ])
        occupied_spots = spots.filter(is_occupied=True).count()
        
        area_stats.append({
            'area': area,
            'bookings': area_bookings,
            'total_spots': total_spots,
            'occupied_spots': occupied_spots,
            'available_spots': total_spots - occupied_spots,
            'total_bookings': area_bookings.count(),
            'verified_bookings': area_bookings.filter(is_verified=True).count(),
            'pending_bookings': area_bookings.filter(is_verified=False).count()
        })
    
    return render_template('admin_dashboard.html', area_stats=area_stats)

@app.route('/admin/verify_booking/<booking_id>')
@login_required
def admin_verify_booking(booking_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'})
    
    try:
        booking = Booking.objects(id=ObjectId(booking_id)).first()
        if not booking:
            return jsonify({'error': 'Booking not found'})
        
        booking.is_verified = True
        booking.save()
        return jsonify({'success': True, 'message': 'Booking verified successfully'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/admin/cancel_booking/<booking_id>')
@login_required
def admin_cancel_booking(booking_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'})
    
    try:
        booking = Booking.objects(id=ObjectId(booking_id)).first()
        if not booking:
            return jsonify({'error': 'Booking not found'})
        
        # Free up the parking spot
        spot = booking.spot
        spot.is_occupied = False
        spot.save()
        
        # Delete the booking
        booking.delete()
        return jsonify({'success': True, 'message': 'Booking cancelled successfully'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/book_spot', methods=['POST'])
@login_required
def book_spot():
    if current_user.is_admin:
        return jsonify({'error': 'Admins cannot book spots'})

    try:
        area_id = request.form.get('area_id')
        vehicle_type = request.form.get('vehicle_type')
        vehicle_number = request.form.get('vehicle_number')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%dT%H:%M')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%dT%H:%M')

        # Validate dates
        if start_date < datetime.now():
            return jsonify({'error': 'Start date must be in the future'})
        if end_date <= start_date:
            return jsonify({'error': 'End date must be after start date'})

        # Find available spot
        try:
            area = ParkingArea.objects(id=ObjectId(area_id)).first()
        except:
            return jsonify({'error': 'Invalid parking area ID'})

        if not area:
            return jsonify({'error': 'Invalid parking area'})

        spot = ParkingSpot.objects(area=area, vehicle_type=vehicle_type, is_occupied=False).first()
        if not spot:
            return jsonify({'error': 'No available spots of this type'})

        # Calculate duration in hours
        duration = (end_date - start_date).total_seconds() / 3600

        # Create booking
        booking = Booking(
            user=current_user,
            spot=spot,
            vehicle_number=vehicle_number,
            start_date=start_date,
            end_date=end_date,
            duration=int(duration)
        ).save()  # Save immediately to get the ID

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr_data = f"Booking ID: {booking.id}\nUser: {current_user.username}\nVehicle: {vehicle_number}\nArea: {area.name}\nStart: {start_date}\nEnd: {end_date}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert QR code to base64
        buffered = BytesIO()
        qr_img.save(buffered)
        booking.qr_code = base64.b64encode(buffered.getvalue()).decode()
        
        # Mark spot as occupied and save booking
        spot.is_occupied = True
        spot.save()
        booking.save()

        return jsonify({
            'message': 'Spot booked successfully!',
            'qr_code': booking.qr_code
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/cancel_booking/<booking_id>')
@login_required
def cancel_booking(booking_id):
    try:
        try:
            booking = Booking.objects(id=ObjectId(booking_id)).first()
        except:
            flash('Invalid booking ID')
            return redirect(url_for('user_dashboard'))

        if not booking:
            flash('Booking not found')
            return redirect(url_for('user_dashboard'))
        
        if str(booking.user.id) != str(current_user.id) and not current_user.is_admin:
            flash('Not authorized')
            return redirect(url_for('user_dashboard'))
        
        # Free up the spot
        spot = booking.spot
        spot.is_occupied = False
        spot.save()
        
        # Delete the booking
        booking.delete()
        
        flash('Booking cancelled successfully')
        return redirect(url_for('user_dashboard' if not current_user.is_admin else 'admin_dashboard'))
    except Exception as e:
        flash(f'Error: {str(e)}')
        return redirect(url_for('user_dashboard'))

@app.route('/verify_booking/<booking_id>')
@login_required
def verify_booking(booking_id):
    try:
        if not current_user.is_admin:
            flash('Only admins can verify bookings')
            return redirect(url_for('user_dashboard'))
        
        try:
            booking = Booking.objects(id=ObjectId(booking_id)).first()
        except:
            flash('Invalid booking ID')
            return redirect(url_for('admin_dashboard'))

        if booking:
            booking.is_verified = True
            booking.save()
            flash('Booking verified successfully')
        else:
            flash('Booking not found')
        
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Error: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Drop all collections to start fresh
    User.objects.delete()
    ParkingArea.objects.delete()
    ParkingSpot.objects.delete()
    Booking.objects.delete()
    
    # Create default admin user if it doesn't exist
    admin = User(username='admin', is_admin=True)
    admin.set_password('admin123')
    admin.save()
    print("Admin user created - Username: admin, Password: admin123")
    
    # Create default user if it doesn't exist
    default_user = User(username='user')
    default_user.set_password('user123')
    default_user.save()
    print("Default user created - Username: user, Password: user123")
    
    # Create parking areas if they don't exist
    areas = [
        {
            'name': 'Girls Hostel Front',
            'latitude': 13.0827,
            'longitude': 80.2707,
            'spots': [{'type': 'bus', 'count': 50}]
        },
        {
            'name': '8th Block Front',
            'latitude': 13.0828,
            'longitude': 80.2708,
            'spots': [
                {'type': 'two_wheeler', 'count': 30},
                {'type': 'four_wheeler', 'count': 10}
            ]
        },
        {
            'name': 'Admin Block',
            'latitude': 13.0829,
            'longitude': 80.2709,
            'spots': [
                {'type': 'two_wheeler', 'count': 30},
                {'type': 'four_wheeler', 'count': 10}
            ]
        },
        {
            'name': 'Tifac Core',
            'latitude': 13.0830,
            'longitude': 80.2710,
            'spots': [
                {'type': 'two_wheeler', 'count': 20},
                {'type': 'four_wheeler', 'count': 5}
            ]
        },
        {
            'name': '11th Block',
            'latitude': 13.0831,
            'longitude': 80.2711,
            'spots': [{'type': 'bus', 'count': 10}]
        },
        {
            'name': 'Polytechnic Block',
            'latitude': 13.0832,
            'longitude': 80.2712,
            'spots': [
                {'type': 'two_wheeler', 'count': 20},
                {'type': 'four_wheeler', 'count': 10}
            ]
        }
    ]
    
    # Create areas and their spots
    for area_data in areas:
        area = ParkingArea(
            name=area_data['name'],
            latitude=area_data['latitude'],
            longitude=area_data['longitude']
        ).save()
        
        # Create spots for this area
        for spot_data in area_data['spots']:
            for _ in range(spot_data['count']):
                ParkingSpot(
                    area=area,
                    vehicle_type=spot_data['type']
                ).save()
        
        print(f"Created {area_data['name']} with spots:")
        for spot_data in area_data['spots']:
            print(f"- {spot_data['count']} {spot_data['type']} spots")
    
    print("All parking areas and spots created successfully!")
    
    app.run(debug=True)
