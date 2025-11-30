from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Tour, Venue, Event


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'website_url', 'created_at']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Venue)
class VenueAdmin(GISModelAdmin):
    list_display = ['name', 'city', 'state', 'country', 'latitude', 'longitude']
    list_filter = ['country', 'state']
    search_fields = ['name', 'city', 'country']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'city', 'state', 'country')
        }),
        ('Location', {
            'fields': ('location',),
            'description': 'Click on the map to set the venue location.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'venue', 'start_date', 'end_date', 'category', 'status', 'tour_list']
    list_filter = ['status', 'category', 'tours', 'start_date']
    search_fields = ['name', 'venue__name', 'venue__city']
    filter_horizontal = ['tours']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'

    fieldsets = (
        ('Event Information', {
            'fields': ('name', 'venue', 'tours', 'category', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Additional Information', {
            'fields': ('external_url', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def tour_list(self, obj):
        """Display comma-separated list of tours in list view."""
        return obj.tour_names or 'No tour affiliation'
    tour_list.short_description = 'Tours'
