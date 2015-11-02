How to generate certificates
============================

Generate RSA private key (don't replace pass:x, it will be ignored):

   openssl genrsa -des3 -passout pass:x -out server.pass.key 2048

Strip passphrase protection:

   openssl rsa -passin pass:x -in server.pass.key -out server.key
   rm server.pass.key

Generate CSR for self-signing:

   openssl req -new -key server.key -out server.csr -config openssl.cfg

Create self-signed certificate for 1 year:

   openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

To extend the certificate validity period, generate another CSR, then use it to
generate a new self-signed certificate.
