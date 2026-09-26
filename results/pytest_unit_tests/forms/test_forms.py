
import pytest
from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from server.forms import (
    validate_username_available,
    validate_username_exists,
    validate_birthday,
    BasicForm,
    LoginForm,
    AccountRegisterForm,
    PasswordForm,
    AppointmentForm,
    EmployeeRegistrationForm,
)
pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    """Create a regular Django user."""
    usr = User.objects.create_user(username="test@example.com", email="test@example.com", password="secret123")
    return usr


@pytest.fixture
def another_user():
    """Create a second user to test uniqueness."""
    return User.objects.create_user(username="other@example.com", email="other@example.com", password="pwd456")


def test_validate_username_available_raises_if_exists(another_user):
    """validate_username_available raises when username already exists."""
    with pytest.raises(ValidationError) as exc:
        validate_username_available("other@example.com")
    assert "already registered" in str(exc.value)


def test_validate_username_available_passes_when_free():
    """validate_username_available does not raise for a new username."""
    # Ensure no user with this email exists
    User.objects.filter(username__iexact="free@example.com").delete()
    # Should not raise
    validate_username_available("free@example.com")


def test_validate_username_exists_raises_when_missing():
    """validate_username_exists raises when username does not exist."""
    User.objects.filter(username__iexact="missing@example.com").delete()
    with pytest.raises(ValidationError) as exc:
        validate_username_exists("missing@example.com")
    assert "does not exist" in str(exc.value)


def test_validate_username_exists_passes_when_present(user):
    """validate_username_exists does not raise for an existing username."""
    validate_username_exists("test@example.com")


def test_validate_birthday_raises_for_too_old():
    """validate_birthday raises when the year is more than 200 years ago."""
    old_date = date.today().replace(year=date.today().year - 201)
    with pytest.raises(ValidationError) as exc:
        validate_birthday(old_date)
    assert "later date" in str(exc.value)


def test_validate_birthday_raises_for_future():
    """validate_birthday raises when the date is in the future."""
    future_date = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError) as exc:
        validate_birthday(future_date)
    assert "earlier date" in str(exc.value)


def test_validate_birthday_accepts_realistic_date():
    """validate_birthday accepts a realistic birth date."""
    realistic = date.today() - timedelta(days=365 * 30)  # 30 years ago
    # Should not raise
    validate_birthday(realistic)


def test_basic_form_disable_and_error_handling():
    """BasicForm methods correctly manipulate field attributes and errors."""
    class SampleForm(BasicForm):
        name = forms.CharField(max_length=10)

    form = SampleForm()
    # Disable field
    form.disable_field("name")
    assert form.fields["name"].widget.attrs.get("disabled") == ""

    # Simulate cleaned_data and trigger mark_error
    form.is_valid()  # populates cleaned_data
    form.cleaned_data["name"] = "abc"
    form.mark_error("name", "bad value")
    assert "name" in form.errors
    assert form.errors["name"] == ["bad value"]
    assert "name" not in form.cleaned_data

    # Clear errors
    form.clear_errors()
    assert form.errors == {}


def test_login_form_invalid_password(user):
    """LoginForm.clean adds error when password does not match."""
    form = LoginForm(data={"email": "test@example.com", "password": "wrongpass"})
    assert not form.is_valid()
    # The password field should have an error added by mark_error
    assert "password" in form.errors
    assert any("Incorrect password" in e for e in form.errors["password"])


def test_login_form_valid_credentials(user):
    """LoginForm.clean passes when correct credentials are supplied."""
    form = LoginForm(data={"email": "test@example.com", "password": "secret123"})
    assert form.is_valid()
    # No errors should be present
    assert form.errors == {}


def test_account_register_form_password_mismatch():
    """AccountRegisterForm.clean flags mismatch between password fields."""
    data = {
        "firstname": "John",
        "lastname": "Doe",
        "email": "new@example.com",
        "password_first": "abc123",
        "password_second": "def456",
    }
    form = AccountRegisterForm(data=data)
    assert not form.is_valid()
    assert "password_second" in form.errors
    assert any("Passwords do not match" in e for e in form.errors["password_second"])


def test_account_register_form_password_match():
    """AccountRegisterForm.clean passes when passwords match."""
    data = {
        "firstname": "Jane",
        "lastname": "Doe",
        "email": "unique@example.com",
        "password_first": "samepwd",
        "password_second": "samepwd",
    }
    # Ensure the email is not already taken
    User.objects.filter(username__iexact="unique@example.com").delete()
    form = AccountRegisterForm(data=data)
    assert form.is_valid()


def test_password_form_new_passwords_mismatch():
    """PasswordForm.clean flags mismatch between new password entries."""
    data = {
        "password_current": "oldpwd",
        "password_first": "newpwd1",
        "password_second": "newpwd2",
    }
    form = PasswordForm(data=data)
    assert not form.is_valid()
    assert "password_second" in form.errors
    assert any("Passwords do not match" in e for e in form.errors["password_second"])


def test_password_form_current_equals_new():
    """PasswordForm.clean flags when current password equals new password."""
    data = {
        "password_current": "samepwd",
        "password_first": "samepwd",
        "password_second": "samepwd",
    }
    form = PasswordForm(data=data)
    assert not form.is_valid()
    assert "password_current" in form.errors
    assert any("must be different" in e for e in form.errors["password_current"])


def test_appointment_form_end_before_start():
    """AppointmentForm.clean adds error when endTime is before startTime."""
    # Minimal objects for required ModelChoiceFields; use existing objects or create placeholders
    symptom = Symptom.objects.create(name="Headache", description="Pain")
    hospital = Hospital.objects.create(name="General", city="Town", zip="12345", state="ST", address="Addr", phone="1234567890")
    doctor = Account.objects.create(username="doc@example.com", role=Account.ACCOUNT_DOCTOR)
    patient = Account.objects.create(username="pat@example.com", role=Account.ACCOUNT_PATIENT)

    start = datetime.now()
    end = start - timedelta(hours=1)  # end before start
    data = {
        "description": "Checkup",
        "symptom": symptom.id,
        "hospital": hospital.id,
        "doctor": doctor.id,
        "patient": patient.id,
        "appointment_type": "CONSULT",
        "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime": end.strftime("%Y-%m-%d %H:%M:%S"),
    }
    form = AppointmentForm(data=data)
    assert not form.is_valid()
    assert "endTime" in form.errors
    assert any("must come after the start time" in e for e in form.errors["endTime"])


def test_employee_registration_form_doctor_without_speciality():
    """EmployeeRegistrationForm.clean errors when a doctor does not provide a speciality."""
    # Assume employee type 20 is doctor; provide other required fields
    data = {
        "firstname": "Doc",
        "lastname": "Smith",
        "email": "doc2@example.com",
        "password_first": "pwd",
        "password_second": "pwd",
        "employee": "20",  # doctor
        "speciality": "",  # none selected
    }
    # Ensure email is free
    User.objects.filter(username__iexact="doc2@example.com").delete()
    form = EmployeeRegistrationForm(data=data)
    assert not form.is_valid()
    assert "speciality" in form.errors
    assert any("Doctor must have a speciality" in e for e in form.errors["speciality"])


def test_employee_registration_form_non_doctor_with_speciality():
    """EmployeeRegistrationForm.clean errors when a non‑doctor provides a speciality."""
    speciality = Speciality.objects.create(name="Cardiology", description="Heart")
    data = {
        "firstname": "Nurse",
        "lastname": "Joy",
        "email": "nurse@example.com",
        "password_first": "pwd",
        "password_second": "pwd",
        "employee": "10",  # non‑doctor
        "speciality": str(speciality.id),
    }
    User.objects.filter(username__iexact="nurse@example.com").delete()
    form = EmployeeRegistrationForm(data=data)
    assert not form.is_valid()
    assert "speciality" in form.errors
    assert any("Only doctor can have a speciality" in e for e in form.errors["speciality"])


def test_employee_registration_form_valid_doctor():
    """EmployeeRegistrationForm.clean passes for a doctor with a speciality."""
    speciality = Speciality.objects.create(name="Dermatology", description="Skin")
    data = {
        "firstname": "Derm",
        "lastname": "Doc",
        "email": "derm@example.com",
        "password_first": "pwd",
        "password_second": "pwd",
        "employee": "20",  # doctor
        "speciality": str(speciality.id),
    }
    User.objects.filter(username__iexact="derm@example.com").delete()
    form = EmployeeRegistrationForm(data=data)
    assert form.is_valid()
