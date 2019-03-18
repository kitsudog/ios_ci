```
# 生成vendor证书
openssl genrsa -des3 -out vendor.pem 2048
openssl req -new -key vendor.pem -out vendor.csr
# 登录企业账号申请一个新的mdm发布证书(个人号不行)
# https://developer.apple.com/account/ios/certificate/create 获取mdm.cer
openssl x509 -inform der -in mdm.cer -out mdm.pem
# 生成customer证书
openssl genrsa -des3 -out customer.pem 2048
openssl rsa -in customer.pem -out customer.key
openssl req -new -key customer.pem -out customer.csr
openssl req -inform pem -outform der -in customer.csr -out customer.der

wget https://raw.githubusercontent.com/grinich/mdmvendorsign/master/mdm_vendor_sign.py
python2.7 mdm_vendor_sign.py --csr customer.csr --key 'vendor.pem' --mdm mdm.cer
# 用你的 Apple ID 登录 https://identity.apple.com/pushcert/ ，点击“Create aCertificate”，上传 plist_encoded 文件。
# 使用 java 代码签名的请注意，不要上传 plist.xml，而是上传 plist_encoded。
# 上传后会产生一个 APNS 证书，下载后得到一个 .pem 文件(为方便使用，改名为 push_cert.pem)。

# 验证一下APNs证书
openssl s_client -connect gateway.push.apple.com:2195 -cert push_cert.pem -key customer.key -debug -showcerts -status
# 生成APNs证书
openssl pkcs12 -export -in push_cert.pem -out MDMPush.p12 -inkey customer.key
openssl pkcs12 -nodes -in MDMPush.p12 -out MDMPush.pem

# apn推送相关了
export TOKEN=67c7882a1a95db2931ba35ae45428013bace921605c5bc7e8f3a07c7eb243402
export MDM=26A1FD5C-2D78-45E6-B864-19327BD1C0AD
curl --cert MDMPush.pem --http2 -v "https://api.push.apple.com/3/device/${TOKEN}" --data '{"aps": {"sound":"default.caf"}, "mdm":"'${MDM}'"}'    

# token
base64 -D|hexdump -e '16/1 "%02X"'

```
