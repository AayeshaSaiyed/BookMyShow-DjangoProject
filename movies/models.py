from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Genre(models.Model):
        name = models.CharField(max_length=100) 

        def __str__(self):
            return self.name
                

class Language(models.Model):
        name = models.CharField(max_length=100)

        def __str__(self):
            return self.name
        
class CastMember(models.Model):
       name = models.CharField(max_length=100)

       def __str__(self):
        return self.name


       
class Movie(models.Model):
      title = models.CharField(max_length=100)
      description = models.TextField()
      duration = models.IntegerField()
      release_date = models.DateField()
      age_certification = models.CharField(max_length=100)
      trailer_url = models.URLField(max_length=1000)

      language = models.ForeignKey(
            Language,
            on_delete=models.CASCADE
      )


      genres = models.ManyToManyField(Genre)

      def __str__(self):
        return self.title


      cast_members = models.ManyToManyField(CastMember)

class MoviePoster(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE
        
     )
    image = models.ImageField(upload_to = "movie_posters/" )    

class Theatre(models.Model):
     name = models.CharField(max_length=100)
     city = models.CharField(max_length=200)
     address = models.TextField()

     def __str__(self):
        return self.name
     
class Screen(models.Model):
     theatre = models.ForeignKey(
          Theatre,
          on_delete=models.CASCADE
     )
     name = models.CharField(max_length=50)
     total_seats = models.IntegerField()

     def __str__(self):
        return self.name
     

class Show(models.Model):
     movie = models.ForeignKey(
             Movie,
             on_delete=models.CASCADE
     )

     theatre = models.ForeignKey(
               Theatre,
               on_delete=models.CASCADE
          )
     
     screen = models.ForeignKey(
          Screen,
          on_delete=models.CASCADE
     )
     show_date = models.DateField()
     show_time = models.TimeField()
     price = models.DecimalField(
          max_digits=8,
          decimal_places=2
          )
     
     def __str__(self):
        return str(self.show_time)

class Booking(models.Model):
     STATUS_CHOICES =  [
          ('reserved','Reserved'),
          ('confirmed','Confirmed'),
          ('cancelled','Cancelled'),
     ]

     show = models.ForeignKey(
          Show,
          on_delete=models.CASCADE
     )
     user = models.ForeignKey(
              User,
              on_delete=models.CASCADE
         )
     seats = models.CharField(
          max_length=20,
          
     )
     total_price = models.DecimalField(
          max_digits=10,
          decimal_places=2
     )
     status = models.CharField(
          max_length=20,
          choices=STATUS_CHOICES,
          default='reserved'
     )
     booking_date = models.DateTimeField(
          auto_now_add=True
     )
     watched = models.BooleanField(
          default=False
     )
     class Meta:
          indexes = [
               models.Index(fields=['status'], name='booking_status_idx'),
               models.Index(fields=['booking_date'], name ='booking_date_idx'),
               models.Index(fields=['status','booking_date'],name ='booking_status_date_idx'),
          ]
     reserved_at = models.DateTimeField(
          null = True,
          blank = True
     )
     expires_at = models.DateTimeField(
          null = True,
          blank = True
     )

     def __str__(self):
          return f"{self.user} - {self.show.movie.title}"
class Payment(models.Model):
     STATUS_CHOICES = [
          ('pending','Pending'),
          ('success','Success'),
          ('failed', 'Failed'),
          ('cancelled','Cancelled'),
          ('refunded', 'Refunded'),
     ]
     booking = models.ForeignKey(
          Booking,
          on_delete=models.CASCADE,
          related_name='payments'
     )
     amount = models.DecimalField(
          max_digits=10,
          decimal_places=2
     )
     status = models.CharField(
          max_length=20,
          choices=STATUS_CHOICES,
          default = 'pending'
     )
     transaction_id = models.CharField(
          max_length=100,
          unique=True,
          null = True,
          blank=True
     )
     payment_date = models.DateTimeField(
          auto_now_add=True
     )
     def __str__(self):
          return f"{self.booking} - {self.status}"
class Review(models.Model):
     user = models.ForeignKey(
          User,
          on_delete=models.CASCADE
     )
     movie = models.ForeignKey(
               Movie,
               on_delete=models.CASCADE
          )
     rating = models.IntegerField()

     comment = models.TextField()

     created_at = models.DateTimeField(
          auto_now_add=True
     )
     updated_at = models.DateTimeField(
          auto_now=True
     )
     reported = models.BooleanField(
          default=False
     )
     def __str__(self):
          return f"{self.user} - {self.movie.title}"

class Seat(models.Model):
     screen = models.ForeignKey(
          Screen,
          on_delete=models.CASCADE
     )
     seat_number = models.CharField(max_length=10)

     def __str__(self):
          return f"{self.screen.name} - {self.seat_number}"

@receiver(post_save,sender=Screen)
def create_seats(sender, instance, created, **kwargs):
     if created:
          seats_per_row = 6

          for i in range(instance.total_seats):
               row = chr(65 + (i // seats_per_row))
               number = (i % seats_per_row) + 1

               Seat.objects.create(
                    screen = instance,
                    seat_number= f"{row}{number}"
               )

class SeatReservation(models.Model):
     show = models.ForeignKey(
          Show,
          on_delete = models.CASCADE
     )
     seat = models.ForeignKey(
          Seat,
          on_delete=models.CASCADE
     )
     user = models.ForeignKey(
          User,
          on_delete=models.CASCADE
     )
     reserved_at = models.DateTimeField(
          auto_now_add=True
     )
     expires_at = models.DateTimeField()

     def __str__(self):
          return f"{self.show} - {self.seat.seat_number} - {self.user}"   