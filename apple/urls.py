from django.conf.urls import url

from .views import add_device, download_profile, newbee, security_code, login_by_curl, init_account, upload_ipa, download_mp, mobconf, \
    info, login_by_fastlane, security_code_sms, wait, task_state, rebuild, upload_project_ipa, manifest, download_process, download_ipa, \
    test, upload_cert_p12

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
    url(r'rebuild', rebuild),
    url(r'task_state', task_state),
    url(r'download_process', download_process),
    url(r'upload_project_ipa', upload_project_ipa),
    url(r'upload_cert_p12', upload_cert_p12),
    url(r'manifest', manifest),
    url(r'download_ipa', download_ipa),
    url(r'test', test),
]
