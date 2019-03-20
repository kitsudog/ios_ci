from django.conf.urls import url

from .views import add_device, download_profile, newbee, security_code, login_by_curl, init_account, upload_ipa, download_mp, mobconf, \
    info, login_by_fastlane, security_code_sms, wait, task_state

urlpatterns = [
    url(r'init_account', init_account),
    url(r'add_device', add_device),
    url(r'download_profile', download_profile),
    url(r'newbee', newbee),
    url(r'security_code', security_code),
    url(r'sms', security_code_sms),
    url(r'login_by_curl', login_by_curl),
    url(r'login_by_fastlane', login_by_fastlane),
    url(r'upload_ipa', upload_ipa),
    url(r'download_mp', download_mp),
    url(r'mobconf', mobconf),
    url(r'info', info),
    url(r'wait', wait),
    url(r'task_state', task_state),
]
