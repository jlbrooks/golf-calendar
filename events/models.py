from django.contrib.gis.db import models
from django.core.validators import URLValidator
from django.utils.text import slugify


class Tour(models.Model):
    """A professional or amateur golf tour organization."""
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    website_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Venue(models.Model):
    """A golf course or venue where events are held."""
    name = models.CharField(max_length=300)
    city = models.CharField(max_length=200)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100)
    location = models.PointField(geography=True, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['country', 'state', 'city', 'name']
        unique_together = [['name', 'city', 'country']]

    def __str__(self):
        parts = [self.name, self.city]
        if self.state:
            parts.append(self.state)
        parts.append(self.country)
        return ', '.join(parts)

    @property
    def latitude(self):
        return self.location.y if self.location else None

    @property
    def longitude(self):
        return self.location.x if self.location else None


class Event(models.Model):
    """A golf tournament or event."""

    CATEGORY_CHOICES = [
        ('major', 'Major Championship'),
        ('regular', 'Regular Tournament'),
        ('playoff', 'Playoff Event'),
        ('qualifier', 'Qualifier'),
        ('team', 'Team Event'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('postponed', 'Postponed'),
    ]

    name = models.CharField(max_length=300)
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name='events')
    tours = models.ManyToManyField(Tour, blank=True, related_name='events')

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='regular')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    start_date = models.DateField()
    end_date = models.DateField()

    external_url = models.URLField(max_length=500, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date', 'name']
        indexes = [
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_date.year})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError('End date cannot be before start date.')

    @property
    def tour_names(self):
        return ', '.join(tour.name for tour in self.tours.all())

    @property
    def is_upcoming(self):
        from django.utils import timezone
        return self.start_date > timezone.now().date()

    @property
    def is_current(self):
        from django.utils import timezone
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date
