from django.db import models

DLC_KEYWORDS = ['ccc', 'bcc', 'ccc+']

def get_course_category(course_name, course_hour):
    name_lower = course_name.lower()
    if any(kw in name_lower for kw in DLC_KEYWORDS):
        return 'E - DLC'
    if course_hour > 500:
        return 'B - Long Term Course'
    if 90 <= course_hour <= 500:
        return 'C - Short Term Course'
    return 'D - Short Term Course'


class studentdata(models.Model):
    MODE_CHOICES = [
        ('offline', 'Off Campus'),
        ('online', 'On Campus'),
    ]
    CASTE_CHOICES = [
        ('OBC', 'OBC'),
        ('SC', 'SC'),
        ('ST', 'ST'),
        ('PWD', 'PWD'),
        ('GENERAL', 'GENERAL'),
    ]
    CENTER_CHOICES = [
        ('inderlok', 'Inderlok'),
        ('janakpuri', 'Janakpuri'),
        ('karkardooma', 'Karkardooma'),
    ]

    session = models.CharField(max_length=20)           # e.g. "JAN-2024"
    roll_number = models.CharField(max_length=20, blank=True)
    name = models.CharField(max_length=100)
    course_name = models.CharField(max_length=100)
    course_hour = models.PositiveIntegerField()
    course_category = models.CharField(max_length=30, blank=True)  # auto-filled on save
    scheme = models.CharField(max_length=50, blank=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='offline')
    caste_category = models.CharField(max_length=10, choices=CASTE_CHOICES, default='GENERAL')
    center_name = models.CharField(max_length=30, choices=CENTER_CHOICES, default='inderlok')
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    claimable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trained_date = models.CharField(max_length=20, blank=True)   # "JAN-2024" or ""
    certified_date = models.CharField(max_length=20, blank=True)   # "JAN-2024" or ""
    placed = models.BooleanField(default=False)
    scheme = models.CharField(max_length=50, blank=True)
    nsqf = models.CharField(max_length=20, blank=True)
    course_category = models.CharField(max_length=30, blank=True)

    def save(self, *args, **kwargs):
        # Auto-compute category
        self.course_category = get_course_category(self.course_name, self.course_hour)

        # Claimable amount logic
        if self.certified_date:
            self.claimable_amount = self.fee
        elif self.trained_date:
            self.claimable_amount = self.fee * 70 / 100  # fee minus 30%
        else:
            self.claimable_amount = 0

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.course_name} ({self.caste_category})"