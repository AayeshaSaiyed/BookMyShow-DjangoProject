from celery import shared_task
from django.conf import settings
from .models import Booking
from reportlab.pdfgen import canvas
from django.core.mail import EmailMessage
import qrcode
import os

@shared_task
def test_celery():
    return "Celery is Working!"

@shared_task
def generate_ticket_pdf(booking_id):
    booking = Booking.objects.select_related(
        'user',
        'show__movie',
        'show__theatre',
        'show__screen'
    ).get(id=booking_id)

    ticket_dir = os.path.join(settings.MEDIA_ROOT,'tickets')
    os.makedirs(ticket_dir,exist_ok=True)

    pdf_path = os.path.join(
        ticket_dir,
        f'booking_{booking.id}.pdf'
    )

    qr_data = (
        f"Booking ID: {booking.id}\n "
        f"Movie: {booking.show.movie.title}\n "
        f"Theatre: {booking.show.theatre.name}\n "
        f"Date: {booking.show.show_date}\n"
        f"Time: {booking.show.show_time}\n"
        f"Seats: {booking.seats}"
    )
    qr = qrcode.make(qr_data)
    qr_path = os.path.join(
        ticket_dir,
        f'qr_{booking.id}.png'
    )
    qr.save(qr_path)

    pdf = canvas.Canvas(pdf_path)
    pdf.setTitle(f"Movie Ticket - Booking {booking.id}")

    pdf.drawString(50, 800, "MOVIE TICKET")
    pdf.drawString(50, 770, f"Booking ID:{booking.id}")
    pdf.drawString(50, 745, f"Movie:{booking.show.movie.title}")
    pdf.drawString(50, 720, f"Theatre:{booking.show.theatre.name}")
    pdf.drawString(50, 695, f"Screen:{booking.show.screen.name}")
    pdf.drawString(50, 670, f"Date:{booking.show.show_date}")
    pdf.drawString(50, 645, f"Time:{booking.show.show_time}")
    pdf.drawString(50, 620, f"Seats:{booking.seats}")
    pdf.drawString(50, 595, f"Total Price: ₹{booking.total_price}")

    pdf.drawImage(
        qr_path,
        400,
        600,
        width=120,
        height=120
    )

    pdf.save()
    send_ticket_email(booking.id)

    return pdf_path

@shared_task(bind=True, max_retries=3)
def send_ticket_email(self,booking_id):
    try:
        booking = Booking.objects.select_related(
                'user',
                'show__movie',
                'show__theatre'
        ).get(id=booking_id)

        pdf_path = os.path.join(
            settings.MEDIA_ROOT,
            'tickets',
            f'booking_{booking.id}.pdf'
        )

        email = EmailMessage(
            subject=f'Movie Ticket - Booking {booking.id}',
            body=f'''
HELLO {booking.user.username},

Your Movie Booking is Confirmed.

Thank you for booking with BookMyShow!
''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to =[booking.user.email],
        )

        email.attach_file(pdf_path)
        email.send()

        return 'Ticket email sent successfully.'
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
    
    