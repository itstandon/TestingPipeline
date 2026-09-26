import pytest
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model

from server import models


@pytest.mark.django_db
def test_speciality_str():
    """Speciality __str__ returns its name."""
    spec = models.Speciality.objects.create(name="Cardiology", description="Heart")
    assert str(spec) == "Cardiology"


@pytest.mark.django_db
def test_symptom_str():
    """Symptom __str__ returns its name."""
    sym = models.Symptom.objects.create(name="Cough", description="Throat irritation")
    assert str(sym) == "Cough"


@pytest.mark.django_db
def test_location_str_and_admin_display():
    """Location __str__ returns address; Admin list_display is set."""
    loc = models.Location.objects.create(
        city="Mumbai",
        zip="400001",
        state="Maharashtra",
        address="123 Health St."
    )
    assert str(loc) == "123 Health St."
    # Admin attribute is a class, not instantiated; just ensure attribute exists
    assert hasattr(models.Location, "Admin")
    assert getattr(models.Location.Admin, "list_display") == ("city", "country")


@pytest.mark.django_db
def test_hospital_str_and_admin_display():
    """Hospital __str__ returns its name; Admin list_display is defined."""
    loc = models.Location.objects.create(city="Delhi", zip="110001", state="Delhi", address="1 Main Rd")
    hosp = models.Hospital.objects.create(name="City Hospital", phone="1234567890", location=loc)
    assert str(hosp) == "City Hospital"
    assert hasattr(models.Hospital, "Admin")
    assert getattr(models.Hospital.Admin, "list_display") == ('name', 'phone', 'location')


@pytest.mark.django_db
def test_profile_to_gender_and_populated_fields():
    """Profile.to_gender maps keys; get_populated_fields skips default birthday."""
    # to_gender happy path
    assert models.Profile.to_gender('M') == "Male"
    assert models.Profile.to_gender('F') == "Female"
    # unknown key
    assert models.Profile.to_gender('X') == "None"

    # Create related objects
    loc = models.Location.objects.create(city="Chennai", zip="600001", state="Tamil Nadu", address="5 Road")
    hosp = models.Hospital.objects.create(name="General", phone="9876543210", location=loc)
    user = get_user_model().objects.create_user(username="patient1", password="test123")
    acc = models.Account.objects.create(
        role=models.Account.ACCOUNT_PATIENT,
        profile=models.Profile.objects.create(
            firstname="John",
            lastname="Doe",
            sex="M",
            birthday=date(1990, 5, 20),
            phone="1112223333",
            allergies="None",
            prefHospital=hosp,
            primaryCareDoctor=None,
            speciality=None,
        ),
        user=user,
    )
    profile = acc.profile

    # Populate fields – all non‑None and birthday not default
    fields = profile.get_populated_fields()
    assert fields["firstname"] == "John"
    assert fields["lastname"] == "Doe"
    assert fields["sex"] == "M"
    assert fields["birthday"] == date(1990, 5, 20)
    assert fields["phone"] == "1112223333"
    assert fields["allergies"] == "None"
    assert fields["prefHospital"] == hosp
    # primaryCareDoctor and speciality are None and should be absent
    assert "primaryCareDoctor" not in fields
    assert "speciality" not in fields

    # Change birthday to default sentinel; it should be omitted
    profile.birthday = date(1000, 1, 1)
    fields2 = profile.get_populated_fields()
    assert "birthday" not in fields2


@pytest.mark.django_db
def test_account_to_name_to_value_and_str():
    """Account conversion utilities work case‑insensitively and __str__ adds prefix for doctors."""
    # to_name happy path
    assert models.Account.to_name(models.Account.ACCOUNT_DOCTOR) == "Doctor"
    assert models.Account.to_name(999) == "None"

    # to_value case‑insensitive
    assert models.Account.to_value("doctor") == models.Account.ACCOUNT_DOCTOR
    assert models.Account.to_value("DoCtOr") == models.Account.ACCOUNT_DOCTOR
    # unknown string returns 0
    assert models.Account.to_value("unknownrole") == 0

    # Create a doctor account and verify __str__
    user_doc = get_user_model().objects.create_user(username="doc1", password="test")
    profile_doc = models.Profile.objects.create(firstname="Alice", lastname="Smith")
    doc_acc = models.Account.objects.create(
        role=models.Account.ACCOUNT_DOCTOR,
        profile=profile_doc,
        user=user_doc,
    )
    assert str(doc_acc) == "Dr. Alice Smith"

    # Non‑doctor account string does not have prefix
    user_pat = get_user_model().objects.create_user(username="pat1", password="test")
    profile_pat = models.Profile.objects.create(firstname="Bob", lastname="Brown")
    pat_acc = models.Account.objects.create(
        role=models.Account.ACCOUNT_PATIENT,
        profile=profile_pat,
        user=user_pat,
    )
    assert str(pat_acc) == "Bob Brown"


@pytest.mark.django_db
def test_action_to_name_to_value():
    """Action conversion utilities map between ints and strings."""
    assert models.Action.to_name(models.Action.ACTION_MEDTEST) == "Medical Test"
    assert models.Action.to_name(12345) == "None"

    # case‑insensitive lookup
    assert models.Action.to_value("medical test") == models.Action.ACTION_MEDTEST
    assert models.Action.to_value("MeDicaL TeSt") == models.Action.ACTION_MEDTEST
    # unknown returns 0
    assert models.Action.to_value("nonexistent") == 0


@pytest.mark.django_db
def test_appointment_get_populated_fields():
    """Appointment.get_populated_fields returns all fields correctly."""
    user_doc = get_user_model().objects.create_user(username="doc2", password="test")
    user_pat = get_user_model().objects.create_user(username="pat2", password="test")
    profile_doc = models.Profile.objects.create(firstname="Doc", lastname="One")
    profile_pat = models.Profile.objects.create(firstname="Pat", lastname="Two")
    doc_acc = models.Account.objects.create(role=models.Account.ACCOUNT_DOCTOR, profile=profile_doc, user=user_doc)
    pat_acc = models.Account.objects.create(role=models.Account.ACCOUNT_PATIENT, profile=profile_pat, user=user_pat)

    loc = models.Location.objects.create(city="Bangalore", zip="560001", state="Karnataka", address="10 St")
    hosp = models.Hospital.objects.create(name="HealthCare", phone="5556667777", location=loc)
    sym = models.Symptom.objects.create(name="Fever", description="High temperature")

    start = datetime.now()
    end = start + timedelta(hours=1)
    appt = models.Appointment.objects.create(
        doctor=doc_acc,
        patient=pat_acc,
        description="Routine check",
        symptom=sym,
        hospital=hosp,
        appointment_type="Online",
        startTime=start,
        endTime=end,
    )

    fields = appt.get_populated_fields()
    assert fields["doctor"] is doc_acc
    assert fields["patient"] is pat_acc
    assert fields["symptom"] is sym
    assert fields["description"] == "Routine check"
    assert fields["hospital"] is hosp
    assert fields["appointment_type"] == "Online"
    assert fields["startTime"] == start
    assert fields["endTime"] == end


@pytest.mark.django_db
def test_prescription_get_populated_fields():
    """Prescription.get_populated_fields returns all model values."""
    user_doc = get_user_model().objects.create_user(username="doc3", password="test")
    user_pat = get_user_model().objects.create_user(username="pat3", password="test")
    profile_doc = models.Profile.objects.create(firstname="Doc", lastname="Three")
    profile_pat = models.Profile.objects.create(firstname="Pat", lastname="Three")
    doc_acc = models.Account.objects.create(role=models.Account.ACCOUNT_DOCTOR, profile=profile_doc, user=user_doc)
    pat_acc = models.Account.objects.create(role=models.Account.ACCOUNT_PATIENT, profile=profile_pat, user=user_pat)

    presc = models.Prescription.objects.create(
        patient=pat_acc,
        doctor=doc_acc,
        date=date.today(),
        medication="Paracetamol",
        strength="500mg",
        instruction="Twice a day",
        refill=2,
        active=False,
    )
    fields = presc.get_populated_fields()
    assert fields["patient"] is pat_acc
    assert fields["doctor"] is doc_acc
    assert fields["date"] == date.today()
    assert fields["medication"] == "Paracetamol"
    assert fields["strength"] == "500mg"
    assert fields["instruction"] == "Twice a day"
    assert fields["refill"] == 2
    assert fields["active"] is False


@pytest.mark.django_db
def test_medicalinfo_to_blood_and_populated_fields():
    """MedicalInfo.to_blood returns the correct label and populated fields include pk for account."""
    user = get_user_model().objects.create_user(username="patient4", password="test")
    profile = models.Profile.objects.create(firstname="Pat", lastname="Four")
    acc = models.Account.objects.create(role=models.Account.ACCOUNT_PATIENT, profile=profile, user=user)

    # to_blood happy path
    assert models.MedicalInfo.to_blood('A+') == 'A+ Type'
    assert models.MedicalInfo.to_blood('Z-') == "None"

    info = models.MedicalInfo.objects.create(
        account=acc,
        bloodType='B+',
        allergy="Peanuts",
        alzheimer=False,
        asthma=True,
        diabetes=False,
        stroke=False,
        comments="No additional notes",
    )
    fields = info.get_populated_fields()
    assert fields["account"] == acc.pk
    assert fields["bloodType"] == 'B+'
    assert fields["allergy"] == "Peanuts"
    assert fields["asthma"] is True
    assert fields["alzheimer"] is False
    assert fields["stroke"] is False
    assert fields["comments"] == "No additional notes"


@pytest.mark.django_db
def test_medicaltest_get_populated_fields():
    """MedicalTest.get_populated_fields returns all defined fields."""
    user_doc = get_user_model().objects.create_user(username="doc5", password="test")
    user_pat = get_user_model().objects.create_user(username="pat5", password="test")
    profile_doc = models.Profile.objects.create(firstname="Doc", lastname="Five")
    profile_pat = models.Profile.objects.create(firstname="Pat", lastname="Five")
    doc_acc = models.Account.objects.create(role=models.Account.ACCOUNT_DOCTOR, profile=profile_doc, user=user_doc)
    pat_acc = models.Account.objects.create(role=models.Account.ACCOUNT_PATIENT, profile=profile_pat, user=user_pat)

    loc = models.Location.objects.create(city="Hyderabad", zip="500001", state="Telangana", address="99 Blvd")
    hosp = models.Hospital.objects.create(name="Metro Hospital", phone="7778889999", location=loc)

    test = models.MedicalTest.objects.create(
        name="Blood Test",
        date=date.today(),
        hospital=hosp,
        description="Standard blood panel",
        doctor=doc_acc,
        patient=pat_acc,
        private=False,
        completed=True,
    )
    fields = test.get_populated_fields()
    assert fields["name"] == "Blood Test"
    assert fields["date"] == date.today()
    assert fields["hospital"] is hosp
    assert fields["description"] == "Standard blood panel"
    assert fields["doctor"] is doc_acc
    assert fields["patient"] is pat_acc
    assert fields["private"] is False
    assert fields["completed"] is True
    # Image fields default to None
    for img_field in ("image1", "image2", "image3", "image4", "image5"):
        assert fields[img_field] is None


@pytest.mark.django_db
def test_statistics_get_populated_fields():
    """Statistics.get_populated_fields returns start and end dates."""
    stats = models.Statistics.objects.create(
        startDate=date(2023, 1, 1),
        endDate=date(2023, 12, 31),
    )
    fields = stats.get_populated_fields()
    assert fields["startDate"] == date(2023, 1, 1)
    assert fields["endDate"] == date(2023, 12, 31)