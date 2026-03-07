"""
Story 59.7 — SEC-7: Tests pour get_client_ip() avec X-Real-IP en priorité.
"""
from unittest.mock import patch

from django.test import RequestFactory

from core.middleware import get_client_ip


class TestGetClientIpSec7:
    """SEC-7: Tests de la fonction get_client_ip() avec hardening X-Real-IP."""

    def setup_method(self):
        self.factory = RequestFactory()

    def test_59_7_a_x_real_ip_prioritaire(self):
        """59-7-a: X-Real-IP présent → retourné directement, pas de warning."""
        request = self.factory.get(
            '/',
            HTTP_X_REAL_IP='192.168.1.50',
            HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8',
        )
        with patch('core.middleware.logger') as mock_logger:
            ip = get_client_ip(request)
        assert ip == '192.168.1.50'
        mock_logger.warning.assert_not_called()

    def test_59_7_b_xff_seul_sans_x_real_ip(self):
        """59-7-b: X-Real-IP absent, XFF seul → IP XFF retournée."""
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='10.0.0.1')
        ip = get_client_ip(request)
        assert ip == '10.0.0.1'

    def test_59_7_c_xff_multi_ip_warning_loggue(self):
        """59-7-c: X-Real-IP absent, XFF multi-IPs → warning loggé, ips[0] retourné."""
        request = self.factory.get(
            '/',
            HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8, 9.10.11.12',
        )
        with patch('core.middleware.logger') as mock_logger:
            ip = get_client_ip(request)
        assert ip == '1.2.3.4'
        mock_logger.warning.assert_called_once_with(
            'suspicious_xff_header',
            xff_header='1.2.3.4, 5.6.7.8, 9.10.11.12',
            ip_count=3,
            extracted_client_ip='1.2.3.4',
            message='X-Forwarded-For contains multiple IPs without X-Real-IP - potential spoofing or misconfigured proxy',
        )

    def test_59_7_d_ni_real_ip_ni_xff(self):
        """59-7-d: Ni X-Real-IP ni XFF → REMOTE_ADDR retourné."""
        request = self.factory.get('/', REMOTE_ADDR='172.16.0.1')
        ip = get_client_ip(request)
        assert ip == '172.16.0.1'

    def test_59_7_e_x_real_ip_prioritaire_sur_xff_forge(self):
        """59-7-e: X-Real-IP présent ET XFF multi-IPs forgés → X-Real-IP prioritaire, pas de warning."""
        request = self.factory.get(
            '/',
            HTTP_X_REAL_IP='203.0.113.42',
            HTTP_X_FORWARDED_FOR='1.1.1.1, 2.2.2.2, 3.3.3.3',
        )
        with patch('core.middleware.logger') as mock_logger:
            ip = get_client_ip(request)
        assert ip == '203.0.113.42'
        mock_logger.warning.assert_not_called()

    def test_59_7_f_x_real_ip_whitespace_fallback_a_xff(self):
        """59-7-f: X-Real-IP présent mais vide (espaces seuls) → fallback sur XFF, pas de retour vide."""
        request = self.factory.get(
            '/',
            HTTP_X_REAL_IP='   ',
            HTTP_X_FORWARDED_FOR='10.20.30.40',
        )
        ip = get_client_ip(request)
        # X-Real-IP whitespace-only doit être ignoré (strip → falsy) → fallback XFF
        assert ip == '10.20.30.40'
