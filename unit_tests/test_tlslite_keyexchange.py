# Copyright (c) 2015, Hubert Kario
#
# See the LICENSE file for legal information regarding use of this file.

# compatibility with Python 2.6, for that we need unittest2 package,
# which is not available on 3.3 or 3.4
try:
    import unittest2 as unittest
except ImportError:
    import unittest
try:
    import mock
    from mock import call
except ImportError:
    import unittest.mock as mock
    from unittest.mock import call

from tlslite.handshakesettings import HandshakeSettings
from tlslite.messages import ServerHello, ClientHello, ServerKeyExchange,\
        CertificateRequest, ClientKeyExchange
from tlslite.constants import CipherSuite, CertificateType, AlertDescription, \
        HashAlgorithm, SignatureAlgorithm, GroupName, ECCurveType, \
        SignatureScheme
from tlslite.errors import TLSLocalAlert, TLSIllegalParameterException, \
        TLSDecryptionFailed, TLSInsufficientSecurity, TLSUnknownPSKIdentity, \
        TLSInternalError, TLSDecodeError
from tlslite.x509 import X509
from tlslite.x509certchain import X509CertChain
from tlslite.utils.keyfactory import parsePEMKey
from tlslite.utils.codec import Parser
from tlslite.utils.cryptomath import bytesToNumber, getRandomBytes, powMod, \
        numberToByteArray, isPrime, numBits
from tlslite.mathtls import makeX, makeU, makeK, goodGroupParameters
from tlslite.handshakehashes import HandshakeHashes
from tlslite import VerifierDB
from tlslite.extensions import SupportedGroupsExtension, SNIExtension
from tlslite.utils.ecc import getCurveByName, decodeX962Point, encodeX962Point,\
        getPointByteSize
from tlslite.utils.compat import a2b_hex
import ecdsa
from operator import mul
try:
    from functools import reduce
except ImportError:
    pass

from tlslite.keyexchange import KeyExchange, RSAKeyExchange, \
        DHE_RSAKeyExchange, SRPKeyExchange, ECDHE_RSAKeyExchange, \
        RawDHKeyExchange, FFDHKeyExchange
from tlslite.utils.x25519 import x25519, X25519_G, x448, X448_G
from tlslite.mathtls import RFC7919_GROUPS

srv_raw_key = str(
    "-----BEGIN RSA PRIVATE KEY-----\n"\
    "MIICXQIBAAKBgQDRCQR5qRLJX8sy1N4BF1G1fml1vNW5S6o4h3PeWDtg7JEn+jIt\n"\
    "M/NZekrGv/+3gU9C9ixImJU6U+Tz3kU27qw0X+4lDJAZ8VZgqQTp/MWJ9Dqz2Syy\n"\
    "yQWUvUNUj90P9mfuyDO5rY/VLIskdBNOzUy0xvXvT99fYQE+QPP7aRgo3QIDAQAB\n"\
    "AoGAVSLbE8HsyN+fHwDbuo4I1Wa7BRz33xQWLBfe9TvyUzOGm0WnkgmKn3LTacdh\n"\
    "GxgrdBZXSun6PVtV8I0im5DxyVaNdi33sp+PIkZU386f1VUqcnYnmgsnsUQEBJQu\n"\
    "fUZmgNM+bfR+Rfli4Mew8lQ0sorZ+d2/5fsM0g80Qhi5M3ECQQDvXeCyrcy0u/HZ\n"\
    "FNjIloyXaAIvavZ6Lc6gfznCSfHc5YwplOY7dIWp8FRRJcyXkA370l5dJ0EXj5Gx\n"\
    "udV9QQ43AkEA34+RxjRk4DT7Zo+tbM/Fkoi7jh1/0hFkU5NDHweJeH/mJseiHtsH\n"\
    "KOcPGtEGBBqT2KNPWVz4Fj19LiUmmjWXiwJBAIBs49O5/+ywMdAAqVblv0S0nweF\n"\
    "4fwne4cM+5ZMSiH0XsEojGY13EkTEon/N8fRmE8VzV85YmkbtFWgmPR85P0CQQCs\n"\
    "elWbN10EZZv3+q1wH7RsYzVgZX3yEhz3JcxJKkVzRCnKjYaUi6MweWN76vvbOq4K\n"\
    "G6Tiawm0Duh/K4ZmvyYVAkBppE5RRQqXiv1KF9bArcAJHvLm0vnHPpf1yIQr5bW6\n"\
    "njBuL4qcxlaKJVGRXT7yFtj2fj0gv3914jY2suWqp8XJ\n"\
    "-----END RSA PRIVATE KEY-----\n"\
    )

srv_raw_certificate = str(
    "-----BEGIN CERTIFICATE-----\n"\
    "MIIB9jCCAV+gAwIBAgIJAMyn9DpsTG55MA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNV\n"\
    "BAMMCWxvY2FsaG9zdDAeFw0xNTAxMjExNDQzMDFaFw0xNTAyMjAxNDQzMDFaMBQx\n"\
    "EjAQBgNVBAMMCWxvY2FsaG9zdDCBnzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEA\n"\
    "0QkEeakSyV/LMtTeARdRtX5pdbzVuUuqOIdz3lg7YOyRJ/oyLTPzWXpKxr//t4FP\n"\
    "QvYsSJiVOlPk895FNu6sNF/uJQyQGfFWYKkE6fzFifQ6s9kssskFlL1DVI/dD/Zn\n"\
    "7sgzua2P1SyLJHQTTs1MtMb170/fX2EBPkDz+2kYKN0CAwEAAaNQME4wHQYDVR0O\n"\
    "BBYEFJtvXbRmxRFXYVMOPH/29pXCpGmLMB8GA1UdIwQYMBaAFJtvXbRmxRFXYVMO\n"\
    "PH/29pXCpGmLMAwGA1UdEwQFMAMBAf8wDQYJKoZIhvcNAQELBQADgYEAkOgC7LP/\n"\
    "Rd6uJXY28HlD2K+/hMh1C3SRT855ggiCMiwstTHACGgNM+AZNqt6k8nSfXc6k1gw\n"\
    "5a7SGjzkWzMaZC3ChBeCzt/vIAGlMyXeqTRhjTCdc/ygRv3NPrhUKKsxUYyXRk5v\n"\
    "g/g6MwxzXfQP3IyFu3a9Jia/P89Z1rQCNRY=\n"\
    "-----END CERTIFICATE-----\n"\
    )

srv_raw_ec_key = str(
    "-----BEGIN PRIVATE KEY-----\n"
    "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgCOZr0Ovs0eCmh+XM\n"
    "QWDYVpsQ+sJdjiq/itp/kYnWNSahRANCAATINGMQAl7cXlPrYzJluGOgmc8sYvae\n"
    "tO2EsXKYG6lnYhudZiepVYORP8vqLyxCF/bMIuuVKOPWSfsRGo/H8pnK\n"
    "-----END PRIVATE KEY-----\n"
    )

srv_raw_ec_certificate = str(
    "-----BEGIN CERTIFICATE-----\n"
    "MIIBbTCCARSgAwIBAgIJAPM58cskyK+yMAkGByqGSM49BAEwFDESMBAGA1UEAwwJ\n"
    "bG9jYWxob3N0MB4XDTE3MTAyMzExNDI0MVoXDTE3MTEyMjExNDI0MVowFDESMBAG\n"
    "A1UEAwwJbG9jYWxob3N0MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEyDRjEAJe\n"
    "3F5T62MyZbhjoJnPLGL2nrTthLFymBupZ2IbnWYnqVWDkT/L6i8sQhf2zCLrlSjj\n"
    "1kn7ERqPx/KZyqNQME4wHQYDVR0OBBYEFPfFTUg9o3t6ehLsschSnC8Te8oaMB8G\n"
    "A1UdIwQYMBaAFPfFTUg9o3t6ehLsschSnC8Te8oaMAwGA1UdEwQFMAMBAf8wCQYH\n"
    "KoZIzj0EAQNIADBFAiA6p0YM5ZzfW+klHPRU2r13/IfKgeRfDR3dtBngmPvxUgIh\n"
    "APTeSDeJvYWVBLzyrKTeSerNDKKHU2Rt7sufipv76+7s\n"
    "-----END CERTIFICATE-----\n"
    )

class TestKeyExchange(unittest.TestCase):

    expected_sha1_SKE = bytearray(
            b"\x0c\x00\x00\x8d\x00\x01\x05\x00\x01\x02\x00\x01\x03"
            b"\x02\x01"
            b"\x00\x80"
            b"\xb4\xe0t\xa3\x13\x8e\xc8z\'|>\x8c\x1d\x9e\x00\x8c\x1c\x18\xd7"
            b"#a\xe5\x15JH\xd5\xde\x1f\x12\xcej\x02k,4\x00V5\x04\xb3}\x92\xfc"
            b"\xbd@\x0c\x03\x06\x02J\xb8*\xafR2\x10\xd6\x9a\xa9\n\x8e\xe8\xb3"
            b"Y\xaf\tm\x0cZ\xbdzL\xdf:/\x91^c~\xfc\xf4_\xf3\xfdv\x00\xc1d\x97"
            b"\x95\xf4A\xd1\x9e&J@\xect\xc2\xe7\xff\xfc\xdf/d\xbd\x1c\xbc\xa1"
            b"f\x14\x92\x06c\xb853\xaf\xf27\xda\xd1\xf9\x97\xea\xec\x90")

    expected_tls1_1_SKE = bytearray(
            b'\x0c\x00\x00\x8b\x00\x01\x05\x00\x01\x02\x00\x01\x03'
            b'\x00\x80'
            b'=\xdf\xfaW+\x81!Q\xc7\xbf\x11\xeeQ\x88\xb2[\xe6n\xd1\x1f\x86\xa8'
            b'\xe5\xac\\\xae0\x0fg:tA\x1b*1?$\xd6;XQ\xac\xfdw\x85\xae\xdaOd'
            b'\xc8\xb0X_\xae\x80\x87\x11\xb1\x08\x1c3!\xb5\xe6\xcf\x11\xbcV'
            b'\x8f\n\x7f\xe7\xfa\x9a\xed!\xf0\xccF\xdf\x9c<\xe7)=\x9d\xde\x0f'
            b'\n3\x9d5\x14\x05\x06nA\xa0\x19\xd5\xaa\x9d\xd1\x16\xb3\xb9\xae'
            b'\xd1\xe4\xc04\xc1h\xc3\xf5/\xb2\xf6P\r\x1b"\xe9\xc9\x84&\xe1Z')

    expected_tls1_1_ecdsa_SKE = bytearray(
            b'\x0c\x00\x00P\x03\x00\x17\x03\x04\xff\xfa\x00G0E\x02!\x00\xc6'
            b'\xa5\x83\xab\x13\xb83"P\xdcl\x817\xcbS\xab\xebxo\x91K@\x19\xe0'
            b'#\xfe,M\xd7R\'\xb0\x02 <\xd6\x03\xdd\x1fS\x12o\xaaa\x9e\x7f\xf1'
            b')\x93\xa9cr\xa1\xb3\xa7\r\xdb\xbbV\xb2\xac\xf6ZJ\xe3\x0e'
            )
    expected_tls1_2_ecdsa_SKE = bytearray(
            b'\x0c\x00\x00R\x03\x00\x17\x03\x04\xff\xfa\x02\x03\x00G0E\x02!'
            b'\x00\xc6\xa5\x83\xab\x13\xb83"P\xdcl\x817\xcbS\xab\xebxo\x91K@'
            b'\x19\xe0#\xfe,M\xd7R\'\xb0\x02 <\xd6\x03\xdd\x1fS\x12o\xaaa\x9e'
            b'\x7f\xf1)\x93\xa9cr\xa1\xb3\xa7\r\xdb\xbbV\xb2\xac\xf6ZJ\xe3\x0e'
            )

class TestKeyExchangeBasics(TestKeyExchange):
    def test___init__(self):
        keyExchange = KeyExchange(0, None, None, None)

        self.assertIsNotNone(keyExchange)

    def test_makeServerKeyExchange(self):
        keyExchange = KeyExchange(0, None, None, None)
        with self.assertRaises(NotImplementedError):
            keyExchange.makeServerKeyExchange()

    def test_makeClientKeyExchange(self):
        srv_h = ServerHello().create((3, 3), bytearray(32), bytearray(0), 0)
        keyExchange = KeyExchange(0, None, srv_h, None)
        self.assertIsInstance(keyExchange.makeClientKeyExchange(),
                              ClientKeyExchange)

    def test_processClientKeyExchange(self):
        keyExchange = KeyExchange(0, None, None, None)
        with self.assertRaises(NotImplementedError):
            keyExchange.processClientKeyExchange(None)

    def test_processServerKeyExchange(self):
        keyExchange = KeyExchange(0, None, None, None)
        with self.assertRaises(NotImplementedError):
            keyExchange.processServerKeyExchange(None, None)

    def test_signServerKeyExchange_with_sha1_in_TLS1_2(self):
        srv_private_key = parsePEMKey(srv_raw_key, private=True)
        client_hello = ClientHello()
        cipher_suite = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
        server_hello = ServerHello().create((3, 3),
                                            bytearray(32),
                                            bytearray(0),
                                            cipher_suite)
        keyExchange = KeyExchange(cipher_suite,
                                  client_hello,
                                  server_hello,
                                  srv_private_key)

        server_key_exchange = ServerKeyExchange(cipher_suite, (3, 3))\
                              .createDH(5, 2, 3)

        keyExchange.signServerKeyExchange(server_key_exchange, 'sha1')

        self.assertEqual(server_key_exchange.write(), self.expected_sha1_SKE)

    def test_signServerKeyExchange_in_TLS1_1(self):
        srv_private_key = parsePEMKey(srv_raw_key, private=True)
        client_hello = ClientHello()
        cipher_suite = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
        server_hello = ServerHello().create((3, 2),
                                            bytearray(32),
                                            bytearray(0),
                                            cipher_suite)
        keyExchange = KeyExchange(cipher_suite,
                                  client_hello,
                                  server_hello,
                                  srv_private_key)
        server_key_exchange = ServerKeyExchange(cipher_suite, (3, 2))\
                              .createDH(5, 2, 3)

        keyExchange.signServerKeyExchange(server_key_exchange)

        self.assertEqual(server_key_exchange.write(), self.expected_tls1_1_SKE)

    def test_signServerKeyExchange_with_sha1_ecdsa_in_TLS1_2(self):
        srv_private_key = parsePEMKey(srv_raw_ec_key, private=True)
        client_hello = ClientHello()
        cipher_suite = CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA
        server_hello = ServerHello().create((3, 3),
                                            bytearray(32),
                                            bytearray(0),
                                            cipher_suite)
        keyExchange = KeyExchange(cipher_suite,
                                  client_hello,
                                  server_hello,
                                  srv_private_key)

        server_key_exchange = ServerKeyExchange(cipher_suite, (3, 3))\
                              .createECDH(ECCurveType.named_curve,
                                          GroupName.secp256r1,
                                          bytearray(b'\x04\xff\xfa'))

        keyExchange.signServerKeyExchange(server_key_exchange, 'sha1')

        self.maxDiff = None
        self.assertEqual(server_key_exchange.write(),
                         self.expected_tls1_2_ecdsa_SKE)

    def test_signServerKeyExchange_in_TLS1_1_with_ecdsa(self):
        srv_private_key = parsePEMKey(srv_raw_ec_key, private=True)
        client_hello = ClientHello()
        cipher_suite = CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA
        server_hello = ServerHello().create((3, 2),
                                            bytearray(32),
                                            bytearray(0),
                                            cipher_suite)
        keyExchange = KeyExchange(cipher_suite,
                                  client_hello,
                                  server_hello,
                                  srv_private_key)
        server_key_exchange = ServerKeyExchange(cipher_suite, (3, 2))\
                              .createECDH(ECCurveType.named_curve,
                                          GroupName.secp256r1,
                                          bytearray(b'\x04\xff\xfa'))

        keyExchange.signServerKeyExchange(server_key_exchange)

        self.maxDiff = None
        self.assertEqual(bytearray(server_key_exchange.write()),
                         self.expected_tls1_1_ecdsa_SKE)

    def test_signServerKeyExchange_in_TLS1_1_signature_invalid(self):
        srv_private_key = parsePEMKey(srv_raw_key, private=True)
        client_hello = ClientHello()
        cipher_suite = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
        server_hello = ServerHello().create((3, 2),
                                            bytearray(32),
                                            bytearray(0),
                                            cipher_suite)
        keyExchange = KeyExchange(cipher_suite,
                                  client_hello,
                                  server_hello,
                                  srv_private_key)
        server_key_exchange = ServerKeyExchange(cipher_suite, (3, 2)) \
            .createDH(5, 2, 3)

        with self.assertRaises(TLSInternalError):
            keyExchange.privateKey.sign = mock.Mock(
                return_value=bytearray(b'wrong'))
            keyExchange.signServerKeyExchange(server_key_exchange)

class TestKeyExchangeVerifyServerKeyExchange(TestKeyExchange):
    def setUp(self):
        self.srv_cert_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.srv_pub_key = self.srv_cert_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
        self.server_key_exchange = ServerKeyExchange(self.cipher_suite, (3, 3))\
                                   .parse(Parser(self.expected_sha1_SKE[1:]))
        self.ske_tls1_1 = ServerKeyExchange(self.cipher_suite, (3, 2))\
                                    .parse(Parser(self.expected_tls1_1_SKE[1:]))

        self.client_hello = ClientHello()

    def test_verifyServerKeyExchange(self):
        KeyExchange.verifyServerKeyExchange(self.server_key_exchange,
                                            self.srv_pub_key,
                                            self.client_hello.random,
                                            bytearray(32),
                                            [(HashAlgorithm.sha1,
                                              SignatureAlgorithm.rsa)])

    def test_verifyServerKeyExchange_with_invalid_hash(self):
        with self.assertRaises(TLSIllegalParameterException):
            KeyExchange.verifyServerKeyExchange(self.server_key_exchange,
                                                self.srv_pub_key,
                                                self.client_hello.random,
                                                bytearray(32),
                                                [(HashAlgorithm.sha256,
                                                  SignatureAlgorithm.rsa)])

    def test_verifyServerKeyExchange_with_unknown_hash(self):
        self.server_key_exchange.hashAlg = 244
        with self.assertRaises(TLSIllegalParameterException):
            KeyExchange.verifyServerKeyExchange(self.server_key_exchange,
                                                self.srv_pub_key,
                                                self.client_hello.random,
                                                bytearray(32),
                                                [(244,
                                                  SignatureAlgorithm.rsa)])

    def test_verifyServerKeyExchange_with_unknown_sig(self):
        self.server_key_exchange.signAlg = 244
        with self.assertRaises(TLSInternalError):
            KeyExchange.verifyServerKeyExchange(self.server_key_exchange,
                                                self.srv_pub_key,
                                                self.client_hello.random,
                                                bytearray(32),
                                                [(HashAlgorithm.sha1,
                                                  244)])

    def test_verifyServerKeyExchange_with_empty_signature(self):
        self.server_key_exchange.signature = bytearray(0)

        with self.assertRaises(TLSIllegalParameterException):
            KeyExchange.verifyServerKeyExchange(self.server_key_exchange,
                                                self.srv_pub_key,
                                                self.client_hello.random,
                                                bytearray(32),
                                                [(HashAlgorithm.sha1,
                                                  SignatureAlgorithm.rsa)])

    def test_verifyServerKeyExchange_with_damaged_signature(self):
        self.server_key_exchange.signature[-1] ^= 0x01

        with self.assertRaises(TLSDecryptionFailed):
            KeyExchange.verifyServerKeyExchange(self.server_key_exchange,
                                                self.srv_pub_key,
                                                self.client_hello.random,
                                                bytearray(32),
                                                [(HashAlgorithm.sha1,
                                                  SignatureAlgorithm.rsa)])

    def test_verifyServerKeyExchange_in_TLS1_1(self):
        KeyExchange.verifyServerKeyExchange(self.ske_tls1_1,
                                            self.srv_pub_key,
                                            self.client_hello.random,
                                            bytearray(32),
                                            None)

    def test_verifyServerKeyExchange_with_damaged_signature_in_TLS1_1(self):
        self.ske_tls1_1.signature[-1] ^= 0x01
        with self.assertRaises(TLSDecryptionFailed):
            KeyExchange.verifyServerKeyExchange(self.ske_tls1_1,
                                                self.srv_pub_key,
                                                self.client_hello.random,
                                                bytearray(32),
                                                None)


class TestServerKeyExchangeP256(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        certificate = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIBbTCCARSgAwIBAgIJAPM58cskyK+yMAkGByqGSM49BAEwFDESMBAGA1UEAwwJ\n"
            "bG9jYWxob3N0MB4XDTE3MTAyMzExNDI0MVoXDTE3MTEyMjExNDI0MVowFDESMBAG\n"
            "A1UEAwwJbG9jYWxob3N0MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEyDRjEAJe\n"
            "3F5T62MyZbhjoJnPLGL2nrTthLFymBupZ2IbnWYnqVWDkT/L6i8sQhf2zCLrlSjj\n"
            "1kn7ERqPx/KZyqNQME4wHQYDVR0OBBYEFPfFTUg9o3t6ehLsschSnC8Te8oaMB8G\n"
            "A1UdIwQYMBaAFPfFTUg9o3t6ehLsschSnC8Te8oaMAwGA1UdEwQFMAMBAf8wCQYH\n"
            "KoZIzj0EAQNIADBFAiA6p0YM5ZzfW+klHPRU2r13/IfKgeRfDR3dtBngmPvxUgIh\n"
            "APTeSDeJvYWVBLzyrKTeSerNDKKHU2Rt7sufipv76+7s\n"
            "-----END CERTIFICATE-----\n")
        x509 = X509()
        x509.parse(certificate)
        cls.x509 = x509

    def test_verify_ecdsa_signature_in_TLS1_2_SHA512(self):
        skemsg = a2b_hex(
                  "00009103001741048803928b0f1448237646bd5ae80b5144b315eb"
                  "f083212f62db03bfd20ff1ec83b086a6b642e9147953b65518b94fdd"
                  "b7946fa08726478e5d2543e833c24f57da060300483046022100b3ee"
                  "ead2f6b30b905ce674f6b7c9e5e4e59239931a7836bb18be03f39e60"
                  "a81c022100b9a064aead86af8e59aaaa30ca57e06f05e0ede23e4745"
                  "524d830f5b85c7fa14")
        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("5078aff2993c6cc0d5bbc014a60e348890c"
                                "ef321469d9f5ecc270be5e453e7c9")
        server_random = a2b_hex("aa14012f6c6070b585fa53ba1010d5c4c08"
                                "7314bd272cd52734c44c8f6037679")


        KeyExchange.verifyServerKeyExchange(ske,
                                            self.x509.publicKey,
                                            client_random,
                                            server_random,
                                            [(HashAlgorithm.sha512,
                                              SignatureAlgorithm.ecdsa)])

    def test_verify_ecdsa_signature_in_TLS1_2_SHA1(self):
        skemsg = a2b_hex(
                        "00008f0300174104677708522c34"
                        "792f4a71864854bc439134baf70cf9ec887db4f8"
                        "ad39f87071c284f5a07975de42b0beec9dfe08c3"
                        "ee3cdf53c49daa57aadfddee9c3be3ca05670203"
                        "0046304402206e3f278d3b54108b40df17c71ac6"
                        "8a801c7bb863a7c477fd8a21b680ca02fbeb0220"
                        "1b497a72f9af66f406d1146971623d7087710641"
                        "dfaff5cfd575a8359165c18f")
        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("affab7761c9d4882d10c17757f648"
                                "76c04a25c0ccdbfa98d9c6a545794"
                                "ab566c")
        server_random = a2b_hex("21b01edc3232325bc6d761e9d4fea"
                                "ccd811051c5bc5f3e09d769a5e15d"
                                "d67273")

        KeyExchange.verifyServerKeyExchange(ske,
                                            self.x509.publicKey,
                                            client_random,
                                            server_random,
                                            [(HashAlgorithm.sha1,
                                              SignatureAlgorithm.ecdsa)])

    def test_verify_ecdsa_signature_in_TLS1_2_SHA256(self):
        skemsg = a2b_hex(
                        "0000900300174104677708522c34792f4a71864854"
                        "bc439134baf70cf9ec887db4f8ad39f87071c284f5a0"
                        "7975de42b0beec9dfe08c3ee3cdf53c49daa57aadfdd"
                        "ee9c3be3ca05670403004730450220762a8a7bfe61b9"
                        "13f92f396908c889c4d12812057fe2f41b49c4bf572d"
                        "a3ec17022100d02bbc51221eb00702856981a36a0958"
                        "fda7f807f0881c677d20a5cc5cac03f4")
        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("cd10871a3d49e42ec2a9e6fc871d1049"
                                "86f5b9c91f4d3f9d693290a611424d2f")
        server_random = a2b_hex("109f6344e1fad353b2767f63ea152474"
                                "bb12d21f5bd903880a30bda436f31684")

        KeyExchange.verifyServerKeyExchange(ske,
                                            self.x509.publicKey,
                                            client_random,
                                            server_random,
                                            [(HashAlgorithm.sha256,
                                              SignatureAlgorithm.ecdsa)])

    def test_verify_ecdsa_signature_with_mismatched_hash(self):
        # valid SKE but changed sha256 ID to SHA1 ID
        skemsg = a2b_hex(
                        "0000900300174104677708522c34792f4a71864854"
                        "bc439134baf70cf9ec887db4f8ad39f87071c284f5a0"
                        "7975de42b0beec9dfe08c3ee3cdf53c49daa57aadfdd"
                        "ee9c3be3ca05670203004730450220762a8a7bfe61b9"
                        "13f92f396908c889c4d12812057fe2f41b49c4bf572d"
                        "a3ec17022100d02bbc51221eb00702856981a36a0958"
                        "fda7f807f0881c677d20a5cc5cac03f4")
        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("cd10871a3d49e42ec2a9e6fc871d1049"
                                "86f5b9c91f4d3f9d693290a611424d2f")
        server_random = a2b_hex("109f6344e1fad353b2767f63ea152474"
                                "bb12d21f5bd903880a30bda436f31684")

        with self.assertRaises(TLSDecryptionFailed):
            KeyExchange.verifyServerKeyExchange(ske,
                                                self.x509.publicKey,
                                                client_random,
                                                server_random,
                                                [(HashAlgorithm.sha1,
                                                  SignatureAlgorithm.ecdsa)])

    def test_verify_ecdsa_signature_with_unknown_alg(self):
        # valid SKE but changed sha256 ID to 10
        skemsg = a2b_hex(
                        "0000900300174104677708522c34792f4a71864854"
                        "bc439134baf70cf9ec887db4f8ad39f87071c284f5a0"
                        "7975de42b0beec9dfe08c3ee3cdf53c49daa57aadfdd"
                        "ee9c3be3ca05670a03004730450220762a8a7bfe61b9"
                        "13f92f396908c889c4d12812057fe2f41b49c4bf572d"
                        "a3ec17022100d02bbc51221eb00702856981a36a0958"
                        "fda7f807f0881c677d20a5cc5cac03f4")
        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("cd10871a3d49e42ec2a9e6fc871d1049"
                                "86f5b9c91f4d3f9d693290a611424d2f")
        server_random = a2b_hex("109f6344e1fad353b2767f63ea152474"
                                "bb12d21f5bd903880a30bda436f31684")

        with self.assertRaises(TLSIllegalParameterException) as e:
            KeyExchange.verifyServerKeyExchange(ske,
                                                self.x509.publicKey,
                                                client_random,
                                                server_random,
                                                [(0x0a,
                                                  SignatureAlgorithm.ecdsa)])

        self.assertIn("Unknown hash algorithm", str(e.exception))


class TestServerKeyExchangeP384(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        certificate = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIBqTCCATGgAwIBAgIJAOg7t3nOR8B6MAkGByqGSM49BAEwFDESMBAGA1UEAwwJ\n"
            "bG9jYWxob3N0MB4XDTE3MTAyNDA4NDE0NFoXDTE3MTEyMzA4NDE0NFowFDESMBAG\n"
            "A1UEAwwJbG9jYWxob3N0MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAESTMngPUfYFqz\n"
            "6c13TgothkDP0NNLb9BxfJ6PeX+Z2Y9Kb/xONDrAil/avCHW3OzYrZjiVrhENRcR\n"
            "1mtxA2ubSlU4bJwItdRy+frJolg4b27Wl9lSpCAn3rgCff9e0puoo1AwTjAdBgNV\n"
            "HQ4EFgQUZ6FxONYHIe0yOhDzNfNlogyNkg8wHwYDVR0jBBgwFoAUZ6FxONYHIe0y\n"
            "OhDzNfNlogyNkg8wDAYDVR0TBAUwAwEB/zAJBgcqhkjOPQQBA2cAMGQCMASrET+o\n"
            "XSFfkriYgmIW8T5tSHZ7Jys1krAS4GUEHYdTkKWSuGfM+0uqblSNgjjYjAIwPXxK\n"
            "pSc6nBMwoE0NFnEa+iL8O3Zl7LDnX2AuKOaV4Id8UuW9653fRCn7CPrfaPOm\n"
            "-----END CERTIFICATE-----\n")
        x509 = X509()
        x509.parse(certificate)

        cls.x509 = x509

    def test_verify_ecdsa_signature_in_TLS1_2_SHA512(self):
        skemsg = a2b_hex(
            "0000af03001741046d571e6310febf38201af10f823241df990a2887f779e590"
            "00dd8fb3ee801e0e700313225e3268c3db2d1eaf13495b99ac5fc4bff5c22d71"
            "c9e867c958aafebb0603006630640230043bc6fd59d5b39296153264a10d63ae"
            "8937120ca0874e7848004d4ce70d66d133af993edca59e93e31845671a1b6743"
            "0230710169783ce59742bcff9884105bc85675d757cf3bc6ac3250f795ee8021"
            "1f086afab96a9aafd3382c96eeb5afde2bc3")

        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("872eca2bd39eaca9eedb31c285f5809b"
                                "5fd5a51efd6d1dee4e1ce4f741920a36")
        server_random = a2b_hex("d85951258d55798f93619c38ac4fdd54"
                                "153c5930cdf2cba6d555eec8d709e303")

        KeyExchange.verifyServerKeyExchange(ske,
                                            self.x509.publicKey,
                                            client_random,
                                            server_random,
                                            [(HashAlgorithm.sha512,
                                              SignatureAlgorithm.ecdsa)])

    def test_verify_ecdsa_signature_in_TLS1_2_SHA384(self):
        skemsg = a2b_hex(
                "0000b103001741046d571e6310febf38201af10f823241df990a2887f77"
                "9e59000dd8fb3ee801e0e700313225e3268c3db2d1eaf13495b99ac5fc4"
                "bff5c22d71c9e867c958aafebb050300683066023100e12366ba68c36ae"
                "f04c691f0c0067d0c8025f116627c5b963154fd219a9bc27ec4a11d6d1b"
                "d4b5d33de8d2dcf639501c0231008a99dad2fa99a689e25422127f12dfe"
                "8fdcaea1b97cb17b6267ebdd97631e004ca323132cc66e651844b40984c"
                "7aa942")

        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("f706a53d88a5eb52d981c9943413b4f6"
                                "73d7426dd4373fe517c1b881ab5713d2")
        server_random = a2b_hex("d35fab56329f6ff1ac36a6fc6b98a393"
                                "e50bc4cd8b8bf3038f8b914f0c105cd2")

        KeyExchange.verifyServerKeyExchange(ske,
                                            self.x509.publicKey,
                                            client_random,
                                            server_random,
                                            [(HashAlgorithm.sha384,
                                              SignatureAlgorithm.ecdsa)])


    def test_verify_ecdsa_signature_in_TLS1_2_SHA256(self):
        skemsg = a2b_hex(
                "0000b103001741046d571e6310febf38201af10f823241df990a2887f779"
                "e59000dd8fb3ee801e0e700313225e3268c3db2d1eaf13495b99ac5fc4bf"
                "f5c22d71c9e867c958aafebb04030068306602310080e64fbb7063b5c424"
                "4e59611a763adafdbf4bc392e3af7ad29c98251a4dcfd9f59b8c39fa46a8"
                "f035d90e0b35181bee023100a383176790f00b2731f85ba90e05e6814080"
                "8f05860c138e0c57eb496b6411792af4662acea03968d1b192afd6dbc2d6"
                )

        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("2b1ffe918934adb2d66bb085bf56ba31"
                                "0f6568732f81abc7f60c1bc43b2b8d15")
        server_random = a2b_hex("5141986a5d3b26cbc051d58c76074643"
                                "c62d8ba9a0aa77bceaa8ecec59771bfe")

        KeyExchange.verifyServerKeyExchange(ske,
                                            self.x509.publicKey,
                                            client_random,
                                            server_random,
                                            [(HashAlgorithm.sha256,
                                              SignatureAlgorithm.ecdsa)])

class TestServerKeyExchangeP521(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        certificate = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIB9DCCAVegAwIBAgIJALLS/7HVXjvLMAkGByqGSM49BAEwFDESMBAGA1UEAwwJ\n"
            "bG9jYWxob3N0MB4XDTE3MTAyNDA5MzI1OVoXDTE3MTEyMzA5MzI1OVowFDESMBAG\n"
            "A1UEAwwJbG9jYWxob3N0MIGbMBAGByqGSM49AgEGBSuBBAAjA4GGAAQA2W4PjcS5\n"
            "O2XC/BePOpu3qLrIKdEYPTbXPz3kX1KAMUKb7Mndl8gYhmt3orymNfyvw/TjUBeT\n"
            "D9C/kH87MM0MTdIADcZOQ8Kaq1KB33bNbsXtkV29SF+070tE6B0AdbKkA51Ak1G8\n"
            "FWmEZtf01e8ajcfsDLzkQenY8nD9/jdXonyRMD6jUDBOMB0GA1UdDgQWBBT8H+nt\n"
            "DHosWy5fTjmDltyvBB6JUjAfBgNVHSMEGDAWgBT8H+ntDHosWy5fTjmDltyvBB6J\n"
            "UjAMBgNVHRMEBTADAQH/MAkGByqGSM49BAEDgYsAMIGHAkIB8rNy9Uq2ZZwFwbdw\n"
            "FBjteJEkJS26E7m3bLf5YmCmdH6wyQd+EjoPVBwOrQxcH0eR/vYEmouTlsBGxdRN\n"
            "1eIm4DQCQUVPccfLbGV4KK3tkij1GH9ej9AQvLpjVMkyhwNadmGadOcIpbciQyll\n"
            "+m9uHWVCSntAeSzf2A6nnVBvRvGbZu1w\n"
            "-----END CERTIFICATE-----\n")

        x509 = X509()
        x509.parse(certificate)

        cls.x509 = x509

    def test_verify_ecdsa_signature_in_TLS1_2_SHA384(self):
        skemsg = a2b_hex(
            "0000d3030017410402f8552b8fb2ce583f6572a872373857de5a4f179c00870"
            "9305391e847416a894d523759e73205b94c64a683bb61f8a6c01c7fee180591"
            "24f47e77aad3b32ada0503008a30818702420153e2b6526452f2174c4b70f9c"
            "de18c63bc8a70bfde5f313e7608fb799893fea45d414e9ff176a9a0a7cd1b8c"
            "0d659d147501ea6482d8d43ac75e0ce6864674196102415e6f6ac717dad1b10"
            "cd20e9dc3d4f6d1e483a349cc7d37ecdb68231b3b41dd60cff9068e38cbd62d"
            "1203be11556991c85c6b9348b958318a91cdaa2e249ea1cb9e")
        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("ccef6eefa66dda9e90c5e56dc3efa1ec"
                                "259485ebcd2ec736ad2bcb3598ac3615")
        server_random = a2b_hex("739fd50e4ecbb177f882536a71828f8e"
                                "bcbcf3a3217da24fa3eb6f7d7b009401")

        KeyExchange.verifyServerKeyExchange(ske,
                                            self.x509.publicKey,
                                            client_random,
                                            server_random,
                                            [(HashAlgorithm.sha384,
                                              SignatureAlgorithm.ecdsa)])

    def test_verify_ecdsa_signature_in_TLS1_2_SHA512(self):
        skemsg = a2b_hex(
            "0000d3030017410402f8552b8fb2ce583f6572a872373857de5a4f179c0087"
            "09305391e847416a894d523759e73205b94c64a683bb61f8a6c01c7fee180591"
            "24f47e77aad3b32ada0603008a308187024200c1ab9d049e28cdd107b7c180d4"
            "dc8f78970edcee88a8b8fbd1a68572d342d97fa0ad1a7d1285ae8ea387c00d2d"
            "f56dcd36146460ccba99e1323078888364604c3202412388817fea69babcb482"
            "cacfe92056507cb85cd840c6a19c3fbf079e67399d72c81642b11b9e89612405"
            "57e39a617f25efeebcfdcf3bf68c792f3a91318b0bd695")

        parser = Parser(skemsg)

        ske = ServerKeyExchange(
                CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
                (3, 3))
        ske.parse(parser)

        client_random = a2b_hex("455c9402792ab4443cacc8f3bc2c9815"
                                "7a3f3e1026a49e50fc04a9a3d2ba18d3")
        server_random = a2b_hex("ae2c2a0b6f65209c10a6766e8d230eb6"
                                "465927ae363950430ec049d6e32cae24")

        KeyExchange.verifyServerKeyExchange(ske,
                                            self.x509.publicKey,
                                            client_random,
                                            server_random,
                                            [(HashAlgorithm.sha512,
                                              SignatureAlgorithm.ecdsa)])


class TestCalcVerifyBytes(unittest.TestCase):
    def setUp(self):
        self.handshake_hashes = HandshakeHashes()
        self.handshake_hashes.update(bytearray(b'\xab'*32))

    def test_with_TLS1_3(self):
        vrfy = KeyExchange.calcVerifyBytes((3, 4),
                                           self.handshake_hashes,
                                           (HashAlgorithm.sha1,
                                            SignatureAlgorithm.rsa),
                                           None, None, None,
                                           'sha256', b'server')
        self.assertEqual(vrfy, bytearray(
            b'\xc5\x86\xeeO\xbe\xed\xc67g\xe0\xb5\xea(#O\xfd1\x85\xa1\xcd'))

    def test_with_TLS1_2(self):
        vrfy = KeyExchange.calcVerifyBytes((3, 3),
                                           self.handshake_hashes,
                                           (HashAlgorithm.sha1,
                                            SignatureAlgorithm.rsa),
                                           None,
                                           None,
                                           None)
        self.assertEqual(vrfy, bytearray(
            # PKCS#1 prefix
            b'0!0\t\x06\x05+\x0e\x03\x02\x1a\x05\x00\x04\x14'
            # SHA1 hash
            b'L3\x81\xad\x1b\xc2\x14\xc0\x8e\xba\xe4\xb8\xa2\x9d(6V1\xfb\xb0'))

    def test_with_TLS1_1(self):
        vrfy = KeyExchange.calcVerifyBytes((3, 2),
                                           self.handshake_hashes,
                                           None, None, None, None)

        self.assertEqual(vrfy, bytearray(
            # MD5 hash
            b'\xe9\x9f\xb4\xd24\xe9\xf41S\xe6?\xa5\xfe\xad\x16\x14'
            # SHA1 hash
            b'L3\x81\xad\x1b\xc2\x14\xc0\x8e\xba\xe4\xb8\xa2\x9d(6V1\xfb\xb0'
            ))

    def test_with_SSL3(self):
        vrfy = KeyExchange.calcVerifyBytes((3, 0),
                                           self.handshake_hashes,
                                           None,
                                           bytearray(b'\x04'*48),
                                           bytearray(b'\xaa'*32),
                                           bytearray(b'\xbb'*32))

        self.assertEqual(vrfy, bytearray(
            b'r_\x06\xd2(\\}v\x87\xfc\xf5\xa2h\xd6S\xd8'
            b'\xed=\x9b\xe3\xd9_%qe\xa3k\xf5\x85\x0e?\x9fr\xfaML'
            ))

    def test_with_TLS1_3_unsupported_hash(self):
        vrfy = KeyExchange.calcVerifyBytes((3, 4),
                                           self.handshake_hashes,
                                           (HashAlgorithm.md5,
                                            SignatureAlgorithm.rsa),
                                           None, None, None,
                                           'sha256', b'server')
        self.assertEqual(vrfy, bytearray(
            b'\xcfY\xa7\x9b \xea\xae4\xdb\xad)\xaeC\xc6\x98\xfd'))


class TestMakeCertificateVerify(unittest.TestCase):
    def setUp(self):
        cert_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.clnt_pub_key = cert_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
        self.clnt_private_key = parsePEMKey(srv_raw_key, private=True)
        self.handshake_hashes = HandshakeHashes()
        self.handshake_hashes.update(bytearray(b'\xab'*32))

    def test_with_TLS1_2(self):
        certificate_request = CertificateRequest((3, 3))
        certificate_request.create([CertificateType.x509],
                                   [],
                                   [(HashAlgorithm.sha256,
                                     SignatureAlgorithm.rsa),
                                    (HashAlgorithm.sha1,
                                     SignatureAlgorithm.rsa)])

        certVerify = KeyExchange.makeCertificateVerify((3, 3),
                                                       self.handshake_hashes,
                                                       [(HashAlgorithm.sha1,
                                                         SignatureAlgorithm.rsa),
                                                        (HashAlgorithm.sha512,
                                                         SignatureAlgorithm.rsa)],
                                                       self.clnt_private_key,
                                                       certificate_request,
                                                       None, None, None)

        self.assertIsNotNone(certVerify)
        self.assertEqual(certVerify.version, (3, 3))
        self.assertEqual(certVerify.signatureAlgorithm, (HashAlgorithm.sha1,
                                                         SignatureAlgorithm.rsa))
        self.assertEqual(certVerify.signature, bytearray(
            b'.\x03\xa2\xf0\xa0\xfb\xbeUs\xdb\x9b\xea\xcc(\xa6:l\x84\x8e\x13'
            b'\xa1\xaa\xdb1P\xe9\x06\x876\xbe+\xe92\x89\xaa\xa5EU\x07\x9a\xde'
            b'\xd37\xafGCR\xdam\xa2v\xde\xceeFI\x80:ZtL\x96\xafZ\xe2\xe2\xce/'
            b'\x9f\x82\xfe\xdb*\x94\xa8\xbd\xd9Hl\xdc\xc8\xbf\x9b=o\xda\x06'
            b'\xfa\x9e\xbfB+05\xc6\xda\xdf\x05\xf2m[\x18\x11\xaf\x184\x12\x9d'
            b'\xb4:\x9b\xc1U\x1c\xba\xa3\x05\xceOn\x0fY\xcaK*\x0b\x04\xa5'
            ))

    def test_with_TLS1_2_md5(self):
        certificate_request = CertificateRequest((3, 3))
        certificate_request.create([CertificateType.x509],
                                   [],
                                   [(HashAlgorithm.md5,
                                     SignatureAlgorithm.rsa),
                                    (HashAlgorithm.sha1,
                                     SignatureAlgorithm.rsa)])

        certVerify = KeyExchange.makeCertificateVerify((3, 3),
                                                       self.handshake_hashes,
                                                       [(HashAlgorithm.md5,
                                                         SignatureAlgorithm.rsa)],
                                                       self.clnt_private_key,
                                                       certificate_request,
                                                       None, None, None)

        self.assertIsNotNone(certVerify)
        self.assertEqual(certVerify.version, (3, 3))
        self.assertEqual(certVerify.signatureAlgorithm, (HashAlgorithm.md5,
                                                         SignatureAlgorithm.rsa))
        self.assertEqual(certVerify.signature, bytearray(
            b'H5\x03U]\x0c\xb6\xc0Y\x98^\x0f \xf4\x15}\x8d\xf7k\x97\\&8j\x94'
            b'\xc6\x04*e\xa6\x95\xc5\xf3\xb1\xd0\xe6\x85[<9\x91K\xc51\xc3\xe9'
            b'\xc6\x15&\x1c\xfb\xb2?\r|\r\xfa"\x8c\xdaHo]\x89\xc8mOE\x9c]\xa0'
            b'\xab#\xf8\xea(\xefE\xb3\x83)f+hS\xa8\x00\xe1\x11\xbd\xfb\xd5\xf5'
            b'[\x9b7\xb1p\xd7\xa3\xc8\xf37K \x91\x0e\x16\xd6\x94t\xec\xe6\xb1Z'
            b'K\xeeg\xb6)>\x91?\xc2\xe2S\xdf\xa9'))

    def test_with_TLS1_2_rsa_pss_sha256(self):
        def m(length):
            return bytearray(length)

        with mock.patch('tlslite.utils.rsakey.getRandomBytes', m):
            certificate_request = CertificateRequest((3, 3))
            certificate_request.create([CertificateType.x509],
                                       [],
                                       [SignatureScheme.rsa_pss_sha256,
                                        (HashAlgorithm.sha1,
                                         SignatureAlgorithm.rsa)])

            certVerify = KeyExchange.makeCertificateVerify((3, 3),
                                                           self.handshake_hashes,
                                                           [SignatureScheme.\
                                                                   rsa_pss_sha256],
                                                           self.clnt_private_key,
                                                           certificate_request,
                                                           None, None, None)

            self.assertIsNotNone(certVerify)
            self.assertEqual(certVerify.version, (3, 3))
            self.assertEqual(certVerify.signatureAlgorithm,
                             SignatureScheme.rsa_pss_sha256)
            self.assertEqual(certVerify.signature, bytearray(
                b'mj{\xb8\xe1\xfdV\x8f>\xc4\x7fy\xe3h}\xb0\xda\xff\xab1\xab='
                b'\xa7x\xf4x\xcduL\xbbN"\xd9\xad\x7f@N\xae\xb1\xc5\x1c\'\x81'
                b'\x7f\xc4\xe3\xc9:Y6\xf77\xb0\xd8\xc3\xbeo\xd0&\xf6\x05x\xc6'
                b'\x9c\xce\xb4\x1eQx \x13\x93qCy\x8d>tCONS\x83\x15\xf7\xf1'
                b'\x96\x15\x1eXv<\xb6\x80\x7fI\x85\xa3\xe1\x18\xd4\xd6\xbe)68'
                b'\xad\xae\x08\xad\x91\xe9rg\x8b\xc8M\xfe{\x0c\xf5\x0fj\'E"9'
                b'\r'))

    def test_with_TLS1_2_and_no_overlap(self):
        certificate_request = CertificateRequest((3, 3))
        certificate_request.create([CertificateType.x509],
                                   [],
                                   [(HashAlgorithm.sha256,
                                     SignatureAlgorithm.rsa),
                                    (HashAlgorithm.sha224,
                                     SignatureAlgorithm.rsa)])

        certVerify = KeyExchange.makeCertificateVerify((3, 3),
                                                       self.handshake_hashes,
                                                       [(HashAlgorithm.sha1,
                                                         SignatureAlgorithm.rsa),
                                                        (HashAlgorithm.sha512,
                                                         SignatureAlgorithm.rsa)],
                                                       self.clnt_private_key,
                                                       certificate_request,
                                                       None, None, None)

        self.assertIsNotNone(certVerify)
        self.assertEqual(certVerify.version, (3, 3))
        # when there's no overlap, we select the most wanted from our side
        self.assertEqual(certVerify.signatureAlgorithm, (HashAlgorithm.sha1,
                                                         SignatureAlgorithm.rsa))
        self.assertEqual(certVerify.signature, bytearray(
            b'.\x03\xa2\xf0\xa0\xfb\xbeUs\xdb\x9b\xea\xcc(\xa6:l\x84\x8e\x13'
            b'\xa1\xaa\xdb1P\xe9\x06\x876\xbe+\xe92\x89\xaa\xa5EU\x07\x9a\xde'
            b'\xd37\xafGCR\xdam\xa2v\xde\xceeFI\x80:ZtL\x96\xafZ\xe2\xe2\xce/'
            b'\x9f\x82\xfe\xdb*\x94\xa8\xbd\xd9Hl\xdc\xc8\xbf\x9b=o\xda\x06'
            b'\xfa\x9e\xbfB+05\xc6\xda\xdf\x05\xf2m[\x18\x11\xaf\x184\x12\x9d'
            b'\xb4:\x9b\xc1U\x1c\xba\xa3\x05\xceOn\x0fY\xcaK*\x0b\x04\xa5'
            ))

    def test_with_TLS1_1(self):
        certificate_request = CertificateRequest((3, 2))
        certificate_request.create([CertificateType.x509],
                                   [],
                                   None)

        certVerify = KeyExchange.makeCertificateVerify((3, 2),
                                                       self.handshake_hashes,
                                                       None,
                                                       self.clnt_private_key,
                                                       certificate_request,
                                                       None, None, None)

        self.assertIsNotNone(certVerify)
        self.assertEqual(certVerify.version, (3, 2))
        self.assertIsNone(certVerify.signatureAlgorithm)
        self.assertEqual(certVerify.signature, bytearray(
            b'=X\x14\xf3\r6\x0b\x84\xde&J\x15\xa02M\xc8\xf1?\xa0\x10U\x1e\x0b'
            b'\x95^\xa19\x14\xf5\xf1$\xe3U[\xb4/\xe7AY(\xee]\xff\x97H\xb8\xa9'
            b'\x8b\x96n\xa6\xf5\x0f\xffd\r\x08/Hs6`wi8\xc4\x02\xa4}a\xcbS\x99'
            b'\x01;\x0e\x88oj\x9a\x02\x98Y\xb5\x00$f@>\xd8\x0cS\x95\xa8\x9e'
            b'\x14uU\\Z\xd0.\xe7\x01_y\x1d\xea\xad\x1b\xf8c\xa6\xc9@\xc6\x90'
            b'\x19~&\xd9\xaa\xc2\t,s\xde\xb1'
            ))

    def test_with_failed_signature(self):
        certificate_request = CertificateRequest((3, 3))
        certificate_request.create([CertificateType.x509],
                                   [],
                                   [(HashAlgorithm.sha256,
                                     SignatureAlgorithm.rsa),
                                    (HashAlgorithm.sha1,
                                     SignatureAlgorithm.rsa)])
        self.clnt_private_key.sign = mock.Mock(return_value=bytearray(20))

        with self.assertRaises(TLSInternalError):
            certVerify = KeyExchange.makeCertificateVerify(
                (3, 3),
                self.handshake_hashes,
                [(HashAlgorithm.sha1,
                  SignatureAlgorithm.rsa),
                 (HashAlgorithm.sha512,
                  SignatureAlgorithm.rsa)],
                self.clnt_private_key,
                certificate_request,
                None, None, None)

class TestRSAKeyExchange(unittest.TestCase):
    def setUp(self):
        self.srv_private_key = parsePEMKey(srv_raw_key, private=True)
        srv_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.srv_pub_key = srv_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA
        self.client_hello = ClientHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 [])
        self.server_hello = ServerHello().create((3, 2),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 self.cipher_suite)

        self.keyExchange = RSAKeyExchange(self.cipher_suite,
                                          self.client_hello,
                                          self.server_hello,
                                          self.srv_private_key)

    def test_RSA_key_exchange(self):

        self.assertIsNone(self.keyExchange.makeServerKeyExchange())

        premaster_secret = bytearray(b'\xf0'*48)
        premaster_secret[0] = 3
        premaster_secret[1] = 3
        clientKeyExchange = ClientKeyExchange(self.cipher_suite,
                                              (3, 2))
        clientKeyExchange.createRSA(self.srv_pub_key.encrypt(premaster_secret))

        dec_premaster = self.keyExchange.processClientKeyExchange(\
                        clientKeyExchange)

        premaster_secret = bytearray(b'\xf0'*48)
        premaster_secret[0] = 3
        premaster_secret[1] = 3
        self.assertEqual(dec_premaster, premaster_secret)

    def test_RSA_key_exchange_with_client(self):
        self.assertIsNone(self.keyExchange.makeServerKeyExchange())

        client_keyExchange = RSAKeyExchange(self.cipher_suite,
                                            self.client_hello,
                                            self.server_hello,
                                            None)

        client_premaster = client_keyExchange.processServerKeyExchange(\
                self.srv_pub_key,
                None)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(\
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)

    def test_RSA_with_invalid_encryption(self):

        self.assertIsNone(self.keyExchange.makeServerKeyExchange())

        premaster_secret = bytearray(b'\xf0'*48)
        premaster_secret[0] = 3
        premaster_secret[1] = 3
        clientKeyExchange = ClientKeyExchange(self.cipher_suite,
                                              (3, 2))
        enc_premaster = self.srv_pub_key.encrypt(premaster_secret)
        enc_premaster[-1] ^= 0x01
        clientKeyExchange.createRSA(enc_premaster)

        dec_premaster = self.keyExchange.processClientKeyExchange(\
                        clientKeyExchange)

        premaster_secret = bytearray(b'\xf0'*48)
        premaster_secret[0] = 3
        premaster_secret[1] = 3
        self.assertNotEqual(dec_premaster, premaster_secret)

    def test_RSA_with_wrong_size_premaster(self):

        self.assertIsNone(self.keyExchange.makeServerKeyExchange())

        premaster_secret = bytearray(b'\xf0'*47)
        premaster_secret[0] = 3
        premaster_secret[1] = 3
        clientKeyExchange = ClientKeyExchange(self.cipher_suite,
                                              (3, 2))
        enc_premaster = self.srv_pub_key.encrypt(premaster_secret)
        clientKeyExchange.createRSA(enc_premaster)

        dec_premaster = self.keyExchange.processClientKeyExchange(\
                        clientKeyExchange)

        premaster_secret = bytearray(b'\xf0'*47)
        premaster_secret[0] = 3
        premaster_secret[1] = 3
        self.assertNotEqual(dec_premaster, premaster_secret)

    def test_RSA_with_wrong_version_in_IE(self):
        # Internet Explorer sends the version from Server Hello not Client Hello

        self.assertIsNone(self.keyExchange.makeServerKeyExchange())

        premaster_secret = bytearray(b'\xf0'*48)
        premaster_secret[0] = 3
        premaster_secret[1] = 2
        clientKeyExchange = ClientKeyExchange(self.cipher_suite,
                                              (3, 2))
        enc_premaster = self.srv_pub_key.encrypt(premaster_secret)
        clientKeyExchange.createRSA(enc_premaster)

        dec_premaster = self.keyExchange.processClientKeyExchange(\
                        clientKeyExchange)

        premaster_secret = bytearray(b'\xf0'*48)
        premaster_secret[0] = 3
        premaster_secret[1] = 2
        self.assertEqual(dec_premaster, premaster_secret)

    def test_RSA_with_wrong_version(self):

        self.assertIsNone(self.keyExchange.makeServerKeyExchange())

        premaster_secret = bytearray(b'\xf0'*48)
        premaster_secret[0] = 3
        premaster_secret[1] = 1
        clientKeyExchange = ClientKeyExchange(self.cipher_suite,
                                              (3, 2))
        clientKeyExchange.createRSA(self.srv_pub_key.encrypt(premaster_secret))

        dec_premaster = self.keyExchange.processClientKeyExchange(\
                        clientKeyExchange)

        premaster_secret = bytearray(b'\xf0'*48)
        premaster_secret[0] = 3
        premaster_secret[1] = 1
        self.assertNotEqual(dec_premaster, premaster_secret)

class TestDHE_RSAKeyExchange(unittest.TestCase):
    def setUp(self):
        self.srv_private_key = parsePEMKey(srv_raw_key, private=True)
        srv_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.srv_pub_key = srv_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
        self.client_hello = ClientHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 [])
        self.server_hello = ServerHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 self.cipher_suite)

        self.keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                              self.client_hello,
                                              self.server_hello,
                                              self.srv_private_key)

    def test_DHE_RSA_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        cln_X = bytesToNumber(getRandomBytes(32))
        cln_Yc = powMod(srv_key_ex.dh_g,
                        cln_X,
                        srv_key_ex.dh_p)
        cln_secret = numberToByteArray(powMod(srv_key_ex.dh_Ys,
                                              cln_X,
                                              srv_key_ex.dh_p))

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3))
        cln_key_ex.createDH(cln_Yc)

        srv_secret = self.keyExchange.processClientKeyExchange(cln_key_ex)

        self.assertEqual(cln_secret, srv_secret)

    def test_DHE_RSA_key_exchange_with_client(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None)
        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(\
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)

    def test_DHE_RSA_key_exchange_with_custom_parameters(self):
        self.keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                              self.client_hello,
                                              self.server_hello,
                                              self.srv_private_key,
                                              # 6144 bit group
                                              goodGroupParameters[5])
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None,)
        client_premaster = client_keyExchange.processServerKeyExchange(
                None,
                srv_key_ex)
        # because the agreed upon secret can be any value between 1 and p-1,
        # we can't check the exact length. At the same time, short shared
        # secrets are exceedingly rare, a share shorter by 4 bytes will
        # happen only once in 256^4 negotiations or 1 in about 4 milliards
        self.assertLessEqual(len(client_premaster), 6144 // 8)
        self.assertGreaterEqual(len(client_premaster), 6144 // 8 - 4)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)


    def test_DHE_RSA_key_exchange_with_rfc7919_groups(self):
        suppGroupsExt = SupportedGroupsExtension().create([GroupName.ffdhe3072,
                                                           GroupName.ffdhe4096]
                                                         )
        self.client_hello.extensions = [suppGroupsExt]
        self.keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                              self.client_hello,
                                              self.server_hello,
                                              self.srv_private_key,
                                              dhGroups=GroupName.allFF)

        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None,)
        client_premaster = client_keyExchange.processServerKeyExchange(
                None,
                srv_key_ex)
        # because the agreed upon secret can be any value between 1 and p-1,
        # we can't check the exact length. At the same time, short shared
        # secrets are exceedingly rare, a share shorter by 4 bytes will
        # happen only once in 256^4 negotiations or 1 in about 4 milliards
        self.assertLessEqual(len(client_premaster), 3072 // 8)
        self.assertGreaterEqual(len(client_premaster), 3072 // 8 - 4)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)


    def test_DHE_RSA_key_exchange_with_ECC_groups(self):
        suppGroupsExt = SupportedGroupsExtension().create([GroupName.secp256r1,
                                                           GroupName.secp521r1,
                                                           650]
                                                         )
        self.client_hello.extensions = [suppGroupsExt]
        self.keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                              self.client_hello,
                                              self.server_hello,
                                              self.srv_private_key,
                                              dhGroups=GroupName.allFF)

        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None,)
        client_premaster = client_keyExchange.processServerKeyExchange(
                None,
                srv_key_ex)
        # because the agreed upon secret can be any value between 1 and p-1,
        # we can't check the exact length. At the same time, short shared
        # secrets are exceedingly rare, a share shorter by 4 bytes will
        # happen only once in 256^4 negotiations or 1 in about 4 milliards
        self.assertLessEqual(len(client_premaster), 2048 // 8)
        self.assertGreaterEqual(len(client_premaster), 2048 // 8 - 4)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)


    def test_DHE_RSA_key_exchange_with_unknown_ffdhe_group(self):
        suppGroupsExt = SupportedGroupsExtension().create([511])
        self.client_hello.extensions = [suppGroupsExt]
        self.keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                              self.client_hello,
                                              self.server_hello,
                                              self.srv_private_key,
                                              dhGroups=GroupName.allFF)

        with self.assertRaises(TLSInternalError):
            self.keyExchange.makeServerKeyExchange('sha1')


    def test_DHE_RSA_key_exchange_with_invalid_client_key_share(self):
        clientKeyExchange = ClientKeyExchange(self.cipher_suite,
                                              (3, 3))
        clientKeyExchange.createDH(2**16000-1)

        with self.assertRaises(TLSIllegalParameterException):
            self.keyExchange.processClientKeyExchange(clientKeyExchange)

    def test_DHE_RSA_key_exchange_with_small_subgroup_client_key_share(self):
        clientKeyExchange = ClientKeyExchange(self.cipher_suite,
                                              (3, 3))
        clientKeyExchange.createDH(2**512)
        self.keyExchange.dh_Xs = 0

        with self.assertRaises(TLSIllegalParameterException):
            self.keyExchange.processClientKeyExchange(clientKeyExchange)



    def test_DHE_RSA_key_exchange_with_small_prime(self):
        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None)

        srv_key_ex = ServerKeyExchange(self.cipher_suite,
                                       self.server_hello.server_version)
        srv_key_ex.createDH(2**768, 2, 2**512-1)

        with self.assertRaises(TLSInsufficientSecurity):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)

    def test_DHE_RSA_key_exchange_with_invalid_generator(self):
        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None)
        srv_key_ex = ServerKeyExchange(self.cipher_suite,
                                       self.server_hello.server_version)
        g, p = goodGroupParameters[1]
        srv_key_ex.createDH(p, p - 1, powMod(2**256, g, p))

        with self.assertRaises(TLSIllegalParameterException):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)

    def test_DHE_RSA_key_exchange_with_invalid_server_key_share(self):
        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None)
        srv_key_ex = ServerKeyExchange(self.cipher_suite,
                                       self.server_hello.server_version)
        g, p = goodGroupParameters[1]
        srv_key_ex.createDH(p, g, p - 1)

        with self.assertRaises(TLSIllegalParameterException):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)


    def test_DHE_RSA_key_exchange_with_unfortunate_random_value(self):
        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None)
        srv_key_ex = ServerKeyExchange(self.cipher_suite,
                                       self.server_hello.server_version)
        g, p = goodGroupParameters[1]
        srv_key_ex.createDH(p, g, p - 2)

        def m(_):
            return numberToByteArray((p - 1) // 2)
        with mock.patch('tlslite.keyexchange.getRandomBytes', m):
            with self.assertRaises(TLSIllegalParameterException):
                client_keyExchange.processServerKeyExchange(None, srv_key_ex)


    def test_DHE_RSA_key_exchange_with_small_subgroup_shared_secret(self):
        client_keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                None)
        srv_key_ex = ServerKeyExchange(self.cipher_suite,
                                       self.server_hello.server_version)
        # RFC 5114 Group 22
        order = [2, 2, 2, 7, int("df", 16),
                 int("183a872bdc5f7a7e88170937189", 16),
                 int("228c5a311384c02e1f287c6b7b2d", 16),
                 int("5a857d66c65a60728c353e32ece8be1", 16),
                 int("f518aa8781a8df278aba4e7d64b7cb9d49462353", 16),
                 int("1a3adf8d6a69682661ca6e590b447e66ebd1bbdeab5e6f3744f06f4"
                     "6cf2a8300622ed50011479f18143d471a53d30113995663a447dcb8"
                     "e81bc24d988edc41f21", 16)]
        # commented out for performance
        #for i in order:
        #    self.assertTrue(isPrime(i))
        p = reduce(mul, order, 1) * 2 + 1
        self.assertTrue(isPrime(p))
        g = 2

        # check the order of generator
        # (below lines commented out for performance)
        #for l in range(len(order)):
        #    for subset in itertools.combinations(order, l):
        #        n = reduce(mul, subset, 1)
        #        self.assertNotEqual(powMod(g, n, p), 1)
        self.assertEqual(powMod(g, reduce(mul, order, 1), p), 1)

        Ys = powMod(g, 100, p)
        # check order of the key share
        # (commented out for performance)
        #for l in range(len(order)):
        #    for subset in itertools.combinations(order, l):
        #        n = reduce(mul, subset, 1)
        #        #print(subset)
        #        self.assertNotEqual(powMod(Ys, n, p), 1)
        self.assertEqual(powMod(Ys, reduce(mul, order[2:], 1), p), 1)

        srv_key_ex.createDH(p, g, Ys)

        def m(_):
            return numberToByteArray(reduce(mul, order[2:], 1))
        with mock.patch('tlslite.keyexchange.getRandomBytes', m):
            with self.assertRaises(TLSIllegalParameterException):
                client_keyExchange.processServerKeyExchange(None, srv_key_ex)


    def test_DHE_RSA_key_exchange_empty_signature(self):
        self.keyExchange.privateKey.sign = mock.Mock(return_value=bytearray(0))
        with self.assertRaises(TLSInternalError):
            self.keyExchange.makeServerKeyExchange('sha1')

    def test_DHE_RSA_key_exchange_empty_signature_in_TLS_1_1(self):
        self.keyExchange.serverHello.server_version = (3, 2)
        self.keyExchange.privateKey.sign = mock.Mock(return_value=bytearray(0))
        with self.assertRaises(TLSInternalError):
            self.keyExchange.makeServerKeyExchange('sha1')

    def test_DHE_RSA_key_exchange_wrong_signature(self):
        self.keyExchange.privateKey.sign = mock.Mock(return_value=bytearray(20))
        with self.assertRaises(TLSInternalError):
            self.keyExchange.makeServerKeyExchange('sha1')

    def test_DHE_RSA_key_exchange_wrong_signature_in_TLS_1_1(self):
        self.keyExchange.serverHello.server_version = (3, 2)
        self.keyExchange.privateKey.sign = mock.Mock(return_value=bytearray(20))
        with self.assertRaises(TLSInternalError):
            self.keyExchange.makeServerKeyExchange()

class TestSRPKeyExchange(unittest.TestCase):
    def setUp(self):
        self.srv_private_key = parsePEMKey(srv_raw_key, private=True)
        srv_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.srv_pub_key = srv_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_SRP_SHA_RSA_WITH_AES_128_CBC_SHA
        self.client_hello = ClientHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 [],
                                                 srpUsername=bytearray(b'user')
                                                 )
        self.server_hello = ServerHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 self.cipher_suite)

        verifierDB = VerifierDB()
        verifierDB.create()
        entry = verifierDB.makeVerifier('user', 'password', 2048)
        verifierDB[b'user'] = entry

        self.keyExchange = SRPKeyExchange(self.cipher_suite,
                                          self.client_hello,
                                          self.server_hello,
                                          self.srv_private_key,
                                          verifierDB)

    def test_SRP_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha256')

        KeyExchange.verifyServerKeyExchange(srv_key_ex,
                                            self.srv_pub_key,
                                            self.client_hello.random,
                                            self.server_hello.random,
                                            [(HashAlgorithm.sha256,
                                              SignatureAlgorithm.rsa)])

        a = bytesToNumber(getRandomBytes(32))
        A = powMod(srv_key_ex.srp_g,
                   a,
                   srv_key_ex.srp_N)
        x = makeX(srv_key_ex.srp_s, bytearray(b'user'), bytearray(b'password'))
        v = powMod(srv_key_ex.srp_g,
                   x,
                   srv_key_ex.srp_N)
        u = makeU(srv_key_ex.srp_N,
                  A,
                  srv_key_ex.srp_B)

        k = makeK(srv_key_ex.srp_N,
                  srv_key_ex.srp_g)
        S = powMod((srv_key_ex.srp_B - (k*v)) % srv_key_ex.srp_N,
                   a+(u*x),
                   srv_key_ex.srp_N)

        cln_premaster = numberToByteArray(S)

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3)).createSRP(A)

        srv_premaster = self.keyExchange.processClientKeyExchange(cln_key_ex)

        self.assertEqual(cln_premaster, srv_premaster)

    def test_SRP_key_exchange_without_signature(self):
        self.cipher_suite = CipherSuite.TLS_SRP_SHA_WITH_AES_128_CBC_SHA
        self.keyExchange.cipherSuite = self.cipher_suite
        self.server_hello.cipher_suite = self.cipher_suite

        srv_key_ex = self.keyExchange.makeServerKeyExchange()

        a = bytesToNumber(getRandomBytes(32))
        A = powMod(srv_key_ex.srp_g,
                   a,
                   srv_key_ex.srp_N)
        x = makeX(srv_key_ex.srp_s, bytearray(b'user'), bytearray(b'password'))
        v = powMod(srv_key_ex.srp_g,
                   x,
                   srv_key_ex.srp_N)
        u = makeU(srv_key_ex.srp_N,
                  A,
                  srv_key_ex.srp_B)

        k = makeK(srv_key_ex.srp_N,
                  srv_key_ex.srp_g)
        S = powMod((srv_key_ex.srp_B - (k*v)) % srv_key_ex.srp_N,
                   a+(u*x),
                   srv_key_ex.srp_N)

        cln_premaster = numberToByteArray(S)

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3)).createSRP(A)

        srv_premaster = self.keyExchange.processClientKeyExchange(cln_key_ex)

        self.assertEqual(cln_premaster, srv_premaster)

    def test_SRP_init_with_invalid_name(self):
        with self.assertRaises(TypeError):
            SRPKeyExchange(self.cipher_suite,
                           self.client_hello,
                           self.server_hello,
                           None, None,
                           srpUsername='user',
                           password=bytearray(b'password'),
                           settings=HandshakeSettings())

    def test_SRP_init_with_invalid_password(self):
        with self.assertRaises(TypeError):
            SRPKeyExchange(self.cipher_suite,
                           self.client_hello,
                           self.server_hello,
                           None, None,
                           srpUsername=bytearray(b'user'),
                           password='password',
                           settings=HandshakeSettings())

    def test_SRP_with_invalid_name(self):
        self.client_hello.srp_username = bytearray(b'test')

        with self.assertRaises(TLSUnknownPSKIdentity):
            self.keyExchange.makeServerKeyExchange('sha1')

    def test_SRP_with_invalid_client_key_share(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        A = srv_key_ex.srp_N

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3)).createSRP(A)

        with self.assertRaises(TLSIllegalParameterException):
            self.keyExchange.processClientKeyExchange(cln_key_ex)

    def test_SRP_key_exchange_with_client(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = SRPKeyExchange(self.cipher_suite,
                                            self.client_hello,
                                            self.server_hello,
                                            None, None,
                                            srpUsername=bytearray(b'user'),
                                            password=bytearray(b'password'),
                                            settings=HandshakeSettings())

        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(\
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)

    def test_client_SRP_key_exchange_with_unknown_params(self):
        keyExchange = ServerKeyExchange(self.cipher_suite,
                                        self.server_hello.server_version)
        keyExchange.createSRP(1, 2, 3, 4)

        client_keyExchange = SRPKeyExchange(self.cipher_suite,
                                            self.client_hello,
                                            self.server_hello,
                                            None, None,
                                            srpUsername=bytearray(b'user'),
                                            password=bytearray(b'password'))
        with self.assertRaises(TLSInsufficientSecurity):
            client_keyExchange.processServerKeyExchange(None, keyExchange)

    def test_client_SRP_key_exchange_with_too_small_params(self):
        keyExchange = self.keyExchange.makeServerKeyExchange('sha1')

        settings = HandshakeSettings()
        settings.minKeySize = 3072
        client_keyExchange = SRPKeyExchange(self.cipher_suite,
                                            self.client_hello,
                                            self.server_hello,
                                            None, None,
                                            srpUsername=bytearray(b'user'),
                                            password=bytearray(b'password'),
                                            settings=settings)
        with self.assertRaises(TLSInsufficientSecurity):
            client_keyExchange.processServerKeyExchange(None, keyExchange)

    def test_client_SRP_key_exchange_with_too_big_params(self):
        keyExchange = self.keyExchange.makeServerKeyExchange('sha1')

        settings = HandshakeSettings()
        settings.minKeySize = 512
        settings.maxKeySize = 1024
        client_keyExchange = SRPKeyExchange(self.cipher_suite,
                                            self.client_hello,
                                            self.server_hello,
                                            None, None,
                                            srpUsername=bytearray(b'user'),
                                            password=bytearray(b'password'),
                                            settings=settings)
        with self.assertRaises(TLSInsufficientSecurity):
            client_keyExchange.processServerKeyExchange(None, keyExchange)

    def test_client_SRP_key_exchange_with_invalid_params(self):
        keyExchange = self.keyExchange.makeServerKeyExchange('sha1')
        keyExchange.srp_B = keyExchange.srp_N

        settings = HandshakeSettings()
        client_keyExchange = SRPKeyExchange(self.cipher_suite,
                                            self.client_hello,
                                            self.server_hello,
                                            None, None,
                                            srpUsername=bytearray(b'user'),
                                            password=bytearray(b'password'),
                                            settings=settings)
        with self.assertRaises(TLSIllegalParameterException):
            client_keyExchange.processServerKeyExchange(None, keyExchange)

class TestECDHE_RSAKeyExchange(unittest.TestCase):
    def setUp(self):
        self.srv_private_key = parsePEMKey(srv_raw_key, private=True)
        srv_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.srv_pub_key = srv_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA
        ext = [SupportedGroupsExtension().create([GroupName.secp256r1])]
        self.client_hello = ClientHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 [],
                                                 extensions=ext)
        self.server_hello = ServerHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 self.cipher_suite)

        self.keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                self.srv_private_key,
                                                [GroupName.secp256r1])

    def test_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        KeyExchange.verifyServerKeyExchange(srv_key_ex,
                                            self.srv_pub_key,
                                            self.client_hello.random,
                                            self.server_hello.random,
                                            [(HashAlgorithm.sha1,
                                              SignatureAlgorithm.rsa)])

        curveName = GroupName.toStr(srv_key_ex.named_curve)
        curve = getCurveByName(curveName)
        generator = curve.generator
        cln_Xc = ecdsa.util.randrange(generator.order())
        cln_Ys = decodeX962Point(srv_key_ex.ecdh_Ys, curve)
        cln_Yc = encodeX962Point(generator * cln_Xc)

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3))
        cln_key_ex.createECDH(cln_Yc)

        cln_S = cln_Ys * cln_Xc
        cln_premaster = numberToByteArray(cln_S.x(),
                                          getPointByteSize(cln_S))

        srv_premaster = self.keyExchange.processClientKeyExchange(cln_key_ex)

        self.assertEqual(cln_premaster, srv_premaster)

    def test_ECDHE_key_exchange_with_invalid_CKE(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        KeyExchange.verifyServerKeyExchange(srv_key_ex,
                                            self.srv_pub_key,
                                            self.client_hello.random,
                                            self.server_hello.random,
                                            [(HashAlgorithm.sha1,
                                              SignatureAlgorithm.rsa)])

        curveName = GroupName.toStr(srv_key_ex.named_curve)
        curve = getCurveByName(curveName)
        generator = curve.generator
        cln_Xc = ecdsa.util.randrange(generator.order())
        cln_Ys = decodeX962Point(srv_key_ex.ecdh_Ys, curve)
        cln_Yc = encodeX962Point(generator * cln_Xc)

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3))
        cln_key_ex.createECDH(cln_Yc)

        cln_key_ex.ecdh_Yc[-1] ^= 0x01

        with self.assertRaises(TLSIllegalParameterException):
            self.keyExchange.processClientKeyExchange(cln_key_ex)

    def test_ECDHE_key_exchange_with_empty_value_in_CKE(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        KeyExchange.verifyServerKeyExchange(srv_key_ex,
                                            self.srv_pub_key,
                                            self.client_hello.random,
                                            self.server_hello.random,
                                            [(HashAlgorithm.sha1,
                                              SignatureAlgorithm.rsa)])

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3))
        cln_key_ex.createECDH(bytearray())

        with self.assertRaises(TLSDecodeError):
            self.keyExchange.processClientKeyExchange(cln_key_ex)

    def test_ECDHE_key_exchange_with_missing_curves(self):
        self.client_hello.extensions = [SNIExtension().create(bytearray(b"a"))]

        ske = self.keyExchange.makeServerKeyExchange('sha1')

        self.assertEqual(ske.curve_type, ECCurveType.named_curve)
        self.assertEqual(ske.named_curve, GroupName.secp256r1)

    def test_ECDHE_key_exchange_with_no_curves_in_ext(self):
        self.client_hello.extensions = [SupportedGroupsExtension()]

        with self.assertRaises(TLSInternalError):
            ske = self.keyExchange.makeServerKeyExchange('sha1')

    def test_ECDHE_key_exchange_with_no_mutual_curves(self):
        ext = SupportedGroupsExtension().create([GroupName.secp160r1])
        self.client_hello.extensions = [ext]
        with self.assertRaises(TLSInsufficientSecurity):
            self.keyExchange.makeServerKeyExchange('sha1')

    def test_client_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.secp256r1])
        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(\
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)

    def test_client_ECDHE_key_exchange_with_invalid_server_curve(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')
        srv_key_ex.named_curve = GroupName.secp384r1

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.secp256r1])
        with self.assertRaises(TLSIllegalParameterException):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)

    def test_client_ECDHE_key_exchange_with_no_share(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')
        srv_key_ex.ecdh_Ys = bytearray()

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.secp256r1])
        with self.assertRaises(TLSDecodeError):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)

class TestRSAKeyExchange_with_PSS_scheme(unittest.TestCase):
    def setUp(self):
        self.srv_private_key = parsePEMKey(srv_raw_key, private=True)
        srv_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.srv_pub_key = srv_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA
        self.client_hello = ClientHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 [])
        self.server_hello = ServerHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 self.cipher_suite)

        self.keyExchange = DHE_RSAKeyExchange(self.cipher_suite,
                                              self.client_hello,
                                              self.server_hello,
                                              self.srv_private_key)


    def test_signServerKeyExchange_with_sha256_in_TLS1_2(self):
        def m(length):
            return bytearray(length)

        with mock.patch('tlslite.utils.rsakey.getRandomBytes', m):
            ske = ServerKeyExchange(self.cipher_suite, (3, 3))
            ske = ske.createDH(5, 2, 3)

            self.keyExchange.signServerKeyExchange(ske, 'rsa_pss_sha256')

            self.assertEqual(ske.signature,
                             bytearray(b'E\xae\x8e\xbe~RU\n\xab4\x8e\x10y\x94'
                                       b'\x01\xdfVr\x8b\x03\xa4\xb7\x9dI\xf1'
                                       b'\xb7\x16\xfa\xa0-\x9a\x16^pZ\x979\xc2'
                                       b'&\xa5\xfcU\x9a"\xc7~u\x1e_y\xc1w\x91'
                                       b'\x98L\x10\xb4\xed\x103\xdf\xac\xba'
                                       b'\x19Q\x0e\x8an\x13\x99\x8d1\x17XK\x9a'
                                       b'\x00\xcdno\xc7\xae\x92:pU\xf8\xfbl'
                                       b'\xeeg\xe0s\x03\xc8\xcb\xe5\xc4\xb9z'
                                       b'\xcf\nv\xca\x80`\xbe\xc9\x85\xcfM\x89'
                                       b'\xaeE\xf0\xa1\xd8`\x99\x93\xa0Bp\x1cw'
                                       b'W\xce\x8e'))

    def test_signServerKeyExchange_with_sha384_in_TLS1_2(self):
        def m(length):
            return bytearray(length)

        with mock.patch('tlslite.utils.rsakey.getRandomBytes', m):
            ske = ServerKeyExchange(self.cipher_suite, (3, 3))
            ske = ske.createDH(5, 2, 3)

            self.keyExchange.signServerKeyExchange(ske, 'rsa_pss_sha384')

            self.assertEqual(ske.signature,
                             bytearray(b"QH\x02Xl2\xa37\xeeV\x9d\x84\x96E;_iJ"
                                       b"\xcd\xed\x85#\x96\x0c\xc2\x94\xbd\xfa"
                                       b"\xbbt&\xffo\xe2o\xa2\xbb\x08\xf1v\xdb"
                                       b"\xdc\xcdj\x96R\x88\xf8{\x182\xfd\x99t"
                                       b"\x9d\xb8\xba\x87\xd3\x8f\x8b\x88\xe8"
                                       b"\x1c\x02\xa2\xfd5\x0b\x9b\xe1\x8c\xc0"
                                       b"O\x13\x8d\xc5SU\xd5pN\xe2\xa9\xe1F|"
                                       b"\xe9\xb5\xa9\x80s_\x91\xeb:\xcd\xee("
                                       b"\x03\xe5[\xf5\xc7z\x02\'/\x0f\xdc\x1f"
                                       b"\xd2\x93\x8b\x12\x01%\x1d\x04\xf1["
                                       b"\xe4\x9a\x83\xf8\xd3#+"))


class TestECDHE_RSAKeyExchange_with_x25519(unittest.TestCase):
    def setUp(self):
        self.srv_private_key = parsePEMKey(srv_raw_key, private=True)
        srv_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.srv_pub_key = srv_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA
        ext = [SupportedGroupsExtension().create([GroupName.x25519])]
        self.client_hello = ClientHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 [],
                                                 extensions=ext)
        self.server_hello = ServerHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 self.cipher_suite)

        self.keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                self.srv_private_key,
                                                [GroupName.x25519])

    def test_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        KeyExchange.verifyServerKeyExchange(srv_key_ex,
                                            self.srv_pub_key,
                                            self.client_hello.random,
                                            self.server_hello.random,
                                            [(HashAlgorithm.sha1,
                                              SignatureAlgorithm.rsa)])

        self.assertEqual(srv_key_ex.named_curve, GroupName.x25519)
        generator = bytearray(X25519_G)
        cln_Xc = getRandomBytes(32)
        cln_Ys = srv_key_ex.ecdh_Ys
        cln_Yc = x25519(cln_Xc, generator)

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3))
        cln_key_ex.createECDH(cln_Yc)

        cln_S = x25519(cln_Xc, cln_Ys)

        srv_premaster = self.keyExchange.processClientKeyExchange(cln_key_ex)

        self.assertEqual(cln_S, srv_premaster)

    def test_client_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x25519])
        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(\
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)

    def test_client_ECDHE_key_exchange_with_invalid_size(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x25519])
        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()
        clientKeyExchange.ecdh_Yc += bytearray(b'\x00')

        with self.assertRaises(TLSIllegalParameterException):
            self.keyExchange.processClientKeyExchange(clientKeyExchange)

    def test_client_ECDHE_key_exchange_with_all_zero_share(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x25519])
        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()
        clientKeyExchange.ecdh_Yc = bytearray(32)

        with self.assertRaises(TLSIllegalParameterException):
            self.keyExchange.processClientKeyExchange(clientKeyExchange)

    def test_client_ECDHE_key_exchange_with_high_bit_set(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x25519])
        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()
        clientKeyExchange.ecdh_Yc[-1] |= 0x80

        S = self.keyExchange.processClientKeyExchange(clientKeyExchange)

        # we have modified public value, so can't actually compute shared
        # value as a result, just sanity check
        self.assertEqual(32, len(S))
        self.assertNotEqual(bytearray(32), S)

    def test_client_with_invalid_size_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x25519])
        srv_key_ex.ecdh_Ys += bytearray(b'\x00')
        with self.assertRaises(TLSIllegalParameterException):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)

    def test_client_with_all_zero_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x25519])
        srv_key_ex.ecdh_Ys = bytearray(32)
        with self.assertRaises(TLSIllegalParameterException):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)

    def test_client_with_high_bit_set_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x25519])
        srv_key_ex.ecdh_Ys[-1] |= 0x80
        S = client_keyExchange.processServerKeyExchange(None, srv_key_ex)

        # we have modified public value, so can't calculate the resulting
        # shared secret as a result, perform just a sanity check
        self.assertEqual(32, len(S))
        self.assertNotEqual(bytearray(32), S)


class TestECDHE_RSAKeyExchange_with_x448(unittest.TestCase):
    def setUp(self):
        self.srv_private_key = parsePEMKey(srv_raw_key, private=True)
        srv_chain = X509CertChain([X509().parse(srv_raw_certificate)])
        self.srv_pub_key = srv_chain.getEndEntityPublicKey()
        self.cipher_suite = CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA
        ext = [SupportedGroupsExtension().create([GroupName.x448])]
        self.client_hello = ClientHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 [],
                                                 extensions=ext)
        self.server_hello = ServerHello().create((3, 3),
                                                 bytearray(32),
                                                 bytearray(0),
                                                 self.cipher_suite)

        self.keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                self.client_hello,
                                                self.server_hello,
                                                self.srv_private_key,
                                                [GroupName.x448])

    def test_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        KeyExchange.verifyServerKeyExchange(srv_key_ex,
                                            self.srv_pub_key,
                                            self.client_hello.random,
                                            self.server_hello.random,
                                            [(HashAlgorithm.sha1,
                                              SignatureAlgorithm.rsa)])

        self.assertEqual(srv_key_ex.named_curve, GroupName.x448)
        generator = bytearray(X448_G)
        cln_Xc = getRandomBytes(56)
        cln_Ys = srv_key_ex.ecdh_Ys
        cln_Yc = x448(cln_Xc, generator)

        cln_key_ex = ClientKeyExchange(self.cipher_suite, (3, 3))
        cln_key_ex.createECDH(cln_Yc)

        cln_S = x448(cln_Xc, cln_Ys)

        srv_premaster = self.keyExchange.processClientKeyExchange(cln_key_ex)

        self.assertEqual(cln_S, srv_premaster)

    def test_client_ECDHE_key_exchange(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x448])
        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()

        server_premaster = self.keyExchange.processClientKeyExchange(\
                clientKeyExchange)

        self.assertEqual(client_premaster, server_premaster)

    def test_client_ECDHE_key_exchange_with_invalid_size(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x448])
        client_premaster = client_keyExchange.processServerKeyExchange(\
                None,
                srv_key_ex)
        clientKeyExchange = client_keyExchange.makeClientKeyExchange()
        clientKeyExchange.ecdh_Yc += bytearray(b'\x00')

        with self.assertRaises(TLSIllegalParameterException):
            self.keyExchange.processClientKeyExchange(clientKeyExchange)

    def test_client_with_invalid_size_ECDHE_key_share(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x448])
        srv_key_ex.ecdh_Ys += bytearray(b'\x00')
        with self.assertRaises(TLSIllegalParameterException):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)

    def test_client_with_all_zero_ECDHE_key_share(self):
        srv_key_ex = self.keyExchange.makeServerKeyExchange('sha1')

        client_keyExchange = ECDHE_RSAKeyExchange(self.cipher_suite,
                                                  self.client_hello,
                                                  self.server_hello,
                                                  None,
                                                  [GroupName.x448])
        srv_key_ex.ecdh_Ys = bytearray(56)
        with self.assertRaises(TLSIllegalParameterException):
            client_keyExchange.processServerKeyExchange(None, srv_key_ex)


class TestRawDHKeyExchange(unittest.TestCase):
    def test___init__(self):
        group = mock.Mock()
        version = mock.Mock()
        kex = RawDHKeyExchange(group, version)

        self.assertIs(kex.group, group)
        self.assertIs(kex.version, version)

    def test_get_random_private_key(self):
        kex = RawDHKeyExchange(None, None)

        with self.assertRaises(NotImplementedError):
            kex.get_random_private_key()

    def test_calc_public_value(self):
        kex = RawDHKeyExchange(None, None)

        with self.assertRaises(NotImplementedError):
            kex.calc_public_value(None)

    def test_calc_shared_value(self):
        kex = RawDHKeyExchange(None, None)

        with self.assertRaises(NotImplementedError):
            kex.calc_shared_key(None, None)


class TestFFDHKeyExchange(unittest.TestCase):
    def test___init___with_conflicting_options(self):
        with self.assertRaises(ValueError):
            FFDHKeyExchange(GroupName.ffdhe2048, (3, 3), 2, 31)

    def test___init___with_invalid_generator(self):
        with self.assertRaises(TLSIllegalParameterException):
            FFDHKeyExchange(None, (3, 3), 31, 2)

    def test___init___with_rfc7919_group(self):
        kex = FFDHKeyExchange(GroupName.ffdhe2048, (3, 3))

        self.assertEqual(kex.generator, 2)
        self.assertEqual(kex.prime, RFC7919_GROUPS[0][1])

    def test_calc_public_value(self):
        kex = FFDHKeyExchange(GroupName.ffdhe2048, (3, 4))

        private = 2
        public = kex.calc_public_value(private)
        # verify that numbers are zero-padded
        self.assertEqual(public,
                bytearray(b'\x00' * 255 + b'\x04'))

    def test_calc_shared_secret(self):
        kex = FFDHKeyExchange(GroupName.ffdhe2048, (3, 4))

        private = 2
        key_share = 4
        shared = kex.calc_shared_key(private, key_share)
        # verify that numbers are zero-padded on MSBs
        self.assertEqual(shared,
                bytearray(b'\x00' * 255 + b'\x10'))

    def test_calc_shared_secret_for_bytearray_input(self):
        kex = FFDHKeyExchange(GroupName.ffdhe2048, (3, 4))

        private = 2
        key_share = bytearray(b'\x00' * 255 + b'\x04')
        shared = kex.calc_shared_key(private, key_share)
        # verify that numbers are zero-padded on MSBs
        self.assertEqual(shared,
                bytearray(b'\x00' * 255 + b'\x10'))

    def test_calc_shared_secret_for_invalid_sized_input(self):
        kex = FFDHKeyExchange(GroupName.ffdhe2048, (3, 4))

        private = 2
        key_share = bytearray(b'\x00' * 10 + b'\x04')
        with self.assertRaises(TLSIllegalParameterException):
            kex.calc_shared_key(private, key_share)
