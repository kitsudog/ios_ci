from django.conf.urls import url

from apple.views import add_device, init_app, download_profile

urlpatterns = [
    url(r'add_device', add_device),
    url(r'init_app', init_app),
    url(r'download_profile', download_profile),
]
