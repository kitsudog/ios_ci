#!/usr/bin/env bash
# http://www.skyfox.org/ios-mobileconfig-sign.html
# 导出有用的证书为 InnovCertificates.p12 带有专用秘钥的
openssl pkcs12 -clcerts -nokeys -out InnovCertificates.pem -in InnovCertificates.p12
openssl pkcs12 -nocerts -out key.pem -in InnovCertificates.p12
wget https://developer.apple.com/certificationauthority/AppleWWDRCA.cer -o AppleWWDRCA.cer
openssl x509 -inform DER -outform PEM -in AppleWWDRCA.cer -out root.crt.pem
openssl smime -sign -in ../mdm.mobileconfig -out ../mdm_signed.mobileconfig -signer InnovCertificates.pem -inkey key.pem  -certfile root.crt.pem -outform der -nodetach