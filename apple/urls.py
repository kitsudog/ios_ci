from django.conf.urls import url

from .views import add_device, download_profile, newbee, security_code, login_by_curl, init_account, upload_ipa, download_mp, mobconf, \
    info

urlpatterns = {
    url(r'init_account', init_account),
    url(r'add_device', add_device),
    url(r'download_profile', download_profile),
    url(r'newbee', newbee),
    url(r'security_code', security_code),
    url(r'login_by_curl', login_by_curl),
    url(r'upload_ipa', upload_ipa),
    url(r'download_mp', download_mp),
    url(r'mobconf', mobconf),
    url(r'info', info),
}
