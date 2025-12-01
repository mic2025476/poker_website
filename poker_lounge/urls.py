from django.contrib import admin
from django.urls import include, path
from home import views as homeView
from gallery import views as galleryView
from pricing import views as priceView
from contact import views as contactView
from django.views.generic import TemplateView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls'),name='home'),
    path('i18n/', include('django.conf.urls.i18n'),name='set_language'),
    path('', homeView.home, name='home'),  # Home page at '/'
    path('gallery/', galleryView.gallery, name='gallery'),
    path('pricing/', priceView.pricing, name='pricing'),
    path('contact/', contactView.contact, name='contact'),
    path('customers/', include('customers.urls')),
    path('bookings/', include('bookings.urls'), name='bookings'),
    path('payments/', include('payments.urls')),
    path("terms/", TemplateView.as_view(template_name="core/terms.html"), name="terms"),
    path("privacy/", TemplateView.as_view(template_name="core/privacy.html"), name="privacy"),
    path("impressum/", TemplateView.as_view(template_name="core/impressum.html"), name="impressum"),
]