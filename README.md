# Parking Management System

A web-based parking management system with user and admin dashboards, QR code generation, and real-time parking slot tracking.

## Features

- User Authentication (Admin and Regular Users)
- Real-time parking slot availability
- QR code generation for bookings
- Admin verification system
- Multiple parking areas with different vehicle types
- Booking management
- Responsive design

## Prerequisites

- Python 3.7+
- pip (Python package manager)

## Installation

1. Clone the repository
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

5. Access the application at `http://localhost:5000`

## Default Parking Areas

- Girls Hostel Frontside: 50 bus spots
- 8th Block Frontside: 30 two-wheeler spots, 10 four-wheeler spots
- Admin Block: 30 two-wheeler spots, 10 four-wheeler spots
- 11th Block: 10 bus spots
- Polytechnic Block: 20 two-wheeler spots, 10 four-wheeler spots

## Usage

1. Login as admin or user
2. Users can:
   - View available parking spots
   - Book parking spots
   - View their bookings and QR codes
3. Admins can:
   - View all bookings
   - Verify bookings using QR codes
   - Monitor parking area usage
#   P a r k i n g - S y s t e m  
 #   P a r k i n g - S y s t e m  
 