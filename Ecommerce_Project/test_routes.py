import unittest
from app import app, db, User, Product, Order

class ShopZoneTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_customer_pages(self):
        # 1. Home Page
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200, "Home page failed")

        # 2. Login Page
        res = self.client.get('/login')
        self.assertEqual(res.status_code, 200, "Login page failed")

        # 3. Register Page
        res = self.client.get('/register')
        self.assertEqual(res.status_code, 200, "Register page failed")

        # 4. Product Listing / Shop Page
        res = self.client.get('/products')
        self.assertEqual(res.status_code, 200, "Products page failed")

        with self.app.app_context():
            p = Product.query.first()
            pid = p.product_id if p else 1

        # 5. Product Details Page
        res = self.client.get(f'/product/{pid}')
        self.assertEqual(res.status_code, 200, "Product detail page failed")

        # 6. Compare Page
        res = self.client.get('/compare')
        self.assertEqual(res.status_code, 200, "Compare page failed")

        # Login as customer
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['user_name'] = 'Rahul Sharma'
            sess['role_id'] = 2

        # 7. Cart Page
        res = self.client.get('/cart')
        self.assertEqual(res.status_code, 200, "Cart page failed")

        # Add item to cart
        self.client.post(f'/add-to-cart/{pid}', data={'quantity': 1})

        # 8. Checkout Page
        res = self.client.get('/checkout')
        self.assertEqual(res.status_code, 200, "Checkout page failed")

        with self.app.app_context():
            order = Order.query.first()
            oid = order.order_id if order else 1

        # 9. Order Confirmation Page
        res = self.client.get(f'/order-success/{oid}')
        self.assertEqual(res.status_code, 200, "Order confirmation page failed")

        # 10. My Orders Page
        res = self.client.get('/my-orders')
        self.assertEqual(res.status_code, 200, "My orders page failed")

        # 11. Order Tracking Page
        res = self.client.get(f'/order/{oid}')
        self.assertEqual(res.status_code, 200, "Order tracking page failed")

        # 12. Profile Page
        res = self.client.get('/profile')
        self.assertEqual(res.status_code, 200, "Profile page failed")

    def test_admin_pages(self):
        # 13. Admin Login Page
        res = self.client.get('/admin/login')
        self.assertEqual(res.status_code, 200, "Admin login page failed")

        # Login as Admin
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Admin Superuser'
            sess['role_id'] = 1

        # 14. Admin Dashboard
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200, "Admin dashboard failed")

        # 15. Product & Category Management
        res = self.client.get('/admin/products')
        self.assertEqual(res.status_code, 200, "Admin products failed")

        # 16. Order Management
        res = self.client.get('/admin/orders')
        self.assertEqual(res.status_code, 200, "Admin orders failed")

        # 17. Users, Reviews & Returns Management
        res = self.client.get('/admin/users-reviews')
        self.assertEqual(res.status_code, 200, "Admin users reviews failed")

        # 18. Reports & Analytics
        res = self.client.get('/admin/reports')
        self.assertEqual(res.status_code, 200, "Admin reports failed")

if __name__ == '__main__':
    unittest.main()
