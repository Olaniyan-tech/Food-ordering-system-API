# Multi-Vendor Food Ordering Saas - API

## 🔹 Project Overview

Food Ordering SaaS API is a scalable multi-vendor backend built with Django REST Framework. It enables multiple vendors (restaurants) to onboard, manage their menus, and handle customer orders, while users can browse and order from different vendors in one platform.

The system uses JWT authentication with secure cookie-based storage and is designed for scalability, modularity, and real-world production use

## 🔹 User Features

   - User registration and authentication (JWT + cookies)
   
   - Secure token refresh and logout 
   
   - Browse food items across multiple vendors
   
   - View vendor profiles and menus
   
   - Adding items to cart (with quantity)
   
   - Updating cart items (increase, decrease, delete)
   
   - Place orders per vendor 
   
   - Checkout with address and phone number submission
   
   - Cancel pending orders
   
   - Leave reviews for orders and vendors
   
## 🔹 Vendor Features

   - Vendor registration and onboarding
   
   - Vendor profile management (store info, location, etc.) 
   
   - Add, update, and delete food items
   
   - Manage menu categories
   
   - Toggle food availability (in stock / out of stock)
   
   - View and manage incoming orders
   
   - Update order status (e.g preparing → ready → cancel) 
   
   - View customer reviews and ratings
   
## 🔹 Admin Features

   - Approve or reject vendor registrations
   
   - Manage users and vendors 
   
   - Monitor platform activity (orders, payments)
   
   - Handle disputes and reports

## 🔹 Payment & Orders

   - Automatic calculation of order totals
   
   - Payment integration and verification

## 🔹 System & Architecture Features

   - Service layer architecture (clean separation of logic)
   
   - Background task processing (Celery + Redis)
      - Order notifications
      - Payment verifications
   
   - Scalable API design for frontend/mobile integration
   
   - Secure authentication (JWT with refresh & logout)




##  🔹 Installation

1. Clone the repository
   ```bash
   git clone https://github.com/Olaniyan-tech/Food-ordering-system-API.git
   cd Food-ordering-system-API

2. Create a virtual environment
   ```bash
   python -m venv venv

3. Activate the virtual environment
   ```bash
   venv\Scripts\activate

5. Install dependencies
   ```bash
   pip install -r requirements.txt

7. Run migrations
   ```bash
   python manage.py migrate

6. Start the server
   ```bash
   python manage.py runserver


---


## 🔹 API Endpoints

### Authentication

| Endpoint | Method | Description |
|--------|--------|------------|
| `/api/accounts/register/` | POST | Register a new user |
| `/api/accounts/login/` | POST | Login user and set JWT cookies |
| `/api/accounts/token/refresh/` | POST | Refresh access token using refresh cookie |
| `/api/accounts/logout/` | POST | Logout user and blacklist refresh token |
| `/api/users/profile/` | POST | Retrieve logged-in user's profile |

### Menu & Orders

| Endpoint | Method | Description |
|--------|--------|------------|
| `/api/menu/` | GET | Retrieve all available food items |
| `/api/add_to_cart/` | POST | Add or increase quantity of food in cart |
| `/api/my-orders/` | GET | Lists all orders of the logged-in user |
| `/api/remove/` | POST | Decrease or delete pending items from cart|
| `/api/cancel/` | DELETE | Cancel all items in the pending cart |
| `/api/order/details/update/` | PATCH | Update order delivery details (address & phone) |
| `/api/checkout/` | POST | Checkout current cart, finalize order |
| `/api/order/<int:order_id>/details/` | GET | Check the details of the current order |
| `/api/order/<int:order_id>/pay/` | POST | Initialize payment for the checked out order | 
| `/api/order/verify/<str:reference>/` | GET | Verify the payment for the order | 
| `/api/order/<int:order_id>/review/` | POST | Submit reviews for completed orders |
| `/api/order/<int:order_id>/review/update/` | PATCH | Update order reviews |
| `/api/order/<int:order_id>/review/detail/` | GET | Get a detail of a particular review |
| `/api/foods/<int:food_id>/reviews/` | GET | View all reviews for a food item |


## Example Requests

### Register User

POST /api/users/register/  
Content-Type: application/json

```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "phone": "+2348096753421",
  "password": "yourpassword"
}
```

- Success Response (201 Created):
  ```json
  {
  "message": "Account created successfully. Please log in to continue",
  "username": "john_doe",
  "email": "john@example.com",
  "phone": "+2348096753421"
   }
  ```
- Error Response (400 Bad Request – e.g., email or phone already exists):
  ```json
  {
  "message": "Registration failed. Check input.",
  "errors": {
    "email": ["Email already exists."],
    "phone": ["Phone number already exists."]
   }
  }
  ```

### Login User

POST /api/users/login/
Content-Type: application/json

```json
{
  "username": "john_doe",
  "password": "yourpassword"
}
```

- Success Response (201 Created):
  ```json
  {
    "message": "Login successful"
   }
  ```
🔹Access and refresh tokens are set in HTTP-only cookies automatically.

### Menu List
GET /api/menu/

```json
[
  {
    "id": 1,
    "name": "Jollof Rice",
    "price": 300.00,
    "descriptions": "Spicy Nigerian rice dish",
    "image_url": "https://example.com/images/jollof.jpg",
    "category": "Main Course"
  },
  {
    "id": 2,
    "name": "Pounded Yam",
    "price": 500.00,
    "descriptions": "Traditional Nigerian dish",
    "image_url": "https://example.com/images/pounded_yam.jpg",
    "category": "Main Course"
  }
]
```

### Add to Cart

POST /api/cart/add/
Content-Type: application/json

```json
{
  "food": 1,
  "quantity": 2
}
```
- Success Response (201 Created):
  ```json
  {
  "id": 1,
  "user": "john_doe",
  "address": "",
  "phone": "",
  "total": 1200.00,
  "status": "pending",
  "date_created": "2026-03-02T18:45:00Z",
  "items": [
    {
      "id": 1,
      "food": {
        "id": 1,
        "name": "Jollof Rice",
        "price": 300.00,
        "descriptions": "Spicy Nigerian rice dish",
        "image_url": "https://example.com/images/jollof.jpg",
        "category": "Main Course"
      },
      "quantity": 2,
      "price_at_purchase": 600.00,
      "subtotal": 1200.00
     }
   ]
  }
  ```

### Remove from Cart

POST /api/cart/remove/
Content-Type: application/json

```json
{
  "item_id": 1,
  "action": "decrease"  or  "delete"
}
```
- Success Response (200 OK):
  Decrease quantity from 2 to 1
  
  ```json
  
    {
      "id": 1,
      "user": "john_doe",
      "total": 300.00,
      "status": "pending",
      "items": [
        {
          "id": 1,
          "food": { "id": 1, "name": "Jollof Rice", "price": 300.00 },
          "quantity": 1,
          "price_at_purchase": 300.00,
          "subtotal": 300
        }
      ]
    }
  ```

### Cancel Cart

DELETE /api/cart/cancel/

- Success Response (200 OK):
  ```json
  {
  "message": "Cart cancelled successfully"
  }
  ```

### Update Order Details

PATCH /api/order/details/
Content-Type: application/json

```json
{
  "address": "Osun State, Oshogbo",
  "phone": "+2348076324576"
}
```
- Success Response (200 OK):
  ```json
   {
      "message": "Order details updated"
   }
  ```

### Checkout

POST /api/checkout/
Content-Type: application/json

```json
{
  "address": "Osun State, Oshogbo",
  "phone": "+2348076324576"
}
```

- Success Response (200 OK):
  ```json
    {
      "message": "Order checked out successfully",
      "user": "john_doe",
      "address": "Osun State, Oshogbo",
      "phone": "+2348076324576",
      "status": "out for delivery",
      "total": 600.00
    }
  ```

### Order details

POST /api/order/order_id
Content-Type: application/json

- Success Response (200 OK):
  ```json
    {
     "id": 9,
    "user": "Adebayo",
    "address": "Laaro Area, Ilobu, Osun State",
    "phone": "+2349039624784",
    "total": "300.00",
    "status": "CONFIRMED",
    "date_created": "2026-03-23T22:56:28.433819Z",
  
  "items": [
        {
            "id": 9,
            "food": {
                "id": 1,
                "name": "Fried Rice",
                "price": "300.00",
                "descriptions": "",
                "image_url": null,
                "category": "Main Course"
            },
            "quantity": 1,
            "price_at_purchase": "300.00",
            "subtotal": 300.0
        }
     ]
    }
  ```

### Initialize Payment

POST /api/order/order_id/pay
Content-Type: application/json

✅ Response (200 OK)
```json

{
  "payment_url": "https://paystack.com/pay/abc123",
  "reference": "ORDER-9-73C1A641"
}
```
❌ Error (400 Bad Request)
```json

{
   "error": "Order has already been paid for"
}
```

### Verify Payment

POST /api/order/verify/reference_id
Content-Type: application/json

✅ Response (200 OK)
```json

{
  "message": "Payment successfull",
  "order_id": 9,
  "payment_status": "PAID",
  "amount_paid": 300.0
}
```
❌ Error (402 Payment required)
```json

{
   "error": "Payment failed",
   "payment_status": "Failed"
}
```



## Testing the API

You can test this API using any API client such as:

- **Postman** (recommended)
- **Insomnia**
- **Thunder Client (VS Code extension)**

### Using Postman

1. Start the Django development server:
   ```bash
   python manage.py runserver
2. Open Postman and create a new request.
3. Use the Base URL
```arduino
http://127.0.0.1:8000/api/
```

4. Test authentication endpoints:
   
   - **Register → POST /users/register/**
   - **Login → POST /users/login/**
     
6. After login, authentication tokens are stored in HTTP-only cookies, so:
   - **No need to manually add Authorization headers**
   - **Postman will automatically send cookies on subsequent requests**

7. Test protected endpoints such as:
   
   - **GET `/api/menu/`**
   - **POST `/api/add_to_cart/`**
   - **GET `/api/my-orders/`**
   - **POST `/api/remove/`**
   - **POST `/api/cancel/`**
   - **GET `/api/order/<int:order_id>/details/`**
   - **PATCH `/api/order/details/update/`**
   - **POST `/api/order/<int:order_id>/review/`**
   - **PATCH `/api/order/<int:order_id>/review/update/`**
   - **GET `/api/order/<int:order_id>/review/detail/`**
   - **GET `/api/foods/<int:food_id>/reviews/`**

```md
### Cookie-based Authentication

This API uses JWT authentication stored in **HTTP-only cookies** for improved security.  
Access tokens are automatically sent with each request once the user is logged in.
```

## 🔹 Tech Stack
```md

- Python ----- Programming Language
- Django ----- Web framework for building server-side applications
- Django REST Framework ----- API layer
- Simple JWT ----- JWT token authentication
- PostgreSQL ----- Database
- django-cors-headers ----- Support frontend integration


## Notes

- This is a backend-only project.
- All endpoints require authentication except register and login.
- Frontend applications (React, Vue, Mobile apps) can consume this API.
```
