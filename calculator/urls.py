from django.urls import path

from . import views

app_name = "calculator"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("api/pincode/<str:pincode>/", views.pincode_location, name="pincode-location"),
]
