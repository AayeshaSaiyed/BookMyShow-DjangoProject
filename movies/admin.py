from django.contrib import admin

from .models import Genre,Language,Movie, CastMember, MoviePoster, Theatre, Screen, Show, Booking, Review, Seat, SeatReservation

admin.site.register(Genre)
admin.site.register(Language)
admin.site.register(CastMember)
admin.site.register(Theatre)
admin.site.register(Screen)
admin.site.register(Show)
admin.site.register(Booking)
admin.site.register(Review)
admin.site.register(Seat)
admin.site.register(SeatReservation)

class MoviePosterInline(admin.TabularInline):
    model = MoviePoster
    extra = 3

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'language',
        'duration',
        'release_date',
        'age_certification',

    )

    list_filter = (
        'genres',
        'language',
        'age_certification',

    )
    search_fields = ('title',)
    inlines = [MoviePosterInline]



