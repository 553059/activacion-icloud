from cryptography import x509
from cryptography.hazmat.backends import default_backend
p='certs/server.crt'
with open(p,'rb') as f:
    data=f.read()
cert=x509.load_pem_x509_certificate(data,default_backend())
print('subject=', cert.subject.rfc4514_string())
try:
    ext=cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    print('SANs=', ext.value)
except Exception as e:
    print('no SAN', e)
print('issuer=', cert.issuer.rfc4514_string())
print('self-signed=', cert.issuer==cert.subject)
