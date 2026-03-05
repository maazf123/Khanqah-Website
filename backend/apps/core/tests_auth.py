from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class LoginPageTests(TestCase):
    """Tests for the login page (GET requests)."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("login")

    def test_login_page_returns_200(self):
        """GET /login/ returns HTTP 200."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)

    def test_login_page_uses_correct_template(self):
        """GET /login/ renders registration/login.html."""
        response = self.client.get(self.login_url)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_login_page_contains_form_fields(self):
        """Login page contains a form with username and password inputs."""
        response = self.client.get(self.login_url)
        content = response.content.decode()
        # Must have a <form> element
        self.assertIn("<form", content)
        # Must have username and password input fields
        self.assertIn('name="username"', content)
        self.assertIn('name="password"', content)


class SuccessfulLoginTests(TestCase):
    """Tests for successful login (POST with valid credentials)."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("login")
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="adminpass123",
            email="admin@test.com",
        )

    def test_valid_login_redirects(self):
        """POST with valid credentials returns a 302 redirect."""
        response = self.client.post(
            self.login_url,
            {"username": "admin", "password": "adminpass123"},
        )
        self.assertEqual(response.status_code, 302)

    def test_valid_login_redirects_to_homepage(self):
        """After successful login, the user is redirected to '/'."""
        response = self.client.post(
            self.login_url,
            {"username": "admin", "password": "adminpass123"},
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_valid_login_authenticates_user(self):
        """After successful login, the session contains the authenticated user."""
        self.client.post(
            self.login_url,
            {"username": "admin", "password": "adminpass123"},
        )
        # After login, subsequent requests should show an authenticated user.
        response = self.client.get("/")
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_staff_user_can_login(self):
        """A regular staff user (non-superuser) can also log in."""
        staff_user = User.objects.create_user(
            username="staff",
            password="staffpass123",
            is_staff=True,
        )
        response = self.client.post(
            self.login_url,
            {"username": "staff", "password": "staffpass123"},
        )
        self.assertEqual(response.status_code, 302)
        # Confirm the user is authenticated after login.
        response = self.client.get("/")
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user, staff_user)


class FailedLoginTests(TestCase):
    """Tests for failed login attempts."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("login")
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="adminpass123",
            email="admin@test.com",
        )

    def test_wrong_password_returns_200(self):
        """POST with a wrong password re-renders the login form (HTTP 200)."""
        response = self.client.post(
            self.login_url,
            {"username": "admin", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)

    def test_nonexistent_user_returns_200(self):
        """POST with a nonexistent username re-renders the login form (HTTP 200)."""
        response = self.client.post(
            self.login_url,
            {"username": "noone", "password": "doesntmatter"},
        )
        self.assertEqual(response.status_code, 200)

    def test_failed_login_shows_error_message(self):
        """Failed login includes an error message in the response body."""
        response = self.client.post(
            self.login_url,
            {"username": "admin", "password": "wrongpassword"},
        )
        content = response.content.decode()
        # Django's AuthenticationForm sets a non-field error on bad credentials.
        # The template should render this error somewhere on the page.
        self.assertTrue(
            "Please enter a correct username and password" in content
            or "errorlist" in content
            or response.context["form"].errors,
            "Expected an error message after failed login, but none found.",
        )

    def test_failed_login_does_not_authenticate_user(self):
        """After a failed login, the user remains anonymous."""
        self.client.post(
            self.login_url,
            {"username": "admin", "password": "wrongpassword"},
        )
        response = self.client.get("/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_empty_credentials_returns_200(self):
        """POST with empty username and password re-renders the form."""
        response = self.client.post(
            self.login_url,
            {"username": "", "password": ""},
        )
        self.assertEqual(response.status_code, 200)


class LogoutTests(TestCase):
    """Tests for the logout flow."""

    def setUp(self):
        self.client = Client()
        self.logout_url = reverse("logout")
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="adminpass123",
            email="admin@test.com",
        )
        # Log in before each test
        self.client.login(username="admin", password="adminpass123")

    def test_logout_redirects(self):
        """POST /logout/ returns a redirect (HTTP 302)."""
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 302)

    def test_logout_redirects_to_homepage(self):
        """After logout, the user is redirected to '/'."""
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_logout_deauthenticates_user(self):
        """After logout, the user is no longer authenticated."""
        self.client.post(self.logout_url)
        response = self.client.get("/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_user_is_authenticated_before_logout(self):
        """Sanity check: user is authenticated before calling logout."""
        response = self.client.get("/")
        self.assertTrue(response.wsgi_request.user.is_authenticated)


class NavBarTests(TestCase):
    """Tests for nav bar content based on authentication status."""

    def setUp(self):
        self.client = Client()
        self.homepage_url = "/"
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="adminpass123",
            email="admin@test.com",
            is_staff=True,
        )

    def test_anonymous_sees_login_link(self):
        """An anonymous visitor sees a 'Login' link in the nav bar."""
        response = self.client.get(self.homepage_url)
        content = response.content.decode()
        self.assertIn("Login", content)

    def test_anonymous_does_not_see_logout(self):
        """An anonymous visitor does NOT see 'Logout' in the nav bar."""
        response = self.client.get(self.homepage_url)
        content = response.content.decode()
        self.assertNotIn("Logout", content)

    def test_anonymous_does_not_see_admin_panel(self):
        """An anonymous visitor does NOT see 'Admin Panel' in the nav bar."""
        response = self.client.get(self.homepage_url)
        content = response.content.decode()
        self.assertNotIn("Admin Panel", content)

    def test_logged_in_admin_sees_admin_panel(self):
        """A logged-in admin/staff user sees an 'Admin Panel' link."""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(self.homepage_url)
        content = response.content.decode()
        self.assertIn("Admin Panel", content)

    def test_logged_in_admin_sees_logout(self):
        """A logged-in admin/staff user sees a 'Logout' link."""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(self.homepage_url)
        content = response.content.decode()
        self.assertIn("Logout", content)

    def test_logged_in_admin_does_not_see_login_link(self):
        """A logged-in admin/staff user does NOT see a 'Login' link."""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(self.homepage_url)
        content = response.content.decode()
        self.assertNotIn("Login", content)

    def test_admin_panel_links_to_admin_site(self):
        """The 'Admin Panel' link points to /admin/."""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(self.homepage_url)
        content = response.content.decode()
        self.assertIn("/admin/", content)

    def test_logout_link_points_to_logout_url(self):
        """The 'Logout' link points to the logout URL."""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(self.homepage_url)
        content = response.content.decode()
        logout_url = reverse("logout")
        self.assertIn(logout_url, content)
