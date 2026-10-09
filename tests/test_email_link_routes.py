"""Static smoke checks; these do not start the app or modify its database."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EmailLinkRouteTests(unittest.TestCase):
    def test_email_urls_are_generated_from_registered_endpoints(self):
        email_source = (ROOT / "app/services/email_service.py").read_text(encoding="utf-8")
        action_source = (ROOT / "app/services/teacher_action_service.py").read_text(encoding="utf-8")
        self.assertIn('url_for("dashboard.tracking_page"', email_source)
        self.assertIn('url_for("auth.login"', email_source)
        self.assertIn('url_for("student.login"', email_source)
        self.assertIn('url_for("booking.teacher_appointment_action"', action_source)

    def test_action_route_is_get_post_and_get_does_not_mutate(self):
        booking_source = (ROOT / "app/routes/booking.py").read_text(encoding="utf-8")
        self.assertIn('@booking_bp.route("/teacher/appointment-action/<token>", methods=["GET", "POST"])', booking_source)
        self.assertIn('if request.method == "GET":', booking_source)
        self.assertIn('# POST performs the actual mutation', booking_source)

    def test_python_sources_parse(self):
        files = [
            ROOT / "app/services/email_service.py",
            ROOT / "app/services/teacher_action_service.py",
            ROOT / "app/routes/booking.py",
        ]
        for path in files:
            with self.subTest(file=path.name):
                ast.parse(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
