from django.shortcuts import render,redirect
from django.core.paginator import Paginator
from .models import Show, Movie, Booking, Review, Seat, SeatReservation, Payment, Theatre,Genre, Language
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, Sum, Min, Max, Q
from django.db.models.functions import TruncDate,ExtractHour, TruncWeek,TruncMonth, TruncYear
from urllib.parse import urlparse, parse_qs
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.http import JsonResponse, HttpResponse, FileResponse
import razorpay, json,csv
from django.conf import settings
import os
from .tasks import generate_ticket_pdf, send_ticket_email




def show_list(request):
    shows = Show.objects.all()
    bookings = Booking.objects.filter(
        user = request.user,
        status='confirmed'
    )


    return render(request,'shows.html',{'shows':shows, 'bookings':bookings})

def get_youtube_embed_url(url):
    parsed_url = urlparse(url)

    if parsed_url.netloc in ['www.youtube.com', 'youtube.com']:
        video_id = parse_qs(parsed_url.query).get('v')

        if video_id:
            return f"https://www.youtube-nocookie.com/embed/{video_id[0]}"

    if parsed_url.netloc in ['youtu.be','www.youtu.be']:
        video_id = parsed_url.path.strip('/')

        if video_id:
            return f"https://www.youtube-nocookie.com/embed/{video_id}"

    return None

def movie_detail(request, movie_id):
    movie = Movie.objects.get(id=movie_id)
    recently_viewed = request.session.get('recently_viewed',[])

    recently_viewed = [movie.id for movie_id in recently_viewed if movie_id != movie.id ]

    recently_viewed = (0,movie.id)

    request.session['recently_viewed'] = recently_viewed[:10]

    trailer_url = get_youtube_embed_url(movie.trailer_url)

    shows = Show.objects.filter(movie=movie)
    average_rating = Review.objects.filter(movie=movie).aggregate(
        rating_avg =  Avg('rating')
        )['rating_avg']

    reviews = Review.objects.filter(movie=movie)

    for review in reviews:
        review.is_verified_viewer = Booking.objects.filter(
            user = review.user,
            show__movie = movie,
            status = 'confirmed',
            watched = True
        ).exists()

    similar_movies = Movie.objects.filter(
        language = movie.language,
        genres__in = movie.genres.all()
    ).exclude(
        id = movie.id
    ).distinct()

    trending_movies = Movie.objects.annotate(
        booking_count = Count('show__booking')
    ).order_by('-booking_count')[:5]

    recent_movies = Movie.objects.order_by('-release_date')[:5]

    return render(request, 'movie_details.html',{'movie':movie, 'trailer_url':trailer_url, 'shows':shows, 'average_rating':average_rating, 'reviews':reviews, 'similar_movies':similar_movies, 'trending_movies':trending_movies, 'recent_movies':recent_movies}) 

@login_required
def movie_discovery(request):
    sort = request.GET.get('sort','')
    user_booked_movies = Booking.objects.filter(
        user = request.user,
        status="confirmed"
    ).values_list(
        'show__movie_id',
        flat=True
    )

    booked_genres = Genre.objects.filter(
        movie__id__in=user_booked_movies
    ).values_list('id',flat=True)

    booked_languages = Language.objects.filter(
        movie__id__in = user_booked_movies
    ).values_list('id',flat=True)

    recently_viewed_ids = request.session.get('recently_viewed',[])

    recommended_movies = Movie.objects.filter(
        Q(genres__id__in=booked_genres) |
        Q(language_id__in=booked_languages) |
        Q(id__in=recently_viewed_ids) 
    ).exclude(
        id__in=user_booked_movies
    ).distinct()[:5]
    search = request.GET.get('search','')
    genre = request.GET.get('genre','')
    language = request.GET.get('language','')
    city = request.GET.get('city','')
    theatre = request.GET.get('theatre','')
    release_from = request.GET.get('release_from','')
    release_to = request.GET.get('release_to','')
    show_time_from = request.GET.get('show_time_from','')
    show_time_to = request.GET.get('show_time_to','')
    min_rating = request.GET.get('min_rating','')

    movies = Movie.objects.filter(title__icontains=search)

    if genre:
        movies = movies.filter(genres__id=genre)
    if language:
        movies = movies.filter(language__id=language)
    if city:
        movies = movies.filter(show__theatre__city__iexact=city)
    if theatre:
        movies = movies.filter(show__theatre__id=theatre)
    if release_from:
        movies = movies.filter(release_date__gte=release_from)
    if release_to:
        movies = movies.filter(release_date__lte=release_to)
    if show_time_from:
        movies = movies.filter(show__show_time__gte=show_time_from)
    if show_time_to:
        movies = movies.filter(show__show_time__lte=show_time_to)
    if min_rating:
        movies = movies.annotate(
            average_rating=Avg("review__rating")
        ).filter(average_rating__gte=min_rating)
    if sort == "popular":
        movies = movies.annotate(
            booking_count=Count('show__booking')
        ).order_by('-booking_count')
    elif sort == 'newest':
        movies = movies.order_by('-release_date')
    elif sort == 'rating':
        movies = movies.annotate(
            average_rating=Avg('review__rating')
        ).order_by('-average_rating')
    elif sort == 'price_low':
        movies = movies.annotate(
            lowest_price=Min('show__price')
        ).order_by('lowest_price')
    elif sort == 'price_high':
        movies = movies.annotate(
            highest_price=Max('show__price')
        ).order_by('-highest_price')

    movies=movies.distinct()
    paginator = Paginator(movies,6)
    page_number = request.GET.get('page')
    movies = paginator.get_page(page_number)

    genre = Genre.objects.all()
    languages = Language.objects.all()
    theatres = Theatre.objects.all()


    return render(request,'movie_discovery.html',{
        'movies':movies,
        'genre':genre,
        'languages':languages,
        'page_obj':movies,
        'recommended_movies':recommended_movies,
    })

def select_seats(request, show_id):
    show = Show.objects.get(id=show_id)

    seats = Seat.objects.filter(screen = show.screen)

    bookings = Booking.objects.filter(
        show = show,
        status = 'confirmed'
    )

    booked_seats = []

    for booking in bookings:
            booked_seats.extend(booking.seats.split(','))


    #get active seat reservation
    SeatReservation.objects.filter(
        expires_at__lte=timezone.now()
     ).delete()
    reserved_seats = SeatReservation.objects.filter(
        show=show
    ).values_list('seat__seat_number', flat=True)
    
        
    return render(request, 'select_seat.html',{'show':show, 'seats': seats, 'booked_seats': booked_seats, 'reserved_seats':reserved_seats})
def reserve_seats(request, show_id):

    show = Show.objects.get(id = show_id)

    if request.method == 'POST':
        selected_seats = request.POST.get('seats','')
        print("SELECTED SEATS:", selected_seats)

        expires_at = timezone.now() + timedelta(minutes=2)
       
        Booking.objects.create(
            show=show,
            user=request.user,
            seats=selected_seats,
            total_price = 0,
            status = 'reserved',
            reserved_at = timezone.now(),
            expires_at = expires_at
        )
      
        return redirect( f'/payment/{show.id}/?seats={selected_seats}')
    
def payment(request, show_id):
    show = Show.objects.get(id=show_id)
    client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET
            )
        )
    seats = request.GET.get('seats','')

    selected_seats = seats.split(',')
    total_price = show.price*len(selected_seats)
    amount = int(total_price * 100)

    order = client.order.create({
        'amount': amount,
        'currency':'INR',
        'payment_capture':1
    })
    print("RAZORPAY ORDER:", order)
    
    if request.method == 'POST':
        selected_seats = request.POST.get('seats')
        total_price = request.POST.get('total_price')

        reservation = SeatReservation.objects.filter(
            show=show,
            user=request.user,
            seat__seat_number__in=selected_seats.split(','),
            expires_at__gt=timezone.now())
        if reservation.count() != len(selected_seats.split(',')):
            return JsonResponse({
                'success':False,
                'message':'Your seat reservation has expired or is invalid.'
            })
        Booking.objects.create(
            show = show,
            user = request.user,
            seats = selected_seats,
            total_price = total_price

        )
        return redirect('show_list')

    return render(request,'payment.html',{
        'show':show,
        'seats':seats,
        'order_id':order['id'],
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'amount':amount,
        'total_price':total_price
    })

def payment_success(request):
    if request.method != 'POST':
        return JsonResponse({
        'success':False,
        'message':'Invalid request method.'
    })
    data = json.loads(request.body)

    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_signature = data.get('razorpay_signature')
    show_id = data.get('show_id')
    seats = data.get('seats','')

    client = razorpay.Client(
        auth = (
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        )
    )
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id':razorpay_order_id,
            'razorpay_payment_id':razorpay_payment_id,
            'razorpay_signature':razorpay_signature
        })

        show = Show.objects.get(id = show_id)

        selected_seats = seats.split(',')

        reservation = SeatReservation.objects.filter(
            show= show,
            user = request.user,
            seat__seat_number__in= selected_seats,
            expires_at__gt=timezone.now()
        )

        if reservation.count() != len(selected_seats):
            return JsonResponse({
                'success':False,
                'message':'Your seat reservation has expired or is invalid.'
            })

        total_price = show.price * len(selected_seats)

        booking = Booking.objects.create(
            show = show,
            user = request.user,
            seats = seats,
            total_price = total_price,
            status = 'confirmed'
        )
        generate_ticket_pdf(booking.id)
        try:
            send_ticket_email(booking.id)
        except Exception as e:
            print("Email Failed:",e)
        reservation.delete()

        return JsonResponse({
            'success':True,
            'message':'Payment verified and booking confirmed.'
        })
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({
            'success':False,
            'message':'Payment verification failed.'
        })
    except Show.DoesNotExist:
        return JsonResponse({
            'success':False,
            'message':'Show Not Found.'
        })
    
@login_required
@user_passes_test(lambda user:user.is_staff)

def admin_dashboard(request):
    total_revenue = Booking.objects.filter(
        status = "confirmed"
    ).aggregate(
        total = Sum ('total_price')
    )['total'] or 0

    total_bookings = Booking.objects.filter(
        status = 'confirmed'
    ).count()

    total_users = User.objects.count()

    total_shows = Show.objects.count()

    booking_trends = (
        Booking.objects.filter(status='confirmed').annotate(date=TruncDate('booking_date')).values('date').annotate(total=Count('id')).order_by('date')
    )

    booking_date = [
        item['date'].strftime('%Y-%m-%d')
        for item in booking_trends
    ]

    booking_counts = [
        item['total']
        for item in booking_trends
    ]

    period = request.GET.get('period','daily')

   

    if period == 'weekly':
        date_function = TruncWeek('booking_date')
    elif period == 'monthly':
        date_function = TruncMonth('booking_date')
    elif period == 'yearly':
        date_function = TruncYear('booking_date')
    else:
        date_function = TruncDate('booking_date')


    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')     

    revenue_queryset = Booking.objects.filter(status='confirmed')

    
    if start_date:
        revenue_queryset = revenue_queryset.filter(
            booking_date__date__gte=start_date
            )
    if end_date:
        revenue_queryset = revenue_queryset.filter(
            booking_date__date__lte=end_date
        )       
   
    revenue_trends = (
        revenue_queryset
        .annotate(date=date_function)
        .values('date')
        .annotate(total = Sum('total_price'))
        .order_by('date')

    )  
    revenue_dates = [
        item['date'].strftime('%Y-%m-%d')
        for item in revenue_trends
    ]

    revenue_amounts = [
        float(item['total'] or 0)
        for item in revenue_trends
    ]

    #most booked movies.
    most_booked_movies = (
        Booking.objects.filter(
            status="confirmed"
            )
            .values(
            "show__movie__title"
            )
            .annotate(
            total_bookings=Count("id")
            )
            .order_by(
            "-total_bookings"
            )
            [:10]
            )
    
    #top performing theatre.
    top_theatre = (
        Booking.objects.filter(status="confirmed")
        .values("show__theatre__name")
        .annotate(
            total_booking=Count("id"),
            revenue = Sum("total_price") 
        )
        .order_by("-revenue")[:10]
    )

    #peak booking hour
    peak_hours = (
        Booking.objects
        .filter(status="confirmed")
        .annotate(
            hour = ExtractHour("booking_date")
        )
        .values("hour")
        .annotate(
            total=Count("id")
        )
        .order_by("-total")
    )

    #Cancellation
    cancelled_bookings = Booking.objects.filter(
        status = "cancelled"
    ).count()

    #Refunds
    refunded_amount = (
        Payment.objects
        .filter(status="refunded")
        .aggregate(
            total= Sum("amount")
        )
        ["total"] or 0
    )

    #theatre occupancy

    theatre_occupancy = []

    theatres = Theatre.objects.all()
    for theatre in theatres:

        total_seats = Seat.objects.filter(
                screen__theatre=theatre           
            ).count()

        confirmed_bookings = Booking.objects.filter(
            show__theatre=theatre,
            status="confirmed"
        ).values_list("seats",flat=True)

        booked_seats = 0

    for seats in confirmed_bookings:
        if seats:
            booked_seats += len(
                [seat.strip() for seat in seats.split(",") if seat.strip()]
            )

    occupancy = (
        (booked_seats / total_seats) * 100
        if total_seats > 0
        else 0
    )

    theatre_occupancy.append({
        "name":theatre.name,
        "total_seats":total_seats,
        "booked_seats":booked_seats,
        "occupancy":round(occupancy,2)
    })

    #user Growth
    user_growth = (
        User.objects.annotate(date=TruncDate("date_joined"))
        .values("date")
        .annotate(
            total=Count("id")
        )
        .order_by("date")
    )
    user_growth_date = [
        item['date'].strftime("%Y-%m-%d")
        for item in user_growth
    ]
    user_growth_counts = [
        item['total']
        for item in user_growth
    ]

    return render(request,
                  'admin_dashboard.html',
                  { 
                    'total_revenue': total_revenue, 
                    'total_bookings': total_bookings,
                    'total_users': total_users, 
                    'total_shows':total_shows , 
                    'booking_date':json.dumps(booking_date),
                    'booking_counts':json.dumps(booking_counts),
                    'revenue_dates':json.dumps(revenue_dates),
                    'revenue_amounts':json.dumps(revenue_amounts),
                    'most_booked_movies':most_booked_movies,
                    'top_theatre':top_theatre,
                    'peak_hours':peak_hours,
                    'cancelled_bookings':cancelled_bookings,
                    'refunded_amount':refunded_amount,
                    'user_growth_dates':json.dumps(user_growth_date),
                    'user_growth_counts':json.dumps(user_growth_counts),
                    'theatre_occupancy':theatre_occupancy,
                    'period':period,
                    'start_date':start_date,
                    'end_date':end_date,
                    })
def export_booking_csv(request):
    response = HttpResponse(content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename = "booking_report.csv"'
    writer = csv.writer(response)

    writer.writerow([
        'Booking ID',
        'User',
        'Movie',
        'Theatre',
        'Show Date',
        'Show Time',
        'Seats',
        'Total Price',
        'Status',
        'Booking Date'
    ])
    bookings = Booking.objects.select_related(
        'user',
        'show__movie',
        'show__theatre'
    ).all()

    for booking in bookings:
        writer.writerow([
            booking.id,
            booking.user.username,
            booking.show.movie.title,
            booking.show.theatre.name,
            booking.show.show_date,
            booking.show.show_time,
            booking.seats,
            booking.total_price,
            booking.status,
            booking.booking_date,
        ])
    return response
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        User.objects.create_user(
            username=username,
            password=password
        )
        return redirect('login')
    return render(request, 'register.html')

def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username = username,
            password = password
        )

        if user is not None:
            login(request,user)
            return redirect('show_list')
        
    return render(request, "login.html")

def add_review(request, movie_id):
    movie = Movie.objects.get(id=movie_id)

    if request.method == 'POST':
       
       
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')

        booking = Booking.objects.filter(
            user = request.user,
            show__movie = movie,
            status = 'confirmed',
            watched = True
        ).first()

        if booking is None:
            return render(request,'review.html',{
                'movie': movie,
                'error': 'You can review this movie only after watching it.'
            })

        existing_review = Review.objects.filter(
            user = request.user,
            movie = movie,
        ).first()

        if existing_review:
            return render(request,'review.html',{
                'movie': movie,
                'error': 'You have already reviewd this movie.You can edit your existing review.'
            })
        Review.objects.create(
            user = request.user,
            movie = movie,
            rating = rating,
            comment = comment
        )

        return redirect('movie_detail',movie_id = movie.id)
    
    return render(request,'review.html',{
        'movie':movie
    })
def edit_review(request, review_id):
    review = Review.objects.get(
        id = review_id,
        user = request.user
    )
    if request.method == "POST":
        review.rating = request.POST.get('rating')
        review.comment = request.POST.get('comment')
        review.save()

        return redirect('movie_detail', movie_id=review.movie.id)
    return render(request,'edit_review.html',{
        'review':review
    })
def report_review(request,review_id):
    review = Review.objects.get(id = review_id)

    if request.method == "POST":
        review.reported = True
        review.save()

    return redirect('movie_detail',movie_id=review.movie.id)

def reserve_seat(request, show_id):
    
    if request.method == "POST":
        show = Show.objects.get(id=show_id)

        selected_seats = request.POST.get('seats','')

        seat_names = [
            seat.strip()
            for seat in selected_seats.split(',')
            if seat.strip()
        ]

        if not seat_names:
            return JsonResponse({
                "success":False,
                "message":"Please select atleast one seat."
            })

        with transaction.atomic():
            
            #removing expired reservation.
            SeatReservation.objects.filter(
                expires_at__lte=timezone.now()
            ).delete()

            #get selected seats for this screen
            seats = Seat.objects.select_for_update().filter(
                screen = show.screen,
                seat_number__in = seat_names 
            )
            #check if selected seat is exist?
            if seats.count() != len(seat_names):
                return JsonResponse({
                    "success": False,
                    "message":"Invalid Seat Selected."
                })
            #check temporary reservation
            already_reserved = SeatReservation.objects.filter(
                show = show,
                seat__in = seats
            ).exists()

            if already_reserved:
                return JsonResponse({
                    "success":False,
                    "message":"Seat already temporarily reserved."
                })

            #check confirmed bookings
            bookings = Booking.objects.filter(
                show = show,
                status = 'confirmed'
            )
            booked_seats = []
            for booking in bookings:
                booked_seats.extend(
                    booking.seats.split(',')
                )
            for seat_name in seat_names:
                if seat_name in booked_seats:
                    return JsonResponse({
                        "success":False,
                        "message":f"Seat {seat_name} is already booked."
                    })
            #Reserve seat for 2 mins

            expires_at=timezone.now() + timedelta(minutes = 2)  

            for seat in seats:
                reservation = SeatReservation.objects.create(
                    show=show,
                    seat = seat,
                    user = request.user,
                    expires_at=expires_at
                )
                
            return redirect(
                f"/payment/{show.id}/?seats={selected_seats}"
            )

@login_required
def download_ticket(request,booking_id):
    booking = Booking.objects.get(
        id=booking_id,
        user = request.user
    )

    pdf_path = os.path.join(
        settings.MEDIA_ROOT,
        'tickets',
        f'booking_{booking.id}.pdf'
    )

    if not os.path.exists(pdf_path):
        generate_ticket_pdf.delay(booking.id)
        return HttpResponse(
            "Your ticket is being generated. Please try again in a few seconds."
        )
    return FileResponse(
        open(pdf_path,'rb'),
        as_attachment=True,
        filename=f'ticket_{booking.id}.pdf'
    )