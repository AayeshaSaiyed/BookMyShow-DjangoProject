from django.urls import path
from . import views

urlpatterns = [
    path('shows/',views.show_list  ,name = 'show_list'),
    path('movies/<int:movie_id>/',views.movie_detail, name = 'movie_detail'),
    path('select-seat/<int:show_id>/', views.select_seats, name = 'select_seats'),
    path('reserve-seat/<int:show_id>/', views.reserve_seat, name = 'reserve_seat'),
    path('payment/<int:show_id>/', views.payment, name='payment'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('review/<int:movie_id>/', views.add_review, name= 'add_review'),
    path('review/edit/<int:review_id>/', views.edit_review, name= 'edit_review'),
    path('review/<int:review_id>/report/', views.report_review, name= 'report_review'),
    path('admin-dashboard/', views.admin_dashboard, name= 'admin_dashboard'),
    path('export-booking-csv/', views.export_booking_csv, name='export_booking_csv'),
    path('movies/',views.movie_discovery,name='movie_discovery'),
    path('download-ticket/<int:booking_id>/',views.download_ticket,name='download_ticket'),

]
