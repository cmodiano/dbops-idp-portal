"""
Tests for integration icon upload endpoint (DRF).
Tests: POST /admin/integrations/upload-icon
"""

import pytest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User


@pytest.mark.django_db
class TestUploadIconView(TestCase):
    """Tests for POST /admin/integrations/upload-icon endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create DBOPS user (required for admin endpoints)
        self.dbops_user = User.objects.create(
            username='dbops_user',
            profile='dbops'
        )
        
        # Create non-DBOPS user
        self.regular_user = User.objects.create(
            username='regular_user',
            profile='dba_applicatif'
        )
    
    def test_upload_icon_png(self):
        """Test POST /admin/integrations/upload-icon with PNG file → 201."""
        self.client.force_authenticate(user=self.dbops_user)
        
        # Create a test PNG file
        png_file = SimpleUploadedFile(
            "test_icon.png",
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01',
            content_type='image/png'
        )
        
        response = self.client.post(
            '/api/v1/admin/integrations/upload-icon/',
            {'file': png_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertIn('icon_url', response.data['data'])
        self.assertIn('/static/icons/', response.data['data']['icon_url'])
    
    def test_upload_icon_jpeg(self):
        """Test POST /admin/integrations/upload-icon with JPEG file → 201."""
        self.client.force_authenticate(user=self.dbops_user)
        
        # Create a test JPEG file
        jpeg_file = SimpleUploadedFile(
            "test_icon.jpg",
            b'\xff\xd8\xff\xe0\x00\x10JFIF',
            content_type='image/jpeg'
        )
        
        response = self.client.post(
            '/api/v1/admin/integrations/upload-icon/',
            {'file': jpeg_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertIn('icon_url', response.data['data'])
    
    def test_upload_icon_svg(self):
        """Test POST /admin/integrations/upload-icon with SVG file → 201."""
        self.client.force_authenticate(user=self.dbops_user)
        
        # Create a test SVG file
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        svg_file = SimpleUploadedFile(
            "test_icon.svg",
            svg_content,
            content_type='image/svg+xml'
        )
        
        response = self.client.post(
            '/api/v1/admin/integrations/upload-icon/',
            {'file': svg_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertIn('icon_url', response.data['data'])
    
    def test_upload_icon_invalid_mime(self):
        """Test POST /admin/integrations/upload-icon with invalid MIME type → 400."""
        self.client.force_authenticate(user=self.dbops_user)

        # Create a test file with invalid MIME type and extension
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b'This is not an image',
            content_type='text/plain'
        )

        response = self.client.post(
            '/api/v1/admin/integrations/upload-icon/',
            {'file': invalid_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        # SEC-5: Extension is validated first, so INVALID_EXTENSION is returned
        self.assertEqual(response.data['error']['code'], 'INVALID_EXTENSION')
    
    def test_upload_icon_too_large(self):
        """Test POST /admin/integrations/upload-icon with file > 2MB → 400."""
        self.client.force_authenticate(user=self.dbops_user)
        
        # Create a test file larger than 2MB
        large_file = SimpleUploadedFile(
            "large_icon.png",
            b'x' * (3 * 1024 * 1024),  # 3MB
            content_type='image/png'
        )
        
        response = self.client.post(
            '/api/v1/admin/integrations/upload-icon/',
            {'file': large_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'FILE_TOO_LARGE')
    
    def test_upload_icon_no_file(self):
        """Test POST /admin/integrations/upload-icon without file → 400."""
        self.client.force_authenticate(user=self.dbops_user)
        
        response = self.client.post(
            '/api/v1/admin/integrations/upload-icon/',
            {},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'NO_FILE')
    
    def test_upload_icon_forbidden_non_dbops(self):
        """Test POST /admin/integrations/upload-icon with non-DBOPS user → 403."""
        self.client.force_authenticate(user=self.regular_user)
        
        png_file = SimpleUploadedFile(
            "test_icon.png",
            b'\x89PNG\r\n\x1a\n',
            content_type='image/png'
        )
        
        response = self.client.post(
            '/api/v1/admin/integrations/upload-icon/',
            {'file': png_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
